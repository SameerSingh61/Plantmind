"""The four trigger rules — now real Cypher queries against AuraDB, not
Python graph traversal. Composed as a handful of small, readable
statements per rule rather than one giant query, glued together in
Python — same "traversal does the reasoning, the LLM only writes"
discipline as before, just against a real graph database this time.
"""
import statistics

from graph.neo4j_client import run


def _tag(key: str) -> str:
    return key.split(":", 1)[1]


# ---------------------------------------------------------------------------
# Rule 1: unclosed_recommendation
# ---------------------------------------------------------------------------
def _team_median_experience(equipment_type: str) -> float:
    rows = run(
        "MATCH (eq:Equipment {type: $eq_type})<-[hew:HAS_EXPERIENCE_WITH]-(p:Person) "
        "RETURN p.key AS person_key, sum(hew.work_order_count) AS total",
        eq_type=equipment_type,
    )
    totals = [r["total"] for r in rows if r["total"]]
    return statistics.median(totals) if totals else 0.0


def _person_experience(person_key: str, equipment_type: str) -> int:
    rows = run(
        "MATCH (eq:Equipment {type: $eq_type})<-[hew:HAS_EXPERIENCE_WITH]-(p:Person {key: $person_key}) "
        "RETURN sum(hew.work_order_count) AS total",
        eq_type=equipment_type, person_key=person_key,
    )
    return rows[0]["total"] or 0 if rows else 0


def check_experience_gap(wo_key: str) -> dict | None:
    """Rule 3, also folded into rule 1's composite briefing."""
    rows = run(
        "MATCH (wo:WorkOrder {key: $wo_key})-[:PERFORMED_ON]->(eq:Equipment) "
        "MATCH (wo)-[:ASSIGNED_TO]->(person:Person) "
        "OPTIONAL MATCH (eq)<-[:INVOLVED]-(inc:Incident) "
        "RETURN eq.key AS eq_key, eq.type AS eq_type, person.key AS person_key, "
        "       person.name AS person_name, person.id AS person_id, "
        "       count(inc) AS incident_count",
        wo_key=wo_key,
    )
    if not rows:
        return None
    row = rows[0]
    if row["incident_count"] == 0:
        return None

    median = _team_median_experience(row["eq_type"])
    person_count = _person_experience(row["person_key"], row["eq_type"])
    if median <= 0 or person_count >= median / 2:
        return None

    return {
        "type": "experience_gap",
        "person": row["person_name"],
        "person_id": row["person_id"],
        "prior_work_orders_on_equipment_class": person_count,
        "team_median": median,
        "source": {"doc": "work_order_index", "page": None},
    }


def check_unclosed_recommendations(eq_key: str) -> list[dict]:
    rows = run(
        "MATCH (eq:Equipment {key: $eq_key})<-[:INVOLVED]-(inc:Incident {classification: 'incident'})"
        "      -[rec:RECOMMENDED]->(proc:Procedure) "
        "WHERE NOT (proc)-[:GOVERNS]->(eq) "
        "OPTIONAL MATCH (inc)-[:EXHIBITED]->(fm:FailureMode) "
        "RETURN inc.id AS incident, inc.date AS date, fm.id AS failure_mode, "
        "       rec.text AS recommendation, rec.owner_role AS rec_owner, rec.owner AS rec_owner_name, "
        "       rec.target_date AS rec_target_date, rec.source_document AS doc, rec.page AS page",
        eq_key=eq_key,
    )
    findings = []
    for row in rows:
        findings.append({
            "type": "unimplemented_recommendation",
            "incident": row["incident"],
            "date": row["date"],
            "failure_mode": row["failure_mode"],
            "recommendation": row["recommendation"],
            "rec_owner": row["rec_owner"] or row["rec_owner_name"],
            "rec_target_date": row["rec_target_date"],
            "implementation_status": "no_linked_procedure",
            "source": {"doc": row["doc"], "page": row["page"]},
        })
    return findings


def check_recurrence_on_equipment(eq_key: str, unclosed: list[dict]) -> dict | None:
    target_modes = {f["failure_mode"] for f in unclosed if f.get("failure_mode")}
    if not target_modes:
        return None
    rows = run(
        "MATCH (eq:Equipment {key: $eq_key})<-[:INVOLVED]-(nm:Incident {classification: 'near_miss'})"
        "      -[:EXHIBITED]->(fm:FailureMode) "
        "WHERE fm.id IN $modes "
        "RETURN nm.id AS id, nm.date AS date, fm.id AS failure_mode, "
        "       nm.source_document AS doc, nm.page AS page "
        "ORDER BY nm.date",
        eq_key=eq_key, modes=list(target_modes),
    )
    if not rows:
        return None
    last = rows[-1]
    return {
        "type": "recurrence",
        "count": len(rows),
        "records": [r["id"] for r in rows],
        "shared_failure_mode": rows[0]["failure_mode"],
        "source": {"doc": last["doc"], "page": last["page"]},
    }


def rule_unclosed_recommendation(wo_key: str) -> dict | None:
    rows = run(
        "MATCH (wo:WorkOrder {key: $wo_key})-[:PERFORMED_ON]->(eq:Equipment) "
        "OPTIONAL MATCH (wo)-[:ASSIGNED_TO]->(person:Person) "
        "RETURN wo.id AS wo_id, wo.work_type AS work_type, wo.raised_date AS raised, "
        "       eq.key AS eq_key, eq.id AS eq_tag, eq.name AS eq_name, person.name AS person_name",
        wo_key=wo_key,
    )
    if not rows:
        return None
    row = rows[0]
    eq_key = row["eq_key"]

    unclosed = check_unclosed_recommendations(eq_key)
    if not unclosed:
        return None

    findings = list(unclosed)
    recurrence = check_recurrence_on_equipment(eq_key, unclosed)
    if recurrence:
        findings.append(recurrence)
    exp_gap = check_experience_gap(wo_key)
    if exp_gap:
        findings.append(exp_gap)

    if len(findings) < 2:
        return None

    month = int((row["raised"] or "0000-01")[5:7]) if row["raised"] else None
    season = "monsoon" if month in (6, 7, 8, 9) else "non-monsoon"

    return {
        "trigger_rule": "unclosed_recommendation",
        "trigger_event": {
            "work_order": row["wo_id"],
            "equipment": row["eq_tag"],
            "equipment_name": row["eq_name"],
            "work_type": row["work_type"],
            "raised": row["raised"],
            "assigned_to": row["person_name"],
            "season_context": season,
        },
        "findings": findings,
    }


# ---------------------------------------------------------------------------
# Rule 2: recurrence_pattern (global sweep)
# ---------------------------------------------------------------------------
def rule_recurrence_pattern(min_count: int = 3) -> list[dict]:
    candidates = run(
        "MATCH (fm:FailureMode)<-[:EXHIBITED]-(inc:Incident {classification: 'incident'})"
        "      -[:INVOLVED]->(eq:Equipment) "
        "WITH fm, eq.type AS eq_type, "
        "     collect(DISTINCT eq.id) AS equipment_tags, "
        "     collect(DISTINCT {id: inc.id, date: inc.date}) AS incidents "
        "WHERE size(equipment_tags) >= 3 AND size(incidents) >= $min_count "
        "RETURN fm.id AS failure_mode, eq_type AS equipment_type, equipment_tags, incidents",
        min_count=min_count,
    )
    results = []
    for c in candidates:
        near_misses = run(
            "MATCH (fm:FailureMode {id: $fm})<-[:EXHIBITED]-(nm:Incident {classification: 'near_miss'})"
            "      -[:INVOLVED]->(eq:Equipment {type: $eq_type}) "
            "RETURN DISTINCT nm.id AS id ORDER BY id",
            fm=c["failure_mode"], eq_type=c["equipment_type"],
        )
        dates = sorted(i["date"] for i in c["incidents"] if i["date"])
        results.append({
            "type": "recurrence_pattern",
            "failure_mode": c["failure_mode"],
            "equipment_type": c["equipment_type"],
            "equipment_involved": sorted(c["equipment_tags"]),
            "incident_count": len(c["incidents"]),
            "incidents": sorted(i["id"] for i in c["incidents"]),
            "corroborating_near_misses": [n["id"] for n in near_misses],
            "date_range": [dates[0], dates[-1]] if dates else [None, None],
        })
    results.sort(key=lambda r: (-r["incident_count"], -len(r["equipment_involved"])))
    return results


# ---------------------------------------------------------------------------
# Rule 4: orphaned_knowledge (global sweep, feeds the retirement agent)
# ---------------------------------------------------------------------------
def rule_orphaned_knowledge(min_work_orders: int = 5, majority_threshold: float = 0.5) -> list[dict]:
    candidates = run(
        "MATCH (eq:Equipment)<-[:PERFORMED_ON]-(wo:WorkOrder) "
        "WITH eq, collect(wo.id) AS wo_ids, count(wo) AS wo_count "
        "WHERE wo_count >= $min_wo AND NOT (eq)<-[:GOVERNS]-(:Procedure) "
        "RETURN eq.key AS eq_key, eq.id AS eq_tag, eq.name AS eq_name, wo_ids, wo_count",
        min_wo=min_work_orders,
    )
    results = []
    for c in candidates:
        authors = run(
            "MATCH (eq:Equipment {key: $eq_key})<-[:PERFORMED_ON]-(wo:WorkOrder)-[:ASSIGNED_TO]->(p:Person) "
            "RETURN p.name AS name, p.id AS id, p.status AS status, p.tenure_end AS tenure_end, "
            "       count(wo) AS author_count ORDER BY author_count DESC LIMIT 1",
            eq_key=c["eq_key"],
        )
        if not authors:
            continue
        top = authors[0]
        share = top["author_count"] / c["wo_count"]
        if share < majority_threshold:
            continue
        results.append({
            "type": "orphaned_knowledge",
            "equipment": c["eq_tag"],
            "equipment_name": c["eq_name"],
            "work_order_count": c["wo_count"],
            "primary_author": top["name"],
            "primary_author_id": top["id"],
            "primary_author_share": round(share, 2),
            "primary_author_status": top["status"],
            "primary_author_tenure_end": top["tenure_end"],
            "work_orders": c["wo_ids"],
        })
    return results


def run_nightly_sweep() -> dict:
    return {
        "recurrence_patterns": rule_recurrence_pattern(),
        "orphaned_knowledge": rule_orphaned_knowledge(),
    }
