#!/usr/bin/env python3
"""Acceptance tests 1-10 from the build brief. Run from repo root:

    python3 tests/acceptance_tests.py

Tests 5, 8, 9, 10 hit the live backend (start it first: uvicorn
backend.main:app --port 8123, or bash scripts/dev.sh). Everything else
queries AuraDB directly (graph/build.py must have been run at least once
to populate it).
"""
import re
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from graph.neo4j_client import run as neo4j_run  # noqa: E402
from graph.normalizer import TagNormalizer  # noqa: E402
from graph.parser import parse_all  # noqa: E402
from graph.rules import rule_recurrence_pattern  # noqa: E402

CORPUS = ROOT / "corpus"
API = "http://localhost:8123"

results = []


def check(name: str, condition: bool, detail: str = ""):
    status = "PASS" if condition else "FAIL"
    results.append((name, status, detail))
    print(f"[{status}] {name}" + (f" — {detail}" if detail else ""))
    return condition


def main():
    equipment_tags = [r["tag"] for r in neo4j_run("MATCH (e:Equipment) RETURN e.id AS tag")]
    normalizer = TagNormalizer(equipment_tags)

    # -- Test 1: every operational document references a registered tag ----
    unresolved = []
    checked = 0
    for directory in ["03_work_orders", "04_incidents", "05_near_misses"]:
        for doc in parse_all(CORPUS / directory):
            checked += 1
            raw_tags = doc.front_matter.get("equipment_tags") or []
            resolved = [normalizer.normalize(t) for t in raw_tags]
            resolved = [r for r in resolved if r]
            if not resolved:
                resolved = normalizer.extract_tags_from_body(doc.body)
            if not resolved:
                unresolved.append(doc.path.name)
    check(
        "1. Every work order/incident/near-miss references a registered tag",
        len(unresolved) == 0,
        f"{checked} documents checked, {len(unresolved)} unresolved: {unresolved}"
        if unresolved else f"{checked}/{checked} resolved (administrative procedures and "
                            f"regulatory standards are legitimately equipment-agnostic and excluded)",
    )

    # -- Test 2: 30+ of 40 equipment have 3+ linked documents ----------------
    # "Linked documents" = distinct source files reaching the equipment via
    # any of the ontology's three equipment-pointing edges: an incident/
    # near-miss that INVOLVED it, a work order PERFORMED_ON it, or a
    # procedure that GOVERNS it. A governing procedure is a real corpus
    # document about that equipment, same as a work order is.
    rows = neo4j_run(
        "MATCH (eq:Equipment)<-[r:INVOLVED|PERFORMED_ON|GOVERNS]-(x) "
        "RETURN eq.key AS eq_key, collect(DISTINCT r.source_document) AS docs"
    )
    doc_counts = {r["eq_key"]: len(r["docs"]) for r in rows}
    well_documented = sum(1 for c in doc_counts.values() if c >= 3)
    check(
        "2. 30+/40 equipment items have 3+ linked documents",
        well_documented >= 30,
        f"{well_documented}/40 equipment items have 3+ linked documents",
    )

    # -- Test 3: all three storylines resolve via pure traversal ------------
    s1_rows = neo4j_run(
        "MATCH (:Incident {key:'Incident:INC-2019-04'})-[:RECOMMENDED]->(proc:Procedure) "
        "RETURN NOT (proc)-[:GOVERNS]->() AS unclosed"
    )
    s1 = bool(s1_rows and s1_rows[0]["unclosed"])

    s2_rows = neo4j_run(
        "MATCH (:FailureMode {key:'FailureMode:tube_sheet_fouling'})<-[:EXHIBITED]-(inc:Incident)"
        "      -[:INVOLVED]->(eq:Equipment) "
        "RETURN DISTINCT eq.key AS eq_key"
    )
    equip = {r["eq_key"] for r in s2_rows}
    s2 = equip == {"Equipment:E-204", "Equipment:E-206", "Equipment:E-211"}

    s3_rows = neo4j_run(
        "MATCH (eq:Equipment {key:'Equipment:V-2301'}) "
        "RETURN NOT (eq)<-[:GOVERNS]-() AS orphaned"
    )
    s3 = bool(s3_rows and s3_rows[0]["orphaned"])

    check("3. Storyline 1 (unclosed loop) resolves via traversal", s1)
    check("3. Storyline 2 (cross-equipment pattern) resolves via traversal", s2, f"equipment found: {equip}")
    check("3. Storyline 3 (knowledge cliff) resolves via traversal", s3)

    # -- Test 4: a 3-hop question answerable only through the graph ---------
    # Equipment -INVOLVED- Incident -RECOMMENDED-> Procedure -SATISFIES-> RegulatoryClause
    hop_rows = neo4j_run(
        "MATCH (eq:Equipment)<-[:INVOLVED]-(inc:Incident)-[:RECOMMENDED]->(proc:Procedure)"
        "      -[:SATISFIES]->(clause:RegulatoryClause) "
        "RETURN eq.key AS eq_key, inc.key AS inc_key, proc.key AS proc_key, clause.key AS clause_key LIMIT 1"
    )
    check(
        "4. A 3-hop Equipment→Incident→Procedure→RegulatoryClause chain exists",
        len(hop_rows) > 0,
        f"e.g. {tuple(hop_rows[0].values())}" if hop_rows else "none found",
    )

    # -- Test 6: recurrence pattern rule finds the exchanger pattern ---------
    patterns = rule_recurrence_pattern()
    flagship = next((p for p in patterns if p["failure_mode"] == "tube_sheet_fouling"), None)
    check(
        "6. Rule 2 surfaces the E-204/E-206/E-211 pattern unprompted",
        flagship is not None and set(flagship["equipment_involved"]) == {"E-204", "E-206", "E-211"},
        str(flagship),
    )

    # -- Test 7: normalizer resolves 3 tag spelling variants -----------------
    variants = ["P101A", "P-101 A", "P-101A"]
    normalized = [normalizer.normalize(v) for v in variants]
    check(
        "7. Normalizer resolves P101A / P-101 A / P-101A to one node",
        len(set(normalized)) == 1 and normalized[0] == "P-101A",
        f"{variants} -> {normalized}",
    )

    # -- API-dependent tests (5, 8, 9) ---------------------------------------
    api_up = False
    try:
        requests.get(f"{API}/api/health", timeout=2)
        api_up = True
    except Exception:
        pass

    if not api_up:
        check("5. WO-2026-4471 produces briefing in <10s with citations", False, "backend not running on :8123")
        check("8. Out-of-corpus question triggers refusal + names a real Person", False, "backend not running")
        check("9. Graph explorer path P-101A -> INC-2019-04 -> missing procedure", False, "backend not running")
    else:
        requests.post(f"{API}/api/reset", timeout=30)
        start = time.time()
        resp = requests.post(f"{API}/api/demo/trigger-storyline-1", timeout=15).json()
        elapsed = time.time() - start
        briefing_text = (resp.get("briefing") or {}).get("text", "")
        citations = re.findall(r"\[([^,\]]+),\s*p\.\d+\]", briefing_text)
        check(
            "5. WO-2026-4471 produces briefing in <10s with citations",
            elapsed < 10 and resp.get("briefing") is not None and len(citations) > 0,
            f"elapsed={elapsed:.2f}s, citations found: {citations}",
        )

        refusal = requests.post(
            f"{API}/api/query", json={"question": "What is the design pressure rating for V-2301?"}, timeout=15
        ).json()
        person = refusal.get("person_to_ask")
        person_is_real = bool(person) and bool(
            neo4j_run("MATCH (p:Person {name: $name}) RETURN p", name=person.get("name"))
        )
        check(
            "8. Out-of-corpus question triggers refusal + names a real Person",
            refusal.get("refused") is True and person_is_real,
            f"refused={refusal.get('refused')}, person_to_ask={person}",
        )

        path_resp = requests.get(
            f"{API}/api/graph/path",
            params={"source": "Equipment:P-101A", "target": "Procedure:REC-INC-2019-04-1"},
            timeout=10,
        ).json()
        node_keys = [n["key"] for n in path_resp.get("nodes", [])]
        expected = ["Equipment:P-101A", "Incident:INC-2019-04", "Procedure:REC-INC-2019-04-1"]
        check(
            "9. Graph explorer animates P-101A -> INC-2019-04 -> missing procedure",
            node_keys == expected,
            f"path returned: {node_keys}",
        )

    # -- Test 10: every displayed claim has a citation that resolves --------
    if api_up:
        briefing_text = (requests.get(f"{API}/api/briefings", timeout=5).json()["briefings"] or [{}])[0].get("text", "")
        citation_matches = re.findall(r"\[([^,\]]+\.md),\s*p\.(\d+)\]", briefing_text)
        all_resolve = True
        bad = []
        for doc_name, page in citation_matches:
            found = False
            for sub in ["03_work_orders", "04_incidents", "05_near_misses", "02_procedures"]:
                if (CORPUS / sub / doc_name).exists():
                    found = True
                    break
            if not found:
                all_resolve = False
                bad.append(doc_name)
        check(
            "10. Every citation in the briefing resolves to a real source document",
            len(citation_matches) > 0 and all_resolve,
            f"{len(citation_matches)} citations checked" + (f", missing: {bad}" if bad else ""),
        )
    else:
        check("10. Every citation in the briefing resolves to a real source document", False, "backend not running")

    print()
    n_pass = sum(1 for _, s, _ in results if s == "PASS")
    print(f"{n_pass}/{len(results)} checks passed")
    return 0 if n_pass == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
