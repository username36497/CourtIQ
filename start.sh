#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
command -v python3 >/dev/null || { echo "Install Python 3.11+ first."; exit 1; }
command -v npm >/dev/null || { echo "Install Node.js 22+ first."; exit 1; }
if [ ! -d .venv ]; then python3 -m venv .venv; fi
.venv/bin/python -m pip install -r backend/requirements.txt
(cd frontend && npm ci && npm run build)
if [ ! -f .env ]; then cp .env.example .env; fi
echo "CourtIQ is starting at http://localhost:8000 — Ctrl+C to stop."
cd backend
exec ../.venv/bin/python -m uvicorn app.main:app --env-file ../.env --host 127.0.0.1 --port 8000
