# Troubleshooting journal

## Entry 1 — 2026-09-23 / initial deployment failure

- Symptom: `/ready` returned 503 even though `docker compose ps` showed `postgres` and `redis` as healthy.
- Hypothesis: the app containers are reaching the database host but not authenticating with the right password.
- Command or test:
    ```bash
    docker compose -p barq-assessment ps -a
    curl -fsS http://127.0.0.1:8080/ready
    docker compose -p barq-assessment exec -T app-01 python -c "import os, psycopg; print(os.environ.get('DATABASE_URL')); conn = psycopg.connect(os.environ['DATABASE_URL'], connect_timeout=5); print(conn.cursor().execute('SELECT 1').fetchone())"
    ```
- Actual output: the application logs showed `OperationalError: FATAL: password authentication failed for user "barq_app"`.
- Failed attempt and what changed your thinking: I first focused on the state of the database container itself. The database was healthy and `pg_isready` accepted connections, which proved the real issue was the application-side secret mismatch rather than a dead PostgreSQL process.
- Root cause: the Compose/application environment still contained a stale `change_me_please` password even though the actual database secret in `.env` was `DFDKLkdlh35g`.
- Fix: aligned the app environment with the actual database secret and removed the stale literal from the runtime config.
- Retest evidence: `python validate.py` returned `PASS: all validation checks succeeded` after the fix.
- Related commit: current HEAD on `main` after the completion of part 3.
- Remaining uncertainty: none for this specific issue.

## Entry 2 — validation mismatch from unrelated local containers

- Symptom: validation reported an unexpected port exposure for a container named `dar-elsoker-frontend` even though the project itself had no such service.
- Hypothesis: the port scan was checking all local Docker containers rather than the project-only stack.
- Command or test:
    ```bash
    docker ps --format "{{.Names}} {{.Ports}}"
    docker compose -p barq-assessment ps --format "{{.Names}} {{.Ports}}"
    ```
- Actual output: `dar-elsoker-frontend` showed port `4200`, which belonged to an unrelated stack, while the project stack correctly exposed only the intended `127.0.0.1:8080->80` mapping.
- Failed attempt and what changed your thinking: the first validation script was scanning all containers. That produced false failures because it did not scope itself to the BARQ Compose project.
- Root cause: validation logic was not project-scoped and therefore counted unrelated host ports.
- Fix: restrict port checks to `docker compose -p barq-assessment ps` and ignore non-project containers.
- Retest evidence: the final validation passed with no unexpected host port failures.
- Related commit: same part 3 branch/commit sequence.
- Remaining uncertainty: none for the port-scope problem.

## Entry 3 — proof that redis and postgres were independently healthy

- Symptom: `GET /ready` and `POST /records` intermittently failed during the first pass even though `docker compose` reported the containers as healthy.
- Hypothesis: the app was running but not actually using the correct DB and Redis connection strings from the project environment.
- Command or test:
    ```bash
    docker compose -p barq-assessment exec -T postgres pg_isready -U barq_app -d barq_tasks
    docker compose -p barq-assessment exec -T redis redis-cli ping
    docker inspect app-01 --format '{{json .Config.Env}}'
    ```
- Actual output: PostgreSQL and Redis both responded correctly; the app environment was the real mismatch.
- Failed attempt and what changed your thinking: database health and Redis health were fine individually; the issue was config alignment rather than service outage.
- Root cause: stale runtime environment values, not backend availability.
- Fix: update config, rebuild the stack, and re-run validation.
- Retest evidence: `python validate.py` succeeded and `python failure_test.py` succeeded.
- Related commit: project HEAD commit `0080512`.
- Remaining uncertainty: minimal; the environment is stable under the verified setup.
