# Security and production-readiness review

## 1) Secret rotation and config leakage

- Risk and evidence: the environment used a stale database password in the first runtime pass; secrets were effectively duplicated across config and environment files.
- Impact: complete PostgreSQL authentication failure and 503s for all record and readiness operations.
- Implemented fix / commit: the runtime config was aligned to the actual `.env` password and the app stack was rebuilt. This is captured in the project fix history.
- Production follow-up: move secrets to Docker secrets or a managed secret vault and eliminate hardcoded fallback values.
- How to verify: run `docker compose -p barq-assessment exec app-01 env` and confirm the runtime DB URL matches the secret source used by PostgreSQL.

## 2) Public port exposure

- Risk and evidence: only the NGINX frontend should be exposed, not PostgreSQL or Redis.
- Impact: direct exposure of stateful services could enable bypassing the app layer and increase attack surface.
- Implemented fix / commit: Compose defines only the NGINX public mapping and keeps the database services on the internal backend network.
- Production follow-up: keep app and data tiers private and add a firewall or network policy that blocks direct DB reachability from untrusted networks.
- How to verify: `docker network inspect barq-assessment_backend` and `docker compose -p barq-assessment ps`.

## 3) Container privilege and user isolation

- Risk and evidence: the app previously started with a wildcard runtime expectation; the Dockerfile now uses a non-root app user.
- Impact: reduces the blast radius of a compromise inside the app container.
- Implemented fix / commit: the `Dockerfile` creates the `app` user and runs the process as that non-root account.
- Production follow-up: enforce a read-only root filesystem and drop Linux capabilities that are not required.
- How to verify: `docker inspect app-01 --format '{{.Config.User}}'`.

## 4) Image provenance and scanning

- Risk and evidence: container images were built locally without explicit vulnerability policy or digest pinning.
- Impact: vulnerable base images or unreviewed package updates can reach production.
- Implemented fix / commit: not yet full production hardening; local Docker builds were verified but no image scan was added.
- Production follow-up: add Trivy or Grype into CI, pin images by digest, and review dependency update cadence.
- How to verify: run a CI security scan on the built images and fail on critical issues.

## 5) Network segmentation between front and back ends

- Risk and evidence: if backend services are reachable from the public edge, attackers can bypass the app and query data directly.
- Impact: data exfiltration or service disruption.
- Implemented fix / commit: the stack is split across `frontend` and `backend` with `nginx` on the edge and app/data services on the protected network.
- Production follow-up: test cross-network restrictions in CI and monitor connection attempts from the frontend to backend services.
- How to verify: `docker compose -p barq-assessment exec nginx getent hosts postgres` should fail; internal service names resolve only within the internal network.

## 6) Data persistence and backup hygiene

- Risk and evidence: database state is valuable and persistence must be controlled. Backups and restore operations must be explicit and versioned.
- Impact: accidental loss of records or failed restore can erase evidence and business data.
- Implemented fix / commit: named PostgreSQL volume plus `backup.sh` and `restore.sh` are included and validated against the live stack.
- Production follow-up: add retention policy, encryption-at-rest, and automated off-host backup copies.
- How to verify: create a record through `/records`, run the backup script, restore it, and confirm the record survives the restore cycle.

## 7) Logging and monitoring gaps

- Risk and evidence: the application emits useful JSON logs, but there is no centralized exporter or alerting threshold configured in this lab setup.
- Impact: outages and dependency failures are visible locally but not strongly monitored in production.
- Implemented fix / commit: the app logs structured events and the validation suite checks endpoint readiness, but this is not yet a full monitoring stack.
- Production follow-up: forward logs to a central system and alert on repeated 503s or dependency timeouts.
- How to verify: inspect container logs and trigger a simulated failure to confirm alerts and dashboards capture the event.

## 8) Availability and single points of failure

- Risk and evidence: a single PostgreSQL instance remains a single point of failure for the datastore layer.
- Impact: if PostgreSQL is destroyed or inaccessible, both app instances fail readiness and record creation.
- Implemented fix / commit: app-level resilience is improved, but this is still a single-node database deployment in the lab.
- Production follow-up: add a primary/replica setup, failover automation, and backup validation drills.
- How to verify: stop PostgreSQL and confirm the app enters a clean degraded state with clear 503 responses.

## 9) Retry policy and upstream behavior

- Risk and evidence: NGINX currently disables upstream retries for a predictable failure model. This is safer than retry storms, but it also means a full backend outage causes direct failures.
- Impact: user-facing errors may rise during outages.
- Implemented fix / commit: explicit configuration is already in place and documented in the decisions log.
- Production follow-up: if using retries, apply a bounded retry policy only for idempotent operations and with timeouts tuned to service criticality.
- How to verify: run the built-in `failure_test.py` and confirm the surviving backend handles traffic while one backend is stopped.

## 10) Safe cleanup and lifecycle discipline

- Risk and evidence: Compose state and data are easy to discard accidentally without understanding persistence requirements.
- Impact: data loss, changed runtime assumptions, and broken validation.
- Implemented fix / commit: instructions clearly separate normal shutdown from persistence testing, and the backup scripts are explicit about the restore path.
- Production follow-up: add lifecycle automation to snapshot state before upgrades and require review before destructive cleanup.
- How to verify: run `docker compose -p barq-assessment down` and confirm the target stack stops cleanly without destructive volume removal unless intentionally requested.
