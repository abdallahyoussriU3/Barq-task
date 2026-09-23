#!/usr/bin/env python3
"""Validate the Dockerized BARQ environment and fail on the first non-compliant check."""
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

PROJECT = os.getenv("COMPOSE_PROJECT_NAME", "barq-assessment")
BASE_URL = os.getenv("APP_URL", "http://127.0.0.1:8080")
MAX_WAIT_SECONDS = int(os.getenv("VALIDATION_TIMEOUT_SECONDS", "60"))
ALLOWLISTED_PUBLIC_PORTS = {"8080"}

failures = []


def note(kind, message):
    prefix = "PASS" if kind == "PASS" else "FAIL"
    print(f"{prefix}: {message}")
    if kind == "FAIL":
        failures.append(message)


def run_command(command):
    result = subprocess.run(command, capture_output=True, text=True)
    return result.returncode, result.stdout.strip(), result.stderr.strip()


def request_json(path, method="GET", payload=None, timeout=5):
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(f"{BASE_URL}{path}", data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            body = response.read().decode("utf-8", errors="replace")
            try:
                return response.status, json.loads(body) if body else {}
            except json.JSONDecodeError:
                return response.status, body
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            return exc.code, json.loads(body) if body else {}
        except json.JSONDecodeError:
            return exc.code, body
    except Exception as exc:
        return None, {"error": str(exc)}


def wait_for_ready(path, expected_status=200, timeout_seconds=MAX_WAIT_SECONDS):
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        status, payload = request_json(path)
        if status == expected_status:
            return True, payload
        time.sleep(1)
    return False, payload if "payload" in locals() else {} # type: ignore


def docker_service_state(service_name):
    code, stdout, _ = run_command(["docker", "compose", "-p", PROJECT, "ps", "--status", "running", service_name])
    return code == 0 and service_name in stdout


def check_public_access():
    status, payload = request_json("/")
    if status == 200 and payload.get("message"): # type: ignore
        note("PASS", "Public entrypoint available at /")
        return True
    note("FAIL", f"Public entrypoint unavailable: {status} {payload}")
    return False


def check_required_endpoints():
    checks = {
        "/health": 200,
        "/ready": 200,
        "/instance": 200,
        "/records": 200,
        "/counter": 200,
    }
    ok = True
    for path, expected in checks.items():
        status, payload = request_json(path)
        if status == expected:
            note("PASS", f"{path} returned {status}")
        else:
            ok = False
            note("FAIL", f"{path} returned {status} instead of {expected}: {payload}")
    return ok


def check_postgres_and_redis_readiness():
    ok = True
    code, stdout, stderr = run_command(["docker", "compose", "-p", PROJECT, "exec", "-T", "postgres", "pg_isready", "-U", "barq_app", "-d", "barq_tasks"])
    if code == 0:
        note("PASS", "PostgreSQL readiness check succeeded")
    else:
        ok = False
        note("FAIL", f"PostgreSQL readiness check failed: {stderr or stdout}")
    code, stdout, stderr = run_command(["docker", "compose", "-p", PROJECT, "exec", "-T", "redis", "redis-cli", "ping"])
    if code == 0 and stdout.strip() == "PONG":
        note("PASS", "Redis readiness check succeeded")
    else:
        ok = False
        note("FAIL", f"Redis readiness check failed: {stderr or stdout}")
    return ok


def check_backend_identity():
    seen = set()
    for _ in range(12):
        status, payload = request_json("/instance")
        if status != 200:
            note("FAIL", f"/instance returned {status} while probing backends: {payload}")
            return False
        instance = payload.get("instance_id") # type: ignore
        if instance:
            seen.add(instance)
        time.sleep(0.5)
    if {"app-01", "app-02"}.issubset(seen):
        note("PASS", "Both backend instances responded through NGINX")
        return True
    note("FAIL", f"Expected both backends in /instance responses, saw {sorted(seen)}")
    return False


def check_record_workflow():
    record_title = f"validate-{time.time_ns()}"
    status, payload = request_json("/records", method="POST", payload={"title": record_title})
    if status != 201:
        note("FAIL", f"POST /records failed with {status}: {payload}")
        return False
    created = payload.get("record", {}).get("title") # type: ignore
    if created != record_title:
        note("FAIL", f"Unexpected created record title: {created!r}")
        return False
    note("PASS", "POST /records accepted a new row")
    status, payload = request_json("/records")
    if status != 200 or any(item.get("title") == record_title for item in payload.get("records", [])):
        note("PASS", "GET /records returned the created row")
        return True
    note("FAIL", f"GET /records did not include {record_title}: {payload}")
    return False


def check_counter_workflow():
    status, payload = request_json("/counter")
    if status == 200 and isinstance(payload.get("counter"), int):
        note("PASS", "/counter returned an integer counter")
        return True
    note("FAIL", f"/counter did not return a valid counter: {payload}")
    return False


def check_network_isolation():
    ok = True
    for service_name in ["postgres", "redis"]:
        code, stdout, stderr = run_command(["docker", "inspect", "-f", "{{json .NetworkSettings.Networks}}", service_name])
        if code != 0:
            ok = False
            note("FAIL", f"Could not inspect {service_name}: {stderr or stdout}")
            continue
        if "frontend" in stdout:
            ok = False
            note("FAIL", f"{service_name} is attached to the frontend network")
    for service_name in ["app-01", "app-02", "nginx"]:
        code, stdout, stderr = run_command(["docker", "inspect", "-f", "{{json .NetworkSettings.Networks}}", service_name])
        if code != 0:
            ok = False
            note("FAIL", f"Could not inspect {service_name}: {stderr or stdout}")
            continue
        if service_name == "nginx" and "backend" in stdout:
            ok = False
            note("FAIL", "Nginx should not attach to the backend network")
        if service_name in {"app-01", "app-02"} and "frontend" not in stdout:
            ok = False
            note("FAIL", f"{service_name} is missing the frontend network")
        if service_name in {"app-01", "app-02"} and "backend" not in stdout:
            ok = False
            note("FAIL", f"{service_name} is missing the backend network")
    return ok


def check_host_port_exposure():
    ok = True
    code, stdout, stderr = run_command(["docker", "compose", "-p", PROJECT, "ps", "--format", "{{.Names}} {{.Ports}}"])
    if code != 0:
        note("FAIL", f"Unable to inspect project port exposure: {stderr or stdout}")
        return False
    for line in stdout.splitlines():
        name, _, ports = line.partition(" ")
        if not name or not ports:
            continue
        if name == "nginx":
            if any(f"127.0.0.1:{port}" in ports or f"0.0.0.0:{port}" in ports for port in ["8080"]):
                continue
            note("FAIL", f"Nginx is not bound to the permitted public port 8080: {ports}")
            ok = False
        elif "0.0.0.0:" in ports or "127.0.0.1:" in ports or ":" in ports:
            note("FAIL", f"Unexpected host port exposure for {name}: {ports}")
            ok = False
    return ok


def main():
    if not all(docker_service_state(service) for service in ["postgres", "redis", "app-01", "app-02", "nginx"]):
        note("FAIL", "Not all required containers are running")
        print(f"FAIL: validation aborted because docker compose -p {PROJECT} is not healthy")
        return 1

    checks = [
        check_public_access,
        check_required_endpoints,
        check_postgres_and_redis_readiness,
        check_backend_identity,
        check_record_workflow,
        check_counter_workflow,
        check_network_isolation,
        check_host_port_exposure,
    ]
    for check in checks:
        try:
            check()
        except Exception as exc:  # pragma: no cover - defensive guard for CI debugging
            note("FAIL", f"{check.__name__} raised an unexpected exception: {exc}")

    if failures:
        print(f"FAIL: {len(failures)} validation check(s) failed")
        return 1
    print("PASS: all validation checks succeeded")
    return 0


if __name__ == "__main__":
    sys.exit(main())
