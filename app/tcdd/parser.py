from __future__ import annotations

import datetime
from typing import Any

from .exceptions import TcddUnexpectedResponseError
from .models import TrainAvailability

# Booking class mapping – validated via /datas/booking-classes.json
ECONOMY_BC_ID = 1
BUSINESS_BC_ID = 4
ACCESSIBLE_BC_ID = 23
SPECIAL_BC_IDS = {22, 7, 8, 24, 26}


def _epoch_ms_to_local(ms: int, tz_name: str = "Europe/Istanbul") -> datetime.datetime:
    dt_utc = datetime.datetime.fromtimestamp(ms / 1000, tz=datetime.timezone.utc)
    try:
        import zoneinfo

        tz = zoneinfo.ZoneInfo(tz_name)
        return dt_utc.astimezone(tz)
    except Exception:
        return dt_utc


def _parse_travel_date_norm(travel_date: str | datetime.date | datetime.datetime) -> str:
    """Return YYYY-MM-DD normalized date string."""
    if isinstance(travel_date, datetime.datetime):
        return travel_date.strftime("%Y-%m-%d")
    if isinstance(travel_date, datetime.date):
        return travel_date.strftime("%Y-%m-%d")
    s = str(travel_date).strip()
    # Accept DD.MM.YYYY or DD-MM-YYYY or YYYY-MM-DD
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            dt = datetime.datetime.strptime(s[:10], fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue
    # If already YYYY-MM-DD with extra time, just take first 10
    if len(s) >= 10 and s[4] == "-" and s[7] == "-":
        return s[:10]
    raise TcddUnexpectedResponseError(f"invalid travel_date format {travel_date!r}")


def _extract_economy(booking_caps: Any) -> int:
    if not isinstance(booking_caps, list):
        return 0
    cap_by_id: dict[int, int] = {}
    for c in booking_caps:
        if not isinstance(c, dict):
            continue
        bc_id = c.get("bookingClassId")
        cap = c.get("capacity")
        try:
            bc_id_int = int(bc_id) if bc_id is not None else None
            cap_int = int(cap) if cap is not None else 0
        except Exception:
            continue
        if bc_id_int is not None:
            cap_by_id[bc_id_int] = cap_int
    return int(cap_by_id.get(ECONOMY_BC_ID, 0))


def parse_train_availability(raw: Any, travel_date: str | datetime.date | datetime.datetime) -> list[TrainAvailability]:
    """Parse verified TCDD train-availability response into normalized records.

    - Validates top-level container shape; raises TcddUnexpectedResponseError on incompatible shape.
    - Does NOT return [] for shape failures.
    - Filters by requested travel date using local departure date.
    - Extracts only normal economy category 1; business 4, accessible 23, special 22 etc. are ignored.
    - Returns empty list only for valid responses with no matching trains (VALID_EMPTY).
    """
    if not isinstance(raw, dict):
        raise TcddUnexpectedResponseError(f"expected dict response, got {type(raw).__name__}")

    if "trainLegs" not in raw:
        raise TcddUnexpectedResponseError("missing 'trainLegs' in response")

    legs = raw.get("trainLegs")
    if not isinstance(legs, list):
        raise TcddUnexpectedResponseError("'trainLegs' expected list")

    travel_date_norm = _parse_travel_date_norm(travel_date)

    out: list[TrainAvailability] = []

    for leg in legs:
        if not isinstance(leg, dict):
            continue
        # trainAvailabilities may be missing -> skip leg? If leg has no trainAvailabilities, it's valid empty for that leg
        t_avails = leg.get("trainAvailabilities")
        if t_avails is None:
            continue
        if not isinstance(t_avails, list):
            raise TcddUnexpectedResponseError("'trainAvailabilities' expected list")
        for ta in t_avails:
            if not isinstance(ta, dict):
                continue
            trains = ta.get("trains")
            if trains is None:
                continue
            if not isinstance(trains, list):
                raise TcddUnexpectedResponseError("'trains' expected list")
            for train in trains:
                if not isinstance(train, dict):
                    continue
                try:
                    segs = train.get("segments")
                    if not segs or not isinstance(segs, list):
                        continue
                    dep_ms = segs[0].get("departureTime") if isinstance(segs[0], dict) else None
                    arr_ms = segs[-1].get("arrivalTime") if isinstance(segs[-1], dict) else None
                    if dep_ms is None or arr_ms is None:
                        continue
                    dep_local = _epoch_ms_to_local(int(dep_ms))
                    arr_local = _epoch_ms_to_local(int(arr_ms))
                    dep_date = dep_local.strftime("%Y-%m-%d")
                    # Filter by requested travel date
                    if dep_date != travel_date_norm:
                        continue

                    # Extract identifiers
                    train_id = train.get("id", "")
                    # name and number - fallbacks
                    train_name = str(train.get("name", "") or train.get("commercialName", ""))
                    train_number = str(train.get("number", ""))
                    # booking capacities
                    booking_caps = train.get("bookingClassCapacities")
                    # If bookingClassCapacities is missing, we treat as 0 economy but still produce record?
                    # Require usable capacities; if None, treat as 0
                    economy = _extract_economy(booking_caps) if booking_caps is not None else 0

                    # Ensure we produce valid record; train_id must be present? If missing, skip
                    # Keep train_id as int or str
                    if train_id == "" or train_id is None:
                        # skip train with no identifier
                        continue

                    out.append(
                        TrainAvailability(
                            train_id=train_id,
                            train_name=train_name,
                            train_number=train_number,
                            departure_at=dep_local,
                            arrival_at=arr_local,
                            economy_available=int(economy),
                        )
                    )
                except TcddUnexpectedResponseError:
                    raise
                except Exception:
                    # Skip malformed train entry individually; do not fail whole response for one bad train
                    continue

    return out
