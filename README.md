# BARQ Assessment Runtime Guide

This project runs a Flask API behind NGINX with two app instances, PostgreSQL, and Redis. The stack is intended to be started with Docker Compose and validated end-to-end via shell checks and Python checks.

## Repository state

- Project name: `barq-assessment`
- Public port: `8080`
- App instances: `app-01`, `app-02`
- Service names: `nginx`, `postgres`, `redis`
- Networks: `barq-assessment_frontend` and `barq-assessment_backend`

## 1. Setup and bootstrap

```bash
cd /path/to/barq-starter
cp .env.example .env
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt

docker compose -p barq-assessment up --build -d
docker compose -p barq-assessment ps -a
docker compose -p barq-assessment logs --no-color
```

The app expects a local `.env` file with the database secret and project settings. The actual runtime password is loaded from `.env`; the Compose stack and app containers then align to it.

## 2. Access and validation

```bash
curl -fsS http://127.0.0.1:8080/
curl -fsS http://127.0.0.1:8080/health
curl -fsS http://127.0.0.1:8080/ready
curl -fsS http://127.0.0.1:8080/instance
curl -fsS http://127.0.0.1:8080/counter
curl -fsS http://127.0.0.1:8080/records
python validate.py
python -m unittest discover -s tests -v
```

Expected behavior:

- `/` returns the app message
- `/health` always returns 200
- `/ready` returns 200 only when PostgreSQL and Redis are both reachable
- `/instance` returns a backend identity
- `/records` allows creating a record and listing rows
- `/counter` increments a Redis-backed count

## 3. Failure test

```bash
python failure_test.py
```

This script stops one backend instance, measures service availability while it is down, restores it, and verifies the recovered instance serves traffic again.

## 4. PostgreSQL backup and restore

```bash
mkdir -p backups
./backup.sh backups/barq_backup.sql
./restore.sh backups/barq_backup.sql
```

This creates a dump from the live PostgreSQL container and replays it into the database. The script is intended for the project-owned Compose stack only and will fail if the backup file is missing or the DB is not healthy.

## 5. Cleanup

```bash
docker compose -p barq-assessment down
```

This stops the stack without forcing a volume removal. During persistence verification, do not use `--volumes` unless you intentionally want to discard stored PostgreSQL data.

## 6. CI

The workflow is in [.github/workflows/ci.yml](.github/workflows/ci.yml). It checks Compose syntax, builds the stack, waits for readiness, runs app tests, and executes the deployment validation before exiting non-zero if any step fails.

```bash
docker compose -p barq-assessment config
python -m unittest discover -s tests -v
python validate.py
```

## 7. Root cause that was fixed

The key runtime issue was a stale PostgreSQL password value in the application environment: the app container reached the database host but the database rejected the login. Once the shared secret was aligned between the Compose environment and the database, the readiness and record endpoints recovered normally.
