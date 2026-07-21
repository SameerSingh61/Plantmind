#!/usr/bin/env python3
"""Generate the 12 personnel records for Kaveri Refinery Unit 3.

Facts are hand-authored (a real team would interview these people); this
script only renders them into the document format so every record has
consistent structure. Run from repo root: python3 scripts/generate_personnel.py
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "corpus" / "08_personnel"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Hand-authored facts. tenure_end null = still active.
PERSONNEL = [
    {
        "id": "EMP-001",
        "name": "R. Krishnan",
        "role": "Senior Operations Engineer",
        "unit": "DCU",
        "tenure_start": "1998-03-01",
        "tenure_end": "2026-08-15",
        "status": "retiring",
        "specialization": "Coker vessels, vacuum system operation, startup/shutdown sequencing",
        "bio": (
            "R. Krishnan joined Kaveri Refinery in March 1998 as a junior operator "
            "on the original CDU commissioning team and moved into the DCU when the "
            "coker was commissioned in 2013. He has signed off on more work orders "
            "against V-2301 (Coker knockout drum) than any other engineer in the "
            "unit's history, and is the de facto authority on that vessel's operating "
            "quirks. He retires on 2026-08-15. No procedure currently documents the "
            "knowledge held in his work order notes on V-2301."
        ),
    },
    {
        "id": "EMP-002",
        "name": "A. Verma",
        "role": "Maintenance Technician",
        "unit": "CDU",
        "tenure_start": "2024-06-10",
        "tenure_end": None,
        "status": "active",
        "specialization": "Rotating equipment, pump seals",
        "bio": (
            "A. Verma joined the CDU maintenance team in June 2024 after two years "
            "at a smaller merchant refinery. Still building equipment-specific "
            "history on Unit 3's crude charge pumps."
        ),
    },
    {
        "id": "EMP-003",
        "name": "S. Iyer",
        "role": "Maintenance Head",
        "unit": "CDU/VDU",
        "tenure_start": "2010-01-15",
        "tenure_end": None,
        "status": "active",
        "specialization": "Maintenance planning, RCA ownership, permit-to-work sign-off",
        "bio": (
            "S. Iyer has led CDU/VDU maintenance planning since 2010 and is the "
            "named recommendation owner on several incident RCAs, including "
            "INC-2019-04."
        ),
    },
    {
        "id": "EMP-004",
        "name": "P. Nair",
        "role": "Process Engineer",
        "unit": "CDU",
        "tenure_start": "2015-08-01",
        "tenure_end": None,
        "status": "active",
        "specialization": "Preheat train thermal performance, exchanger fouling",
        "bio": (
            "P. Nair covers preheat train performance monitoring and filed the "
            "2020 fouling incident on E-204."
        ),
    },
    {
        "id": "EMP-005",
        "name": "M. Reddy",
        "role": "Process Engineer",
        "unit": "CDU",
        "tenure_start": "2017-02-20",
        "tenure_end": None,
        "status": "active",
        "specialization": "Crude assay tracking, blend scheduling",
        "bio": (
            "M. Reddy joined in 2017 covering crude blend scheduling and filed "
            "the 2022 fouling incident on E-206."
        ),
    },
    {
        "id": "EMP-006",
        "name": "K. Rao",
        "role": "Process Engineer",
        "unit": "VDU",
        "tenure_start": "2012-11-05",
        "tenure_end": None,
        "status": "active",
        "specialization": "Vacuum system performance, ejector systems",
        "bio": (
            "K. Rao has covered VDU process performance since 2012 and filed "
            "the 2023 fouling incident affecting the gas oil pumparound circuit."
        ),
    },
    {
        "id": "EMP-007",
        "name": "J. Fernandes",
        "role": "Process Engineer",
        "unit": "CDU",
        "tenure_start": "2019-04-15",
        "tenure_end": None,
        "status": "active",
        "specialization": "Preheat train monitoring, energy efficiency",
        "bio": (
            "J. Fernandes joined in 2019 and filed the most recent (2024) "
            "fouling incident on E-211, the third exchanger in the pattern."
        ),
    },
    {
        "id": "EMP-008",
        "name": "T. Singh",
        "role": "Maintenance Technician",
        "unit": "CDU",
        "tenure_start": "2016-09-01",
        "tenure_end": None,
        "status": "active",
        "specialization": "Rotating equipment, pump overhauls",
        "bio": (
            "T. Singh has eight years on CDU rotating equipment and is the "
            "most experienced technician on crude charge pump work."
        ),
    },
    {
        "id": "EMP-009",
        "name": "V. Menon",
        "role": "Maintenance Technician",
        "unit": "DCU",
        "tenure_start": "2014-05-12",
        "tenure_end": None,
        "status": "active",
        "specialization": "Coker vessels, fired heaters",
        "bio": (
            "V. Menon has worked DCU maintenance since 2014, mostly alongside "
            "R. Krishnan on coker equipment."
        ),
    },
    {
        "id": "EMP-010",
        "name": "D. Gupta",
        "role": "Inspection Engineer",
        "unit": "Unit 3",
        "tenure_start": "2011-03-22",
        "tenure_end": None,
        "status": "active",
        "specialization": "Statutory inspection, corrosion monitoring, PESO compliance",
        "bio": (
            "D. Gupta runs the statutory inspection program across Unit 3 "
            "and signs the majority of pressure vessel inspection records."
        ),
    },
    {
        "id": "EMP-011",
        "name": "L. Pillai",
        "role": "Safety Officer",
        "unit": "Unit 3",
        "tenure_start": "2018-07-09",
        "tenure_end": None,
        "status": "active",
        "specialization": "Permit-to-work, near-miss investigation",
        "bio": (
            "L. Pillai reviews near-miss cards and permit-to-work compliance "
            "across the unit."
        ),
    },
    {
        "id": "EMP-012",
        "name": "N. Joshi",
        "role": "Shift Operations Engineer",
        "unit": "Unit 3",
        "tenure_start": "2020-01-20",
        "tenure_end": None,
        "status": "active",
        "specialization": "Startup/shutdown sequencing, shift handover",
        "bio": (
            "N. Joshi covers shift operations and handover documentation "
            "across CDU, VDU, and DCU."
        ),
    },
]


def render(p: dict) -> str:
    lines = [
        "---",
        f"record_type: personnel",
        f"person_id: {p['id']}",
        f"name: {p['name']}",
        f"role: {p['role']}",
        f"unit: {p['unit']}",
        f"tenure_start: {p['tenure_start']}",
        f"tenure_end: {p['tenure_end']}",
        f"status: {p['status']}",
        "---",
        "",
        f"# Personnel Record — {p['name']}",
        "",
        f"**Role:** {p['role']}  ",
        f"**Unit:** {p['unit']}  ",
        f"**Tenure:** {p['tenure_start']} to {p['tenure_end'] or 'present'}  ",
        f"**Specialization:** {p['specialization']}",
        "",
        p["bio"],
        "",
    ]
    return "\n".join(lines)


def main():
    for p in PERSONNEL:
        fname = OUT_DIR / f"{p['id']}_{p['name'].replace('. ', '').replace(' ', '_')}.md"
        fname.write_text(render(p))
    (OUT_DIR / "personnel.json").write_text(json.dumps(PERSONNEL, indent=2))
    print(f"Wrote {len(PERSONNEL)} personnel records to {OUT_DIR}")


if __name__ == "__main__":
    main()
