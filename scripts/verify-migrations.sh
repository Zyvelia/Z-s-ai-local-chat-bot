#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
: "${PGHOST:=localhost}" "${PGPORT:=5432}" "${PGUSER:=character}" "${PGDATABASE:=character_chat}"
: "${TEST_DATABASE_URL:=postgresql+asyncpg://${PGUSER}:${PGPASSWORD:?Set PGPASSWORD}@${PGHOST}:${PGPORT}/${PGDATABASE}}"
export TEST_DATABASE_URL DATABASE_URL="$TEST_DATABASE_URL"
python backend/scripts/migrate.py
python backend/scripts/migrate.py --verify-only
# Rerunning is intentionally supported; no migration should execute twice.
python backend/scripts/migrate.py
(cd backend && python -m pytest -q tests/test_postgres_migrations.py tests/test_api_integration.py)
