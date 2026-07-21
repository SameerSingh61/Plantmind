#!/bin/bash
# Regenerates the entire template-generated corpus from scratch.
# Always run this after editing generate_storylines.py or
# generate_bulk_corpus.py — the bulk script's output is seeded-random and
# order-dependent, so a partial re-run can leave orphaned files from a
# previous version alongside the new ones. Wipe first, always.
set -euo pipefail
cd "$(dirname "$0")/.."

rm -rf corpus/02_procedures corpus/03_work_orders corpus/04_incidents \
       corpus/05_near_misses corpus/06_inspections corpus/07_regulatory
mkdir -p corpus/02_procedures corpus/03_work_orders corpus/04_incidents \
         corpus/05_near_misses corpus/06_inspections corpus/07_regulatory

python3 scripts/generate_personnel.py
python3 scripts/generate_storylines.py
python3 scripts/generate_bulk_corpus.py

# P&IDs: finalize_pid_drawings.py writes the actual, already-verified
# corpus JSON (fast, deterministic, free). It does NOT re-render the
# images or re-run vision extraction — those are a separate one-time
# pipeline (draw_pid_images.py -> extract_pid_vision.py, ~real API cost)
# documented in corpus/01_drawings/extracted/VERIFICATION_LOG.md. Only
# re-run that pipeline if the drawing layout itself changes.
python3 scripts/finalize_pid_drawings.py

echo "=== corpus counts ==="
for d in corpus/*/; do echo "$d: $(ls "$d" | wc -l)"; done
