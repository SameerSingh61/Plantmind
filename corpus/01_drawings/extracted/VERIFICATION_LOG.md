# P&ID Vision Extraction — Verification Log

Real extraction run: `scripts/extract_pid_vision.py` against `gpt-4o` (vision),
against the rendered images in `corpus/01_drawings/images/`. Raw,
unverified model output is preserved in this directory as
`{drawing_id}-raw.json`. This log records what a human verification pass
found wrong before the corrected output was allowed to become the actual
corpus file (`corpus/01_drawings/{drawing_id}.json`).

## PID-DCU-001 (6 tags)

- **Tag misread:** model read the fired-heater triangle's label as
  `H-201`; the drawing actually reads `H-301`. All 6 symbols were
  otherwise correctly located.
- **Connection misattribution near the crossing:** the drawing has two
  lines (`12"-CV-4020` from V-2302→V-2301, and `12"-CV-4021` from
  V-2303→V-2301) that visually cross close to V-2301. The model
  attributed both to `H-201`(sic)`→V-2301` and `H-201→C-301` instead —
  it noticed the ambiguity itself (`low_confidence_notes` flagged the
  overlap) but resolved it incorrectly. Corrected to the two vessels
  each feeding V-2301 directly, matching the drawn arrowheads.

## PID-CDU-001 (15 tags)

- **All 15 equipment tags correctly identified** — no tag errors here.
- **Connection direction reversed** on two lines: extraction said
  `E-201→P-102A` (`4"-CR-1020`) and `E-201→P-102B` (`4"-CR-1021`); the
  arrowheads in the drawing point the other way, `P-102A→E-201` and
  `P-102B→E-201`. Corrected.
- **Wrong endpoint:** extraction said `D-101→E-201` carries
  `4"-CR-1010`; that line actually runs `D-101→P-102A`. Corrected, and
  added the missing parallel line `D-101→P-102B` (`4"-CR-1011`), which
  the extraction dropped entirely.
- **All 7 cross-sheet stub arrows missed as connections** — the model's
  `cross_sheet_references` correctly noted `PID-CDU-002` exists as a
  referenced sheet, but none of the 7 individual stub arrows (E-203's
  continuation, and the 6 pump-suction stubs for P-103A/B, P-104A/B,
  P-105A/B, P-106 coming from `C-101` on the other sheet) were captured
  as connections. Added all 7 back from visual inspection.

## PID-CDU-002 (19 tags — the busiest sheet)

- **Missed 3 of 19 equipment symbols entirely: `H-101`, `C-101`,
  `C-201`.** This is the most cluttered drawing (many lines converge on
  the two columns), and it shows: the model's own
  `low_confidence_notes` flagged the area "around E-209" as unclear, but
  the actual miss was worse — it dropped both column nodes and one
  furnace triangle rather than mis-locating them. Every connection that
  should route through C-101 or C-201 (the atmospheric column pumparounds,
  the vacuum column feed/draws) was consequently also missing or
  misattributed to adjacent equipment (e.g. `E-204→E-206` instead of the
  real chain `E-204→E-205→E-206`, skipping a node).
- Rebuilt the full connection list for this sheet from visual inspection
  rather than patching the extraction line-by-line — the miss rate here
  was too high to trust partial correction.

## Takeaway

Tag identification was strong on the two sparser sheets (15/15 and 6/6,
modulo one single-character misread) and noticeably worse on the busiest
one (16/19). Connection direction and attribution near crossing lines was
the single biggest error source across all three sheets — consistent
with what a real P&ID audit would flag: dense sheets need either higher
resolution, a cleaner as-built drawing, or a second extraction pass
before the output is trusted, exactly the caveat the original scope note
carried.
