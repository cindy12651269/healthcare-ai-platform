"""
Verify a captured escalation webhook delivery (Issue #35 hosted acceptance).

Save the raw request body exactly as received to a file, copy the X-Webhook-Signature
header, and run with the webhook secret in the environment (not on the command line):

    WEBHOOK_SECRET=... python -m scripts.verify_webhook --body-file body.json --signature 'sha256=...'

Exit code 0 = signature valid, 1 = invalid. Uses api.webhook.verify_signature.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

from api.webhook import verify_signature


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m scripts.verify_webhook")
    parser.add_argument("--body-file", required=True, help="raw request body, byte for byte")
    parser.add_argument("--signature", required=True, help="X-Webhook-Signature header value")
    args = parser.parse_args(argv)

    secret = os.environ.get("WEBHOOK_SECRET")
    if not secret:
        parser.error("WEBHOOK_SECRET must be set in the environment")

    with open(args.body_file, "rb") as f:
        body = f.read()

    if not verify_signature(body, args.signature, secret):
        print("INVALID signature")
        return 1

    payload = json.loads(body)
    print(f"VALID signature | event={payload.get('event')} intake_id={payload.get('intake_id')} "
          f"clinic_id={payload.get('clinic_id')} idempotency_key={payload.get('idempotency_key')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
