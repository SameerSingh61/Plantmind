"""The four trigger rules. Each is a plain graph traversal — no ML, as the
brief insists. They read structured graph output; only the briefing agent
(a separate module) turns that structured output into prose. Keeping the
reasoning here and the writing there is what keeps alerts reliable instead
of hallucinated.
"""
import statistics


def _equipment_tag(node_key: str) -> str:
    return node_key.split(":", 1)[1]


def _out(g, node, edge_type):
    return [v for _, v, d in g.out_edges(node, data=True) if d.get("edge_type") == edge_type]


def _in(g, node, edge_type):
    return [u for u, _, d in g.in_edges(node, data=True) if d.get("edge_type") == edge_type]


def _node(g, key):
    return g.nodes[key]


def _doc_ref(attrs: dict) -> dict:
    return {"doc": attrs.get("source_document"), "page": attrs.get("page")}


# ---------------------------------------------------------------------------
# Rule 1: unclosed_recommendation
# ---------------------------------------------------------------------------
def _team_median_experience(g, equipment_type: str) -> float:
    sums: dict[str, int] = {}
    for node, attrs in g.nodes(data=True):
        if attrs.get("node_type") != "Person":
            continue
        total = 0
        for _, eq_key, d in g.out_edges(node, data=True):
            if d.get("edge_type") != "HAS_EXPERIENCE_WITH":
                continue
            if _node(g, eq_key).get("type") == equipment_type:
                total += d.get("work_order_count", 0)
        if total > 0:
            sums[node] = total
    if not sums:
        return 0.0
    return statistics.median(sums.values())


def _person_experience(g, person_key: str, equipment_type: str) -> int:
    total = 0
    for _, eq_key, d in g.out_edges(person_key, data=True):
        if d.get("edge_type") != "HAS_EXPERIENCE_WITH":
            continue
        if _node(g, eq_key).get("type") == equipment_type:
            total += d.get("work_order_count", 0)
    return total


def check_experience_gap(g, wo_key: str) -> dict | None:
    """Rule 3, also folded into rule 1's composite briefing."""
    equipment = _out(g, wo_key, "PERFORMED_ON")
    assignees = _out(g, wo_key, "ASSIGNED_TO")
    if not equipment or not assignees:
        return None
    eq_key = equipment[0]
    person_key = assignees[0]
    eq_type = _node(g, eq_key).get("type")

    has_incident_history = bool(_in(g, eq_key, "INVOLVED"))
    if not has_incident_history:
        return None

    median = _team_median_experience(g, eq_type)
    person_count = _person_experience(g, person_key, eq_type)
    if median <= 0 or person_count >= median / 2:
        return None

    return {
        "type": "experience_gap",
        "person": _node(g, person_key).get("name"),
        "person_id": _node(g, person_key).get("id"),
        "prior_work_orders_on_equipment_class": person_count,
        "team_median": median,
        "source": {"doc": "work_order_index", "page": None},
    }


def check_unclosed_recommendations(g, eq_key: str) -> list[dict]:
    findings = []
    for inc_key in _in(g, eq_key, "INVOLVED"):
        if _node(g, inc_key).get("classification") != "incident":
            continue
        for _, proc_key, edge_attrs in [
            (u, v, d) for u, v, d in g.out_edges(inc_key, data=True) if d.get("edge_type") == "RECOMMENDED"
        ]:
            governs = _out(g, proc_key, "GOVERNS")
            if eq_key in governs:
                continue  # implemented — this recommendation is closed
            fm_keys = _out(g, inc_key, "EXHIBITED")
            findings.append({
                "type": "unimplemented_recommendation",
                "incident": _node(g, inc_key).get("id"),
                "date": _node(g, inc_key).get("date"),
                "failure_mode": _equipment_tag(fm_keys[0]) if fm_keys else None,
                "recommendation": edge_attrs.get("text"),
                "rec_owner": edge_attrs.get("owner_role") or edge_attrs.get("owner"),
                "rec_target_date": edge_attrs.get("target_date"),
                "implementation_status": "no_linked_procedure",
                "source": _doc_ref(edge_attrs),
            })
    return findings


def check_recurrence_on_equipment(g, eq_key: str, unclosed: list[dict]) -> dict | None:
    """Near-misses on the same equipment sharing a failure mode with an
    unclosed recommendation — the echo that follows an unclosed loop."""
    if not unclosed:
        return None
    target_modes = {f["failure_mode"] for f in unclosed if f.get("failure_mode")}
    if not target_modes:
        return None
    matches = []
    for inc_key in _in(g, eq_key, "INVOLVED"):
        attrs = _node(g, inc_key)
        if attrs.get("classification") != "near_miss":
            continue
        fm_keys = _out(g, inc_key, "EXHIBITED")
        fms = {_equipment_tag(k) for k in fm_keys}
        if fms & target_modes:
            matches.append((attrs.get("id"), attrs.get("date"), inc_key))
    if len(matches) < 1:
        return None
    matches.sort(key=lambda m: m[1] or "")
    last_key = matches[-1][2]
    last_attrs = _node(g, last_key)
    return {
        "type": "recurrence",
        "count": len(matches),
        "records": [m[0] for m in matches],
        "shared_failure_mode": next(iter(target_modes)),
        "source": _doc_ref(last_attrs),
    }


def rule_unclosed_recommendation(g, wo_key: str) -> dict | None:
    """The composite briefing payload for a newly opened work order:
    unimplemented recommendations on this equipment, the near-miss echoes
    that followed, and an experience-gap check on the assignee.
    """
    equipment = _out(g, wo_key, "PERFORMED_ON")
    if not equipment:
        return None
    eq_key = equipment[0]
    wo_attrs = _node(g, wo_key)

    unclosed = check_unclosed_recommendations(g, eq_key)
    if not unclosed:
        return None

    findings = list(unclosed)
    recurrence = check_recurrence_on_equipment(g, eq_key, unclosed)
    if recurrence:
        findings.append(recurrence)
    exp_gap = check_experience_gap(g, wo_key)
    if exp_gap:
        findings.append(exp_gap)

    if len(findings) < 2:
        return None  # briefing system prompt requires 2+ findings

    assignees = _out(g, wo_key, "ASSIGNED_TO")
    assignee_name = _node(g, assignees[0]).get("name") if assignees else None
    month = int((wo_attrs.get("raised_date") or "0000-01")[5:7]) if wo_attrs.get("raised_date") else None
    season = "monsoon" if month in (6, 7, 8, 9) else "non-monsoon"

    return {
        "trigger_rule": "unclosed_recommendation",
        "trigger_event": {
            "work_order": wo_attrs.get("id"),
            "equipment": _equipment_tag(eq_key),
            "equipment_name": _node(g, eq_key).get("name"),
            "work_type": wo_attrs.get("work_type"),
            "raised": wo_attrs.get("raised_date"),
            "assigned_to": assignee_name,
            "season_context": season,
        },
        "findings": findings,
    }


# ---------------------------------------------------------------------------
# Rule 2: recurrence_pattern (global sweep, not tied to a single new WO)
# ---------------------------------------------------------------------------
def rule_recurrence_pattern(g, min_count: int = 3) -> list[dict]:
    """3+ *incidents* (not near-misses — those are weaker corroborating
    signal, listed separately) sharing a failure mode across different
    equipment of the same type. Sorted strongest-signal-first so the
    highest-confidence pattern surfaces at the top.
    """
    results = []
    for fm_key, fm_attrs in list(g.nodes(data=True)):
        if fm_attrs.get("node_type") != "FailureMode":
            continue
        inc_keys = _in(g, fm_key, "EXHIBITED")
        by_equipment_type: dict[str, set[str]] = {}
        records_by_type: dict[str, list[tuple[str, str, str, str]]] = {}
        for inc_key in inc_keys:
            classification = _node(g, inc_key).get("classification")
            eq_keys = _out(g, inc_key, "INVOLVED")
            for eq_key in eq_keys:
                eq_type = _node(g, eq_key).get("type")
                by_equipment_type.setdefault(eq_type, set()).add(eq_key)
                records_by_type.setdefault(eq_type, []).append(
                    (_node(g, inc_key).get("id"), _node(g, inc_key).get("date"), eq_key, classification)
                )
        for eq_type, eq_set in by_equipment_type.items():
            records = records_by_type[eq_type]
            incident_records = [r for r in records if r[3] == "incident"]
            near_miss_records = [r for r in records if r[3] == "near_miss"]
            incident_equipment = {r[2] for r in incident_records}
            if len(incident_equipment) >= 3 and len(incident_records) >= min_count:
                results.append({
                    "type": "recurrence_pattern",
                    "failure_mode": _equipment_tag(fm_key),
                    "equipment_type": eq_type,
                    "equipment_involved": sorted(_equipment_tag(e) for e in incident_equipment),
                    "incident_count": len(incident_records),
                    "incidents": sorted(r[0] for r in incident_records),
                    "corroborating_near_misses": sorted(r[0] for r in near_miss_records),
                    "date_range": [
                        min(r[1] for r in incident_records),
                        max(r[1] for r in incident_records),
                    ],
                })
    results.sort(key=lambda r: (-r["incident_count"], -len(r["equipment_involved"])))
    return results


# ---------------------------------------------------------------------------
# Rule 4: orphaned_knowledge (global sweep, feeds the retirement agent)
# ---------------------------------------------------------------------------
def rule_orphaned_knowledge(g, min_work_orders: int = 5, majority_threshold: float = 0.5) -> list[dict]:
    results = []
    for eq_key, eq_attrs in list(g.nodes(data=True)):
        if eq_attrs.get("node_type") != "Equipment":
            continue
        wo_keys = _in(g, eq_key, "PERFORMED_ON")
        if len(wo_keys) < min_work_orders:
            continue
        governs = _in(g, eq_key, "GOVERNS")
        if governs:
            continue  # has at least one current procedure — not orphaned

        author_counts: dict[str, int] = {}
        for wo_key in wo_keys:
            for person_key in _out(g, wo_key, "ASSIGNED_TO"):
                author_counts[person_key] = author_counts.get(person_key, 0) + 1
        if not author_counts:
            continue
        top_person, top_count = max(author_counts.items(), key=lambda kv: kv[1])
        if top_count / len(wo_keys) < majority_threshold:
            continue

        results.append({
            "type": "orphaned_knowledge",
            "equipment": _equipment_tag(eq_key),
            "equipment_name": eq_attrs.get("name"),
            "work_order_count": len(wo_keys),
            "primary_author": _node(g, top_person).get("name"),
            "primary_author_id": _node(g, top_person).get("id"),
            "primary_author_share": round(top_count / len(wo_keys), 2),
            "primary_author_status": _node(g, top_person).get("status"),
            "primary_author_tenure_end": _node(g, top_person).get("tenure_end"),
            "work_orders": [_node(g, w).get("id") for w in wo_keys],
        })
    return results


def run_nightly_sweep(g) -> dict:
    return {
        "recurrence_patterns": rule_recurrence_pattern(g),
        "orphaned_knowledge": rule_orphaned_knowledge(g),
    }
