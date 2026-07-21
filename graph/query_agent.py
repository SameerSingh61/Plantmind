"""The grounded query surface. Every claim in an answer carries a
citation; when the graph doesn't cover what was asked, the system says so
and names the person with the most direct experience on the equipment in
question — it never improvises. See THE QUERY SURFACE in the build brief.

Backed by AuraDB (Neo4j) — every lookup here is a real Cypher query.
"""
import json
import re
import time

from graph.llm import call_llm
from graph.neo4j_client import run
from graph.normalizer import TagNormalizer

SYSTEM_PROMPT = """You are the grounded query layer for Kaveri Refinery Unit 3's knowledge graph.

You will receive a question and a JSON context object containing everything
the knowledge graph currently knows that is relevant to it (equipment
history, incidents, near-misses, procedures, regulatory clauses, work
orders). Every fact in the context carries a source document and page.

## Absolute rules

1. State ONLY what appears in the context. You have no other knowledge
   of this plant. If a detail is not in the context, it does not exist.
2. Every factual sentence must end with a citation in the form
   [DOC, p.N]. Sentences without a source in the context must not be
   written at all.
3. Never recommend a specific technical procedure, torque value,
   isolation step, or safety action beyond what is explicitly recorded.
   You surface what the record shows. You are not the engineer.
4. Never estimate probability, risk score, or severity not already
   present in the record.
5. If the context does not contain information that actually answers
   the question, respond with exactly: NO_MATCH
   Do not guess, extrapolate, or answer a nearby but different question.

Keep answers under 120 words, excluding citations."""

# Fact categories we know we cannot answer at all (no such field exists
# anywhere in the ontology) — used by the offline fallback (no live model
# call) to decide when to refuse rather than force an answer from
# unrelated context.
UNANSWERABLE_KEYWORDS = [
    "vibration threshold", "temperature limit", "pressure rating",
    "torque", "clearance spec", "design capacity", "spec sheet",
    "tolerance value", "setpoint", "wall thickness limit",
    "material grade", "flow coefficient",
]


def _top_experience_person(eq_key: str) -> dict | None:
    rows = run(
        "MATCH (eq:Equipment {key: $eq_key})<-[hew:HAS_EXPERIENCE_WITH]-(p:Person) "
        "RETURN p.name AS name, p.id AS id, p.role AS role, hew.work_order_count AS work_order_count "
        "ORDER BY hew.work_order_count DESC LIMIT 1",
        eq_key=eq_key,
    )
    return rows[0] if rows else None


def _identify_equipment(question: str) -> list[str]:
    tags = [r["tag"] for r in run("MATCH (e:Equipment) RETURN e.id AS tag")]
    normalizer = TagNormalizer(tags)
    found = normalizer.extract_tags_from_body(question)
    return [f"Equipment:{t}" for t in found]


def _gather_context(eq_key: str) -> dict:
    eq_rows = run(
        "MATCH (eq:Equipment {key: $eq_key}) "
        "RETURN eq.id AS tag, eq.name AS name, eq.type AS type, eq.unit AS unit, eq.criticality AS criticality",
        eq_key=eq_key,
    )
    eq = eq_rows[0]

    incident_rows = run(
        "MATCH (eq:Equipment {key: $eq_key})<-[:INVOLVED]-(inc:Incident) "
        "OPTIONAL MATCH (inc)-[:EXHIBITED]->(fm:FailureMode) "
        "RETURN inc.id AS id, inc.date AS date, inc.classification AS classification, "
        "       fm.id AS failure_mode, inc.source_document AS doc, inc.page AS page",
        eq_key=eq_key,
    )
    incidents, near_misses = [], []
    for r in incident_rows:
        entry = {
            "id": r["id"], "date": r["date"], "failure_mode": r["failure_mode"],
            "source": {"doc": r["doc"], "page": r["page"]},
        }
        (incidents if r["classification"] == "incident" else near_misses).append(entry)

    procedures = run(
        "MATCH (eq:Equipment {key: $eq_key})<-[:GOVERNS]-(proc:Procedure) "
        "RETURN proc.id AS id, proc.title AS title, proc.revision AS revision, "
        "       proc.revision_date AS revision_date, proc.source_document AS doc, proc.page AS page",
        eq_key=eq_key,
    )

    work_orders = run(
        "MATCH (eq:Equipment {key: $eq_key})<-[:PERFORMED_ON]-(wo:WorkOrder) "
        "RETURN wo.id AS id, wo.raised_date AS date, wo.work_type AS work_type, "
        "       wo.completion_notes AS notes, wo.source_document AS doc, wo.page AS page "
        "ORDER BY wo.raised_date DESC LIMIT 8",
        eq_key=eq_key,
    )

    return {
        "equipment": {"tag": eq["tag"], "name": eq["name"], "type": eq["type"],
                      "unit": eq["unit"], "criticality": eq["criticality"],
                      "source": {"doc": "equipment_register.csv", "page": 1}},
        "incidents": incidents,
        "near_misses": near_misses,
        "procedures_governing": [
            {"id": p["id"], "title": p["title"], "revision": p["revision"],
             "revision_date": p["revision_date"], "source": {"doc": p["doc"], "page": p["page"]}}
            for p in procedures
        ],
        "recent_work_orders": [
            {"id": w["id"], "date": w["date"], "work_type": w["work_type"], "notes": w["notes"],
             "source": {"doc": w["doc"], "page": w["page"]}}
            for w in work_orders
        ],
    }


def _fallback_answer(context: dict, question: str) -> str:
    lower_q = question.lower()
    if any(kw in lower_q for kw in UNANSWERABLE_KEYWORDS):
        return "NO_MATCH"

    eq = context["equipment"]
    lines = [f"{eq['tag']} ({eq['name']}) is a {eq['type']} in {eq['unit']} [{eq['source']['doc']}, p.{eq['source']['page']}]."]
    if context["incidents"]:
        i = context["incidents"][0]
        lines.append(f"It has an incident on record: {i['id']} ({i['date']}, {i['failure_mode']}) [{i['source']['doc']}, p.{i['source']['page']}].")
    if context["procedures_governing"]:
        p = context["procedures_governing"][0]
        lines.append(f"It is governed by {p['id']} ({p['title']}, {p['revision']}) [{p['source']['doc']}, p.{p['source']['page']}].")
    elif context["recent_work_orders"]:
        lines.append("No current procedure governs this equipment [graph:GOVERNS-check].")
    if context["recent_work_orders"]:
        w = context["recent_work_orders"][0]
        lines.append(f"Most recent work order: {w['id']} ({w['date']}) [{w['source']['doc']}, p.{w['source']['page']}].")
    if len(lines) == 1:
        return "NO_MATCH"
    return " ".join(lines)


def answer_query(question: str) -> dict:
    start = time.time()
    eq_keys = _identify_equipment(question)

    if not eq_keys:
        elapsed_ms = int((time.time() - start) * 1000)
        return {
            "answer": "No equipment tag in this question matches anything in the knowledge graph.",
            "refused": True,
            "person_to_ask": None,
            "citations": [],
            "time_to_answer_ms": elapsed_ms,
        }

    eq_key = eq_keys[0]
    context = _gather_context(eq_key)
    top_person = _top_experience_person(eq_key)

    llm_text = call_llm(SYSTEM_PROMPT, json.dumps({"question": question, "context": context}, indent=2), max_tokens=250)
    source = "llm"
    if llm_text is None:
        llm_text = _fallback_answer(context, question)
        source = "fallback_template"

    refused = llm_text.strip() == "NO_MATCH"
    elapsed_ms = int((time.time() - start) * 1000)

    if refused:
        eq_tag = context["equipment"]["tag"]
        if top_person:
            answer = (
                f"The graph has no record covering this specific question for {eq_tag}. "
                f"{top_person['name']} ({top_person['role']}) has the most direct experience on this "
                f"equipment — {top_person['work_order_count']} work orders on file — and is the person "
                f"to ask [derived:work_order_aggregation]."
            )
        else:
            answer = f"The graph has no record covering this specific question for {eq_tag}, and no person with recorded experience on it was found."
        return {
            "answer": answer, "refused": True,
            "person_to_ask": top_person, "citations": [], "source": source,
            "time_to_answer_ms": elapsed_ms,
        }

    citations = re.findall(r"\[([^,\]]+),\s*p\.([^\]]+)\]", llm_text) or re.findall(r"\[([^\]]+)\]", llm_text)
    return {
        "answer": llm_text, "refused": False,
        "person_to_ask": None, "citations": citations, "source": source,
        "time_to_answer_ms": elapsed_ms,
    }
