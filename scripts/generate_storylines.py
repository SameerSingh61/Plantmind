#!/usr/bin/env python3
"""Hand-authored documents for the three planted storylines plus the tag-variant
and empty-tag-field messiness that rides along with them.

These are the documents the demo depends on, so they are written by hand
(not templated) — same discipline the prompt asks of a real team.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INC = ROOT / "corpus" / "04_incidents"
NM = ROOT / "corpus" / "05_near_misses"
WO = ROOT / "corpus" / "03_work_orders"
PROC = ROOT / "corpus" / "02_procedures"
for d in (INC, NM, WO, PROC):
    d.mkdir(parents=True, exist_ok=True)


def write(path: Path, text: str):
    path.write_text(text.strip() + "\n")


# ---------------------------------------------------------------------------
# STORYLINE 1 — the unclosed loop: P-101A
# ---------------------------------------------------------------------------

write(INC / "INC-2019-04.md", """
---
record_type: incident
incident_id: INC-2019-04
classification: incident
date: 2019-08-03
unit: CDU
equipment_tags: [P-101A]
failure_mode: mechanical_seal_failure
regulatory_reportable: false
filed_by: EMP-003
recommendations:
  - text: "Introduce a pre-startup seal flush verification step for monsoon-season startups on crude charge pumps"
    owner: "S. Iyer"
    owner_role: "Maintenance Head"
    target_date: "2019-12-31"
    recommended_procedure_id: "REC-INC-2019-04-1"
    source_page: 4
source_page_count: 5
---

# Incident Report INC-2019-04

**Date/Time:** 2019-08-03, 05:40 hrs
**Unit:** CDU
**Equipment Involved:** P-101A (Crude charge pump A)
**Classification:** Mechanical failure, no injury, no reportable release

## Description (p.1)

During restart of P-101A following a scheduled monsoon-season power dip, the
mechanical seal failed approximately four minutes after startup, releasing a
small quantity of crude to the pump pedestal drip tray. The standby pump
(P-101B) was started per procedure and the unit continued without a trip.

## Immediate Cause (p.2)

Seal face damage consistent with running dry for a short interval during
startup. Flush line to the seal pot had not been verified open prior to
starting the pump.

## Root Cause (p.3)

SOP-33 (Crude Pump Startup Procedure) does not include a step to verify the
seal flush line is open and flowing before the pump is brought up to speed.
This step exists informally in some operators' practice but is not written
down anywhere. Monsoon-season startups follow an unplanned power-dip restart
sequence more often than dry-season ones, which increases how often this gap
is actually exercised.

## Contributing Factors (p.4)

- No written verification step for seal flush prior to startup
- Restart occurred during a shift changeover window
- Monsoon season increases frequency of unplanned restarts on this pump

## Recommendations (p.4)

| # | Recommendation | Owner | Target Date |
|---|---|---|---|
| 1 | Introduce a pre-startup seal flush verification step for monsoon-season startups on crude charge pumps | S. Iyer, Maintenance Head | 2019-12-31 |

## Sign-off (p.5)

Filed by: S. Iyer, Maintenance Head
""")

# Stub procedure node representing the recommendation above. It is never
# incorporated into SOP-33 or any other current procedure, so it carries
# no GOVERNS edge to P-101A. That absence — not a flag field — is what the
# unclosed_recommendation rule detects.
write(PROC / "REC-INC-2019-04-1.md", """
---
record_type: procedure
procedure_id: REC-INC-2019-04-1
title: "Proposed: Pre-startup seal flush verification for monsoon-season crude pump startups"
status: proposed
equipment_tags: []
revision: null
revision_date: null
satisfies_clauses: []
governs_equipment: []
source_page: 1
---

# Proposed Procedure (never incorporated)

Drafted following INC-2019-04 as a recommended addition to crude pump startup
practice. This document was never merged into SOP-33 or issued as a
standalone procedure. It carries no current governing relationship to any
equipment.
""")

write(NM / "NM-2022-11.md", """
---
record_type: incident
incident_id: NM-2022-11
classification: near_miss
date: 2022-07-19
unit: CDU
equipment_tags: [P101A]
failure_mode: mechanical_seal_failure
regulatory_reportable: false
filed_by: EMP-012
recommendations: []
source_page_count: 1
---

# Near-Miss Card NM-2022-11

**Date:** 2022-07-19
**Equipment:** P101A
**Reported by:** N. Joshi, Shift Operations Engineer

## What happened (p.1)

Operator noted seal weeping and unusual vibration on P101A within the first
five minutes of a monsoon restart following a grid trip. Pump was tripped
and swapped to standby before any release occurred. No injury, no product
loss beyond drip tray. Startup sequence followed current SOP-33; no seal
flush verification step exists in that procedure.
""")

write(NM / "NM-2024-07.md", """
---
record_type: incident
incident_id: NM-2024-07
classification: near_miss
date: 2024-08-02
unit: CDU
equipment_tags: [P-101A]
failure_mode: mechanical_seal_failure
regulatory_reportable: false
filed_by: EMP-012
recommendations: []
source_page_count: 1
---

# Near-Miss Card NM-2024-07

**Date:** 2024-08-02
**Equipment:** P-101A
**Reported by:** N. Joshi, Shift Operations Engineer

## What happened (p.1)

Second occurrence of seal weeping on P-101A during a monsoon-season restart
after an unplanned power dip, same signature as NM-2022-11 and the 2019
incident on this pump. Standby pump swap performed without incident.
Startup sequence followed current SOP-33, which still has no seal flush
verification step for restart conditions.
""")

# The demo trigger: a new work order opening on P-101A in July 2026.
write(WO / "WO-2026-4471.md", """
---
record_type: work_order
wo_id: WO-2026-4471
equipment_tags: [P-101A]
raised_date: 2026-07-19
work_type: corrective_maintenance
priority: high
permit_type: hot_work
assigned_to: EMP-002
planned_hours: 6
actual_hours: null
completion_notes: null
status: open
source_page: 1
---

# Work Order WO-2026-4471

**Equipment:** P-101A (Crude charge pump A)
**Raised:** 2026-07-19
**Work Type:** Corrective maintenance
**Priority:** High
**Permit Required:** Hot work
**Assigned To:** A. Verma

## Description

Crude charge pump A reported for seal inspection ahead of scheduled
monsoon-season restart. Work order opened, not yet closed.
""")

# Filler WO on the same pump carrying the third tag-variant spelling.
write(WO / "WO-2023-52.md", """
---
record_type: work_order
wo_id: WO-2023-52
equipment_tags: ["P-101 A"]
raised_date: 2023-03-11
work_type: preventive_maintenance
priority: medium
permit_type: none
assigned_to: EMP-008
planned_hours: 3
actual_hours: 3
completion_notes: "Routine PM, bearing grease topped up, no abnormalities found."
status: closed
source_page: 1
---

# Work Order WO-2023-52

**Equipment:** P-101 A
**Raised:** 2023-03-11
**Work Type:** Preventive maintenance
**Assigned To:** T. Singh

## Notes

Routine PM, bearing grease topped up, no abnormalities found.
""")

print("Storyline 1 documents written.")

# ---------------------------------------------------------------------------
# STORYLINE 2 — the cross-equipment pattern: E-204, E-206, E-211
# ---------------------------------------------------------------------------

write(INC / "INC-2020-09.md", """
---
record_type: incident
incident_id: INC-2020-09
classification: incident
date: 2020-11-02
unit: CDU
equipment_tags: [E-204]
failure_mode: tube_sheet_fouling
regulatory_reportable: false
filed_by: EMP-004
recommendations:
  - text: "Increase E-204 tube-side cleaning frequency to quarterly during high-TAN blend runs"
    owner: "P. Nair"
    owner_role: "Process Engineer"
    target_date: "2021-01-31"
    recommended_procedure_id: "SOP-08"
    source_page: 3
source_page_count: 3
---

# Incident Report INC-2020-09

**Date:** 2020-11-02
**Unit:** CDU
**Equipment Involved:** E-204 (Crude/naphtha preheat exchanger)

## Description (p.1)

Preheat train outlet temperature dropped 6°C below design over three weeks,
traced to tube-side fouling in E-204.

## Root Cause (p.2)

Tube sheet fouling attributed to processing a high-TAN North Sea substitute
crude blend ("Blend B") for an extended run. Deposit composition consistent
with organic acid fouling under these crude conditions.

## Recommendations (p.3)

| # | Recommendation | Owner | Target Date |
|---|---|---|---|
| 1 | Increase E-204 tube-side cleaning frequency to quarterly during Blend B runs | P. Nair | 2021-01-31 |

Recommendation incorporated into SOP-08 (Exchanger Cleaning and Fouling
Management), Rev 3, issued 2021-01-20.

Filed by: P. Nair, Process Engineer
""")

write(INC / "INC-2021-20.md", """
---
record_type: incident
incident_id: INC-2021-20
classification: incident
date: 2021-09-14
unit: CDU
equipment_tags: [E-206]
failure_mode: tube_sheet_fouling
regulatory_reportable: false
filed_by: EMP-005
recommendations:
  - text: "Add Blend B fouling check to E-206 quarterly inspection scope"
    owner: "M. Reddy"
    owner_role: "Process Engineer"
    target_date: "2021-12-15"
    recommended_procedure_id: "SOP-08"
    source_page: 3
source_page_count: 3
---

# Incident Report INC-2021-20

**Date:** 2021-09-14
**Unit:** CDU
**Equipment Involved:** E-206 (Crude/vacuum residue preheat exchanger)

## Description (p.1)

Differential pressure across E-206 rose steadily over a six-week Blend B
processing campaign, indicating tube-side fouling.

## Root Cause (p.2)

Deposit sampling confirmed organic acid fouling consistent with Blend B
crude, the same mechanism suspected in prior preheat-train exchanger
performance issues.

## Recommendations (p.3)

| # | Recommendation | Owner | Target Date |
|---|---|---|---|
| 1 | Add Blend B fouling check to E-206 quarterly inspection scope | M. Reddy | 2021-12-15 |

Recommendation incorporated into SOP-08, Rev 3.

Filed by: M. Reddy, Process Engineer
""")

# Deliberate messiness: equipment tag appears only in body text, never in a
# structured field. Ingestion must fall back to a body-text scan for this one.
write(INC / "INC-2022-16.md", """
---
record_type: incident
incident_id: INC-2022-16
classification: incident
date: 2022-12-05
unit: CDU
equipment_tags: []
failure_mode: tube_sheet_fouling
regulatory_reportable: false
filed_by: EMP-004
recommendations:
  - text: "Repeat quarterly cleaning cadence established in 2020 for this exchanger"
    owner: "P. Nair"
    owner_role: "Process Engineer"
    target_date: "2023-02-28"
    recommended_procedure_id: "SOP-08"
    source_page: 3
source_page_count: 3
---

# Incident Report INC-2022-16

**Date:** 2022-12-05
**Unit:** CDU

## Description (p.1)

Recurrence of the fouling pattern first seen in 2020 on this same exchanger.
Preheat outlet temperature on the naphtha side of the train dropped again
during a second extended Blend B campaign. The affected unit is E-204, the
same exchanger flagged in INC-2020-09; deposit sampling confirms the same
tube-side organic acid fouling mechanism.

## Root Cause (p.2)

Quarterly cleaning cadence from SOP-08 Rev 3 lapsed during a maintenance
resourcing shortfall; E-204 went eight months without a tube-side clean
during a period that included another Blend B run.

## Recommendations (p.3)

| # | Recommendation | Owner | Target Date |
|---|---|---|---|
| 1 | Repeat quarterly cleaning cadence established in 2020 for this exchanger | P. Nair | 2023-02-28 |

Filed by: P. Nair, Process Engineer
""")

write(INC / "INC-2023-08.md", """
---
record_type: incident
incident_id: INC-2023-08
classification: incident
date: 2023-06-21
unit: CDU
equipment_tags: [E-211]
failure_mode: tube_sheet_fouling
regulatory_reportable: false
filed_by: EMP-006
recommendations:
  - text: "Extend Blend B fouling monitoring to gas oil pumparound circuit exchangers"
    owner: "K. Rao"
    owner_role: "Process Engineer"
    target_date: "2023-09-30"
    recommended_procedure_id: "SOP-08"
    source_page: 3
source_page_count: 3
---

# Incident Report INC-2023-08

**Date:** 2023-06-21
**Unit:** CDU
**Equipment Involved:** E-211 (Gas oil pumparound exchanger)

## Description (p.1)

Gas oil pumparound circuit showed reduced heat recovery over a four-week
window coinciding with a Blend B processing campaign.

## Root Cause (p.2)

Tube-side fouling confirmed by inspection, deposit composition consistent
with the organic acid fouling mechanism seen on E-204 (2020, 2022) and
E-206 (2021), though this RCA was filed independently without cross-
reference to those reports.

## Recommendations (p.3)

| # | Recommendation | Owner | Target Date |
|---|---|---|---|
| 1 | Extend Blend B fouling monitoring to gas oil pumparound circuit exchangers | K. Rao | 2023-09-30 |

Recommendation incorporated into SOP-08, Rev 4.

Filed by: K. Rao, Process Engineer
""")

write(INC / "INC-2024-19.md", """
---
record_type: incident
incident_id: INC-2024-19
classification: incident
date: 2024-10-08
unit: CDU
equipment_tags: [E-211]
failure_mode: tube_sheet_fouling
regulatory_reportable: false
filed_by: EMP-007
recommendations:
  - text: "Review whether SOP-08 fouling cadence should be blend-triggered rather than calendar-triggered"
    owner: "J. Fernandes"
    owner_role: "Process Engineer"
    target_date: "2025-01-15"
    recommended_procedure_id: "SOP-08"
    source_page: 3
source_page_count: 3
---

# Incident Report INC-2024-19

**Date:** 2024-10-08
**Unit:** CDU
**Equipment Involved:** E-211 (Gas oil pumparound exchanger)

## Description (p.1)

Second fouling event on E-211 in fifteen months, again coinciding with a
Blend B campaign, despite the SOP-08 Rev 4 monitoring added after
INC-2023-08.

## Root Cause (p.2)

Calendar-based quarterly cleaning cadence in SOP-08 does not align with
actual Blend B campaign scheduling, which is set by crude procurement, not
by the maintenance calendar. This is the fifth fouling event of this type
across three different preheat-train exchangers since 2020, though no prior
RCA on this failure mode references any of the others.

## Recommendations (p.3)

| # | Recommendation | Owner | Target Date |
|---|---|---|---|
| 1 | Review whether SOP-08 fouling cadence should be blend-triggered rather than calendar-triggered | J. Fernandes | 2025-01-15 |

Filed by: J. Fernandes, Process Engineer
""")

print("Storyline 2 documents written.")

# ---------------------------------------------------------------------------
# STORYLINE 3 — the knowledge cliff: V-2301, R. Krishnan
# ---------------------------------------------------------------------------
# 14 work orders, 2013-2026. 12 signed by EMP-001 (R. Krishnan), 2 by
# EMP-009 (V. Menon). No Procedure node GOVERNS V-2301 at all — every
# documented fact about this vessel lives in these completion notes.

V2301_WOS = [
    dict(wo_id="WO-2013-05", date="2013-04-18", assignee="EMP-009",
         work_type="preventive_maintenance", priority="medium",
         permit="confined_space", planned=4, actual=5,
         notes="Post-commissioning inspection PM. Level bridle isolation "
               "valves stiff to operate, noted for follow-up."),
    dict(wo_id="WO-2014-19", date="2014-08-02", assignee="EMP-001",
         work_type="corrective_maintenance", priority="medium",
         permit="confined_space", planned=3, actual=6,
         notes="Level indication reading erratic during high-level trip "
               "test. Found bridle partially blocked with wax deposit, "
               "typical for this vessel in warmer months. Cleared manually."),
    dict(wo_id="WO-2015-22", date="2015-05-27", assignee="EMP-001",
         work_type="preventive_maintenance", priority="low",
         permit="confined_space", planned=4, actual=4,
         notes="Routine PM, nothing unusual."),
    dict(wo_id="WO-2016-31", date="2016-09-09", assignee="EMP-009",
         work_type="corrective_maintenance", priority="medium",
         permit="confined_space", planned=3, actual=7,
         notes="Same bridle wax blockage as WO-2014-19. Used the usual "
               "steam-trace warm-up on the bridle before attempting to "
               "clear it this time, worked faster than forcing it cold."),
    dict(wo_id="WO-2017-08", date="2017-03-14", assignee="EMP-001",
         work_type="inspection", priority="low",
         permit="confined_space", planned=2, actual=2,
         notes="Statutory internal inspection support, no findings."),
    dict(wo_id="WO-2018-27", date="2018-07-22", assignee="EMP-001",
         work_type="corrective_maintenance", priority="high",
         permit="confined_space", planned=4, actual=9,
         notes="High-level trip nuisance-tripped twice in one week. Root "
               "cause traced to the same bridle fouling behaviour as prior "
               "years. Applied the steam-trace warm-up before isolation "
               "this time, holds cleaner for longer than a cold clear-out."),
    dict(wo_id="WO-2019-33", date="2019-06-14", assignee="EMP-001",
         work_type="corrective_maintenance", priority="medium",
         permit="confined_space", planned=3, actual=5,
         notes="Level bridle reading drift again. Used the usual "
               "workaround on the level bridle - warm it with the steam "
               "trace for 20 minutes before isolating, then clear by hand. "
               "Cold clear-outs take three times as long and risk cracking "
               "the gauge glass."),
    dict(wo_id="WO-2020-14", date="2020-02-11", assignee="EMP-001",
         work_type="preventive_maintenance", priority="low",
         permit="confined_space", planned=4, actual=4,
         notes="Routine PM. Steam trace warm-up on bridle done "
               "preemptively before isolation this cycle, no fouling found "
               "on opening."),
    dict(wo_id="WO-2021-36", date="2021-10-03", assignee="EMP-001",
         work_type="corrective_maintenance", priority="medium",
         permit="confined_space", planned=3, actual=6,
         notes="Bridle fouling again, same pattern as every prior year on "
               "this vessel. Steam-trace warm-up method used, cleared in "
               "20 minutes."),
    dict(wo_id="WO-2022-09", date="2022-01-29", assignee="EMP-001",
         work_type="inspection", priority="low",
         permit="confined_space", planned=2, actual=2,
         notes="Statutory inspection support, no findings."),
    dict(wo_id="WO-2023-25", date="2023-08-17", assignee="EMP-009",
         work_type="corrective_maintenance", priority="medium",
         permit="confined_space", planned=3, actual=7,
         notes="Bridle blockage, V. Menon covering while R. Krishnan on "
               "leave. Had to call R. Krishnan for the steam-trace warm-up "
               "trick, not written down anywhere on file."),
    dict(wo_id="WO-2024-11", date="2024-04-05", assignee="EMP-001",
         work_type="corrective_maintenance", priority="medium",
         permit="confined_space", planned=3, actual=5,
         notes="Bridle fouling, usual steam-trace warm-up method, cleared "
               "without issue."),
    dict(wo_id="WO-2025-30", date="2025-11-19", assignee="EMP-001",
         work_type="preventive_maintenance", priority="low",
         permit="confined_space", planned=4, actual=4,
         notes="Routine PM, bridle warmed preemptively per usual practice, "
               "no fouling found."),
    dict(wo_id="WO-2026-02", date="2026-01-14", assignee="EMP-001",
         work_type="corrective_maintenance", priority="medium",
         permit="confined_space", planned=3, actual=5,
         notes="Bridle fouling again, cleared with the standard steam-"
               "trace warm-up. Worth writing this down properly before I "
               "retire in August - nobody else has done this on their own "
               "yet."),
]

for wo in V2301_WOS:
    write(WO / f"{wo['wo_id']}.md", f"""
---
record_type: work_order
wo_id: {wo['wo_id']}
equipment_tags: [V-2301]
raised_date: {wo['date']}
work_type: {wo['work_type']}
priority: {wo['priority']}
permit_type: {wo['permit']}
assigned_to: {wo['assignee']}
planned_hours: {wo['planned']}
actual_hours: {wo['actual']}
completion_notes: "{wo['notes']}"
status: closed
source_page: 1
---

# Work Order {wo['wo_id']}

**Equipment:** V-2301 (Coker knockout drum)
**Raised:** {wo['date']}
**Work Type:** {wo['work_type'].replace('_', ' ').title()}

## Completion Notes

{wo['notes']}
""")

print(f"Storyline 3: {len(V2301_WOS)} work orders written for V-2301.")
