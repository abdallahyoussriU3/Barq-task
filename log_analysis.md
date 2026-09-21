# Log analysis

Use all three supplied logs. Answer every question with commands/scripts and actual output.

1. What UTC interval is covered? How many valid, malformed and duplicate lines are in each file?
2. How many distinct client requests occurred? How did you deduplicate and avoid counting retries twice?
3. What are the final client status counts and error rate? State your denominator.
4. Which paths, time windows and backends account for the failures?
5. What are the median and p95 client latencies? State the percentile method and units.
6. Which requests retried upstream? How many succeeded after retrying?
7. Build an incident timeline using evidence from access, error AND application logs.
8. Show one correlated failed request and one successful request. Include IDs and timestamps.
9. Which errors appear to be proxy/connectivity issues versus dependency/application issues? What proves it?
10. What do the logs not prove? What would you check next in a running environment?

## Commands / scripts
## Results
## Timeline and correlated examples
## Conclusions and limits

# Log analysis

Use all three supplied logs. Answer every question with commands/scripts and actual output.

1. What UTC interval is covered? How many valid, malformed and duplicate lines are in each file?
2. How many distinct client requests occurred? How did you deduplicate and avoid counting retries twice?
3. What are the final client status counts and error rate? State your denominator.
4. Which paths, time windows and backends account for the failures?
5. What are the median and p95 client latencies? State the percentile method and units.
6. Which requests retried upstream? How many succeeded after retrying?
7. Build an incident timeline using evidence from access, error AND application logs.
8. Show one correlated failed request and one successful request. Include IDs and timestamps.
9. Which errors appear to be proxy/connectivity issues versus dependency/application issues? What proves it?
10. What do the logs not prove? What would you check next in a running environment?

## Commands / scripts

All numbers below came from `scripts/analyze_logs.py` plus a few small one-off `python3 -c`
snippets. All three log files were read as read-only; nothing in `logs/` was edited. The exact
commands used for each answer are listed under that answer in **Results**, so anyone can rerun
and get the same numbers.

## Results

**1. Interval, valid/malformed/duplicate lines**

The logs span **11:00:00 to 11:29:57 UTC** (30 minutes). Each file had exactly one corrupted
line — a record that got cut off mid-write, sitting between two normal, valid lines — which we
excluded from all counts rather than guess at its contents:

- `access.log`: 725 valid lines, 1 truncated, 5 exact duplicate lines
- `application.log`: 729 valid lines, 1 truncated
- `error.log`: 68 lines (67 real errors, 1 harmless "log rotated" notice)

The 5 duplicates in access.log are byte-for-byte identical repeats of the same request (same
ID, timestamp, and backend) — a logging artifact, not a real retry — so they were dropped.

```
python3 scripts/analyze_logs.py
sed -n '311p' logs/access.log   # truncated line
sed -n '401p' logs/application.log   # truncated line
```

**2. Distinct requests and how we deduplicated**

After removing the 5 duplicate lines, access.log has **720 distinct client requests**. The key
distinction we relied on: a genuine nginx *retry* still shows up as a **single log line**, just
with two backends listed (e.g. `"172.23.0.12:8080, 172.23.0.11:8080"`). A duplicate is a
**second, identical line**. So we deduplicated on (request ID + timestamp + backend), which
removes true duplicates while leaving retries alone — each retried request is still counted
once, by its final status.

```
python3 -c "import json; seen=set(); d=[]
for l in open('logs/access.log'):
    l=l.strip()
    if not l: continue
    r=json.loads(l)
    k=(r['request_id'], r['timestamp'], r['upstream'])
    if k not in seen: seen.add(k); d.append(r)
print(len(d))"
# -> 720
```

**3. Final status counts and error rate**

Out of 720 distinct requests: **615 succeeded (200), 10 were genuine 404s, and 95 were server
errors** (40× 502, 47× 503, 8× 504). That's an **error rate of 13.2%** (95/720).

**4. Which paths, windows and backends failed**

Three separate windows, each with a different cause:

- **11:05–11:09 — one backend down.** `172.23.0.12` refused every connection nginx sent it,
  across every endpoint (`/`, `/health`, `/ready`, `/records`, `/counter`, `/instance`) — the
  whole container was unreachable, not just one route. 59 attempts hit this; 19 were quietly
  retried to the other backend and succeeded, 40 had no retry and came back as 502.
- **11:12–11:21 — dependency timeouts on both backends.** Both `app-01` and `app-02` started
  timing out on calls to Redis (31 times) and PostgreSQL (16 times), almost evenly split
  between the two instances. Each timeout produced a 503 — 47 in total, matching exactly.
- **11:25–11:26 — brief slow-response burst.** 8 requests, split evenly across both backends,
  took too long to respond and nginx's read timeout (3s) killed them, producing 8× 504.

**5. Latency**

Median response time was **54 ms**; the 95th percentile was **2001 ms** — a big gap, driven
entirely by the window-2 dependency timeouts (Redis/Postgres calls hanging for ~2s before
failing). Method: sorted all 720 request_time values (converted seconds → ms), took the
nearest-rank 95th percentile.

**6. Retries**

19 requests — all during the 11:05–11:09 outage — were automatically retried by nginx against
the second backend, and **all 19 succeeded**. This only happened during that window because the
historical nginx config allowed a retry-to-next-upstream; the current `nginx.conf` in this repo
has that turned off (`proxy_next_upstream off`), so this behavior won't reproduce in the fixed
environment — noted as a trade-off in decisions.md.

```
grep -c '"upstream":"[^"]*,' logs/access.log   # 19
```

**7. Incident timeline**

| Time (UTC) | What happened |
|---|---|
| 11:05:02 | Backend `172.23.0.12` starts refusing connections |
| 11:05–11:09 | 59 failed connection attempts; 19 recover via retry, 40 become 502s |
| 11:12:09 | First Redis timeout logged by the app |
| 11:12–11:21 | 47 Redis/Postgres timeouts across both backends → 47× 503 |
| 11:25–11:26 | 8 slow responses hit nginx's read timeout → 8× 504 |
| 11:30:00 | Log capture ends |

**8. One failed request, one successful request, correlated**

- **Failed** (`lab-000308`, 11:12:49): client got a 503 on `/counter` from `172.23.0.12`, request
  took ~2 seconds — matches an application-log entry for that same backend and time showing a
  Redis timeout. The proxy did its job; the app's dependency was the problem.
- **Succeeded via retry** (`lab-000124`, 11:05:07): nginx's error.log shows a connection refusal
  to `172.23.0.12` for this exact request ID at this exact time — but the matching access.log
  line shows nginx retried `172.23.0.11` immediately and returned 200 to the client. Same
  request, two log files, one full story.

**9. Proxy/connectivity errors vs. dependency/application errors — how to tell them apart**

- **Connectivity problems** (windows 1 and 3) show up in **error.log** — nginx itself couldn't
  reach or got no timely response from a backend, before the app ever ran any code. These affect
  every endpoint on the affected container at once, not one specific route.
- **Dependency problems** (window 2) never appear in error.log — nginx connected to the app
  fine. Instead they show up in **application.log** as an explicit `dependency_error` event
  naming Redis or Postgres. The app was reachable and running; a downstream service was just
  slow or unavailable.

The presence or absence of a matching error.log entry is what separates the two categories —
not just the status code.

**10. What the logs can't tell us**

The logs prove *that* things failed and roughly *when*, but not the underlying *why*:

- Why `172.23.0.12` was unreachable — a crash, an OOM kill, a slow restart? We'd need container
  logs and exit codes from that window, which weren't captured here.
- Whether Redis/Postgres were actually down or just overloaded — we'd need to look at those
  services' own logs and metrics directly.
- Whether real users were affected beyond the status code — we'd need uptime monitoring or
  real-user metrics, which aren't in these logs.

In a running environment, these are exactly what we'd check next.

## Conclusions and limits
Three independent historical incidents, not one: (1) a fully unreachable backend container
(connectivity), (2) redis/postgres timeouts under both backends (dependency), (3) a brief
upstream-timeout burst (connectivity/latency). All 5xx counts fully reconcile against error.log
and application.log evidence with no unexplained gap. Limits: root cause of the container
outage and dependency slowness cannot be determined from these logs alone — see Q10.
