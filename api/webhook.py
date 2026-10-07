"""
Escalation notification webhook (Issue #33).

When an intake is persisted with review_status needs_review (#29), one logical notification is
sent to the configured receiver: an HMAC-SHA256-signed JSON payload built from an explicit
allowlist (intake reference and non-PHI metadata only), with a stable idempotency key, bounded
retries and a persisted delivery log (webhook_deliveries). Delivery is best-effort: no outcome
is ever raised to the caller, so a webhook problem cannot fail the patient's request.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import socket
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Literal, Optional
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict
from sqlalchemy.exc import IntegrityError

from api.config import get_settings
from db.models import HealthRecord, WebhookDelivery

logger = logging.getLogger(__name__)

EVENT_TYPE = "intake.escalated"
SCHEMA_VERSION = 1
SIGNATURE_HEADER = "X-Webhook-Signature"
IDEMPOTENCY_HEADER = "Idempotency-Key"
EVENT_HEADER = "X-Webhook-Event"
MIN_SECRET_LENGTH = 32
ESCALATED_STATUS = "needs_review"


# The complete payload. Built field by field from the persisted record; nothing else can be added.
class EscalationPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    event: Literal["intake.escalated"]
    schema_version: Literal[1]
    idempotency_key: str
    intake_id: str
    clinic_id: str


def idempotency_key_for(intake_id: str) -> str:
    # One logical notification per escalated intake: derived only from the opaque record id
    return f"{EVENT_TYPE}:{intake_id}"


def build_payload(record: HealthRecord) -> EscalationPayload:
    return EscalationPayload(
        event=EVENT_TYPE,
        schema_version=SCHEMA_VERSION,
        idempotency_key=idempotency_key_for(record.id),
        intake_id=record.id,
        clinic_id=record.clinic_id,
    )


# Canonical bytes: compact separators, sorted keys, UTF-8. The signature covers exactly these bytes.
def serialize(payload: EscalationPayload) -> bytes:
    return json.dumps(payload.model_dump(), separators=(",", ":"), sort_keys=True).encode("utf-8")


def sign(body: bytes, secret: str) -> str:
    return "sha256=" + hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


# Receiver-side check (also used by tests): recompute over the raw request body, constant-time compare
def verify_signature(body: bytes, header_value: Optional[str], secret: str) -> bool:
    if not header_value:
        return False
    return hmac.compare_digest(sign(body, secret), header_value)


def safe_target(url: str) -> str:
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc.rsplit('@', 1)[-1]}"


# Transport: returns the HTTP status, raises on timeout/connection errors. Redirects are not
# followed and response bodies are never read.
class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


_opener = urllib.request.build_opener(_NoRedirect)


def _post(url: str, body: bytes, headers: Dict[str, str], timeout: float) -> int:
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with _opener.open(request, timeout=timeout) as response:
            return response.status
    except urllib.error.HTTPError as e:
        e.close()
        return e.code


Transport = Callable[[str, bytes, Dict[str, str], float], int]


def _classify_status(status: int) -> tuple[str, bool]:
    """(outcome, retryable) for an HTTP response."""
    if 200 <= status < 300:
        return "delivered", False
    if status in (408, 429) or status >= 500:
        return f"http_{status // 100}xx" if status >= 500 else f"http_{status}", True
    return f"http_{status // 100}xx", False


def _classify_exception(exc: BaseException) -> str:
    if isinstance(exc, (socket.timeout, TimeoutError)):
        return "timeout"
    if isinstance(exc, urllib.error.URLError) and isinstance(exc.reason, (socket.timeout, TimeoutError)):
        return "timeout"
    return "connection_error"


def _config() -> Optional[Dict[str, Any]]:
    settings = get_settings()
    url, secret = settings.webhook_url, settings.webhook_secret
    if not url and not secret:
        return None
    if not url or not secret or len(secret) < MIN_SECRET_LENGTH:
        logger.warning("Escalation webhook disabled: WEBHOOK_URL and WEBHOOK_SECRET (>= 32 chars) are both required")
        return None
    if urlsplit(url).scheme not in ("http", "https"):
        logger.warning("Escalation webhook disabled: WEBHOOK_URL must be http(s)")
        return None
    return {
        "url": url,
        "secret": secret,
        "timeout": settings.webhook_timeout_seconds,
        "max_attempts": settings.webhook_max_attempts,
        "backoff": settings.webhook_retry_backoff_seconds,
    }


def _now() -> datetime:
    return datetime.now(timezone.utc)


def notify_escalation(
    record_id: str,
    *,
    session_factory,
    transport: Optional[Transport] = None,
    sleep: Optional[Callable[[float], None]] = None,
) -> Dict[str, Any]:
    """
    Send the escalation notification for a persisted intake. Never raises.

    Returns {"status": ...}: disabled | not_escalated | already_notified | delivered | failed | error.
    The status is for server logs and tests only; it is not returned to the patient.
    """
    try:
        config = _config()
        if config is None:
            return {"status": "disabled"}
        return _notify(record_id, config, session_factory, transport or _post, sleep or time.sleep)
    except Exception:
        logger.exception("Escalation webhook failed unexpectedly | intake_id=%s", record_id)
        return {"status": "error"}


def _notify(record_id, config, session_factory, transport, sleep) -> Dict[str, Any]:
    session = session_factory()
    try:
        record = session.get(HealthRecord, record_id)
        # Trigger from the persisted escalation decision only
        if record is None or record.review_status != ESCALATED_STATUS:
            return {"status": "not_escalated"}

        payload = build_payload(record)
        body = serialize(payload)
        key = payload.idempotency_key

        # Claim the logical notification: the unique key makes a second claim fail
        delivery = WebhookDelivery(
            idempotency_key=key,
            intake_id=record.id,
            event_type=EVENT_TYPE,
            target=safe_target(config["url"]),
            status="pending",
            attempts=0,
            attempt_log=[],
        )
        session.add(delivery)
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
            logger.info("Escalation webhook already handled | idempotency_key=%s", key)
            return {"status": "already_notified", "idempotency_key": key}

        # Identical bytes, signature and key for every attempt
        headers = {
            "Content-Type": "application/json",
            SIGNATURE_HEADER: sign(body, config["secret"]),
            IDEMPOTENCY_HEADER: key,
            EVENT_HEADER: EVENT_TYPE,
        }

        attempt_log = []
        for attempt in range(1, config["max_attempts"] + 1):
            http_status: Optional[int] = None
            try:
                http_status = transport(config["url"], body, headers, config["timeout"])
                outcome, retryable = _classify_status(http_status)
            except Exception as exc:
                outcome, retryable = _classify_exception(exc), True

            attempt_log.append({"attempt": attempt, "outcome": outcome, "http_status": http_status, "at": _now().isoformat()})
            delivery.attempts = attempt
            delivery.last_http_status = http_status
            delivery.last_error = None if outcome == "delivered" else outcome
            delivery.attempt_log = list(attempt_log)

            if outcome == "delivered":
                delivery.status = "delivered"
                delivery.delivered_at = _now()
                session.commit()
                break
            if not retryable or attempt == config["max_attempts"]:
                delivery.status = "failed"
                session.commit()
                break
            session.commit()
            sleep(config["backoff"] * (2 ** (attempt - 1)))

        logger.info(
            "Escalation webhook %s | idempotency_key=%s | attempts=%s | target=%s",
            delivery.status, key, delivery.attempts, delivery.target,
        )
        return {"status": delivery.status, "idempotency_key": key, "attempts": delivery.attempts}
    finally:
        session.close()
