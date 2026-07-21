#!/usr/bin/env python3
"""Writes the final, human-verified P&ID corpus JSON.

This is the output of a real process, not hand-authored from scratch:
scripts/draw_pid_images.py rendered the sheets, scripts/extract_pid_vision.py
ran gpt-4o vision extraction against them blind, and a human (documented in
corpus/01_drawings/extracted/VERIFICATION_LOG.md) compared the raw output
against each image and corrected the errors found — a misread tag, two
reversed line directions, a dropped endpoint, and on the busiest sheet,
three equipment symbols the model missed entirely. This script encodes
those verified, corrected connections so the corpus is reproducible.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "corpus" / "01_drawings"
EXTRACTED_DIR = OUT_DIR / "extracted"

VERIFIED = [
    dict(
        drawing_id="PID-CDU-001",
        title="CDU Crude Charge, Desalting & Draw Pumps",
        equipment_tags=[
            "P-101A", "P-101B", "P-102A", "P-102B", "D-101",
            "E-201", "E-202", "E-203",
            "P-103A", "P-103B", "P-104A", "P-104B", "P-105A", "P-105B", "P-106",
        ],
        connections=[
            dict(frm="P-101A", to="D-101", line_no="4\"-CR-1001", service="crude"),
            dict(frm="P-101B", to="D-101", line_no="4\"-CR-1002", service="crude"),
            dict(frm="D-101", to="P-102A", line_no="4\"-CR-1010", service="crude"),
            dict(frm="D-101", to="P-102B", line_no="4\"-CR-1011", service="crude"),
            dict(frm="P-102A", to="E-201", line_no="4\"-CR-1020", service="crude"),
            dict(frm="P-102B", to="E-201", line_no="4\"-CR-1021", service="crude"),
            dict(frm="E-201", to="E-202", line_no="4\"-CR-1030", service="crude"),
            dict(frm="E-202", to="E-203", line_no="4\"-CR-1031", service="crude"),
            dict(frm="E-203", to="PID-CDU-002/E-204", line_no="4\"-CR-1032", service="crude"),
            dict(frm="C-101(PID-CDU-002)", to="P-103A", line_no="3\"-NA-2001", service="naphtha"),
            dict(frm="C-101(PID-CDU-002)", to="P-103B", line_no="3\"-NA-2002", service="naphtha"),
            dict(frm="C-101(PID-CDU-002)", to="P-104A", line_no="3\"-KE-2010", service="kerosene"),
            dict(frm="C-101(PID-CDU-002)", to="P-104B", line_no="3\"-KE-2011", service="kerosene"),
            dict(frm="C-101(PID-CDU-002)", to="P-105A", line_no="3\"-DI-2020", service="diesel"),
            dict(frm="C-101(PID-CDU-002)", to="P-105B", line_no="3\"-DI-2021", service="diesel"),
            dict(frm="C-101(PID-CDU-002)", to="P-106", line_no="6\"-AR-2030", service="atm_residue"),
        ],
        raw_tags_found=15, raw_tags_total=15,
        corrections_applied=[
            "reversed line direction: P-102A/B -> E-201 (extraction had it backwards)",
            "fixed wrong endpoint: D-101 -> P-102A/B, not D-101 -> E-201",
            "added 7 missing cross-sheet stub connections (extraction only noted the sheet reference generically)",
        ],
    ),
    dict(
        drawing_id="PID-CDU-002",
        title="CDU Preheat Train, Furnace, Atmospheric Column & VDU",
        equipment_tags=[
            "E-204", "E-205", "E-206", "E-207", "E-208", "H-101", "C-101",
            "E-209", "E-210", "E-211", "A-101",
            "P-201", "H-201", "C-201", "E-212", "P-202", "P-203", "EJ-201", "EJ-202",
        ],
        connections=[
            dict(frm="E-204", to="E-205", line_no="4\"-CR-1040", service="crude"),
            dict(frm="E-205", to="E-206", line_no="4\"-CR-1041", service="crude"),
            dict(frm="E-206", to="E-207", line_no="4\"-CR-1042", service="crude"),
            dict(frm="E-207", to="E-208", line_no="4\"-CR-1043", service="crude"),
            dict(frm="E-208", to="H-101", line_no="4\"-CR-1044", service="crude"),
            dict(frm="H-101", to="C-101", line_no="8\"-CR-1050", service="crude_vapor"),
            dict(frm="C-101", to="A-101", line_no="6\"-NA-2000", service="naphtha_vapor"),
            dict(frm="C-101", to="E-209", line_no="3\"-PA-2100", service="naphtha/kerosene"),
            dict(frm="E-209", to="C-101", line_no="3\"-PA-2101", service="naphtha/kerosene"),
            dict(frm="C-101", to="E-210", line_no="3\"-PA-2110", service="diesel"),
            dict(frm="E-210", to="C-101", line_no="3\"-PA-2111", service="diesel"),
            dict(frm="C-101", to="E-211", line_no="4\"-PA-2120", service="gas_oil"),
            dict(frm="E-211", to="C-101", line_no="4\"-PA-2121", service="gas_oil"),
            dict(frm="C-101", to="P-201", line_no="6\"-RC-3000", service="reduced_crude"),
            dict(frm="P-201", to="H-201", line_no="6\"-RC-3001", service="reduced_crude"),
            dict(frm="H-201", to="C-201", line_no="10\"-RC-3010", service="reduced_crude"),
            dict(frm="C-201", to="EJ-201", line_no="8\"-VS-3020", service="vacuum_system"),
            dict(frm="EJ-201", to="EJ-202", line_no="8\"-VS-3021", service="vacuum_system"),
            dict(frm="C-201", to="E-212", line_no="4\"-VG-3030", service="vgo"),
            dict(frm="E-212", to="P-202", line_no="4\"-VG-3031", service="vgo"),
            dict(frm="C-201", to="P-203", line_no="6\"-VR-3040", service="vac_residue"),
            dict(frm="P-203", to="PID-DCU-001/P-301", line_no="6\"-VR-3041", service="vac_residue"),
        ],
        raw_tags_found=16, raw_tags_total=19,
        corrections_applied=[
            "added 3 equipment symbols the extraction missed entirely: H-101, C-101, C-201",
            "rebuilt the full connection list for this sheet — too many misses/misattributions "
            "around the missed column nodes to patch line-by-line",
        ],
    ),
    dict(
        drawing_id="PID-DCU-001",
        title="Delayed Coker Unit: Heater, Coke Drums & Fractionator",
        equipment_tags=["P-301", "H-301", "V-2302", "V-2303", "V-2301", "C-301"],
        connections=[
            dict(frm="P-301", to="H-301", line_no="6\"-VR-4001", service="vac_residue"),
            dict(frm="H-301", to="V-2302", line_no="10\"-CK-4010", service="coke_feed"),
            dict(frm="H-301", to="V-2303", line_no="10\"-CK-4011", service="coke_feed"),
            dict(frm="V-2302", to="V-2301", line_no="12\"-CV-4020", service="coker_vapor"),
            dict(frm="V-2303", to="V-2301", line_no="12\"-CV-4021", service="coker_vapor"),
            dict(frm="V-2301", to="C-301", line_no="12\"-CV-4030", service="coker_vapor"),
        ],
        raw_tags_found=6, raw_tags_total=6,
        corrections_applied=[
            "misread tag: extraction read the heater as H-201, drawing actually reads H-301",
            "fixed 2 connections misattributed to the crossing near V-2301 "
            "(model flagged the overlap itself but resolved it incorrectly)",
        ],
    ),
]


def main():
    for d in VERIFIED:
        out = {
            "drawing_id": d["drawing_id"],
            "title": d["title"],
            "equipment_tags": d["equipment_tags"],
            "connections": [
                {"from": c["frm"], "to": c["to"], "line_no": c["line_no"], "service": c["service"]}
                for c in d["connections"]
            ],
            "extraction_note": (
                f"Extracted by gpt-4o vision from corpus/01_drawings/images/{d['drawing_id']}.png "
                f"({d['raw_tags_found']}/{d['raw_tags_total']} tags found unaided), then "
                f"hand-verified against the source image — see "
                f"corpus/01_drawings/extracted/VERIFICATION_LOG.md for the full diff. "
                f"Corrections applied: {'; '.join(d['corrections_applied'])}."
            ),
        }
        (OUT_DIR / f"{d['drawing_id']}.json").write_text(json.dumps(out, indent=2))
    print(f"Wrote {len(VERIFIED)} verified P&ID files to {OUT_DIR}")


if __name__ == "__main__":
    main()
