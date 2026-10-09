"""
Hosted acceptance check (Issue #35): synthetic flagged intake -> correct clinic's review queue,
with cross-clinic denial. The signed webhook is then checked at the receiver (scripts/verify_webhook.py).

    STAFF_A_TOKEN=... STAFF_B_TOKEN=... python -m scripts.hosted_check --api https://<api-host>

STAFF_A_TOKEN: token for demo-staff-a (clinic "default"); STAFF_B_TOKEN: token for demo-admin-b
("demo-clinic-b"). Tokens are read from the environment so they stay out of shell history.
Exit code 0 only if every check passes. Synthetic text only.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from typing import Any, Callable, Optional, Tuple
from uuid import uuid4

# (method, path, bearer token or None, JSON body or None) -> (HTTP status, parsed JSON or None)
Http = Callable[[str, str, Optional[str], Optional[dict]], Tuple[int, Any]]

CLINIC_A = "default"
CLINIC_B = "demo-clinic-b"


def urllib_http(base_url: str) -> Http:
    def call(method, path, token=None, body=None):
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        data = json.dumps(body).encode() if body is not None else None
        request = urllib.request.Request(base_url.rstrip("/") + path, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return response.status, json.loads(response.read() or b"null")
        except urllib.error.HTTPError as e:
            return e.code, None

    return call


def run(http: Http, token_a: str, token_b: str, log=print) -> Optional[str]:
    """Run every check. Returns the flagged intake id on success, None on any failure."""
    ok = True

    def check(name, condition, detail=""):
        nonlocal ok
        ok = ok and bool(condition)
        log(f"[{'PASS' if condition else 'FAIL'}] {name}{f' ({detail})' if detail else ''}")
        return condition

    status, health = http("GET", "/health", None, None)
    check("health check", status == 200 and (health or {}).get("status") == "ok", f"HTTP {status}")
    check("mock mode", (health or {}).get("llm_mode") == "mock", f"llm_mode={(health or {}).get('llm_mode')}")

    # Unique text: identical input is de-duplicated by input_hash and would not be stored again
    text = f"Synthetic demo intake {uuid4().hex[:8]}: crushing chest pain and trouble breathing since breakfast."
    status, trace = http("POST", "/api/ingest", None, {"text": text, "consent_granted": True})
    trace = trace or {}
    escalation = trace.get("escalation") or {}
    persistence = trace.get("persistence") or {}
    check("intake accepted", status == 200, f"HTTP {status}")
    check("intake flagged", escalation.get("review_status") == "needs_review", f"reasons={escalation.get('reasons')}")
    if not check("intake persisted", persistence.get("status") == "saved", f"persistence={persistence.get('status')}"):
        return None
    intake_id = persistence["record_id"]

    status, queue = http("GET", f"/api/clinics/{CLINIC_A}/intakes?review_status=needs_review", token_a, None)
    check("in clinic A review queue", status == 200 and intake_id in {r["id"] for r in queue or []}, f"HTTP {status}")

    status, _ = http("GET", f"/api/clinics/{CLINIC_A}/intakes/{intake_id}", token_b, None)
    check("clinic B denied clinic A intake", status == 403, f"HTTP {status}")

    status, queue_b = http("GET", f"/api/clinics/{CLINIC_B}/intakes", token_b, None)
    check("not in clinic B queue", status == 200 and intake_id not in {r["id"] for r in queue_b or []}, f"HTTP {status}")

    log(f"Flagged intake id: {intake_id}")
    log(f"Expect one webhook at the receiver with Idempotency-Key: intake.escalated:{intake_id}")
    return intake_id if ok else None


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m scripts.hosted_check")
    parser.add_argument("--api", required=True, help="public API base URL")
    args = parser.parse_args(argv)
    token_a, token_b = os.environ.get("STAFF_A_TOKEN"), os.environ.get("STAFF_B_TOKEN")
    if not token_a or not token_b:
        parser.error("STAFF_A_TOKEN and STAFF_B_TOKEN must be set in the environment")
    return 0 if run(urllib_http(args.api), token_a, token_b) else 1


if __name__ == "__main__":
    sys.exit(main())
