#!/usr/bin/env python3
"""Parse logs/access.log, logs/application.log, logs/error.log.
Reports parse failures, status/level distributions, and a per-minute timeline.
Read-only: never modifies the original log files.
"""
import json
import re
import sys
from collections import Counter
from pathlib import Path

LOG_DIR = Path("logs")

def load_json_lines(path):
    ok, bad = [], []
    for i, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            ok.append(json.loads(line))
        except json.JSONDecodeError:
            bad.append((i, line))
    return ok, bad

def report_json_log(name):
    path = LOG_DIR / name
    records, bad = load_json_lines(path)
    print(f"\n=== {name} ===")
    print(f"parsed: {len(records)}  malformed/skipped: {len(bad)}")
    if bad:
        print("  first malformed line:", bad[0])
    return records

def main():
    access = report_json_log("access.log")
    app = report_json_log("application.log")

    print("\n--- access.log status distribution ---")
    for status, count in Counter(r.get("status") for r in access).most_common():
        print(f"  {status}: {count}")

    print("\n--- application.log level distribution ---")
    for level, count in Counter(r.get("level") for r in app).most_common():
        print(f"  {level}: {count}")

    print("\n--- access.log errors (>=500) by minute ---")
    minute_errors = Counter(
        r["timestamp"][:16] for r in access if isinstance(r.get("status"), int) and r["status"] >= 500
    )
    for minute, count in sorted(minute_errors.items()):
        print(f"  {minute}: {count}")

    print("\n--- application.log dependency_error events ---")
    dep_errors = [r for r in app if r.get("event") == "dependency_error"]
    print(f"  count: {len(dep_errors)}")
    for r in dep_errors[:5]:
        print(" ", r)

    print("\n--- error.log line count + first/last timestamps ---")
    err_path = LOG_DIR / "error.log"
    err_lines = err_path.read_text(encoding="utf-8", errors="replace").splitlines()
    err_lines = [l for l in err_lines if l.strip()]
    print(f"  count: {len(err_lines)}")
    if err_lines:
        print("  first:", err_lines[0])
        print("  last:", err_lines[-1])

    # crude duplicate check by request_id in access.log
    ids = [r.get("request_id") for r in access if r.get("request_id")]
    dupes = {k: v for k, v in Counter(ids).items() if v > 1}
    print(f"\n--- access.log duplicate request_ids: {len(dupes)} ---")
    for k, v in list(dupes.items())[:5]:
        print(f"  {k}: {v} occurrences")

if __name__ == "__main__":
    main()
