#!/usr/bin/env python3
"""PlantMind API. Run from repo root:

    uvicorn backend.main:app --reload --port 8000

Backed by AuraDB (Neo4j) — the graph lives in the cloud instance, not in
an in-process pickle. /api/reset re-runs the full corpus ingestion against
AuraDB (a few seconds of network round trips) to discard anything
inserted during a demo session.
"""
import json
import sys
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from graph.briefing_agent import generate_briefing  # noqa: E402
from graph.build import GraphBuilder  # noqa: E402
from graph.neo4j_client import run as neo4j_run  # noqa: E402
from graph.normalizer import TagNormalizer  # noqa: E402
from graph.parser import parse_document  # noqa: E402
from graph.query_agent import answer_query  # noqa: E402
from graph.retirement_agent import (generate_retirement_questions,  # noqa: E402
                                     record_interview_answer)
from graph.rules import (rule_orphaned_knowledge,  # noqa: E402
                          rule_recurrence_pattern, rule_unclosed_recommendation)

CORPUS = ROOT / "corpus"

app = FastAPI(title="PlantMind API")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)

STATE = {"briefing_feed": [], "normalizer": None}


def refresh_normalizer():
    tags = [r["tag"] for r in neo4j_run("MATCH (e:Equipment) RETURN e.id AS tag")]
    STATE["normalizer"] = TagNormalizer(tags)


refresh_normalizer()


def nid(node_type: str, natural_id: str) -> str:
    return f"{node_type}:{natural_id}"


# ---------------------------------------------------------------------------
# Graph explorer
# ---------------------------------------------------------------------------
@app.get("/api/graph")
def get_graph():
    node_rows = neo4j_run("MATCH (n) RETURN n, labels(n)[0] AS label")
    nodes = []
    for row in node_rows:
        node = {k: v for k, v in row["n"].items() if k not in ("_labels", "answer_text")}
        node["key"] = node.get("key")
        nodes.append(node)

    edge_rows = neo4j_run(
        "MATCH (a)-[r]->(b) RETURN a.key AS source, b.key AS target, type(r) AS edge_type, properties(r) AS props"
    )
    edges = [{"source": e["source"], "target": e["target"], "edge_type": e["edge_type"], **e["props"]} for e in edge_rows]
    return {"nodes": nodes, "edges": edges}


@app.get("/api/graph/node/{node_key:path}")
def get_node(node_key: str):
    rows = neo4j_run("MATCH (n {key: $key}) RETURN n", key=node_key)
    if not rows:
        raise HTTPException(404, "node not found")
    attrs = {k: v for k, v in rows[0]["n"].items() if k != "_labels"}

    neighbors = []
    for row in neo4j_run(
        "MATCH (n {key: $key})-[r]->(m) RETURN type(r) AS edge_type, m.key AS other",
        key=node_key,
    ):
        neighbors.append({"direction": "out", "edge_type": row["edge_type"], "node": row["other"]})
    for row in neo4j_run(
        "MATCH (n {key: $key})<-[r]-(m) RETURN type(r) AS edge_type, m.key AS other",
        key=node_key,
    ):
        neighbors.append({"direction": "in", "edge_type": row["edge_type"], "node": row["other"]})

    return {"key": node_key, "attrs": attrs, "neighbors": neighbors}


@app.get("/api/graph/path")
def get_path(source: str, target: str):
    rows = neo4j_run(
        "MATCH p = shortestPath((a {key: $source})-[*..15]-(b {key: $target})) "
        "RETURN [n IN nodes(p) | n] AS path_nodes, "
        "       [r IN relationships(p) | {type: type(r), start: startNode(r).key, end: endNode(r).key}] AS path_rels",
        source=source, target=target,
    )
    if not rows or not rows[0]["path_nodes"]:
        raise HTTPException(404, "no path between these nodes")
    nodes_in_path = [
        {"key": n.get("key"), **{k: v for k, v in n.items() if k not in ("_labels", "answer_text")}}
        for n in rows[0]["path_nodes"]
    ]
    edges_in_path = [
        {"source": r["start"], "target": r["end"], "edge_type": r["type"]}
        for r in rows[0]["path_rels"]
    ]
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
    eq_tag = STATE["normalizer"].normalize(wo.equipment_tag)
    if not eq_tag:
        raise HTTPException(400, f"unknown equipment tag '{wo.equipment_tag}'")
    person_key = nid("Person", wo.assigned_to)
    if not neo4j_run("MATCH (p:Person {key: $k}) RETURN p", k=person_key):
        raise HTTPException(400, f"unknown person id '{wo.assigned_to}'")

    wo_key = nid("WorkOrder", wo.wo_id)
    eq_key = nid("Equipment", eq_tag)

    neo4j_run(
        "MERGE (w:WorkOrder {key: $wo_key}) "
        "SET w.id = $wo_id, w.raised_date = $raised_date, w.work_type = $work_type, "
        "    w.priority = $priority, w.permit_type = $permit_type, "
        "    w.planned_hours = $planned_hours, w.actual_hours = 0, "
        "    w.completion_notes = $completion_notes, w.status = 'open', "
        "    w.source_document = $doc, w.page = 1, w.confidence = 1.0 "
        "WITH w "
        "MATCH (eq:Equipment {key: $eq_key}) "
        "MERGE (w)-[:PERFORMED_ON {source_document: $doc, page: 1}]->(eq) "
        "WITH w "
        "MATCH (p:Person {key: $person_key}) "
        "MERGE (w)-[:ASSIGNED_TO {source_document: $doc, page: 1}]->(p)",
        wo_key=wo_key, wo_id=wo.wo_id, raised_date=wo.raised_date, work_type=wo.work_type,
        priority=wo.priority, permit_type=wo.permit_type,
        planned_hours=wo.planned_hours or 0, completion_notes=wo.completion_notes or "",
        doc=f"{wo.wo_id}.md", eq_key=eq_key, person_key=person_key,
    )

    # recompute this pair's HAS_EXPERIENCE_WITH count
    count_rows = neo4j_run(
        "MATCH (p:Person {key: $person_key})<-[:ASSIGNED_TO]-(w:WorkOrder)-[:PERFORMED_ON]->(eq:Equipment {key: $eq_key}) "
        "RETURN count(w) AS c",
        person_key=person_key, eq_key=eq_key,
    )
    count = count_rows[0]["c"]
    neo4j_run(
        "MATCH (p:Person {key: $person_key}), (eq:Equipment {key: $eq_key}) "
        "MERGE (p)-[r:HAS_EXPERIENCE_WITH]->(eq) "
        "SET r.work_order_count = $count, r.source_document = 'derived:work_order_aggregation', r.confidence = 1.0",
        person_key=person_key, eq_key=eq_key, count=count,
    )
    return wo_key


@app.post("/api/work-orders")
def create_work_order(wo: WorkOrderIn):
    """Insert a work order and, if the graph detects a compound-risk
    condition, generate and return an unprompted briefing. This is the
    system speaking first — see acceptance test 5."""
    start = time.time()
    wo_key = _insert_work_order(wo)
    payload = rule_unclosed_recommendation(wo_key)
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
    return {"patterns": rule_recurrence_pattern()}


@app.get("/api/sweep/orphaned-knowledge")
def sweep_orphaned_knowledge():
    return {"orphans": rule_orphaned_knowledge()}


# ---------------------------------------------------------------------------
# Query surface
# ---------------------------------------------------------------------------
class QueryIn(BaseModel):
    question: str


@app.post("/api/query")
def query(q: QueryIn):
    return answer_query(q.question)


# ---------------------------------------------------------------------------
# Retirement capture
# ---------------------------------------------------------------------------
@app.get("/api/retirement/{equipment_tag}")
def retirement_questions(equipment_tag: str):
    orphans = rule_orphaned_knowledge()
    match = next((o for o in orphans if o["equipment"] == equipment_tag), None)
    if not match:
        raise HTTPException(404, f"no orphaned-knowledge finding for {equipment_tag}")
    questions = generate_retirement_questions(match)
    return {"finding": match, "questions": questions}


class InterviewAnswerIn(BaseModel):
    person_id: str
    equipment_tag: str
    wo_id: str
    answer_text: str


@app.post("/api/retirement/answer")
def submit_interview_answer(a: InterviewAnswerIn):
    key = record_interview_answer(a.person_id, a.equipment_tag, a.answer_text, a.wo_id)
    rows = neo4j_run("MATCH (n {key: $k}) RETURN n", k=key)
    return {"new_node": key, "attrs": rows[0]["n"] if rows else None}


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
    """Re-runs the full corpus ingestion against AuraDB, discarding
    anything inserted into the graph during this session (demo work
    orders, retirement-interview answers), and clears the briefing feed."""
    builder = GraphBuilder()
    builder.build()
    builder.flush()
    refresh_normalizer()
    STATE["briefing_feed"] = []
    n = neo4j_run("MATCH (n) RETURN count(n) AS c")[0]["c"]
    e = neo4j_run("MATCH ()-[r]->() RETURN count(r) AS c")[0]["c"]
    return {"status": "reset", "nodes": n, "edges": e}


@app.get("/api/health")
def health():
    n = neo4j_run("MATCH (n) RETURN count(n) AS c")[0]["c"]
    e = neo4j_run("MATCH ()-[r]->() RETURN count(r) AS c")[0]["c"]
    return {"status": "ok", "nodes": n, "edges": e, "briefings_in_feed": len(STATE["briefing_feed"])}
