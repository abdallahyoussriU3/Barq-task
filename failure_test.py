#!/usr/bin/env python3
"""Stop one app instance, verify the remaining backend handles traffic, then restore it."""
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

PROJECT = os.getenv("COMPOSE_PROJECT_NAME", "barq-assessment")
BASE_URL = os.getenv("APP_URL", "http://127.0.0.1:8080")


def run_command(command):
    result = subprocess.run(command, capture_output=True, text=True)
    return result.returncode, result.stdout.strip(), result.stderr.strip()


def http_status(path):
    req = urllib.request.Request(f"{BASE_URL}{path}", method="GET")
    try:
        with urllib.request.urlopen(req, timeout=3) as response:
            return response.status, response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", errors="replace")
    except Exception as exc:
        return None, str(exc)


def wait_until(predicate, timeout_seconds=30, interval=1.0):
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return False


def current_instances():
    seen = set()
    for _ in range(8):
        status, payload = http_status("/instance")
        if status == 200:
            try:
                import json
                data = json.loads(payload)
                if data.get("instance_id"):
                    seen.add(data["instance_id"])
            except json.JSONDecodeError:
                pass
        time.sleep(0.5)
    return seen


def main():
    print("INFO: verifying both app instances are healthy before the failure test")
    if not wait_until(lambda: {"app-01", "app-02"}.issubset(current_instances()), timeout_seconds=30):
        print("FAIL: both backends did not respond before the experiment")
        return 1

    print("INFO: stopping app-01 to simulate a backend outage")
    code, _, stderr = run_command(["docker", "compose", "-p", PROJECT, "stop", "app-01"])
    if code != 0:
        print(f"FAIL: could not stop app-01: {stderr}")
        return 1

    success = 0
    errors = 0
    for _ in range(20):
        status, _ = http_status("/health")
        if status == 200:
            success += 1
        else:
            errors += 1
        time.sleep(0.25)

    print(f"INFO: measured traffic while app-01 was stopped -- successes={success}, errors={errors}")
    if not wait_until(lambda: current_instances() == {"app-02"}, timeout_seconds=20):
        print("FAIL: traffic did not shift cleanly to the surviving backend")
        return 1

    print("INFO: restoring app-01")
    code, _, stderr = run_command(["docker", "compose", "-p", PROJECT, "start", "app-01"])
    if code != 0:
        print(f"FAIL: could not restore app-01: {stderr}")
        return 1

    if not wait_until(lambda: {"app-01", "app-02"}.issubset(current_instances()), timeout_seconds=30):
        print("FAIL: recovered app-01 did not resume serving traffic")
        return 1

    recovered = current_instances()
    print(f"PASS: failure and recovery verified; recovered instances={sorted(recovered)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
