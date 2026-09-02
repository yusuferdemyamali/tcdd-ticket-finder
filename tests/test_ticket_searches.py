import datetime
import sqlite3
import sys
import pathlib

import pytest

# Ensure no tcdd import via ticket_searches
def test_ticket_searches_import_without_tcdd():
    # import should succeed without pulling app.tcdd
    from app.ticket_searches import TicketSearchStatus
    from app.ticket_searches.models import TicketSearch
    assert TicketSearchStatus.ACTIVE.value == "ACTIVE"
    # Verify source does not import tcdd
    for p in pathlib.Path("app/ticket_searches").glob("*.py"):
        text = p.read_text()
        assert "app.tcdd" not in text
        assert "import telegram" not in text.lower()
        assert "playwright" not in text.lower()


def test_database_can_be_initialized(tmp_path):
    from app.database import init_db
    conn = sqlite3.connect(":memory:")
    init_db(conn)
    cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='ticket_searches'")
    assert cur.fetchone() is not None
    cur = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='ticket_searches'")
    sql = cur.fetchone()[0]
    assert "origin_station_id" in sql
    assert "origin_station_name" in sql
    assert "destination_station_id" in sql
    assert "travel_date" in sql
    assert "departure_time_from" in sql
    assert "departure_time_to" in sql
    assert "status" in sql
    assert "CHECK" in sql
    assert "ACTIVE" in sql
    assert "created_at" in sql
    assert "updated_at" in sql
    # partial unique index
    cur = conn.execute("SELECT name, sql FROM sqlite_master WHERE type='index' AND name='idx_ticket_searches_one_active'")
    row = cur.fetchone()
    assert row is not None
    assert "WHERE status = 'ACTIVE'" in row[1] or 'WHERE status = "ACTIVE"' in row[1] or "ACTIVE" in row[1]
    # idempotent
    init_db(conn)
    # check columns
    cur = conn.execute("PRAGMA table_info(ticket_searches)")
    cols = {r[1] for r in cur.fetchall()}
    expected = {
        "id", "origin_station_id", "origin_station_name", "destination_station_id", "destination_station_name",
        "travel_date", "departure_time_from", "departure_time_to", "status",
        "last_checked_at", "last_successful_check_at", "next_check_at",
        "tcdd_outage_notified", "last_tcdd_error_at",
        "found_at", "completed_at", "cancelled_at", "expired_at",
        "created_at", "updated_at"
    }
    assert expected.issubset(cols)


def test_search_can_be_saved_and_read():
    from zoneinfo import ZoneInfo
    from app.ticket_searches.repository import TicketSearchRepository
    from app.ticket_searches.service import TicketSearchService
    IST = ZoneInfo("Europe/Istanbul")
    conn = sqlite3.connect(":memory:")
    repo = TicketSearchRepository(conn)
    now = datetime.datetime(2026, 9, 10, 10, 0, tzinfo=IST)
    svc = TicketSearchService(repo, now=lambda: now)
    s = svc.create_search(1325, "İSTANBUL(SÖĞÜTLÜÇEŞME)", 98, "ANKARA GAR", "2026-09-10", "08:00", "10:00")
    assert s.status.value == "ACTIVE"
    fetched = svc.get_search(s.id)
    assert fetched.origin_station_id == 1325
    assert fetched.origin_station_name == "İSTANBUL(SÖĞÜTLÜÇEŞME)"
    assert fetched.destination_station_id == 98
    assert fetched.destination_station_name == "ANKARA GAR"
    assert fetched.travel_date == "2026-09-10"
    assert fetched.departure_time_from == "08:00"
    assert fetched.departure_time_to == "10:00"
    assert fetched.status.value == "ACTIVE"
    assert fetched.created_at is not None
    assert fetched.updated_at is not None


def test_search_survives_new_connection(tmp_path):
    from zoneinfo import ZoneInfo
    from app.ticket_searches.repository import TicketSearchRepository
    from app.ticket_searches.service import TicketSearchService
    IST = ZoneInfo("Europe/Istanbul")
    db_path = str(tmp_path / "test.db")
    conn1 = sqlite3.connect(db_path)
    repo1 = TicketSearchRepository(conn1)
    now = datetime.datetime(2026, 9, 10, 10, 0, tzinfo=IST)
    svc1 = TicketSearchService(repo1, now=lambda: now)
    s = svc1.create_search(1, "A", 2, "B", "2026-09-10", "08:00", "10:00")
    s_id = s.id
    conn1.close()
    conn2 = sqlite3.connect(db_path)
    conn2.row_factory = sqlite3.Row
    repo2 = TicketSearchRepository(conn2)
    fetched = repo2.get_by_id(s_id)
    assert fetched is not None
    assert fetched.travel_date == "2026-09-10"
    assert fetched.status.value == "ACTIVE"


def test_state_not_memory_only():
    from zoneinfo import ZoneInfo
    from app.ticket_searches.repository import TicketSearchRepository
    from app.ticket_searches.service import TicketSearchService
    IST = ZoneInfo("Europe/Istanbul")
    conn = sqlite3.connect(":memory:")
    repo = TicketSearchRepository(conn)
    now = datetime.datetime(2026, 9, 10, 10, 0, tzinfo=IST)
    svc = TicketSearchService(repo, now=lambda: now)
    s = svc.create_search(1, "A", 2, "B", "2026-09-10", "08:00", "10:00")
    # change status
    found = svc.mark_found(s.id)
    # verify persisted via direct SQL
    cur = conn.execute("SELECT status, found_at FROM ticket_searches WHERE id = ?", (s.id,))
    row = cur.fetchone()
    assert row[0] == "FOUND"
    assert row[1] is not None


def test_valid_search_is_accepted():
    from zoneinfo import ZoneInfo
    from app.ticket_searches.repository import TicketSearchRepository
    from app.ticket_searches.service import TicketSearchService
    IST = ZoneInfo("Europe/Istanbul")
    conn = sqlite3.connect(":memory:")
    repo = TicketSearchRepository(conn)
    now = datetime.datetime(2026, 9, 10, 12, 0, tzinfo=IST)
    svc = TicketSearchService(repo, now=lambda: now)
    s = svc.create_search(1, "A", 2, "B", "2026-09-10", "08:00", "10:00")
    assert s.status.value == "ACTIVE"
    # same-day allowed
    conn2 = sqlite3.connect(":memory:")
    repo2 = TicketSearchRepository(conn2)
    svc2 = TicketSearchService(repo2, now=lambda: now)
    s2 = svc2.create_search(1, "A", 2, "B", "2026-09-10", "09:00", "09:00")
    assert s2.status.value == "ACTIVE"
    # future date
    conn3 = sqlite3.connect(":memory:")
    repo3 = TicketSearchRepository(conn3)
    svc3 = TicketSearchService(repo3, now=lambda: now)
    s3 = svc3.create_search(1, "A", 2, "B", "2026-09-11", "08:00", "10:00")
    assert s3.status.value == "ACTIVE"


def test_past_travel_date_rejected_no_active_created():
    from zoneinfo import ZoneInfo
    from app.ticket_searches.repository import TicketSearchRepository
    from app.ticket_searches.service import TicketSearchService
    from app.ticket_searches.exceptions import TicketSearchValidationError
    IST = ZoneInfo("Europe/Istanbul")
    conn = sqlite3.connect(":memory:")
    repo = TicketSearchRepository(conn)
    now = datetime.datetime(2026, 9, 10, 12, 0, tzinfo=IST)
    svc = TicketSearchService(repo, now=lambda: now)
    with pytest.raises(TicketSearchValidationError):
        svc.create_search(1, "A", 2, "B", "2026-09-09", "08:00", "10:00")
    assert repo.get_active() is None
    # ensure no row at all
    assert len(repo.list_all()) == 0


def test_midnight_crossing_rejected_no_active_created():
    from zoneinfo import ZoneInfo
    from app.ticket_searches.repository import TicketSearchRepository
    from app.ticket_searches.service import TicketSearchService
    from app.ticket_searches.exceptions import TicketSearchValidationError
    IST = ZoneInfo("Europe/Istanbul")
    conn = sqlite3.connect(":memory:")
    repo = TicketSearchRepository(conn)
    now = datetime.datetime(2026, 9, 10, 12, 0, tzinfo=IST)
    svc = TicketSearchService(repo, now=lambda: now)
    with pytest.raises(TicketSearchValidationError):
        svc.create_search(1, "A", 2, "B", "2026-09-10", "10:00", "08:00")
    assert repo.get_active() is None
    with pytest.raises(TicketSearchValidationError):
        svc.create_search(1, "A", 2, "B", "2026-09-10", "23:00", "01:00")
    assert repo.get_active() is None


def test_departure_window_boundaries_inclusive():
    from zoneinfo import ZoneInfo
    from app.ticket_searches.repository import TicketSearchRepository
    from app.ticket_searches.service import TicketSearchService
    IST = ZoneInfo("Europe/Istanbul")
    conn = sqlite3.connect(":memory:")
    repo = TicketSearchRepository(conn)
    now = datetime.datetime(2026, 9, 10, 10, 0, tzinfo=IST)
    svc = TicketSearchService(repo, now=lambda: now)
    s = svc.create_search(1, "A", 2, "B", "2026-09-10", "08:00", "10:00")
    assert s.is_departure_in_window("08:00") is True
    assert s.is_departure_in_window("10:00") is True
    assert s.is_departure_in_window("09:00") is True
    assert s.is_departure_in_window("07:59") is False
    assert s.is_departure_in_window("10:01") is False
    # via service helper
    assert svc.is_departure_in_window(s, "08:00") is True
    assert svc.is_departure_in_window(s, "10:00") is True
    assert svc.is_departure_in_window(s, "07:59") is False
    assert svc.is_departure_in_window(s, "10:01") is False


def test_second_active_search_rejected():
    from zoneinfo import ZoneInfo
    from app.ticket_searches.repository import TicketSearchRepository
    from app.ticket_searches.service import TicketSearchService
    from app.ticket_searches.exceptions import TicketSearchConflictError
    IST = ZoneInfo("Europe/Istanbul")
    conn = sqlite3.connect(":memory:")
    repo = TicketSearchRepository(conn)
    now = datetime.datetime(2026, 9, 10, 12, 0, tzinfo=IST)
    svc = TicketSearchService(repo, now=lambda: now)
    s1 = svc.create_search(1, "A", 2, "B", "2026-09-10", "08:00", "10:00")
    with pytest.raises(TicketSearchConflictError):
        svc.create_search(3, "C", 4, "D", "2026-09-11", "09:00", "11:00")
    # existing remains unchanged
    assert repo.get_active().id == s1.id
    assert repo.get_active().status.value == "ACTIVE"


def test_direct_repository_conflict_path():
    from app.ticket_searches.repository import TicketSearchRepository
    from app.ticket_searches.models import TicketSearch, TicketSearchStatus
    conn = sqlite3.connect(":memory:")
    repo = TicketSearchRepository(conn)
    now_iso = "2026-09-10T12:00:00+03:00"
    s1 = TicketSearch(None, 1, "A", 2, "B", "2026-09-10", "08:00", "10:00", TicketSearchStatus.ACTIVE, created_at=now_iso, updated_at=now_iso)
    repo.create(s1)
    s2 = TicketSearch(None, 3, "C", 4, "D", "2026-09-11", "09:00", "11:00", TicketSearchStatus.ACTIVE, created_at=now_iso, updated_at=now_iso)
    with pytest.raises(sqlite3.IntegrityError):
        repo.create(s2)


def test_active_search_lookup():
    from zoneinfo import ZoneInfo
    from app.ticket_searches.repository import TicketSearchRepository
    from app.ticket_searches.service import TicketSearchService
    IST = ZoneInfo("Europe/Istanbul")
    conn = sqlite3.connect(":memory:")
    repo = TicketSearchRepository(conn)
    now = datetime.datetime(2026, 9, 10, 12, 0, tzinfo=IST)
    svc = TicketSearchService(repo, now=lambda: now)
    assert svc.get_active_search() is None
    s = svc.create_search(1, "A", 2, "B", "2026-09-10", "08:00", "10:00")
    active = svc.get_active_search()
    assert active is not None
    assert active.id == s.id
    # after cancel, none
    svc.cancel_search(s.id)
    assert svc.get_active_search() is None


def test_invalid_transition_rejected_persisted_unchanged():
    from zoneinfo import ZoneInfo
    from app.ticket_searches.repository import TicketSearchRepository
    from app.ticket_searches.service import TicketSearchService
    from app.ticket_searches.exceptions import TicketSearchTransitionError
    from app.ticket_searches.models import TicketSearchStatus
    IST = ZoneInfo("Europe/Istanbul")
    conn = sqlite3.connect(":memory:")
    repo = TicketSearchRepository(conn)
    now = datetime.datetime(2026, 9, 10, 12, 0, tzinfo=IST)
    svc = TicketSearchService(repo, now=lambda: now)
    s = svc.create_search(1, "A", 2, "B", "2026-09-10", "08:00", "10:00")
    # ACTIVE -> COMPLETED is invalid
    with pytest.raises(TicketSearchTransitionError):
        svc.mark_completed(s.id)
    assert repo.get_by_id(s.id).status == TicketSearchStatus.ACTIVE
    # FOUND -> CANCELLED invalid
    svc.mark_found(s.id)
    with pytest.raises(TicketSearchTransitionError):
        svc.cancel_search(s.id)
    assert repo.get_by_id(s.id).status == TicketSearchStatus.FOUND
    # COMPLETED -> FOUND invalid
    svc.mark_completed(s.id)
    with pytest.raises(TicketSearchTransitionError):
        svc.mark_found(s.id)
    assert repo.get_by_id(s.id).status == TicketSearchStatus.COMPLETED
    # CANCELLED -> FOUND invalid
    conn2 = sqlite3.connect(":memory:")
    repo2 = TicketSearchRepository(conn2)
    svc2 = TicketSearchService(repo2, now=lambda: now)
    s2 = svc2.create_search(1, "A", 2, "B", "2026-09-10", "08:00", "10:00")
    svc2.cancel_search(s2.id)
    with pytest.raises(TicketSearchTransitionError):
        svc2.mark_found(s2.id)
    assert repo2.get_by_id(s2.id).status == TicketSearchStatus.CANCELLED


def test_mark_found_and_completed_flow():
    from zoneinfo import ZoneInfo
    from app.ticket_searches.repository import TicketSearchRepository
    from app.ticket_searches.service import TicketSearchService
    from app.ticket_searches.models import TicketSearchStatus
    IST = ZoneInfo("Europe/Istanbul")
    conn = sqlite3.connect(":memory:")
    repo = TicketSearchRepository(conn)
    now = datetime.datetime(2026, 9, 10, 10, 0, tzinfo=IST)
    svc = TicketSearchService(repo, now=lambda: now)
    s = svc.create_search(1, "A", 2, "B", "2026-09-10", "08:00", "10:00")
    found = svc.mark_found(s.id)
    assert found.status == TicketSearchStatus.FOUND
    assert found.found_at is not None
    # persisted
    persisted = repo.get_by_id(s.id)
    assert persisted.status == TicketSearchStatus.FOUND
    assert persisted.found_at is not None
    completed = svc.mark_completed(s.id)
    assert completed.status == TicketSearchStatus.COMPLETED
    assert completed.completed_at is not None
    persisted2 = repo.get_by_id(s.id)
    assert persisted2.status == TicketSearchStatus.COMPLETED
    assert persisted2.completed_at is not None


def test_cancel_and_expire():
    from zoneinfo import ZoneInfo
    from app.ticket_searches.repository import TicketSearchRepository
    from app.ticket_searches.service import TicketSearchService
    from app.ticket_searches.models import TicketSearchStatus
    IST = ZoneInfo("Europe/Istanbul")
    conn = sqlite3.connect(":memory:")
    repo = TicketSearchRepository(conn)
    now = datetime.datetime(2026, 9, 10, 12, 0, tzinfo=IST)
    svc = TicketSearchService(repo, now=lambda: now)
    s = svc.create_search(1, "A", 2, "B", "2026-09-15", "08:00", "10:00")
    cancelled = svc.cancel_search(s.id)
    assert cancelled.status == TicketSearchStatus.CANCELLED
    assert cancelled.cancelled_at is not None
    persisted = repo.get_by_id(s.id)
    assert persisted.status == TicketSearchStatus.CANCELLED
    assert persisted.cancelled_at is not None
    s2 = svc.create_search(2, "C", 3, "D", "2026-09-16", "09:00", "11:00")
    expired = svc.expire_search(s2.id)
    assert expired.status == TicketSearchStatus.EXPIRED
    assert expired.expired_at is not None
    persisted2 = repo.get_by_id(s2.id)
    assert persisted2.status == TicketSearchStatus.EXPIRED
    assert persisted2.expired_at is not None


def test_restart_success_and_clears_timestamps():
    from zoneinfo import ZoneInfo
    from app.ticket_searches.repository import TicketSearchRepository
    from app.ticket_searches.service import TicketSearchService
    from app.ticket_searches.models import TicketSearchStatus
    IST = ZoneInfo("Europe/Istanbul")
    conn = sqlite3.connect(":memory:")
    repo = TicketSearchRepository(conn)
    now_before = datetime.datetime(2026, 9, 10, 9, 0, tzinfo=IST)
    svc = TicketSearchService(repo, now=lambda: now_before)
    s = svc.create_search(1, "A", 2, "B", "2026-09-10", "08:00", "10:00")
    svc.mark_found(s.id)
    svc.mark_completed(s.id)
    # restart before window end 10:00 inclusive should succeed at 09:00
    restarted = svc.restart_search(s.id)
    assert restarted.status == TicketSearchStatus.ACTIVE
    assert restarted.found_at is None
    assert restarted.completed_at is None
    assert restarted.cancelled_at is None
    assert restarted.expired_at is None
    # active invariant holds
    assert repo.get_active().id == s.id


def test_restart_expired_window_rejected():
    from zoneinfo import ZoneInfo
    from app.ticket_searches.repository import TicketSearchRepository
    from app.ticket_searches.service import TicketSearchService
    from app.ticket_searches.exceptions import TicketSearchValidationError
    from app.ticket_searches.models import TicketSearchStatus
    IST = ZoneInfo("Europe/Istanbul")
    conn = sqlite3.connect(":memory:")
    repo = TicketSearchRepository(conn)
    now_before = datetime.datetime(2026, 9, 10, 9, 0, tzinfo=IST)
    svc = TicketSearchService(repo, now=lambda: now_before)
    s = svc.create_search(1, "A", 2, "B", "2026-09-10", "08:00", "10:00")
    svc.mark_found(s.id)
    svc.mark_completed(s.id)
    # now after window
    svc_after = TicketSearchService(repo, now=lambda: datetime.datetime(2026, 9, 10, 11, 0, tzinfo=IST))
    with pytest.raises(TicketSearchValidationError):
        svc_after.restart_search(s.id)
    assert repo.get_by_id(s.id).status == TicketSearchStatus.COMPLETED


def test_restart_inclusive_boundary():
    from zoneinfo import ZoneInfo
    from app.ticket_searches.repository import TicketSearchRepository
    from app.ticket_searches.service import TicketSearchService
    IST = ZoneInfo("Europe/Istanbul")
    conn = sqlite3.connect(":memory:")
    repo = TicketSearchRepository(conn)
    # travel 08:00-10:00, restart exactly at 10:00 should succeed
    now_at_end = datetime.datetime(2026, 9, 10, 10, 0, tzinfo=IST)
    svc = TicketSearchService(repo, now=lambda: datetime.datetime(2026, 9, 10, 9, 0, tzinfo=IST))
    s = svc.create_search(1, "A", 2, "B", "2026-09-10", "08:00", "10:00")
    svc.mark_found(s.id)
    svc.mark_completed(s.id)
    svc_boundary = TicketSearchService(repo, now=lambda: now_at_end)
    restarted = svc_boundary.restart_search(s.id)
    assert restarted.status.value == "ACTIVE"


def test_restart_active_conflict_rejected():
    from zoneinfo import ZoneInfo
    from app.ticket_searches.repository import TicketSearchRepository
    from app.ticket_searches.service import TicketSearchService
    from app.ticket_searches.exceptions import TicketSearchConflictError
    IST = ZoneInfo("Europe/Istanbul")
    conn = sqlite3.connect(":memory:")
    repo = TicketSearchRepository(conn)
    now = datetime.datetime(2026, 9, 10, 9, 0, tzinfo=IST)
    svc = TicketSearchService(repo, now=lambda: now)
    s1 = svc.create_search(1, "A", 2, "B", "2026-09-10", "08:00", "10:00")
    svc.mark_found(s1.id)
    svc.mark_completed(s1.id)
    # create another active
    s2 = svc.create_search(3, "C", 4, "D", "2026-09-11", "09:00", "11:00")
    assert s2.status.value == "ACTIVE"
    with pytest.raises(TicketSearchConflictError):
        svc.restart_search(s1.id)
    assert repo.get_by_id(s1.id).status.value == "COMPLETED"


def test_replace_active_search_atomic():
    from zoneinfo import ZoneInfo
    from app.ticket_searches.repository import TicketSearchRepository
    from app.ticket_searches.service import TicketSearchService
    from app.ticket_searches.models import TicketSearchStatus
    IST = ZoneInfo("Europe/Istanbul")
    conn = sqlite3.connect(":memory:")
    repo = TicketSearchRepository(conn)
    now = datetime.datetime(2026, 9, 10, 12, 0, tzinfo=IST)
    svc = TicketSearchService(repo, now=lambda: now)
    old = svc.create_search(1, "A", 2, "B", "2026-09-12", "08:00", "10:00")
    new = svc.replace_active_search(3, "C", 4, "D", "2026-09-13", "09:00", "11:00")
    # old cancelled
    old_fetched = repo.get_by_id(old.id)
    assert old_fetched.status == TicketSearchStatus.CANCELLED
    assert old_fetched.cancelled_at is not None
    # new active
    assert new.status == TicketSearchStatus.ACTIVE
    assert repo.get_active().id == new.id
    # no double active
    actives = [r for r in repo.list_all() if r.status == TicketSearchStatus.ACTIVE]
    assert len(actives) == 1


def test_replace_rollback_consistency():
    from zoneinfo import ZoneInfo
    from app.ticket_searches.repository import TicketSearchRepository
    from app.ticket_searches.service import TicketSearchService
    from app.ticket_searches.models import TicketSearchStatus
    import sqlite3
    IST = ZoneInfo("Europe/Istanbul")

    class FakeConn:
        def __init__(self, real):
            self._real = real
            self.fail_next_insert = False
        def execute(self, sql, params=()):
            if self.fail_next_insert and "INSERT INTO ticket_searches" in sql:
                self.fail_next_insert = False
                raise sqlite3.IntegrityError("simulated failure")
            return self._real.execute(sql, params)
        def commit(self):
            return self._real.commit()
        def rollback(self):
            return self._real.rollback()
        def __getattr__(self, name):
            return getattr(self._real, name)

    conn_real = sqlite3.connect(":memory:")
    repo = TicketSearchRepository(conn_real)
    now = datetime.datetime(2026, 9, 10, 12, 0, tzinfo=IST)
    svc = TicketSearchService(repo, now=lambda: now)
    old = svc.create_search(1, "A", 2, "B", "2026-09-14", "08:00", "10:00")
    fake = FakeConn(conn_real)
    fake.fail_next_insert = True
    repo.conn = fake
    from app.ticket_searches.exceptions import TicketSearchConflictError
    with pytest.raises(TicketSearchConflictError):
        svc.replace_active_search(3, "C", 4, "D", "2026-09-15", "09:00", "11:00")
    # restore
    repo.conn = conn_real
    # old still ACTIVE, not cancelled without replacement
    assert repo.get_by_id(old.id).status == TicketSearchStatus.ACTIVE
    assert len([r for r in repo.list_all() if r.status == TicketSearchStatus.ACTIVE]) == 1


def test_replace_without_existing_active():
    from zoneinfo import ZoneInfo
    from app.ticket_searches.repository import TicketSearchRepository
    from app.ticket_searches.service import TicketSearchService
    from app.ticket_searches.models import TicketSearchStatus
    IST = ZoneInfo("Europe/Istanbul")
    conn = sqlite3.connect(":memory:")
    repo = TicketSearchRepository(conn)
    now = datetime.datetime(2026, 9, 10, 12, 0, tzinfo=IST)
    svc = TicketSearchService(repo, now=lambda: now)
    assert repo.get_active() is None
    new = svc.replace_active_search(1, "A", 2, "B", "2026-09-12", "08:00", "10:00")
    assert new.status == TicketSearchStatus.ACTIVE


def test_persistence_independent_from_external():
    # ticket-search persistence init does not require tcdd, telegram, etc.
    import pathlib
    # Already verified import without tcdd, check database init doesn't pull those
    for p in pathlib.Path("app/database.py").read_text().lower().splitlines():
        assert "telegram" not in p
        assert "playwright" not in p
    for p in pathlib.Path("app/ticket_searches").glob("*.py"):
        txt = p.read_text().lower()
        assert "import telegram" not in txt
        assert "playwright" not in txt


def test_tcdd_provider_decoupled():
    # TCDD provider should not depend on ticket-searches
    for p in pathlib.Path("app/tcdd").glob("*.py"):
        txt = p.read_text()
        assert "ticket_search" not in txt.lower()
        assert "import sqlite" not in txt.lower()
