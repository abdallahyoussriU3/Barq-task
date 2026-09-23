# Technical decisions

## 1) Use a containerized Python 3.12 slim image

- Choice: base image `python:3.12-slim-bookworm` for the Flask app containers.
- Why: it is small, consistent, and already includes Python for the app. It also keeps the runtime predictable across local and CI execution.
- Alternative: a heavier full Debian image or a custom image with additional packages.
- Trade-off: slim images reduce size and attack surface but require explicit dependency management and careful health-check design.
- Evidence: [Dockerfile](Dockerfile) and local build logs.
- Production improvement: pin image digest and add SBOM / vulnerability scanning in the CI pipeline.

## 2) Enforce separate frontend and backend networks

- Choice: `nginx` attaches only to `frontend`; `app-01`, `app-02`, `postgres`, and `redis` attach to `backend`, with app instances also on `frontend` for ingress.
- Why: this matches the task requirement for network isolation and prevents direct NGINX access to PostgreSQL or Redis.
- Alternative: a single flat network with internal-only policy enforcement.
- Trade-off: more explicit topology, but it requires careful service reachability mapping.
- Evidence: [docker-compose.yml](docker-compose.yml).
- Production improvement: add explicit firewall rules or service mesh policies for east-west traffic control.

## 3) Use health checks and dependency gating instead of blind startup

- Choice: both app containers depend on healthy PostgreSQL and Redis before starting; container health checks verify readiness before traffic is served.
- Why: this reduces startup races and makes readiness failures explicit rather than silent.
- Alternative: start all containers without gating and rely on retries in the app.
- Trade-off: slower startup, but dramatically better stability and easier debugging.
- Evidence: health results from `docker compose ps` and `/ready` checks.
- Production improvement: add a startup probe and a more detailed metrics dashboard for dependency health.

## 4) Keep NGINX on the public edge and disable upstream retries

- Choice: NGINX listens only on `127.0.0.1:8080->80`, and `proxy_next_upstream off` is configured.
- Why: the task requires a single public ingress point on 8080 and predictable failure semantics without silent retry chains.
- Alternative: letting NGINX retry upstreams or exposing extra host ports.
- Trade-off: less resilience to one backend being unavailable, but clearer operational behavior and a stricter security posture.
- Evidence: [nginx/nginx.conf](nginx/nginx.conf) and validation checks.
- Production improvement: place NGINX behind a load balancer or use active health-checking with controlled retries.

## 5) Use real PostgreSQL persistence and database-backed records

- Choice: store records in PostgreSQL, backed by a named Docker volume.
- Why: the task requires persistence across app restarts and a real restore flow.
- Alternative: ephemeral in-memory records or Redis-only storage.
- Trade-off: adds database complexity but matches production requirements.
- Evidence: `database/init.sql`, `backup.sh`, `restore.sh`, and record creation through `/records`.
- Production improvement: schedule automated backups and add point-in-time recovery or retention policies.

## 6) Keep the app non-root and minimal

- Choice: `Dockerfile` creates a dedicated `app` user and runs the service as that user.
- Why: reduces attack surface, follows least privilege, and aligns with the task’s container-user requirement.
- Alternative: run the container as root.
- Trade-off: more careful permission handling for mounted files and scripts, but safer in production.
- Evidence: [Dockerfile](Dockerfile).
- Production improvement: add a read-only root filesystem and isolate credentials via mounted secrets instead of env values.

## 7) Health and timeout values were set conservatively

- Choice: PostgreSQL and Redis health checks use short timeouts, and app requests use short connection/read timeouts.
- Why: the app must fail fast and return clean 503s rather than hanging under dependency problems.
- Alternative: long timeouts and more aggressive retries.
- Trade-off: fast failures improve availability under failure but can increase 5xx counts during a degraded backend.
- Evidence: current Compose health checks and `app/server.py` timeouts.
- Production improvement: tune timeouts based on telemetry and vary them by dependency criticality.
