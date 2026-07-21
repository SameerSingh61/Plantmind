#!/usr/bin/env python3
"""PlantMind API. Run from repo root:

    uvicorn backend.main:app --reload --port 8000

The graph loads once at startup from data/graph.pkl (built by
graph/build.py) and lives in-process from there so that work orders
inserted during a demo session persist across requests until /api/reset.
"""
import json
import pickle
import sys
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from graph.briefing_agent import generate_briefing  # noqa: E402
from graph.build import nid  # noqa: E402
from graph.normalizer import TagNormalizer  # noqa: E402
from graph.parser import parse_document  # noqa: E402
from graph.query_agent import answer_query  # noqa: E402
from graph.retirement_agent import (generate_retirement_questions,  # noqa: E402
                                     record_interview_answer)
from graph.rules import (check_experience_gap, rule_orphaned_knowledge,  # noqa: E402
                          rule_recurrence_pattern, rule_unclosed_recommendation)

DATA = ROOT / "data"
CORPUS = ROOT / "corpus"

app = FastAPI(title="PlantMind API")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)

STATE = {"g": None, "briefing_feed": [], "normalizer": None}


def load_graph():
    with open(DATA / "graph.pkl", "rb") as f:
        g = pickle.load(f)
    STATE["g"] = g
    tags = [attrs["id"] for _, attrs in g.nodes(data=True) if attrs.get("node_type") == "Equipment"]
    STATE["normalizer"] = TagNormalizer(tags)
    STATE["briefing_feed"] = []
    return g


load_graph()


def g():
    return STATE["g"]


# ---------------------------------------------------------------------------
# Graph explorer
# ---------------------------------------------------------------------------
@app.get("/api/graph")
def get_graph():
    nodes, edges = [], []
    for key, attrs in g().nodes(data=True):
        node = {k: v for k, v in attrs.items() if k != "answer_text"}
        node["key"] = key
        nodes.append(node)
    for u, v, attrs in g().edges(data=True):
        edges.append({"source": u, "target": v, **attrs})
    return {"nodes": nodes, "edges": edges}


@app.get("/api/graph/node/{node_key:path}")
def get_node(node_key: str):
    if node_key not in g():
        raise HTTPException(404, "node not found")
    attrs = dict(g().nodes[node_key])
    neighbors = []
    for _, v, d in g().out_edges(node_key, data=True):
        neighbors.append({"direction": "out", "edge_type": d.get("edge_type"), "node": v})
    for u, _, d in g().in_edges(node_key, data=True):
        neighbors.append({"direction": "in", "edge_type": d.get("edge_type"), "node": u})
    return {"key": node_key, "attrs": attrs, "neighbors": neighbors}


@app.get("/api/graph/path")
def get_path(source: str, target: str):
    import networkx as nx
    undirected = g().to_undirected(as_view=True)
    try:
        path = nx.shortest_path(undirected, source, target)
    except nx.NetworkXNoPath:
        raise HTTPException(404, "no path between these nodes")
    edges_in_path = []
    for a, b in zip(path, path[1:]):
        edge_data = g().get_edge_data(a, b) or g().get_edge_data(b, a) or {}
        edge_type = next(iter(edge_data.values()), {}).get("edge_type") if edge_data else None
        edges_in_path.append({"source": a, "target": b, "edge_type": edge_type})
    nodes_in_path = [{"key": k, **{kk: vv for kk, vv in g().nodes[k].items() if kk != "answer_text"}} for k in path]
    return {"nodes": nodes_in_path, "edges": edges_in_path}


# ---------------------------------------------------------------------------
# Proactive briefings
# ---------------------------------------------------------------------------
@app.get("/api/briefings")
def list_briefings():
    return {"briefings": STATE["briefing_feed"]}


class WorkOrderIn(BaseModel):
    wo_id: str
    equipment_tag: str
    raised_date: str
    work_type: str = "corrective_maintenance"
    priority: str = "medium"
    permit_type: str = "none"
    assigned_to: str
    planned_hours: int | None = None
    completion_notes: str | None = None


def _insert_work_order(wo: WorkOrderIn):
    graph = g()
    eq_tag = STATE["normalizer"].normalize(wo.equipment_tag)
    if not eq_tag:
        raise HTTPException(400, f"unknown equipment tag '{wo.equipment_tag}'")
    person_key = nid("Person", wo.assigned_to)
    if person_key not in graph:
        raise HTTPException(400, f"unknown person id '{wo.assigned_to}'")

    wo_key = nid("WorkOrder", wo.wo_id)
    graph.add_node(
        wo_key, node_type="WorkOrder", id=wo.wo_id,
        raised_date=wo.raised_date, work_type=wo.work_type, priority=wo.priority,
        permit_type=wo.permit_type, planned_hours=wo.planned_hours, actual_hours=None,
        completion_notes=wo.completion_notes, status="open",
        source_document=f"{wo.wo_id}.md", page=1, confidence=1.0,
    )
    eq_key = nid("Equipment", eq_tag)
    graph.add_edge(wo_key, eq_key, key="PERFORMED_ON", edge_type="PERFORMED_ON",
                   source_document=f"{wo.wo_id}.md", page=1)
    graph.add_edge(wo_key, person_key, key="ASSIGNED_TO", edge_type="ASSIGNED_TO",
                   source_document=f"{wo.wo_id}.md", page=1)

    # recompute this pair's HAS_EXPERIENCE_WITH count
    count = sum(
        1 for u, v, d in graph.in_edges(eq_key, data=True)
        if d.get("edge_type") == "PERFORMED_ON"
        and any(dd.get("edge_type") == "ASSIGNED_TO" and vv == person_key for _, vv, dd in graph.out_edges(u, data=True))
    )
    graph.add_edge(person_key, eq_key, key="HAS_EXPERIENCE_WITH", edge_type="HAS_EXPERIENCE_WITH",
                   work_order_count=count, source_document="derived:work_order_aggregation", confidence=1.0)
    return wo_key


@app.post("/api/work-orders")
def create_work_order(wo: WorkOrderIn):
    """Insert a work order and, if the graph detects a compound-risk
    condition, generate and return an unprompted briefing. This is the
    system speaking first — see acceptance test 5."""
    start = time.time()
    wo_key = _insert_work_order(wo)
    payload = rule_unclosed_recommendation(g(), wo_key)
    result = {"wo_key": wo_key, "briefing": None}
    if payload:
        briefing = generate_briefing(payload)
        if briefing["text"] != "NO_BRIEFING":
            entry = {
                "id": f"briefing-{wo.wo_id}-{int(time.time())}",
                "trigger_rule": "unclosed_recommendation",
                "wo_id": wo.wo_id,
                "text": briefing["text"],
                "source": briefing["source"],
                "payload": payload,
                "generated_at": time.time(),
            }
            # dedupe: re-triggering the same WO (e.g. a double-click during
            # a demo) replaces its card instead of piling up duplicates
            STATE["briefing_feed"] = [b for b in STATE["briefing_feed"] if b["wo_id"] != wo.wo_id]
            STATE["briefing_feed"].insert(0, entry)
            result["briefing"] = entry
    result["elapsed_ms"] = int((time.time() - start) * 1000)
    return result


@app.post("/api/demo/trigger-storyline-1")
def trigger_storyline_1():
    """Convenience endpoint: re-parses WO-2026-4471 from the corpus and
    inserts it fresh, exactly reproducing acceptance test 5."""
    doc = parse_document(CORPUS / "03_work_orders" / "WO-2026-4471.md")
    fm = doc.front_matter
    wo = WorkOrderIn(
        wo_id=fm["wo_id"], equipment_tag=fm["equipment_tags"][0],
        raised_date=fm["raised_date"], work_type=fm["work_type"],
        priority=fm["priority"], permit_type=fm["permit_type"],
        assigned_to=fm["assigned_to"], planned_hours=fm.get("planned_hours"),
    )
    return create_work_order(wo)


@app.get("/api/sweep/recurrence-patterns")
def sweep_recurrence_patterns():
    return {"patterns": rule_recurrence_pattern(g())}


@app.get("/api/sweep/orphaned-knowledge")
def sweep_orphaned_knowledge():
    return {"orphans": rule_orphaned_knowledge(g())}


# ---------------------------------------------------------------------------
# Query surface
# ---------------------------------------------------------------------------
class QueryIn(BaseModel):
    question: str


@app.post("/api/query")
def query(q: QueryIn):
    return answer_query(g(), q.question)


# ---------------------------------------------------------------------------
# Retirement capture
# ---------------------------------------------------------------------------
@app.get("/api/retirement/{equipment_tag}")
def retirement_questions(equipment_tag: str):
    orphans = rule_orphaned_knowledge(g())
    match = next((o for o in orphans if o["equipment"] == equipment_tag), None)
    if not match:
        raise HTTPException(404, f"no orphaned-knowledge finding for {equipment_tag}")
    questions = generate_retirement_questions(g(), match)
    return {"finding": match, "questions": questions}


class InterviewAnswerIn(BaseModel):
    person_id: str
    equipment_tag: str
    wo_id: str
    answer_text: str


@app.post("/api/retirement/answer")
def submit_interview_answer(a: InterviewAnswerIn):
    key = record_interview_answer(g(), a.person_id, a.equipment_tag, a.answer_text, a.wo_id)
    return {"new_node": key, "attrs": g().nodes[key]}


# ---------------------------------------------------------------------------
# Drawings
# ---------------------------------------------------------------------------
@app.get("/api/drawings")
def list_drawings():
    return {"drawings": [json.loads(p.read_text()) for p in sorted((CORPUS / "01_drawings").glob("*.json"))]}


@app.get("/api/drawings/{drawing_id}")
def get_drawing(drawing_id: str):
    path = CORPUS / "01_drawings" / f"{drawing_id}.json"
    if not path.exists():
        raise HTTPException(404, "drawing not found")
    return json.loads(path.read_text())


# ---------------------------------------------------------------------------
# Session control
# ---------------------------------------------------------------------------
@app.post("/api/reset")
def reset():
    load_graph()
    return {"status": "reset", "nodes": g().number_of_nodes(), "edges": g().number_of_edges()}


@app.get("/api/health")
def health():
    return {"status": "ok", "nodes": g().number_of_nodes(), "edges": g().number_of_edges(),
            "briefings_in_feed": len(STATE["briefing_feed"])}
