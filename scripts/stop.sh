#!/bin/bash
# Stops the backend and frontend dev servers started by scripts/dev.sh.
lsof -ti:8123 -sTCP:LISTEN | xargs -r kill 2>/dev/null || true
lsof -ti:5173 -sTCP:LISTEN | xargs -r kill 2>/dev/null || true
echo "Stopped (if they were running)."
