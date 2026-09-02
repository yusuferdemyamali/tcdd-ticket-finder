from __future__ import annotations

import sqlite3

from app.database import init_db

from .models import TicketSearch, TicketSearchStatus


def _get_col(row: sqlite3.Row, name: str, default=None):
    try:
        # sqlite3.Row raises IndexError if column missing
        return row[name]
    except (IndexError, KeyError):
        return default
    except Exception:
        return default


def _row_to_search(row: sqlite3.Row) -> TicketSearch:
    return TicketSearch(
        id=row["id"],
        origin_station_id=row["origin_station_id"],
        origin_station_name=row["origin_station_name"],
        destination_station_id=row["destination_station_id"],
        destination_station_name=row["destination_station_name"],
        travel_date=row["travel_date"],
        departure_time_from=row["departure_time_from"],
        departure_time_to=row["departure_time_to"],
        status=TicketSearchStatus(row["status"]),
        last_checked_at=_get_col(row, "last_checked_at"),
        last_successful_check_at=_get_col(row, "last_successful_check_at"),
        next_check_at=_get_col(row, "next_check_at"),
        tcdd_outage_notified=bool(_get_col(row, "tcdd_outage_notified", 0)),
        last_tcdd_error_at=_get_col(row, "last_tcdd_error_at"),
        found_trains_json=_get_col(row, "found_trains_json"),
        found_at=_get_col(row, "found_at"),
        completed_at=_get_col(row, "completed_at"),
        cancelled_at=_get_col(row, "cancelled_at"),
        expired_at=_get_col(row, "expired_at"),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


class TicketSearchRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn
        self.conn.row_factory = sqlite3.Row
        init_db(self.conn)

    def create(self, search: TicketSearch) -> TicketSearch:
        try:
            cur = self.conn.execute(
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
                    search.origin_station_id,
                    search.origin_station_name,
                    search.destination_station_id,
                    search.destination_station_name,
                    search.travel_date,
                    search.departure_time_from,
                    search.departure_time_to,
                    search.status.value,
                    search.last_checked_at,
                    search.last_successful_check_at,
                    search.next_check_at,
                    1 if search.tcdd_outage_notified else 0,
                    search.last_tcdd_error_at,
                    search.found_trains_json,
                    search.found_at,
                    search.completed_at,
                    search.cancelled_at,
                    search.expired_at,
                    search.created_at,
                    search.updated_at,
                ),
            )
        except sqlite3.IntegrityError:
            try:
                self.conn.rollback()
            except Exception:
                pass
            raise
        # Commit unless we are inside an explicit transaction (e.g., BEGIN IMMEDIATE)
        # With default isolation_level, after execute we are in_transaction,
        # but for standalone ops we want to commit. Check if transaction was
        # started implicitly: if we are in_transaction and no explicit BEGIN,
        # we still need to commit. For replace atomic, service uses direct SQL
        # so repository commit is not involved. For normal creates, commit.
        # We commit if not inside a user-managed transaction that expects manual commit.
        # Simplest: always commit; service's replace uses raw connection not this method.
        try:
            self.conn.commit()
        except Exception:
            pass
        search.id = cur.lastrowid
        return search

    def get_by_id(self, search_id: int) -> TicketSearch | None:
        cur = self.conn.execute("SELECT * FROM ticket_searches WHERE id = ?", (search_id,))
        row = cur.fetchone()
        if row is None:
            return None
        return _row_to_search(row)

    def get_active(self) -> TicketSearch | None:
        cur = self.conn.execute("SELECT * FROM ticket_searches WHERE status = 'ACTIVE' LIMIT 1")
        row = cur.fetchone()
        if row is None:
            return None
        return _row_to_search(row)

    def update(self, search: TicketSearch) -> TicketSearch:
        assert search.id is not None
        try:
            self.conn.execute(
                """
                UPDATE ticket_searches SET
                    origin_station_id = ?,
                    origin_station_name = ?,
                    destination_station_id = ?,
                    destination_station_name = ?,
                    travel_date = ?,
                    departure_time_from = ?,
                    departure_time_to = ?,
                    status = ?,
                    last_checked_at = ?,
                    last_successful_check_at = ?,
                    next_check_at = ?,
                    tcdd_outage_notified = ?,
                    last_tcdd_error_at = ?,
                    found_trains_json = ?,
                    found_at = ?,
                    completed_at = ?,
                    cancelled_at = ?,
                    expired_at = ?,
                    created_at = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    search.origin_station_id,
                    search.origin_station_name,
                    search.destination_station_id,
                    search.destination_station_name,
                    search.travel_date,
                    search.departure_time_from,
                    search.departure_time_to,
                    search.status.value,
                    search.last_checked_at,
                    search.last_successful_check_at,
                    search.next_check_at,
                    1 if search.tcdd_outage_notified else 0,
                    search.last_tcdd_error_at,
                    search.found_trains_json,
                    search.found_at,
                    search.completed_at,
                    search.cancelled_at,
                    search.expired_at,
                    search.created_at,
                    search.updated_at,
                    search.id,
                ),
            )
        except sqlite3.IntegrityError:
            try:
                self.conn.rollback()
            except Exception:
                pass
            raise
        try:
            self.conn.commit()
        except Exception:
            pass
        return search

    def list_all(self) -> list[TicketSearch]:
        cur = self.conn.execute("SELECT * FROM ticket_searches ORDER BY id")
        return [_row_to_search(r) for r in cur.fetchall()]

    def list_recovery(self) -> list[TicketSearch]:
        """Return ACTIVE and FOUND searches for monitoring recovery. Exclude terminal states."""
        cur = self.conn.execute(
            "SELECT * FROM ticket_searches WHERE status IN ('ACTIVE','FOUND') ORDER BY id"
        )
        return [_row_to_search(r) for r in cur.fetchall()]
