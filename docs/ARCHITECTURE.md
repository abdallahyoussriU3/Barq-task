# Architecture notes

The final runtime topology is:

- Client traffic enters via the public host port on NGINX.
- NGINX sits on the `frontend` network and forwards traffic to the Flask app instances.
- `app-01` and `app-02` each sit on both `frontend` and `backend` so they can accept ingress while still reaching PostgreSQL and Redis.
- PostgreSQL and Redis stay on the internal `backend` network and are not directly exposed to the host.
- A named Docker volume backs the PostgreSQL data directory for persistence.

Request flow:

- client -> NGINX on port 8080 -> application_pool -> Flask instance -> PostgreSQL/Redis as required
- `/health` confirms the process is alive
- `/ready` verifies PostgreSQL and Redis readiness
- `/records` writes to PostgreSQL and returns stored records
- `/counter` increments a Redis counter

Single points of failure that remain in the lab setup:

- PostgreSQL is still a single datastore node, so its outage causes record writes and readiness checks to fail.
- Redis is also a single cache node; it is a dependency for the counter route and readiness checks.
- NGINX is a single public edge but the task intentionally makes it the only public entry point.

The diagram artifact is required at the repository root as `architecture.png` or `architecture.pdf` and should show the ports, networks, health checks, and persistence relationships above.
