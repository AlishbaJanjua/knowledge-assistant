"""Persistent multi-tenant account registry (JSON under data dir)."""

from __future__ import annotations

import json
import os
import re
import threading
from datetime import datetime, timezone
from typing import Any, Optional

from backend.config import data_path

_lock = threading.Lock()

DEFAULT_WIDGET = {
    "title": "Knowledge Assistant",
    "welcome_message": "Ask me anything about your documents.",
    "primary_color": "#141414",
    "position": "bottom-right",
}

MAX_CUSTOM_PROMPT_CHARS = 4000
MAX_COMPANY_NAME_CHARS = 120


def tenant_id_from_email(email: str) -> str:
    """Stable tenant id used by uploads, Chroma, and LangGraph memory."""

    return email.strip().lower().replace("@", "_").replace(".", "_")


def _accounts_dir() -> str:
    path = data_path("accounts")
    os.makedirs(path, exist_ok=True)
    return path


def _registry_path() -> str:
    return os.path.join(_accounts_dir(), "accounts.json")


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_registry() -> dict:
    path = _registry_path()

    if not os.path.isfile(path):
        return {}

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    return data if isinstance(data, dict) else {}


def _save_registry(registry: dict) -> None:
    path = _registry_path()
    tmp = path + ".tmp"

    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(registry, f, indent=2)

    os.replace(tmp, path)


def _sanitize_widget(widget: Optional[dict]) -> dict:
    base = dict(DEFAULT_WIDGET)

    if not isinstance(widget, dict):
        return base

    title = str(widget.get("title") or base["title"]).strip()[:80]
    welcome = str(widget.get("welcome_message") or base["welcome_message"]).strip()[:300]
    color = str(widget.get("primary_color") or base["primary_color"]).strip()
    position = str(widget.get("position") or base["position"]).strip().lower()

    if not re.fullmatch(r"#[0-9a-fA-F]{6}", color):
        color = base["primary_color"]

    if position not in ("bottom-right", "bottom-left"):
        position = base["position"]

    return {
        "title": title or base["title"],
        "welcome_message": welcome or base["welcome_message"],
        "primary_color": color,
        "position": position,
    }


def public_account_view(account: dict) -> dict:
    """Fields safe to return to the authenticated client (includes custom_prompt)."""

    return {
        "tenant_id": account["tenant_id"],
        "email": account["email"],
        "company_name": account.get("company_name", ""),
        "custom_prompt": account.get("custom_prompt", ""),
        "widget": account.get("widget") or dict(DEFAULT_WIDGET),
        "created_at": account.get("created_at"),
    }


def public_widget_view(account: dict) -> dict:
    """Non-sensitive widget settings for embed/public use."""

    return {
        "tenant_id": account["tenant_id"],
        "company_name": account.get("company_name", ""),
        "widget": account.get("widget") or dict(DEFAULT_WIDGET),
    }


def get_account_by_email(email: str) -> Optional[dict]:
    key = _normalize_email(email)

    with _lock:
        registry = _load_registry()
        account = registry.get(key)

    return dict(account) if account else None


def get_account_by_tenant_id(tenant_id: str) -> Optional[dict]:
    tid = (tenant_id or "").strip()

    with _lock:
        registry = _load_registry()

        for account in registry.values():
            if account.get("tenant_id") == tid:
                return dict(account)

    return None


def account_exists(email: str) -> bool:
    return get_account_by_email(email) is not None


def create_account(
    email: str,
    company_name: str,
    custom_prompt: str = "",
    widget: Optional[dict] = None,
) -> dict:
    key = _normalize_email(email)
    company = (company_name or "").strip()

    if not key or "@" not in key:
        raise ValueError("A valid email is required.")

    if not company:
        raise ValueError("Company name is required.")

    if len(company) > MAX_COMPANY_NAME_CHARS:
        raise ValueError("Company name is too long.")

    prompt = (custom_prompt or "").strip()

    if len(prompt) > MAX_CUSTOM_PROMPT_CHARS:
        raise ValueError(
            f"Custom prompt must be at most {MAX_CUSTOM_PROMPT_CHARS} characters."
        )

    account = {
        "tenant_id": tenant_id_from_email(key),
        "email": key,
        "company_name": company,
        "custom_prompt": prompt,
        "widget": _sanitize_widget(widget),
        "created_at": _now_iso(),
    }

    with _lock:
        registry = _load_registry()

        if key in registry:
            raise ValueError("An account with this email already exists.")

        registry[key] = account
        _save_registry(registry)

    return dict(account)


def update_account(
    email: str,
    *,
    company_name: Optional[str] = None,
    custom_prompt: Optional[str] = None,
    widget: Optional[dict] = None,
) -> dict:
    key = _normalize_email(email)

    with _lock:
        registry = _load_registry()
        account = registry.get(key)

        if not account:
            raise ValueError("Account not found.")

        if company_name is not None:
            company = company_name.strip()

            if not company:
                raise ValueError("Company name is required.")

            if len(company) > MAX_COMPANY_NAME_CHARS:
                raise ValueError("Company name is too long.")

            account["company_name"] = company

        if custom_prompt is not None:
            prompt = custom_prompt.strip()

            if len(prompt) > MAX_CUSTOM_PROMPT_CHARS:
                raise ValueError(
                    f"Custom prompt must be at most {MAX_CUSTOM_PROMPT_CHARS} characters."
                )

            account["custom_prompt"] = prompt

        if widget is not None:
            account["widget"] = _sanitize_widget(widget)

        registry[key] = account
        _save_registry(registry)
        return dict(account)
