from __future__ import annotations

import datetime
import json
import sqlite3
from zoneinfo import ZoneInfo

from .exceptions import (
    TicketSearchConflictError,
    TicketSearchNotFoundError,
    TicketSearchTransitionError,
    TicketSearchValidationError,
)
from .models import TicketSearch, TicketSearchStatus
from .repository import TicketSearchRepository

ISTANBUL_TZ = ZoneInfo("Europe/Istanbul")

ALLOWED_TRANSITIONS: dict[TicketSearchStatus, set[TicketSearchStatus]] = {
    TicketSearchStatus.ACTIVE: {
        TicketSearchStatus.FOUND,
        TicketSearchStatus.CANCELLED,
        TicketSearchStatus.EXPIRED,
    },
    TicketSearchStatus.FOUND: {TicketSearchStatus.COMPLETED},
    TicketSearchStatus.COMPLETED: {TicketSearchStatus.ACTIVE},
}


def _parse_date(value: str) -> datetime.date:
    try:
        return datetime.datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        raise TicketSearchValidationError(f"invalid travel_date {value!r}, expected YYYY-MM-DD")


def _parse_time(value: str) -> datetime.time:
    try:
        return datetime.datetime.strptime(value, "%H:%M").time()
    except ValueError:
        raise TicketSearchValidationError(f"invalid time {value!r}, expected HH:MM")


class TicketSearchService:
    def __init__(self, repo: TicketSearchRepository, now=None) -> None:
        self._repo = repo
        self._now = now

    def _now_dt(self) -> datetime.datetime:
        if self._now is not None:
            dt = self._now()
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=ISTANBUL_TZ)
            return dt
        return datetime.datetime.now(ISTANBUL_TZ)

    def _now_iso(self) -> str:
        return self._now_dt().isoformat()

    def _validate_create_inputs(self, travel_date: str, departure_time_from: str, departure_time_to: str) -> None:
        # travel date not past
        today = self._now_dt().date()
        td = _parse_date(travel_date)
        if td < today:
            raise TicketSearchValidationError(f"travel_date {travel_date} is in the past (today {today} Europe/Istanbul)")
        # time format and window
        _parse_time(departure_time_from)
        _parse_time(departure_time_to)
        if departure_time_from > departure_time_to:
            raise TicketSearchValidationError(f"departure_time_from {departure_time_from} > departure_time_to {departure_time_to}: midnight-crossing not allowed")

    def create_search(
        self,
        origin_station_id: int,
        origin_station_name: str,
        destination_station_id: int,
        destination_station_name: str,
        travel_date: str,
        departure_time_from: str,
        departure_time_to: str,
    ) -> TicketSearch:
        self._validate_create_inputs(travel_date, departure_time_from, departure_time_to)
        # single ACTIVE invariant check service level
        existing = self._repo.get_active()
        if existing is not None:
            raise TicketSearchConflictError("an ACTIVE search already exists")
        now_iso = self._now_iso()
        search = TicketSearch(
            id=None,
            origin_station_id=int(origin_station_id),
            origin_station_name=str(origin_station_name),
            destination_station_id=int(destination_station_id),
            destination_station_name=str(destination_station_name),
            travel_date=travel_date,
            departure_time_from=departure_time_from,
            departure_time_to=departure_time_to,
            status=TicketSearchStatus.ACTIVE,
            created_at=now_iso,
            updated_at=now_iso,
        )
        try:
            return self._repo.create(search)
        except sqlite3.IntegrityError as e:
            # partial unique index violation
            if "ACTIVE" in str(e) or "unique" in str(e).lower():
                raise TicketSearchConflictError("an ACTIVE search already exists") from e
            raise

    def get_search(self, search_id: int) -> TicketSearch:
        s = self._repo.get_by_id(search_id)
        if s is None:
            raise TicketSearchNotFoundError(f"search {search_id} not found")
        return s

    def get_active_search(self) -> TicketSearch | None:
        return self._repo.get_active()

    def _validate_transition(self, old: TicketSearchStatus, new: TicketSearchStatus) -> None:
        allowed = ALLOWED_TRANSITIONS.get(old, set())
        if new not in allowed:
            raise TicketSearchTransitionError(f"invalid transition {old.value} -> {new.value}")

    def mark_found(self, search_id: int, trains=None) -> TicketSearch:
        s = self.get_search(search_id)
        self._validate_transition(s.status, TicketSearchStatus.FOUND)
        s.status = TicketSearchStatus.FOUND
        now_iso = self._now_iso()
        s.found_at = now_iso
        s.updated_at = now_iso
        if trains is not None:
            try:
                s.found_trains_json = self._serialize_trains(trains)
            except Exception:
                pass
        try:
            return self._repo.update(s)
        except sqlite3.IntegrityError as e:
            raise TicketSearchConflictError(str(e)) from e

    def mark_completed(self, search_id: int) -> TicketSearch:
        s = self.get_search(search_id)
        self._validate_transition(s.status, TicketSearchStatus.COMPLETED)
        s.status = TicketSearchStatus.COMPLETED
        now_iso = self._now_iso()
        s.completed_at = now_iso
        s.updated_at = now_iso
        return self._repo.update(s)

    def cancel_search(self, search_id: int) -> TicketSearch:
        s = self.get_search(search_id)
        self._validate_transition(s.status, TicketSearchStatus.CANCELLED)
        s.status = TicketSearchStatus.CANCELLED
        now_iso = self._now_iso()
        s.cancelled_at = now_iso
        s.updated_at = now_iso
        return self._repo.update(s)

    def expire_search(self, search_id: int) -> TicketSearch:
        s = self.get_search(search_id)
        self._validate_transition(s.status, TicketSearchStatus.EXPIRED)
        s.status = TicketSearchStatus.EXPIRED
        now_iso = self._now_iso()
        s.expired_at = now_iso
        s.updated_at = now_iso
        return self._repo.update(s)

    def restart_search(self, search_id: int) -> TicketSearch:
        s = self.get_search(search_id)
        self._validate_transition(s.status, TicketSearchStatus.ACTIVE)
        # must be COMPLETED -> ACTIVE
        # check travel window not passed
        # window end = travel_date + departure_time_to in Istanbul
        try:
            travel_time_str = f"{s.travel_date} {s.departure_time_to}"
            travel_dt = datetime.datetime.strptime(travel_time_str, "%Y-%m-%d %H:%M")
            travel_dt = travel_dt.replace(tzinfo=ISTANBUL_TZ)
        except Exception as e:
            raise TicketSearchValidationError(f"invalid travel_date/time: {e}") from e
        now_dt = self._now_dt()
        if now_dt > travel_dt:
            raise TicketSearchValidationError(
                f"travel window already passed in Europe/Istanbul: now {now_dt.isoformat()} > travel window end {travel_dt.isoformat()}"
            )
        # single ACTIVE invariant
        existing = self._repo.get_active()
        if existing is not None:
            raise TicketSearchConflictError("an ACTIVE search already exists, cannot restart")
        # Clear lifecycle timestamps for new run
        s.status = TicketSearchStatus.ACTIVE
        s.found_at = None
        s.completed_at = None
        s.cancelled_at = None
        s.expired_at = None
        s.found_trains_json = None
        # Reset monitoring outage state for fresh polling run
        s.tcdd_outage_notified = False
        s.last_tcdd_error_at = None
        s.next_check_at = None
        s.updated_at = self._now_iso()
        try:
            return self._repo.update(s)
        except sqlite3.IntegrityError as e:
            raise TicketSearchConflictError("an ACTIVE search already exists") from e

    def replace_active_search(
        self,
        origin_station_id: int,
        origin_station_name: str,
        destination_station_id: int,
        destination_station_name: str,
        travel_date: str,
        departure_time_from: str,
        departure_time_to: str,
    ) -> TicketSearch:
        # validate inputs first, before transaction
        self._validate_create_inputs(travel_date, departure_time_from, departure_time_to)
        now_iso = self._now_iso()
        conn = self._repo.conn
        try:
            conn.execute("BEGIN IMMEDIATE")
            old = self._repo.get_active()
            # if we have old, cancel it
            if old is not None:
                # Use direct SQL to keep within transaction (avoid repo auto-commit)
                conn.execute(
                    "UPDATE ticket_searches SET status = ?, cancelled_at = ?, updated_at = ? WHERE id = ?",
                    (TicketSearchStatus.CANCELLED.value, now_iso, now_iso, old.id),
                )
            # insert new ACTIVE
            cur = conn.execute(
                """
                INSERT INTO ticket_searches (
                    origin_station_id, origin_station_name,
                    destination_station_id, destination_station_name,
                    travel_date, departure_time_from, departure_time_to,
                    status,
                    last_checked_at, last_successful_check_at, next_check_at,
                    tcdd_outage_notified, last_tcdd_error_at,
                    found_trains_json,
                    found_at, completed_at, cancelled_at, expired_at,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    int(origin_station_id),
                    str(origin_station_name),
                    int(destination_station_id),
                    str(destination_station_name),
                    travel_date,
                    departure_time_from,
                    departure_time_to,
                    TicketSearchStatus.ACTIVE.value,
                    None,
                    None,
                    None,
                    0,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    now_iso,
                    now_iso,
                ),
            )
            new_id = cur.lastrowid
            conn.commit()
            result = self._repo.get_by_id(new_id)
            assert result is not None
            return result
        except sqlite3.IntegrityError as e:
            try:
                conn.rollback()
            except Exception:
                pass
            raise TicketSearchConflictError(f"replace failed: {e}") from e
        except TicketSearchValidationError:
            try:
                conn.rollback()
            except Exception:
                pass
            raise
        except Exception as e:
            try:
                conn.rollback()
            except Exception:
                pass
            raise

    # --- Monitoring metadata durable updates ---

    def record_check_attempt(self, search_id: int) -> TicketSearch:
        s = self.get_search(search_id)
        s.last_checked_at = self._now_iso()
        s.updated_at = self._now_iso()
        return self._repo.update(s)

    def record_successful_check(self, search_id: int) -> TicketSearch:
        s = self.get_search(search_id)
        now_iso = self._now_iso()
        s.last_checked_at = now_iso
        s.last_successful_check_at = now_iso
        s.updated_at = now_iso
        return self._repo.update(s)

    def record_tcdd_error(self, search_id: int) -> TicketSearch:
        s = self.get_search(search_id)
        now_iso = self._now_iso()
        s.last_checked_at = now_iso
        s.last_tcdd_error_at = now_iso
        s.updated_at = now_iso
        return self._repo.update(s)

    def set_next_check_at(self, search_id: int, next_check_at: str) -> TicketSearch:
        s = self.get_search(search_id)
        s.next_check_at = next_check_at
        s.updated_at = self._now_iso()
        return self._repo.update(s)

    def set_last_checked_at(self, search_id: int, value: str | None) -> TicketSearch:
        s = self.get_search(search_id)
        s.last_checked_at = value
        s.updated_at = self._now_iso()
        return self._repo.update(s)

    def set_last_successful_check_at(self, search_id: int, value: str | None) -> TicketSearch:
        s = self.get_search(search_id)
        s.last_successful_check_at = value
        s.updated_at = self._now_iso()
        return self._repo.update(s)

    def set_last_tcdd_error_at(self, search_id: int, value: str | None) -> TicketSearch:
        s = self.get_search(search_id)
        s.last_tcdd_error_at = value
        s.updated_at = self._now_iso()
        return self._repo.update(s)

    def set_tcdd_outage_notified(self, search_id: int, notified: bool) -> TicketSearch:
        s = self.get_search(search_id)
        s.tcdd_outage_notified = bool(notified)
        s.updated_at = self._now_iso()
        return self._repo.update(s)

    def clear_tcdd_outage(self, search_id: int) -> TicketSearch:
        return self.set_tcdd_outage_notified(search_id, False)

    # --- Found event durable data ---

    def _serialize_trains(self, trains) -> str:
        data = []
        for t in trains:
            try:
                dep_iso = t.departure_at.isoformat() if hasattr(t.departure_at, "isoformat") else str(t.departure_at)
                arr_iso = t.arrival_at.isoformat() if hasattr(t.arrival_at, "isoformat") else str(t.arrival_at)
            except Exception:
                continue
            data.append(
                {
                    "train_id": t.train_id,
                    "train_name": t.train_name,
                    "train_number": t.train_number,
                    "departure_at": dep_iso,
                    "arrival_at": arr_iso,
                    "economy_available": int(t.economy_available),
                }
            )
        return json.dumps(data, ensure_ascii=False)

    def _deserialize_trains(self, json_str: str | None):
        if not json_str:
            return []
        try:
            raw = json.loads(json_str)
        except Exception:
            return []
        # Return list of simple objects without importing tcdd to keep domain decoupled
        # Use lightweight namespace objects with required attributes for monitoring/notifier
        result = []
        for d in raw:
            try:
                dep = datetime.datetime.fromisoformat(d["departure_at"])
                arr = datetime.datetime.fromisoformat(d["arrival_at"])
                if dep.tzinfo is None:
                    dep = dep.replace(tzinfo=ISTANBUL_TZ)
                if arr.tzinfo is None:
                    arr = arr.replace(tzinfo=ISTANBUL_TZ)
                # Create simple object with same interface as TrainAvailability
                obj = type("FoundTrain", (), {})()
                obj.train_id = d["train_id"]
                obj.train_name = d["train_name"]
                obj.train_number = d["train_number"]
                obj.departure_at = dep
                obj.arrival_at = arr
                obj.economy_available = int(d["economy_available"])
                # Provide computed properties departure_time/date similar to model
                obj.departure_date = dep.strftime("%Y-%m-%d")
                obj.departure_time = dep.strftime("%H:%M")
                obj.arrival_time = arr.strftime("%H:%M")
                result.append(obj)
            except Exception:
                continue
        return result

    def persist_found_trains(self, search_id: int, trains) -> TicketSearch:
        """Persist normalized train fields for found-event retry before notification."""
        s = self.get_search(search_id)
        s.found_trains_json = self._serialize_trains(trains)
        s.updated_at = self._now_iso()
        return self._repo.update(s)

    def get_found_trains(self, search_id: int):
        s = self.get_search(search_id)
        return self._deserialize_trains(s.found_trains_json)

    def get_found_trains_for_search(self, search: TicketSearch):
        return self._deserialize_trains(search.found_trains_json)

    # --- Recovery lookup ---

    def list_recovery_searches(self) -> list[TicketSearch]:
        return self._repo.list_recovery()

    def is_departure_in_window(self, search: TicketSearch, departure_time: str) -> bool:
        return search.is_departure_in_window(departure_time)
