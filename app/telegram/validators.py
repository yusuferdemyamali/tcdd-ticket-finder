from __future__ import annotations

import datetime
import re
from zoneinfo import ZoneInfo

ISTANBUL_TZ = ZoneInfo("Europe/Istanbul")

DATE_RE = re.compile(r"^\d{2}\.\d{2}\.\d{4}$")
TIME_RE = re.compile(r"^\d{2}:\d{2}$")


def validate_date_strict(date_str: str, now_fn=None) -> str:
    """Validate DD.MM.YYYY strict and reject past dates in Europe/Istanbul.

    Returns YYYY-MM-DD domain value on success.
    Raises ValueError with user-friendly message on failure.
    """
    if not isinstance(date_str, str):
        raise ValueError("Tarih DD.MM.YYYY formatında olmalıdır. Örnek: 15.09.2026")
    s = date_str.strip()
    if not DATE_RE.match(s):
        raise ValueError("Tarih DD.MM.YYYY formatında olmalıdır. Örnek: 15.09.2026")

    try:
        dt = datetime.datetime.strptime(s, "%d.%m.%Y")
    except ValueError as e:
        raise ValueError("Geçersiz tarih. Örnek: 15.09.2026") from e

    travel_date = dt.date()

    # Determine today in Europe/Istanbul
    if now_fn is not None:
        now_dt = now_fn()
        if now_dt.tzinfo is None:
            now_dt = now_dt.replace(tzinfo=ISTANBUL_TZ)
        today = now_dt.astimezone(ISTANBUL_TZ).date()
    else:
        today = datetime.datetime.now(ISTANBUL_TZ).date()

    if travel_date < today:
        raise ValueError("Geçmiş bir tarih giremezsin. Lütfen bugünden itibaren bir tarih gir.")

    # Return domain format YYYY-MM-DD
    return travel_date.strftime("%Y-%m-%d")


def format_display_date(yyyy_mm_dd: str) -> str:
    """Convert YYYY-MM-DD to DD.MM.YYYY for display."""
    try:
        dt = datetime.datetime.strptime(yyyy_mm_dd, "%Y-%m-%d")
        return dt.strftime("%d.%m.%Y")
    except Exception:
        return yyyy_mm_dd


def validate_time_strict(time_str: str) -> str:
    """Validate HH:MM zero-padded; raise ValueError if invalid."""
    if not isinstance(time_str, str):
        raise ValueError("Saat HH:MM formatında olmalıdır. Örnek: 17:00")
    s = time_str.strip()
    if not TIME_RE.match(s):
        raise ValueError("Saat HH:MM formatında olmalıdır. Örnek: 17:00")
    try:
        dt = datetime.datetime.strptime(s, "%H:%M")
    except ValueError as e:
        raise ValueError("Geçersiz saat. Örnek: 17:00") from e
    # Extra ensure zero-padded matches strftime
    if dt.strftime("%H:%M") != s:
        raise ValueError("Saat HH:MM formatında olmalıdır. Örnek: 17:00")
    # hour 00-23 already ensured, minute 00-59
    return s


def validate_time_window(from_time: str, to_time: str) -> None:
    """Validate from <= to (inclusive), reject midnight crossing.

    Assumes both already validated HH:MM.
    Raises ValueError if from > to.
    """
    if from_time > to_time:
        raise ValueError("Başlangıç saati bitiş saatinden sonra olamaz. Gece yarısını geçen aralık desteklenmiyor.")
