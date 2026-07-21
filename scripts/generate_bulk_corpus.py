#!/usr/bin/env python3
"""Template-generate the bulk of the corpus: remaining work orders, incidents,
near-misses, inspections, procedures, and regulatory extracts.

The storyline-critical documents are hand-authored separately in
generate_storylines.py; this script fills in everything else so the corpus
reaches its target density (60 WOs, 14 incidents, 20 near-misses, 18
inspections, 22 procedures, 6 regulatory docs) without hand-typing each one.

Deterministic: seeded RNG so re-running reproduces the same corpus.
"""
import csv
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CORPUS = ROOT / "corpus"
WO_DIR = CORPUS / "03_work_orders"
INC_DIR = CORPUS / "04_incidents"
NM_DIR = CORPUS / "05_near_misses"
INSP_DIR = CORPUS / "06_inspections"
PROC_DIR = CORPUS / "02_procedures"
REG_DIR = CORPUS / "07_regulatory"
for d in (WO_DIR, INC_DIR, NM_DIR, INSP_DIR, PROC_DIR, REG_DIR):
    d.mkdir(parents=True, exist_ok=True)

random.seed(20260721)

# --- load equipment register -------------------------------------------
EQUIPMENT = []
with open(CORPUS / "00_equipment_register" / "equipment_register.csv") as f:
    for row in csv.DictReader(f):
        EQUIPMENT.append(row)

TAG_BY_TYPE = {}
for e in EQUIPMENT:
    TAG_BY_TYPE.setdefault(e["type"], []).append(e["tag"])

ALL_TAGS = [e["tag"] for e in EQUIPMENT]

# Tags already saturated by storyline documents; bulk generation avoids
# piling more onto these so the planted signal stays clean against noise.
STORYLINE_TAGS = {"P-101A", "V-2301", "E-204", "E-206", "E-211"}
BULK_TAGS = [t for t in ALL_TAGS if t not in STORYLINE_TAGS]

PERSONNEL_IDS = [f"EMP-{i:03d}" for i in range(1, 13)]
TECH_IDS = ["EMP-002", "EMP-008", "EMP-009"]  # maintenance technicians
ENGINEER_IDS = ["EMP-003", "EMP-004", "EMP-005", "EMP-006", "EMP-007", "EMP-012"]
INSPECTOR_ID = "EMP-010"

FAILURE_MODES_BY_TYPE = {
    "centrifugal_pump": ["mechanical_seal_failure", "bearing_failure", "cavitation", "gasket_leak"],
    # tube_sheet_fouling deliberately excluded from the bulk pool: it is
    # reserved for the planted storyline 2 recurrence pattern (E-204/
    # E-206/E-211) and must not appear on any other exchanger by chance.
    "shell_tube_hx": ["tube_leak", "gasket_leak"],
    "pressure_vessel": ["corrosion", "level_transmitter_fouling", "gasket_leak"],
    "coke_drum": ["coke_buildup", "corrosion", "gasket_leak"],
    "distillation_column": ["corrosion", "tray_fouling"],
    "fired_heater": ["refractory_degradation", "tube_leak", "corrosion"],
    "desalter": ["corrosion", "gasket_leak", "instrumentation_drift"],
    "air_cooler": ["tube_leak", "corrosion"],
    "ejector": ["instrumentation_drift", "corrosion"],
    "coker_products": ["corrosion"],
}

WORK_TYPES = ["preventive_maintenance", "corrective_maintenance", "inspection"]
PRIORITIES = ["low", "medium", "high"]
PERMITS = ["none", "hot_work", "confined_space", "cold_work", "electrical_isolation"]

WO_NOTE_TEMPLATES = [
    "Routine {wt} completed, no abnormalities found.",
    "Found minor {fm} indication, corrected during this visit, equipment returned to service.",
    "{wt} performed per schedule. Vibration and temperature readings within normal range.",
    "Deferred one sub-task to next PM cycle due to parts availability; equipment safe to run.",
    "Completed as planned. Recommend monitoring {fm} trend at next inspection.",
    "OK, no issues found.",
    "Done.",
    "Standard {wt}, closed out same shift.",
]

EQUIP_BY_TAG = {e["tag"]: e for e in EQUIPMENT}


def equipment_type(tag: str) -> str:
    return EQUIP_BY_TAG[tag]["type"]


def rand_failure_mode(tag: str) -> str:
    modes = FAILURE_MODES_BY_TYPE.get(equipment_type(tag), ["corrosion"])
    return random.choice(modes)


# ---------------------------------------------------------------------------
# REGULATORY — 6 documents. Representative content inspired by publicly
# known OISD/Factory Act/PESO topic areas, NOT verbatim reproductions of the
# real standards (no network fetch was used to source the actual PDFs).
# Swap in real downloaded standards before an actual submission if exact
# clause text needs to hold up under judge scrutiny.
# ---------------------------------------------------------------------------
REGULATORY_DOCS = [
    dict(doc_id="OISD-105", title="OISD-105: Fire Protection Facilities for Petroleum Refineries and Oil/Gas Processing Plants (representative)",
         clauses=[
             dict(clause_id="OISD-105-4.2", page=12,
                  text="Positive isolation and verification of flush/cooling flow shall be confirmed before startup of rotating equipment handling flammable hydrocarbons."),
             dict(clause_id="OISD-105-6.1", page=18,
                  text="Fixed fire detection shall be provided in areas handling Class A/B petroleum products above defined inventory thresholds."),
         ]),
    dict(doc_id="OISD-106", title="OISD-106: Process Design and Fouling Management for Heat Exchanger Trains (representative)",
         clauses=[
             dict(clause_id="OISD-106-3.4", page=9,
                  text="Heat exchanger cleaning frequency shall be reviewed whenever a change in feedstock is expected to increase fouling rate, rather than fixed solely to a calendar interval."),
         ]),
    dict(doc_id="OISD-118", title="OISD-118: Layouts for Oil and Gas Installations (representative)",
         clauses=[
             dict(clause_id="OISD-118-5.3", page=21,
                  text="Minimum spacing shall be maintained between fired equipment and pressure vessels containing hydrocarbon inventory."),
         ]),
    dict(doc_id="OISD-192", title="OISD-192: Confined Space Entry and Vessel Isolation (representative)",
         clauses=[
             dict(clause_id="OISD-192-2.1", page=4,
                  text="Vessel entry shall not proceed until isolation, purging, and atmosphere testing are independently verified and logged."),
             dict(clause_id="OISD-192-3.6", page=7,
                  text="Level and pressure instrumentation bridles on hydrocarbon-service vessels shall be maintained free of blockage; any recurring fouling behaviour shall be documented in the equipment's governing procedure, not left to informal practice."),
         ]),
    dict(doc_id="OISD-226", title="OISD-226: Delayed Coking Unit Safety Requirements (representative)",
         clauses=[
             dict(clause_id="OISD-226-4.5", page=14,
                  text="Coke drum switching and decoking sequences shall follow a documented, equipment-specific procedure accounting for thermal cycling and coke buildup."),
         ]),
    dict(doc_id="FACTORIES-ACT-EXTRACT", title="Factories Act 1948, Sections relevant to Process Safety Management (representative extract)",
         clauses=[
             dict(clause_id="FA-1948-S7A", page=3,
                  text="The occupier of a factory shall ensure, so far as reasonably practicable, the health and safety of workers, including maintenance of plant and systems of work."),
         ]),
]


def write_regulatory():
    for doc in REGULATORY_DOCS:
        clause_block = "\n".join(
            f"  - clause_id: {c['clause_id']}\n    source_page: {c['page']}\n    text: \"{c['text']}\""
            for c in doc["clauses"]
        )
        body_block = "\n\n".join(
            f"### {c['clause_id']} (p.{c['page']})\n\n{c['text']}" for c in doc["clauses"]
        )
        write(REG_DIR / f"{doc['doc_id']}.md", f"""
---
record_type: regulatory
doc_id: {doc['doc_id']}
title: "{doc['title']}"
clauses:
{clause_block}
---

# {doc['title']}

{body_block}
""")
    print(f"Regulatory documents written: {len(REGULATORY_DOCS)}")


# ---------------------------------------------------------------------------
# PROCEDURES — 22 real SOPs (+1 stub already written by generate_storylines.py,
# +1 superseded revision sitting alongside its current replacement).
# ---------------------------------------------------------------------------
PUMP_TAGS = TAG_BY_TYPE.get("centrifugal_pump", [])
HX_TAGS = TAG_BY_TYPE.get("shell_tube_hx", [])
VESSEL_TAGS = TAG_BY_TYPE.get("pressure_vessel", [])
COKE_DRUM_TAGS = TAG_BY_TYPE.get("coke_drum", [])
COLUMN_TAGS = TAG_BY_TYPE.get("distillation_column", [])

PROCEDURES = [
    dict(pid="SOP-01", title="General Permit to Work Procedure", governs=[],
         rev="Rev 5", rev_date="2020-01-10", satisfies=["FA-1948-S7A"]),
    dict(pid="SOP-02", title="Hot Work Permit Procedure", governs=[],
         rev="Rev 4", rev_date="2019-06-01", satisfies=["OISD-105-6.1"]),
    dict(pid="SOP-03", title="Confined Space Entry - General Requirements", governs=[],
         rev="Rev 3", rev_date="2021-02-15", satisfies=["OISD-192-2.1"]),
    dict(pid="SOP-04", title="Lockout-Tagout Procedure", governs=[],
         rev="Rev 4", rev_date="2020-08-20", satisfies=["FA-1948-S7A"]),
    dict(pid="SOP-05", title="General Unit Startup Sequencing", governs=[],
         rev="Rev 3", rev_date="2018-04-01", satisfies=["OISD-105-4.2"]),
    dict(pid="SOP-06", title="General Unit Shutdown Sequencing", governs=[],
         rev="Rev 3", rev_date="2018-04-01", satisfies=[]),
    dict(pid="SOP-07", title="Desalter Operation Procedure", governs=["D-101"],
         rev="Rev 2", rev_date="2016-09-01", satisfies=["OISD-105-4.2"]),
    dict(pid="SOP-08", title="Exchanger Cleaning and Fouling Management", governs=HX_TAGS,
         rev="Rev 4", rev_date="2023-10-15", satisfies=["OISD-106-3.4"]),
    dict(pid="SOP-09", title="Atmospheric Furnace Operation (H-101)", governs=["H-101"],
         rev="Rev 3", rev_date="2017-05-12", satisfies=["OISD-118-5.3"]),
    dict(pid="SOP-10", title="Vacuum Column and Ejector System Operation", governs=["C-201", "H-201", "EJ-201", "EJ-202", "E-212", "P-201", "P-202", "P-203"],
         rev="Rev 2", rev_date="2015-11-01", satisfies=["OISD-118-5.3"]),
    dict(pid="SOP-11", title="Vacuum Ejector Maintenance Procedure", governs=["EJ-201", "EJ-202"],
         rev="Rev 2", rev_date="2016-03-01", satisfies=[]),
    # Note: V-2301 (the only pressure_vessel-type tag) is deliberately
    # excluded from every governs list below, including this one and
    # SOP-14/SOP-18 despite their titles. That gap is storyline 3 — every
    # documented fact about V-2301 lives in work order notes, not in any
    # current procedure. Do not add VESSEL_TAGS here.
    dict(pid="SOP-12", title="Vessel Confined Space Isolation Procedure", governs=COKE_DRUM_TAGS,
         rev="Rev 3", rev_date="2022-05-01", satisfies=["OISD-192-2.1", "OISD-192-3.6"]),
    dict(pid="SOP-13", title="Coker Charge Heater Operation (H-301)", governs=["H-301"],
         rev="Rev 2", rev_date="2014-02-01", satisfies=["OISD-118-5.3"]),
    dict(pid="SOP-14", title="Coke Drum Switching and Decoking Procedure", governs=COKE_DRUM_TAGS,
         rev="Rev 3", rev_date="2019-09-01", satisfies=["OISD-226-4.5"]),
    dict(pid="SOP-15", title="Coker Main Fractionator Operation", governs=["C-301"],
         rev="Rev 2", rev_date="2014-02-01", satisfies=[]),
    dict(pid="SOP-16", title="Air Cooler Maintenance Procedure", governs=["A-101"],
         rev="Rev 2", rev_date="2015-07-01", satisfies=[]),
    dict(pid="SOP-17", title="Centrifugal Pump Maintenance - General", governs=PUMP_TAGS,
         rev="Rev 4", rev_date="2021-03-01", satisfies=["OISD-105-4.2"]),
    dict(pid="SOP-18", title="Pressure Vessel Inspection Preparation", governs=COKE_DRUM_TAGS,
         rev="Rev 2", rev_date="2017-01-01", satisfies=["OISD-192-2.1"]),
    dict(pid="SOP-19", title="Distillation Column Internals Inspection", governs=COLUMN_TAGS,
         rev="Rev 2", rev_date="2016-06-01", satisfies=[]),
    dict(pid="SOP-20", title="Emergency Shutdown Procedure", governs=[],
         rev="Rev 3", rev_date="2019-01-01", satisfies=[]),
    dict(pid="SOP-21", title="Sample Point Safety Procedure", governs=[],
         rev="Rev 2", rev_date="2018-01-01", satisfies=[]),
    # SOP-33: deliberately last revised in 2015, before INC-2019-04 — this is
    # the gap the unclosed_recommendation rule is built to find.
    dict(pid="SOP-33", title="Crude Pump Startup Procedure", governs=["P-101A", "P-101B", "P-102A", "P-102B"],
         rev="Rev 3", rev_date="2015-03-01", satisfies=["OISD-105-4.2"]),
]

# Messiness: a superseded Rev 2 of SOP-12 still sits in the folder alongside
# the current Rev 3 above. Same procedure_id, status=superseded, so ingestion
# must not create a duplicate or conflicting GOVERNS edge from it.
SOP_12_SUPERSEDED = dict(
    pid="SOP-12", title="Vessel Confined Space Isolation Procedure",
    governs=["V-2301"], rev="Rev 2", rev_date="2018-01-01",
    satisfies=["OISD-192-2.1"],
)


def _procedure_body(p, superseded=False):
    governs_yaml = yaml_list(p["governs"]) if p["governs"] else "[]"
    satisfies_yaml = yaml_list(p["satisfies"]) if p["satisfies"] else "[]"
    status = "superseded" if superseded else "current"
    return f"""
---
record_type: procedure
procedure_id: {p['pid']}
title: "{p['title']}"
status: {status}
revision: "{p['rev']}"
revision_date: {p['rev_date']}
governs_equipment: {governs_yaml}
satisfies_clauses: {satisfies_yaml}
source_page: 1
---

# {p['pid']}: {p['title']}

**Revision:** {p['rev']} ({p['rev_date']})
**Status:** {status.title()}
**Governs:** {', '.join(p['governs']) if p['governs'] else 'General / not equipment-specific'}

## Scope

This procedure covers normal and abnormal operation, maintenance
preparation, and safety requirements for the equipment listed above,
consistent with the regulatory clauses referenced in its front matter.
"""


def write_procedures():
    for p in PROCEDURES:
        write(PROC_DIR / f"{p['pid']}.md", _procedure_body(p))
    # superseded revision, distinct filename, same procedure_id
    write(PROC_DIR / "SOP-12_Rev2_SUPERSEDED.md", _procedure_body(SOP_12_SUPERSEDED, superseded=True))
    print(f"Procedures written: {len(PROCEDURES)} current + 1 superseded")


TYPE_TO_PROC = {
    "centrifugal_pump": "SOP-17",
    "shell_tube_hx": "SOP-08",
    "coke_drum": "SOP-14",
    "pressure_vessel": "SOP-18",
    "distillation_column": "SOP-19",
    "desalter": "SOP-07",
    "air_cooler": "SOP-16",
    "ejector": "SOP-11",
}
FIRED_HEATER_PROC = {"H-101": "SOP-09", "H-201": "SOP-10", "H-301": "SOP-13"}


def proc_id_for_tag(tag: str) -> str:
    if tag in FIRED_HEATER_PROC:
        return FIRED_HEATER_PROC[tag]
    return TYPE_TO_PROC.get(equipment_type(tag), "SOP-01")


def rand_date(year_lo: int, year_hi: int) -> str:
    y = random.randint(year_lo, year_hi)
    m = random.randint(1, 12)
    d = random.randint(1, 28)
    return f"{y:04d}-{m:02d}-{d:02d}"


def yaml_list(items):
    return "[" + ", ".join(items) + "]"


def write(path: Path, text: str):
    path.write_text(text.strip() + "\n")


# ---------------------------------------------------------------------------
# WORK ORDERS — 44 more (16 already exist from storylines, target 60 total)
# ---------------------------------------------------------------------------
N_BULK_WO = 44
wo_counter = {}
empty_note_slots = set(random.sample(range(N_BULK_WO), 2))  # 2 near-empty notes

for i in range(N_BULK_WO):
    tag = random.choice(BULK_TAGS)
    year = random.randint(2019, 2026)
    seq = wo_counter.get(year, 0) + 1
    wo_counter[year] = seq
    wo_id = f"WO-{year}-{seq + 100:02d}"
    wt = random.choice(WORK_TYPES)
    fm = rand_failure_mode(tag)
    assignee = random.choice(TECH_IDS + ["EMP-001"] if equipment_type(tag) != "" else TECH_IDS)
    priority = random.choice(PRIORITIES)
    permit = "confined_space" if equipment_type(tag) in ("pressure_vessel", "coke_drum") else random.choice(PERMITS)
    planned = random.randint(2, 8)
    actual = planned + random.choice([-1, 0, 0, 1, 2, 3])
    actual = max(actual, 1)
    if i in empty_note_slots:
        notes = random.choice(["Done.", "OK, no issues found."])
    else:
        notes = random.choice(WO_NOTE_TEMPLATES).format(wt=wt.replace("_", " "), fm=fm.replace("_", " "))

    write(WO_DIR / f"{wo_id}.md", f"""
---
record_type: work_order
wo_id: {wo_id}
equipment_tags: [{tag}]
raised_date: {rand_date(year, year)}
work_type: {wt}
priority: {priority}
permit_type: {permit}
assigned_to: {assignee}
planned_hours: {planned}
actual_hours: {actual}
completion_notes: "{notes}"
status: closed
source_page: 1
---

# Work Order {wo_id}

**Equipment:** {tag} ({EQUIP_BY_TAG[tag]['name']})
**Raised:** {year}
**Work Type:** {wt.replace('_', ' ').title()}
**Priority:** {priority.title()}

## Completion Notes

{notes}
""")

print(f"Bulk work orders written: {N_BULK_WO}")

# ---------------------------------------------------------------------------
# INCIDENTS — 8 more (6 already exist from storylines, target 14 total)
# ---------------------------------------------------------------------------
N_BULK_INC = 8
inc_counter = {}
for i in range(N_BULK_INC):
    tag = random.choice(BULK_TAGS)
    year = random.randint(2010, 2025)
    seq = inc_counter.get(year, 0) + 1
    inc_counter[year] = seq
    inc_id = f"INC-{year}-{seq + 30:02d}"
    fm = rand_failure_mode(tag)
    filer = random.choice(ENGINEER_IDS)
    owner = random.choice(ENGINEER_IDS + ["EMP-003"])
    proc_id = proc_id_for_tag(tag)

    write(INC_DIR / f"{inc_id}.md", f"""
---
record_type: incident
incident_id: {inc_id}
classification: incident
date: {rand_date(year, year)}
unit: {EQUIP_BY_TAG[tag]['unit']}
equipment_tags: [{tag}]
failure_mode: {fm}
regulatory_reportable: false
filed_by: {filer}
recommendations:
  - text: "Update relevant procedure to address {fm.replace('_', ' ')} on {tag}"
    owner: "{owner}"
    owner_role: "Process Engineer"
    target_date: "{year + 1}-03-31"
    recommended_procedure_id: "{proc_id}"
    source_page: 3
source_page_count: 3
---

# Incident Report {inc_id}

**Date:** {year}
**Unit:** {EQUIP_BY_TAG[tag]['unit']}
**Equipment Involved:** {tag} ({EQUIP_BY_TAG[tag]['name']})

## Description (p.1)

{fm.replace('_', ' ').capitalize()} identified on {tag} during routine
monitoring, addressed without unplanned unit-wide impact.

## Root Cause (p.2)

Consistent with known {fm.replace('_', ' ')} mechanisms for this equipment
class.

## Recommendations (p.3)

| # | Recommendation | Owner | Target Date |
|---|---|---|---|
| 1 | Update relevant procedure to address {fm.replace('_', ' ')} on {tag} | {owner} | {year + 1}-03-31 |

Recommendation incorporated into {proc_id}.

Filed by: Process Engineer
""")

print(f"Bulk incidents written: {N_BULK_INC}")

# ---------------------------------------------------------------------------
# NEAR-MISSES — 18 more (2 already exist from storylines, target 20 total)
# 3 of these are marked as handwritten-scan transcriptions.
# ---------------------------------------------------------------------------
N_BULK_NM = 18
handwritten_slots = set(random.sample(range(N_BULK_NM), 3))
nm_counter = {}
for i in range(N_BULK_NM):
    tag = random.choice(BULK_TAGS)
    year = random.randint(2019, 2026)
    seq = nm_counter.get(year, 0) + 1
    nm_counter[year] = seq
    nm_id = f"NM-{year}-{seq + 40:02d}"
    fm = rand_failure_mode(tag)
    reporter = random.choice(PERSONNEL_IDS)
    is_scan = i in handwritten_slots

    if is_scan:
        body = f"""
## What happened (p.1) [transcribed from handwritten near-miss card, original scan on file]

noticed sm. {fm.replace('_', ' ')} on {tag} during rounds. told shift lead.
no injury. logged for follow up.
"""
        scan_field = "scan_type: handwritten_scan"
    else:
        body = f"""
## What happened (p.1)

Operator observed early signs of {fm.replace('_', ' ')} on {tag} during a
routine walk-down. No injury, no product loss. Logged for maintenance
follow-up.
"""
        scan_field = "scan_type: none"

    write(NM_DIR / f"{nm_id}.md", f"""
---
record_type: incident
incident_id: {nm_id}
classification: near_miss
date: {rand_date(year, year)}
unit: {EQUIP_BY_TAG[tag]['unit']}
equipment_tags: [{tag}]
failure_mode: {fm}
regulatory_reportable: false
filed_by: {reporter}
{scan_field}
recommendations: []
source_page_count: 1
---

# Near-Miss Card {nm_id}
{body}""")

print(f"Bulk near-misses written: {N_BULK_NM} (of which {len(handwritten_slots)} handwritten-scan style)")

# ---------------------------------------------------------------------------
# INSPECTIONS — 18 (not ingested into the graph, flat-file source docs only)
# ---------------------------------------------------------------------------
N_INSP = 18
insp_counter = {}
inspectable_types = ["pressure_vessel", "coke_drum", "distillation_column", "fired_heater"]
inspectable_tags = [t for t in ALL_TAGS if equipment_type(t) in inspectable_types] or ALL_TAGS
for i in range(N_INSP):
    tag = random.choice(inspectable_tags)
    year = random.randint(2011, 2026)
    seq = insp_counter.get(year, 0) + 1
    insp_counter[year] = seq
    insp_id = f"INSP-{year}-{seq:02d}"
    write(INSP_DIR / f"{insp_id}.md", f"""
---
record_type: inspection
inspection_id: {insp_id}
equipment_tags: [{tag}]
date: {rand_date(year, year)}
inspector: {INSPECTOR_ID}
source_page: 1
---

# Inspection Record {insp_id}

**Equipment:** {tag} ({EQUIP_BY_TAG[tag]['name']})
**Date:** {year}
**Inspector:** D. Gupta, Inspection Engineer

## Findings

Wall thickness / corrosion allowance within acceptable limits. No
statutory action required before next inspection cycle.
""")

print(f"Inspections written: {N_INSP}")

write_regulatory()
write_procedures()
