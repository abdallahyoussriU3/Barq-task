# Log analysis

This project’s log review was based on the three supplied historical log sources in `logs/` and the current runtime behavior of the fixed Compose stack. The same patterns match the incident categories described in the task: backend connectivity failures, dependency timeouts, and a brief upstream timeout burst.

## 1) UTC window and record quality

The historical logs span the UTC window from 11:00:00 to 11:29:57. The analysis treated malformed/truncated records as excluded records rather than guessed data, which is the safest way to preserve data integrity.

Key findings:

- `access.log`: 725 valid entries, 1 truncated line, 5 exact duplicates
- `application.log`: 729 valid entries, 1 truncated line
- `error.log`: 68 lines total, with 67 real error events and one informational log-rotation marker

The duplicate access lines were byte-for-byte repeats of the same request ID, timestamp, and upstream, so they were removed before any rate or error analysis.

## 2) Distinct request count and deduplication strategy

The distinct client request count was 720 after duplicate removal. This avoids double-counting retries while preserving the real upstream retry behavior, since a retry appears as a second backend in the same request record rather than a second identical line.

The deduplication rule was:

- remove exact duplicate lines with same request ID + timestamp + upstream
- keep real retry events in place because they represent a single client request with a different upstream path

## 3) Final status counts and error rate

Across the 720 distinct requests:

- 615 successful responses (200)
- 10 genuine 404s
- 95 server errors (40x 502, 47x 503, 8x 504)

Error rate = 95 / 720 = 13.2%.

## 4) Which paths, windows and backends failed

Three separate issues were visible in the logs:

1. 11:05 to 11:09 UTC — a backend went fully unreachable
    - `172.23.0.12` stopped responding on many routes
    - nginx retried to the other backend for 19 requests and all 19 succeeded
    - the remaining 40 requests without retry surfaced as 502s

2. 11:12 to 11:21 UTC — dependency outage on both app instances
    - Redis and PostgreSQL timeouts caused ~47 requests to fail with 503
    - this matched the application log dependency_error events

3. 11:25 to 11:26 UTC — brief slow-response burst
    - 8 requests hit nginx read-timeout behavior
    - these surfaced as 504s

## 5) Latency and percentile method

Median request latency was roughly 54 ms, while the p95 latency was about 2001 ms. This difference matches the dependency timeouts in the historical data: a few slow requests dominate the tail while most traffic remained fast.

The percentile method used was a sorted nearest-rank percentile over the request timings, measured in milliseconds.

## 6) Retry behavior

The historical logs show 19 requests that were retried upstream during the backend outage window. All 19 recovered successfully after being sent to the surviving backend.

This is also why the current fixed environment disables `proxy_next_upstream` in NGINX: it makes failure behavior explicit and easier to reason about in CI validation.

## 7) Incident timeline

- 11:05:02 UTC: one backend begins refusing connections
- 11:05–11:09 UTC: outage window; retries succeed and some errors surface as 502s
- 11:12:09 UTC: dependency timeout begins in app logs
- 11:12–11:21 UTC: Redis/PostgreSQL timeouts produce 503s across both backends
- 11:25–11:26 UTC: brief slow-response burst hits read timeout and produces 504s
- 11:29:57 UTC: log capture ends

## 8) Correlated example of a failed and successful request

- Failed example: a request to `/counter` during the dependency timeout window returned 503; the app log shows a dependency_error event for Redis/PostgreSQL.
- Successful example: a request retried from the unreachable backend to the healthy backend returned 200; the access log and the app log both line up with the same request ID and time.

## 9) Proxy vs dependency issues

- Proxy/connectivity issue: nginx cannot reach the backend or times out before the app runs any code. The evidence is in the error log and the upstream connection failure.
- Dependency issue: nginx reaches the app, but the app cannot reach PostgreSQL or Redis. The evidence is the application log dependency_error events naming the failing dependency.

This distinction is what separates infrastructure outage from backend dependency failure.

## 10) What the logs do not prove

The logs do not prove the exact internal reason for the unreachable backend or why PostgreSQL/Redis timed out. To answer those questions, the next step would be container-level logs, runtime metrics, and direct service state checks in a live environment. The current evidence shows when and where the failures happened, not the underlying cause beyond reasonable inference.

## Conclusions and limits

The historical log set is consistent with three separate incidents rather than a single monotonic problem:

- one backend outage
- dependency timeouts affecting app readiness and record creation
- a brief slow-response burst

Those findings correspond with the same operational model we used to fix the live environment: verify health, verify dependency readiness, and fail fast with explicit 503s instead of hanging silently.
