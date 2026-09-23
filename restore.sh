#!/usr/bin/env bash
set -euo pipefail

PROJECT="${COMPOSE_PROJECT_NAME:-barq-assessment}"
DB_USER="${POSTGRES_USER:-barq_app}"
DB_NAME="${POSTGRES_DB:-barq_tasks}"
DB_PASSWORD="${POSTGRES_PASSWORD:-change_me_please}"
INPUT_PATH="${1:-${PWD}/backups/barq_backup.sql}"

source .env 2>/dev/null || true
if [[ -n "${POSTGRES_USER:-}" ]]; then DB_USER="$POSTGRES_USER"; fi
if [[ -n "${POSTGRES_DB:-}" ]]; then DB_NAME="$POSTGRES_DB"; fi
if [[ -n "${POSTGRES_PASSWORD:-}" ]]; then DB_PASSWORD="$POSTGRES_PASSWORD"; fi

if [[ ! -f "$INPUT_PATH" ]]; then
  echo "FAIL: backup file not found: $INPUT_PATH" >&2
  exit 1
fi

docker compose -p "$PROJECT" exec -T postgres env PGPASSWORD="$DB_PASSWORD" psql -U "$DB_USER" -d "$DB_NAME" -v ON_ERROR_STOP=1 < "$INPUT_PATH"
printf 'PASS: PostgreSQL restore completed from %s\n' "$INPUT_PATH"
