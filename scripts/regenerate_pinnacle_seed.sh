#!/usr/bin/env bash
# regenerate_pinnacle_seed.sh — capture the live Pinnacle DB into seed_pinnacle.sql.
#
# Pinnacle's per-process schema (ap/billing/crm/gl/hr/performance/planning/
# portfolio) and row volumes (FR-042: 336 invoices / $5.6M AP, 1,680 fee
# invoices / $10.7M, 6,300 daily AUM snapshots, …) live in the AWS-hosted
# RDS instance. This script pg_dumps that DB into a portable INSERT-format
# seed file so a teardown/rebuild can bootstrap from scratch.
#
# Usage:
#   scripts/regenerate_pinnacle_seed.sh           # dumps to scripts/seed_pinnacle.sql
#   scripts/regenerate_pinnacle_seed.sh --output /tmp/seed.sql
#
# Reads connection from .env (DB_HOST/DB_PORT/DB_NAME/DB_USER/DB_PASSWORD).
# Output uses --inserts so the file is portable across pg versions and
# replays cleanly under psql -f.

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
OUTPUT="$PROJECT_DIR/scripts/seed_pinnacle.sql"

while [[ $# -gt 0 ]]; do
    case $1 in
        --output) OUTPUT="$2"; shift 2 ;;
        --help|-h)
            grep -E '^# ' "$0" | sed 's/^# //'
            exit 0 ;;
        *) echo "Unknown arg: $1" >&2; exit 1 ;;
    esac
done

# Load .env if present (read-only — never write secrets to disk via this script).
if [[ -f "$PROJECT_DIR/.env" ]]; then
    set -o allexport
    # shellcheck disable=SC1091
    source "$PROJECT_DIR/.env"
    set +o allexport
fi

: "${DB_HOST:?DB_HOST not set; check .env}"
: "${DB_PORT:=5432}"
: "${DB_NAME:?DB_NAME not set; check .env}"
: "${DB_USER:?DB_USER not set; check .env}"
: "${DB_PASSWORD:?DB_PASSWORD not set; check .env}"

echo "Dumping pinnacle from $DB_HOST → $OUTPUT ..."

PG_DUMP_ARGS=(
    -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME"
    --no-owner --no-privileges --inserts --column-inserts
    --schema=ap --schema=billing --schema=crm --schema=gl
    --schema=hr --schema=performance --schema=planning --schema=portfolio
)

# RDS is on PG 16; if local pg_dump is older, fall back to a versioned
# Docker image so the dump succeeds anyway.
LOCAL_PG_DUMP_MAJOR=0
if command -v pg_dump >/dev/null 2>&1; then
    LOCAL_PG_DUMP_MAJOR=$(pg_dump --version | awk '{print $3}' | cut -d. -f1)
fi

if [[ "$LOCAL_PG_DUMP_MAJOR" -ge 16 ]]; then
    PGSSLMODE=require PGPASSWORD="$DB_PASSWORD" pg_dump "${PG_DUMP_ARGS[@]}" > "$OUTPUT"
elif command -v docker >/dev/null 2>&1; then
    echo "Local pg_dump is v$LOCAL_PG_DUMP_MAJOR (need ≥16); using docker postgres:16."
    docker run --rm \
        -e PGPASSWORD="$DB_PASSWORD" -e PGSSLMODE=require \
        postgres:16 \
        pg_dump "${PG_DUMP_ARGS[@]}" > "$OUTPUT"
else
    echo "ERROR: pg_dump v$LOCAL_PG_DUMP_MAJOR is too old for the PG 16 server" >&2
    echo "       and docker is not installed for the postgres:16 fallback." >&2
    echo "       Install PostgreSQL 16 client tools (e.g., 'brew install postgresql@16')" >&2
    echo "       or Docker, then re-run." >&2
    exit 1
fi

ROWS=$(grep -c '^INSERT INTO' "$OUTPUT" || true)
SIZE=$(du -h "$OUTPUT" | awk '{print $1}')
echo "Wrote $OUTPUT ($SIZE, $ROWS INSERT statements)."
echo "Replay with: psql -h \$DB_HOST -U \$DB_USER -d \$DB_NAME -f $OUTPUT"
