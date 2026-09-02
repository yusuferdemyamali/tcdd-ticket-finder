from __future__ import annotations

import sqlite3

CREATE_TICKET_SEARCHES_SQL = """
CREATE TABLE IF NOT EXISTS ticket_searches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    origin_station_id INTEGER NOT NULL,
    origin_station_name TEXT NOT NULL,
    destination_station_id INTEGER NOT NULL,
    destination_station_name TEXT NOT NULL,
    travel_date TEXT NOT NULL,
    departure_time_from TEXT NOT NULL,
    departure_time_to TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('ACTIVE','FOUND','COMPLETED','CANCELLED','EXPIRED')),
    last_checked_at TEXT,
    last_successful_check_at TEXT,
    next_check_at TEXT,
    tcdd_outage_notified INTEGER NOT NULL DEFAULT 0 CHECK (tcdd_outage_notified IN (0,1)),
    last_tcdd_error_at TEXT,
    found_at TEXT,
    completed_at TEXT,
    cancelled_at TEXT,
    expired_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""

CREATE_ONE_ACTIVE_INDEX_SQL = """
CREATE UNIQUE INDEX IF NOT EXISTS idx_ticket_searches_one_active
ON ticket_searches(status)
WHERE status = 'ACTIVE';
"""


def init_db(conn: sqlite3.Connection) -> None:
    conn.execute(CREATE_TICKET_SEARCHES_SQL)
    conn.execute(CREATE_ONE_ACTIVE_INDEX_SQL)
    conn.commit()


def get_connection(db_path: str = ":memory:") -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn
