from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class MonitoringConfig:
    poll_min_seconds: int = 60
    poll_max_seconds: int = 90


DEFAULT_MIN = 60
DEFAULT_MAX = 90


def _parse_int(raw: str | int | None, name: str) -> int | None:
    if raw is None:
        return None
    if isinstance(raw, int):
        return raw
    s = str(raw).strip()
    if not s:
        return None
    try:
        # Only integer strings allowed
        if "." in s:
            raise ValueError()
        return int(s)
    except (ValueError, TypeError) as e:
        raise ValueError(f"{name} must be an integer, got {raw!r}") from e


def load_monitoring_config(env: dict | None = None) -> MonitoringConfig:
    """Load POLL_MIN_SECONDS and POLL_MAX_SECONDS from env with validation.

    Defaults: 60 and 90 seconds (MVP random 60-90 interval).
    Raises ValueError for invalid values or when min > max.
    """
    source = env if env is not None else os.environ
    # support both dict and os.environ
    try:
        raw_min = source.get("POLL_MIN_SECONDS")  # type: ignore[attr-defined]
    except Exception:
        raw_min = None
    try:
        raw_max = source.get("POLL_MAX_SECONDS")  # type: ignore[attr-defined]
    except Exception:
        raw_max = None

    poll_min = _parse_int(raw_min, "POLL_MIN_SECONDS")
    poll_max = _parse_int(raw_max, "POLL_MAX_SECONDS")

    if poll_min is None:
        poll_min = DEFAULT_MIN
    if poll_max is None:
        poll_max = DEFAULT_MAX

    if poll_min <= 0:
        raise ValueError("POLL_MIN_SECONDS must be > 0")
    if poll_max <= 0:
        raise ValueError("POLL_MAX_SECONDS must be > 0")
    if poll_min > poll_max:
        raise ValueError(f"POLL_MIN_SECONDS ({poll_min}) cannot be greater than POLL_MAX_SECONDS ({poll_max})")

    return MonitoringConfig(poll_min_seconds=poll_min, poll_max_seconds=poll_max)
