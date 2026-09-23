#!/usr/bin/env bash
set -euo pipefail

PROJECT="${COMPOSE_PROJECT_NAME:-barq-assessment}"
DB_USER="${POSTGRES_USER:-barq_app}"
DB_NAME="${POSTGRES_DB:-barq_tasks}"
DB_PASSWORD="${POSTGRES_PASSWORD:-change_me_please}"
OUTPUT_PATH="${1:-${PWD}/backups/barq_backup.sql}"

mkdir -p "$(dirname "$OUTPUT_PATH")"

source .env 2>/dev/null || true
if [[ -n "${POSTGRES_USER:-}" ]]; then DB_USER="$POSTGRES_USER"; fi
if [[ -n "${POSTGRES_DB:-}" ]]; then DB_NAME="$POSTGRES_DB"; fi
if [[ -n "${POSTGRES_PASSWORD:-}" ]]; then DB_PASSWORD="$POSTGRES_PASSWORD"; fi

docker compose -p "$PROJECT" exec -T postgres env PGPASSWORD="$DB_PASSWORD" pg_dump -U "$DB_USER" -d "$DB_NAME" --clean --if-exists --inserts > "$OUTPUT_PATH"

printf 'PASS: PostgreSQL backup created at %s\n' "$OUTPUT_PATH"
