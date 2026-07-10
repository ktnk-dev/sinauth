from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from typing import Any


PASSWORD_ITERATIONS = 390_000


def _b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PASSWORD_ITERATIONS)
    return f"pbkdf2_sha256${PASSWORD_ITERATIONS}${_b64encode(salt)}${_b64encode(digest)}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, iterations_raw, salt_raw, digest_raw = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        iterations = int(iterations_raw)
        salt = _b64decode(salt_raw)
        expected = _b64decode(digest_raw)
    except (ValueError, TypeError):
        return False

    actual = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations)
    return hmac.compare_digest(actual, expected)


def create_token(
    *,
    username: str,
    service: str,
    secret: str,
    ttl_seconds: int,
) -> tuple[str, int]:
    payload = {"sub": username, "service": service}
    return create_signed_payload(payload=payload, secret=secret, ttl_seconds=ttl_seconds)


def decode_token(token: str, secret: str) -> dict[str, Any]:
    payload = decode_signed_payload(token, secret)
    if not payload.get("sub") or not payload.get("service"):
        raise ValueError("invalid token claims")
    return payload


def create_signed_payload(
    *,
    payload: dict[str, Any],
    secret: str,
    ttl_seconds: int,
) -> tuple[str, int]:
    expires_at = int(time.time()) + ttl_seconds
    payload = {**payload, "exp": expires_at}
    payload_raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    body = _b64encode(payload_raw)
    signature = _sign(body, secret)
    return f"{body}.{signature}", expires_at


def decode_signed_payload(token: str, secret: str) -> dict[str, Any]:
    try:
        body, signature = token.split(".", 1)
    except ValueError as exc:
        raise ValueError("invalid token") from exc

    expected = _sign(body, secret)
    if not hmac.compare_digest(signature, expected):
        raise ValueError("invalid token signature")

    try:
        payload = json.loads(_b64decode(body))
    except (ValueError, TypeError) as exc:
        raise ValueError("invalid token payload") from exc

    expires_at = int(payload.get("exp", 0))
    if expires_at < int(time.time()):
        raise ValueError("token expired")
    return payload


def _sign(body: str, secret: str) -> str:
    digest = hmac.new(secret.encode(), body.encode(), hashlib.sha256).digest()
    return _b64encode(digest)
