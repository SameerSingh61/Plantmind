#!/bin/bash
# Starts the backend (:8123) and frontend (:5173) for local development /
# demo rehearsal. Run `bash scripts/stop.sh` to tear both down.
set -euo pipefail
cd "$(dirname "$0")/.."

if [ ! -f data/graph.pkl ]; then
  echo "data/graph.pkl not found — building it from corpus/ first..."
  python3 graph/build.py
fi

lsof -ti:8123 -sTCP:LISTEN | xargs -r kill 2>/dev/null || true
lsof -ti:5173 -sTCP:LISTEN | xargs -r kill 2>/dev/null || true

echo "Starting backend on :8123..."
(uvicorn backend.main:app --port 8123 > /tmp/plantmind-backend.log 2>&1 &)

for i in $(seq 1 20); do
  curl -sf http://localhost:8123/api/health >/dev/null && break
  sleep 1
done
curl -sf http://localhost:8123/api/health >/dev/null || {
  echo "Backend failed to start — check /tmp/plantmind-backend.log"; exit 1;
}
echo "Backend up."

echo "Starting frontend on :5173..."
(cd frontend && VITE_API_BASE=http://localhost:8123 npm run dev -- --port 5173 > /tmp/plantmind-frontend.log 2>&1 &)

for i in $(seq 1 20); do
  curl -sf http://localhost:5173 >/dev/null && break
  sleep 1
done
curl -sf http://localhost:5173 >/dev/null || {
  echo "Frontend failed to start — check /tmp/plantmind-frontend.log"; exit 1;
}
echo "Frontend up."
echo
echo "PlantMind running: http://localhost:5173 (API: http://localhost:8123)"
echo "Logs: /tmp/plantmind-backend.log, /tmp/plantmind-frontend.log"
echo "Stop with: bash scripts/stop.sh"
