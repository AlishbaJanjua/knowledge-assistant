"""Email OTP helpers for the existing email-gate login flow.

OTPs are stored in-process (temporary). They expire, are single-use,
and are never logged. Resend delivers the email.
"""

from __future__ import annotations

import hashlib
import logging
import secrets
import threading
import time
from typing import Optional

import resend

from backend.config import FROM_EMAIL, RESEND_API_KEY

logger = logging.getLogger(__name__)

OTP_LENGTH = 6
OTP_TTL_SECONDS = 10 * 60
OTP_REQUEST_COOLDOWN_SECONDS = 60
OTP_MAX_VERIFY_ATTEMPTS = 5

_lock = threading.Lock()
# email -> { hash, expires_at, last_sent_at, attempts }
_otp_store: dict[str, dict] = {}


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _hash_otp(email: str, otp: str) -> str:
    payload = f"{_normalize_email(email)}:{otp}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def generate_otp() -> str:
    """Secure random 6-digit code (000000–999999)."""

    return f"{secrets.randbelow(10 ** OTP_LENGTH):0{OTP_LENGTH}d}"


def _purge_expired(now: Optional[float] = None) -> None:
    now = time.time() if now is None else now
    expired = [
        email
        for email, record in _otp_store.items()
        if record["expires_at"] <= now
    ]
    for email in expired:
        del _otp_store[email]


def cooldown_remaining(email: str) -> int:
    """Seconds until another OTP may be requested (0 if allowed)."""

    key = _normalize_email(email)
    now = time.time()

    with _lock:
        _purge_expired(now)
        record = _otp_store.get(key)

        if not record:
            return 0

        wait = int(record["last_sent_at"] + OTP_REQUEST_COOLDOWN_SECONDS - now)
        return max(0, wait)


def create_and_store_otp(email: str) -> tuple[str, int]:
    """Create a new OTP for email. Returns (otp, expires_in_seconds)."""

    key = _normalize_email(email)
    otp = generate_otp()
    now = time.time()

    with _lock:
        _purge_expired(now)
        _otp_store[key] = {
            "hash": _hash_otp(key, otp),
            "expires_at": now + OTP_TTL_SECONDS,
            "last_sent_at": now,
            "attempts": 0,
        }

    return otp, OTP_TTL_SECONDS


def verify_otp(email: str, otp: str) -> tuple[bool, str]:
    """Verify OTP. On success the code is consumed (single-use).

    Returns (ok, error_code) where error_code is empty on success.
    """

    key = _normalize_email(email)
    code = (otp or "").strip()
    now = time.time()

    if not code.isdigit() or len(code) != OTP_LENGTH:
        return False, "invalid"

    with _lock:
        _purge_expired(now)
        record = _otp_store.get(key)

        if not record:
            return False, "expired"

        if record["expires_at"] <= now:
            del _otp_store[key]
            return False, "expired"

        if record["attempts"] >= OTP_MAX_VERIFY_ATTEMPTS:
            del _otp_store[key]
            return False, "locked"

        record["attempts"] += 1

        if not secrets.compare_digest(record["hash"], _hash_otp(key, code)):
            if record["attempts"] >= OTP_MAX_VERIFY_ATTEMPTS:
                del _otp_store[key]
                return False, "locked"
            return False, "invalid"

        # Single-use: remove after successful verification.
        del _otp_store[key]
        return True, ""


def clear_otp(email: str) -> None:
    """Remove any pending OTP for an email (e.g. after send failure)."""

    key = _normalize_email(email)

    with _lock:
        _otp_store.pop(key, None)


def send_otp_email(email: str, otp: str) -> None:
    """Send the OTP via Resend. Never log the OTP or API key."""

    if not RESEND_API_KEY:
        raise RuntimeError("RESEND_API_KEY is not configured.")

    if not FROM_EMAIL:
        raise RuntimeError("FROM_EMAIL is not configured.")

    resend.api_key = RESEND_API_KEY

    resend.Emails.send(
        {
            "from": FROM_EMAIL,
            "to": [_normalize_email(email)],
            "subject": "Your Knowledge Assistant verification code",
            "html": (
                "<p>Your verification code is:</p>"
                f"<p style='font-size:24px;font-weight:700;letter-spacing:4px'>"
                f"{otp}</p>"
                "<p>This code expires in 10 minutes. "
                "If you did not request it, you can ignore this email.</p>"
            ),
        }
    )
    logger.info("OTP email dispatched for %s", _normalize_email(email))
