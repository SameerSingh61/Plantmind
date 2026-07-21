"""The grounded query surface. Every claim in an answer carries a
citation; when the graph doesn't cover what was asked, the system says so
and names the person with the most direct experience on the equipment in
question — it never improvises. See THE QUERY SURFACE in the build brief.
"""
import json
import re
import time

from graph.llm import call_claude

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


def _top_experience_person(g, eq_key: str) -> dict | None:
    best = None
    for u, v, d in g.in_edges(eq_key, data=True):
        if d.get("edge_type") != "HAS_EXPERIENCE_WITH":
            continue
        count = d.get("work_order_count", 0)
        if best is None or count > best[1]:
            best = (u, count)
    if best is None:
        return None
    person_attrs = g.nodes[best[0]]
    return {"name": person_attrs.get("name"), "id": person_attrs.get("id"),
            "role": person_attrs.get("role"), "work_order_count": best[1]}


def _identify_equipment(g, question: str) -> list[str]:
    from graph.normalizer import TagNormalizer
    tags = [attrs["id"] for _, attrs in g.nodes(data=True) if attrs.get("node_type") == "Equipment"]
    normalizer = TagNormalizer(tags)
    found = normalizer.extract_tags_from_body(question)
    return [f"Equipment:{t}" for t in found]


def _gather_context(g, eq_key: str) -> dict:
    eq = dict(g.nodes[eq_key])
    incidents, near_misses, procedures, work_orders = [], [], [], []

    for u, v, d in g.in_edges(eq_key, data=True):
        if d.get("edge_type") == "INVOLVED":
            inc = dict(g.nodes[u])
            fm = [g.nodes[vv]["id"] for _, vv, dd in g.out_edges(u, data=True) if dd.get("edge_type") == "EXHIBITED"]
            entry = {
                "id": inc.get("id"), "date": inc.get("date"),
                "failure_mode": fm[0] if fm else None,
                "source": {"doc": inc.get("source_document"), "page": inc.get("page")},
            }
            (incidents if inc.get("classification") == "incident" else near_misses).append(entry)
        elif d.get("edge_type") == "GOVERNS":
            proc = dict(g.nodes[u])
            procedures.append({
                "id": proc.get("id"), "title": proc.get("title"), "revision": proc.get("revision"),
                "revision_date": proc.get("revision_date"),
                "source": {"doc": proc.get("source_document"), "page": proc.get("page")},
            })
        elif d.get("edge_type") == "PERFORMED_ON":
            wo = dict(g.nodes[u])
            work_orders.append({
                "id": wo.get("id"), "date": wo.get("raised_date"), "work_type": wo.get("work_type"),
                "notes": wo.get("completion_notes"),
                "source": {"doc": wo.get("source_document"), "page": wo.get("page")},
            })

    work_orders.sort(key=lambda w: w["date"] or "", reverse=True)
    return {
        "equipment": {"tag": eq.get("id"), "name": eq.get("name"), "type": eq.get("type"),
                      "unit": eq.get("unit"), "criticality": eq.get("criticality"),
                      "source": {"doc": "equipment_register.csv", "page": 1}},
        "incidents": incidents,
        "near_misses": near_misses,
        "procedures_governing": procedures,
        "recent_work_orders": work_orders[:8],
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
        lines.append(f"No current procedure governs this equipment [graph:GOVERNS-check].")
    if context["recent_work_orders"]:
        w = context["recent_work_orders"][0]
        lines.append(f"Most recent work order: {w['id']} ({w['date']}) [{w['source']['doc']}, p.{w['source']['page']}].")
    if len(lines) == 1:
        return "NO_MATCH"
    return " ".join(lines)


def answer_query(g, question: str) -> dict:
    start = time.time()
    eq_keys = _identify_equipment(g, question)

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
    context = _gather_context(g, eq_key)
    top_person = _top_experience_person(g, eq_key)

    llm_text = call_claude(SYSTEM_PROMPT, json.dumps({"question": question, "context": context}, indent=2), max_tokens=250)
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
