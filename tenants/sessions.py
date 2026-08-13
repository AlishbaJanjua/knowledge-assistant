"""Signed session tokens issued after OTP verification."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from typing import Optional

from backend.config import SESSION_SECRET, data_path

SESSION_TTL_SECONDS = 7 * 24 * 60 * 60


def _secret_bytes() -> bytes:
    if SESSION_SECRET:
        return SESSION_SECRET.encode("utf-8")

    path = data_path("accounts", ".session_secret")
    os.makedirs(os.path.dirname(path), exist_ok=True)

    if os.path.isfile(path):
        with open(path, "r", encoding="utf-8") as f:
            value = f.read().strip()

        if value:
            return value.encode("utf-8")

    value = secrets.token_urlsafe(48)

    with open(path, "w", encoding="utf-8") as f:
        f.write(value)

    return value.encode("utf-8")


def create_session_token(email: str, tenant_id: str) -> str:
    payload = {
        "email": email.strip().lower(),
        "tenant_id": tenant_id,
        "exp": int(time.time()) + SESSION_TTL_SECONDS,
    }
    raw = base64.urlsafe_b64encode(
        json.dumps(payload, separators=(",", ":")).encode("utf-8")
    ).decode("ascii")
    sig = hmac.new(_secret_bytes(), raw.encode("ascii"), hashlib.sha256).hexdigest()
    return f"{raw}.{sig}"


def verify_session_token(token: str) -> Optional[dict]:
    if not token or "." not in token:
        return None

    raw, sig = token.rsplit(".", 1)
    expected = hmac.new(
        _secret_bytes(),
        raw.encode("ascii"),
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(expected, sig):
        return None

    try:
        payload = json.loads(base64.urlsafe_b64decode(raw.encode("ascii")))
    except Exception:
        return None

    if not isinstance(payload, dict):
        return None

    exp = payload.get("exp")

    if not isinstance(exp, int) or exp < int(time.time()):
        return None

    email = payload.get("email")
    tenant_id = payload.get("tenant_id")

    if not email or not tenant_id:
        return None

    return {
        "email": str(email).strip().lower(),
        "tenant_id": str(tenant_id),
    }
