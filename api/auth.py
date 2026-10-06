"""
Staff authentication, role checks and clinic isolation (Issue #28).

Staff send `Authorization: Bearer <token>`. A token is an HMAC-SHA256-signed
`{"sub": <user id>, "exp": <unix time>}` payload; the signing key is
AUTH_TOKEN_SECRET from the server environment. Tokens are issued by an
operator with this module's CLI, never by the browser-facing API:

    python -m api.auth create-user --email admin@clinic.test --clinic default --role clinic_admin
    python -m api.auth issue-token --user-id <id>

Every request re-reads the user's clinic memberships from the database, so a
removed membership or role change takes effect immediately. Clinic access is
always decided from those memberships, never from a client-supplied clinic id.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from typing import Callable, Dict, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from api.config import get_settings
from db.models import ROLES, ClinicMembership, User
from db.session import get_db

TOKEN_VERSION = "v1"
MIN_SECRET_LENGTH = 32

_bearer = HTTPBearer(auto_error=False)


class InvalidToken(Exception):
    pass


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(data: str) -> bytes:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))


def _secret() -> bytes:
    secret = get_settings().auth_token_secret
    if not secret or len(secret) < MIN_SECRET_LENGTH:
        raise RuntimeError(f"AUTH_TOKEN_SECRET must be set to at least {MIN_SECRET_LENGTH} characters")
    return secret.encode()


def _sign(message: str, secret: bytes) -> str:
    return _b64(hmac.new(secret, message.encode(), hashlib.sha256).digest())


def issue_token(user_id: str, ttl_seconds: int, *, now: Optional[float] = None) -> str:
    payload = {"sub": user_id, "exp": int((now or time.time()) + ttl_seconds)}
    message = f"{TOKEN_VERSION}.{_b64(json.dumps(payload, separators=(',', ':')).encode())}"
    return f"{message}.{_sign(message, _secret())}"


def verify_token(token: str, *, now: Optional[float] = None) -> str:
    """Return the user id of a valid, unexpired token; raise InvalidToken otherwise."""
    try:
        version, body, signature = token.split(".")
    except ValueError:
        raise InvalidToken("malformed token") from None
    if version != TOKEN_VERSION:
        raise InvalidToken("unsupported token version")
    # Compare bytes: compare_digest raises TypeError on non-ASCII str input
    expected = _sign(f"{version}.{body}", _secret())
    if not hmac.compare_digest(signature.encode(), expected.encode()):
        raise InvalidToken("bad signature")
    try:
        payload = json.loads(_unb64(body))
        user_id, expires = payload["sub"], payload["exp"]
    except (ValueError, KeyError, TypeError):
        raise InvalidToken("malformed payload") from None
    if not isinstance(user_id, str) or not isinstance(expires, int):
        raise InvalidToken("malformed payload")
    if expires <= (now or time.time()):
        raise InvalidToken("token expired")
    return user_id


# FastAPI dependencies

@dataclass(frozen=True)
class Principal:
    user_id: str
    email: str
    roles: Dict[str, str]  # clinic_id -> role, from clinic_memberships


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_principal(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
    db: Session = Depends(get_db),
) -> Principal:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _unauthorized("Not authenticated")
    try:
        user_id = verify_token(credentials.credentials)
    except RuntimeError:
        # Server misconfiguration: refuse staff access rather than accept unsigned tokens
        raise HTTPException(status_code=503, detail="Staff authentication is not configured") from None
    except InvalidToken:
        raise _unauthorized("Invalid or expired token") from None

    user = db.get(User, user_id)
    if user is None:
        raise _unauthorized("Invalid or expired token")

    memberships = db.query(ClinicMembership).filter(ClinicMembership.user_id == user.id)
    return Principal(user_id=user.id, email=user.email, roles={m.clinic_id: m.role for m in memberships})


def require_clinic_role(*allowed_roles: str) -> Callable[..., Principal]:
    """
    Dependency for routes with a `{clinic_id}` path parameter: the caller must be a
    member of that clinic with one of `allowed_roles` (403 otherwise).
    """
    unknown = set(allowed_roles) - set(ROLES)
    if unknown:
        raise ValueError(f"Unknown roles: {sorted(unknown)}")

    def dependency(clinic_id: str, principal: Principal = Depends(get_current_principal)) -> Principal:
        role = principal.roles.get(clinic_id)
        if role is None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a member of this clinic")
        if role not in allowed_roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role for this clinic")
        return principal

    return dependency


# Operator CLI (bootstrap users and issue tokens; not exposed over HTTP)

def _main(argv=None) -> None:
    from db.models import Clinic
    from db.session import transactional_session

    parser = argparse.ArgumentParser(prog="python -m api.auth")
    sub = parser.add_subparsers(dest="command", required=True)

    create = sub.add_parser("create-user", help="create a user, optionally with a clinic membership")
    create.add_argument("--email", required=True)
    create.add_argument("--display-name")
    create.add_argument("--clinic")
    create.add_argument("--role", choices=ROLES)

    issue = sub.add_parser("issue-token", help="print a bearer token for an existing user")
    issue.add_argument("--user-id", required=True)
    issue.add_argument("--ttl-hours", type=float, default=get_settings().auth_token_ttl_hours)

    args = parser.parse_args(argv)

    if args.command == "create-user":
        if bool(args.clinic) != bool(args.role):
            parser.error("--clinic and --role must be given together")
        with transactional_session() as db:
            user = User(email=args.email, display_name=args.display_name)
            db.add(user)
            db.flush()
            if args.clinic:
                if db.get(Clinic, args.clinic) is None:
                    parser.error(f"unknown clinic: {args.clinic}")
                db.add(ClinicMembership(user_id=user.id, clinic_id=args.clinic, role=args.role))
            print(user.id)
    else:
        with transactional_session() as db:
            if db.get(User, args.user_id) is None:
                parser.error(f"unknown user: {args.user_id}")
        print(issue_token(args.user_id, int(args.ttl_hours * 3600)))


if __name__ == "__main__":
    _main()
