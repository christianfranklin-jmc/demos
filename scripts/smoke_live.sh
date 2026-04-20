#!/usr/bin/env bash
# Live smoke test — POST /workflow/step against the local FastAPI backend
# using the real RDS Northwinds credentials from .env.
#
# Assumes:
#   * .env has been sourced (DB_HOST / DB_PORT / DB_NAME / DB_USER / DB_PASSWORD)
#   * uvicorn is serving on :8080
#
# Usage:
#   source .env
#   uv run uvicorn platform_agent.api.app:app --port 8080 &
#   ./scripts/smoke_live.sh

set -euo pipefail

: "${DB_HOST:?Need DB_HOST — source .env first}"
: "${DB_PORT:=5432}"
: "${DB_NAME:?Need DB_NAME}"
: "${DB_USER:?Need DB_USER}"
: "${DB_PASSWORD:?Need DB_PASSWORD}"

SID="11111111-2222-3333-4444-555555555555"
BACKEND="${BACKEND_URL:-http://localhost:8080}"

echo "=== /health ==="
curl -s "$BACKEND/health" && echo

echo
echo "=== POST /workflow/step — Step 1 (Requirements) against Northwinds ==="
curl -N -s -X POST "$BACKEND/workflow/step" \
  -H "Content-Type: application/json" \
  -H "Accept: text/event-stream" \
  -H "X-DSA-Session-ID: $SID" \
  -d "$(cat <<JSON
{
  "step_id": "requirements",
  "user_message": "Help me understand our order data.",
  "prior_artifact": null,
  "connection": {
    "driver_type": "postgresql",
    "host": "$DB_HOST",
    "port": $DB_PORT,
    "database": "$DB_NAME",
    "schema": "public",
    "user": "$DB_USER",
    "credential": {"kind": "password", "password": "$DB_PASSWORD"}
  },
  "resume": false
}
JSON
)"

echo
echo "=== done ==="
