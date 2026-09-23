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

## 8. Answers to the required assessment questions

### 8.1 What failed first? What proved the cause? Which failed attempt taught you something?

The first concrete failure was not on the public edge but inside the app dependency path: the app could reach the database host, but PostgreSQL rejected the login with `FATAL: password authentication failed for user "barq_app"`. That was the decisive proof because the database was reachable and the issue was a credential mismatch, not a container crash or a network outage. The most useful failed attempt was trusting the service health checks too early: `postgres` and `redis` looked healthy, but the app still returned 503 on `/ready` and `/records` because the application configuration had drifted from the actual database secret. The lesson was to validate the application-side environment variables and not treat dependency health alone as proof of end-to-end function.

### 8.2 What patterns did the logs reveal? How did you avoid double-counting requests?

The logs showed a consistent pattern: `nginx` recorded incoming requests with a request ID, and the Flask app emitted matching HTTP entries with the same `X-Request-ID` header. That made it possible to correlate edge traffic to application handling without relying on raw line counts. To avoid double-counting in validation, we used the unique request ID as the identity for a request, and we counted a transaction only once when the same request ID appeared in both the proxy and app logs. We also treated public HTTP status checks as an aggregate signal, not as proof of a valid transaction in isolation.

### 8.3 How do requests flow? Why these ports, networks and readiness checks?

The request flow is: client -> NGINX on `127.0.0.1:8080` -> upstream pool `app-01:8080` and `app-02:8080` -> PostgreSQL on `postgres:5432` and Redis on `redis:6379` as needed. The public port is only exposed on NGINX, while PostgreSQL and Redis stay on the internal `backend` network and are not published to the host. This keeps the database and cache off the public interface and matches the requirement for a clean ingress path. The readiness checks matter because `/ready` only returns 200 when both dependencies are reachable; otherwise the app can still respond to `/health`, but it correctly reports degraded readiness instead of pretending the stack is fully ready.

### 8.4 Why these timeouts, retries, restart settings and resource limits?

The timeouts are intentionally short: database and Redis calls use very small connection and socket timeouts so a bad dependency does not stall request handling for long. Healthcheck retries are bounded so the stack can recover quickly without hanging indefinitely, while `restart: unless-stopped` keeps the services self-healing after temporary crashes. CPU and memory limits were set to keep the lab stack stable under limited local resources and to make the Compose behavior predictable in CI. These settings reflect a pragmatic balance between resilience, fast failure, and constrained local execution rather than a production-grade HA design.

### 8.5 When should validation fail? What does green CI prove, or not prove?

Validation should fail when any required route is missing or wrong, when a backend is absent, when public port exposure is incorrect, when the DB/cache readiness checks fail, or when a request flow no longer reaches both applications through NGINX. A green CI run proves the repository builds cleanly, that required dependencies are installed, the unit tests pass, the compose stack comes up, and the stack passes the project validation checks in a clean environment. It does not prove there are no production risks, that the live video challenge has passed, or that a highly available multi-node production stack is in place.

### 8.6 Which single points of failure remain? How would you fix them in production?

The main remaining single points of failure are PostgreSQL, Redis, and the single NGINX public edge. In this lab, they are intentionally simple and not redundant. In production, the fix would be to use managed PostgreSQL with replication or a primary/standby arrangement, Redis clustering or a managed cache service, and multiple NGINX replicas behind a load balancer with health checks and autoscaling. We would also add secret management, centralized metrics, and alarm-driven alerting so a dependency failure is detected before the service becomes user-visible.

### 8.7 What would you improve? How did you verify AI-assisted work?

The next improvements would be stronger secret handling, a dedicated monitoring stack, log aggregation, and a proper production deployment pipeline with environment-specific configuration. We would also add a more explicit backup and restore playbook for operational use, and we would consider automated image scanning and policy checks. Every AI-assisted change was verified by running the actual Docker stack, the Python unit tests, and the project validation script, then checking the logs and route responses against the real environment instead of trusting the generated text alone. That gave us an evidence-based workflow: build, run, verify, and only then treat the result as complete.

### 8.8 AI usage disclosure

This task used AI assistance for code understanding, doc drafting, and troubleshooting support. The generated suggestions were validated with the repository’s real runtime checks, unit tests, and Docker health verification before being accepted as final changes.
