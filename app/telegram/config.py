from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TelegramConfig:
    token: str
    allowed_user_id: int


def load_telegram_config(env: dict | None = None) -> TelegramConfig:
    """Load TELEGRAM_BOT_TOKEN and TELEGRAM_ALLOWED_USER_ID from env.

    Rejects missing/empty/invalid values without exposing token contents.
    env may be a dict for testing; defaults to os.environ.
    """
    source = env if env is not None else os.environ
    # source.get works for both dict and os.environ
    try:
        token = source.get("TELEGRAM_BOT_TOKEN")  # type: ignore[attr-defined]
        raw_id = source.get("TELEGRAM_ALLOWED_USER_ID")  # type: ignore[attr-defined]
    except Exception:
        token = None
        raw_id = None

    # Do not include token value in error messages/logs
    if token is None or not str(token).strip():
        raise ValueError("TELEGRAM_BOT_TOKEN is required")
    token = str(token).strip()

    if raw_id is None or not str(raw_id).strip():
        raise ValueError("TELEGRAM_ALLOWED_USER_ID is required")
    raw_str = str(raw_id).strip()
    try:
        uid = int(raw_str)
    except (ValueError, TypeError) as e:
        raise ValueError("TELEGRAM_ALLOWED_USER_ID must be an integer") from e
    if uid <= 0:
        raise ValueError("TELEGRAM_ALLOWED_USER_ID must be a positive integer")

    return TelegramConfig(token=token, allowed_user_id=uid)
