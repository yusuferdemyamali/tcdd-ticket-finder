import asyncio
import datetime
import sqlite3
from zoneinfo import ZoneInfo

import pytest

from app.monitoring.config import MonitoringConfig, load_monitoring_config
from app.monitoring.filtering import filter_eligible_trains
from app.monitoring.service import MonitoringService
from app.tcdd.models import TrainAvailability
from app.ticket_searches.models import TicketSearch, TicketSearchStatus
from app.ticket_searches.repository import TicketSearchRepository
from app.ticket_searches.service import TicketSearchService

IST = ZoneInfo("Europe/Istanbul")


class FakeTcdd:
    def __init__(self, trains=None, raise_err=None):
        self.calls = []
        self.trains = trains or []
        self.raise_err = raise_err

    def search_trains(self, origin, dest, travel_date):
        self.calls.append((origin, dest, travel_date))
        if self.raise_err:
            raise self.raise_err
        return self.trains


class FakeNotifier:
    def __init__(self, fail_found=False, fail_expired=False):
        self.found_calls = []
        self.expired_calls = []
        self.fail_found = fail_found
        self.fail_expired = fail_expired

    async def notify_found(self, search, trains):
        self.found_calls.append((search.id, len(trains)))
        if self.fail_found:
            raise RuntimeError("notify failed")

    async def notify_expired(self, search):
        self.expired_calls.append(search.id)
        if self.fail_expired:
            raise RuntimeError("expired notify failed")


# 1.1 config
def test_monitoring_config_defaults():
    cfg = load_monitoring_config(env={})
    assert cfg.poll_min_seconds == 60
    assert cfg.poll_max_seconds == 90


def test_monitoring_config_env_override():
    cfg = load_monitoring_config(env={"POLL_MIN_SECONDS": "30", "POLL_MAX_SECONDS": "45"})
    assert cfg.poll_min_seconds == 30
    assert cfg.poll_max_seconds == 45


def test_monitoring_config_invalid_min_gt_max():
    with pytest.raises(ValueError):
        load_monitoring_config(env={"POLL_MIN_SECONDS": "90", "POLL_MAX_SECONDS": "60"})


def test_monitoring_config_invalid_zero():
    with pytest.raises(ValueError):
        load_monitoring_config(env={"POLL_MIN_SECONDS": "0", "POLL_MAX_SECONDS": "90"})
    with pytest.raises(ValueError):
        load_monitoring_config(env={"POLL_MIN_SECONDS": "60", "POLL_MAX_SECONDS": "0"})


def test_monitoring_config_invalid_non_int():
    with pytest.raises(ValueError):
        load_monitoring_config(env={"POLL_MIN_SECONDS": "abc", "POLL_MAX_SECONDS": "90"})


# 1.2 separate module import without polling
def test_monitoring_import_without_polling_or_tcdd():
    # Import should not start polling or make TCDD requests
    import app.monitoring.service as svc_mod
    import pathlib

    text = pathlib.Path("app/monitoring/service.py").read_text()
    # Should not execute polling on import (no top-level loop invocation)
    assert "run_loop" not in text or "asyncio.run" not in text.split("class MonitoringService")[0]
    # Verify not importing telegram handlers directly for isolation
    assert "from app.telegram.handlers" not in text
    assert "from app.telegram import" not in text or "formatting" in text  # formatting allowed via notifier, but not handlers
    # Also check filtering does not use raw JSON
    ftext = pathlib.Path("app/monitoring/filtering.py").read_text()
    assert "bookingClass" not in ftext
    assert "raw" not in ftext.lower() or "raw tcdd" not in ftext.lower()


# 1.3 deterministic one-check + thin polling loop
@pytest.mark.asyncio
async def test_one_check_without_sleep():
    conn = sqlite3.connect(":memory:")
    repo = TicketSearchRepository(conn)
    svc = TicketSearchService(repo, now=lambda: datetime.datetime(2026, 9, 10, 7, 0, tzinfo=IST))
    tcdd = FakeTcdd()
    notifier = FakeNotifier()
    slept = []
    mon = MonitoringService(svc, tcdd, notifier, config=MonitoringConfig(60, 90), now_fn=lambda: datetime.datetime(2026, 9, 10, 7, 0, tzinfo=IST), sleep_fn=lambda s: slept.append(s))
    res = await mon.run_once()
    assert res == "no_active"
    assert slept == []  # run_once should not sleep


@pytest.mark.asyncio
async def test_polling_loop_uses_random_interval():
    conn = sqlite3.connect(":memory:")
    repo = TicketSearchRepository(conn)
    svc = TicketSearchService(repo, now=lambda: datetime.datetime(2026, 9, 10, 7, 0, tzinfo=IST))
    svc.create_search(1, "A", 2, "B", "2026-09-10", "08:00", "10:00")
    tcdd = FakeTcdd()
    notifier = FakeNotifier()
    slept = []
    intervals = []

    def fake_random(a, b):
        intervals.append((a, b))
        assert a == 60 and b == 90
        return 70

    mon = MonitoringService(svc, tcdd, notifier, config=MonitoringConfig(60, 90), random_fn=fake_random, sleep_fn=lambda s: slept.append(s))
    await mon.run_loop(iterations=2)
    assert slept == [70]
    assert intervals == [(60, 90)]


# 2.1 filtering
def test_filtering_matching_wrong_date_outside_window_boundary():
    search = TicketSearch(id=1, origin_station_id=1, origin_station_name="A", destination_station_id=2, destination_station_name="B", travel_date="2026-09-10", departure_time_from="08:00", departure_time_to="10:00", status=TicketSearchStatus.ACTIVE)
    dep_ok = datetime.datetime(2026, 9, 10, 9, 0, tzinfo=IST)
    arr_ok = datetime.datetime(2026, 9, 10, 10, 0, tzinfo=IST)
    dep_out = datetime.datetime(2026, 9, 10, 7, 59, tzinfo=IST)
    dep_wrong = datetime.datetime(2026, 9, 11, 9, 0, tzinfo=IST)
    dep_boundary_from = datetime.datetime(2026, 9, 10, 8, 0, tzinfo=IST)
    dep_boundary_to = datetime.datetime(2026, 9, 10, 10, 0, tzinfo=IST)
    trains = [
        TrainAvailability(train_id=1, train_name="T1", train_number="1", departure_at=dep_ok, arrival_at=arr_ok, economy_available=1),  # eligible
        TrainAvailability(train_id=2, train_name="T2", train_number="2", departure_at=dep_out, arrival_at=arr_ok, economy_available=1),  # outside window
        TrainAvailability(train_id=3, train_name="T3", train_number="3", departure_at=dep_wrong, arrival_at=arr_ok, economy_available=5),  # wrong date
        TrainAvailability(train_id=4, train_name="T4", train_number="4", departure_at=dep_boundary_from, arrival_at=arr_ok, economy_available=1),  # inclusive from
        TrainAvailability(train_id=5, train_name="T5", train_number="5", departure_at=dep_boundary_to, arrival_at=arr_ok, economy_available=1),  # inclusive to
        TrainAvailability(train_id=6, train_name="T6", train_number="6", departure_at=dep_ok, arrival_at=arr_ok, economy_available=0),  # economy 0
    ]
    eligible = filter_eligible_trains(search, trains)
    ids = {t.train_id for t in eligible}
    assert 1 in ids
    assert 4 in ids
    assert 5 in ids
    assert 2 not in ids
    assert 3 not in ids
    assert 6 not in ids
    assert len(eligible) == 3


# 2.2 sorting
def test_filtering_sorted_ascending():
    search = TicketSearch(id=1, origin_station_id=1, origin_station_name="A", destination_station_id=2, destination_station_name="B", travel_date="2026-09-10", departure_time_from="08:00", departure_time_to="10:00", status=TicketSearchStatus.ACTIVE)
    dep1 = datetime.datetime(2026, 9, 10, 9, 30, tzinfo=IST)
    dep2 = datetime.datetime(2026, 9, 10, 8, 0, tzinfo=IST)
    dep3 = datetime.datetime(2026, 9, 10, 8, 15, tzinfo=IST)
    arr = datetime.datetime(2026, 9, 10, 10, 0, tzinfo=IST)
    trains = [
        TrainAvailability(train_id=1, train_name="T1", train_number="1", departure_at=dep1, arrival_at=arr, economy_available=1),
        TrainAvailability(train_id=2, train_name="T2", train_number="2", departure_at=dep2, arrival_at=arr, economy_available=1),
        TrainAvailability(train_id=3, train_name="T3", train_number="3", departure_at=dep3, arrival_at=arr, economy_available=1),
    ]
    eligible = filter_eligible_trains(search, trains)
    assert [t.train_id for t in eligible] == [2, 3, 1]


# 2.3 economy only
def test_economy_only():
    search = TicketSearch(id=1, origin_station_id=1, origin_station_name="A", destination_station_id=2, destination_station_name="B", travel_date="2026-09-10", departure_time_from="08:00", departure_time_to="10:00", status=TicketSearchStatus.ACTIVE)
    dep = datetime.datetime(2026, 9, 10, 9, 0, tzinfo=IST)
    arr = datetime.datetime(2026, 9, 10, 10, 0, tzinfo=IST)
    t0 = TrainAvailability(train_id=1, train_name="T", train_number="1", departure_at=dep, arrival_at=arr, economy_available=0)
    t1 = TrainAvailability(train_id=2, train_name="T", train_number="2", departure_at=dep, arrival_at=arr, economy_available=1)
    t5 = TrainAvailability(train_id=3, train_name="T", train_number="3", departure_at=dep, arrival_at=arr, economy_available=5)
    assert len(filter_eligible_trains(search, [t0])) == 0
    assert len(filter_eligible_trains(search, [t1])) == 1
    assert len(filter_eligible_trains(search, [t5])) == 1


# 3.1 no active
@pytest.mark.asyncio
async def test_no_active_no_tcdd_call():
    conn = sqlite3.connect(":memory:")
    repo = TicketSearchRepository(conn)
    svc = TicketSearchService(repo, now=lambda: datetime.datetime(2026, 9, 10, 7, 0, tzinfo=IST))
    tcdd = FakeTcdd()
    notifier = FakeNotifier()
    mon = MonitoringService(svc, tcdd, notifier, config=MonitoringConfig(60, 90), now_fn=lambda: datetime.datetime(2026, 9, 10, 7, 0, tzinfo=IST))
    res = await mon.run_once()
    assert res == "no_active"
    assert tcdd.calls == []


# 3.2 active TCDD query
@pytest.mark.asyncio
async def test_active_search_queries_tcdd_with_criteria():
    conn = sqlite3.connect(":memory:")
    repo = TicketSearchRepository(conn)
    svc = TicketSearchService(repo, now=lambda: datetime.datetime(2026, 9, 10, 7, 0, tzinfo=IST))
    s = svc.create_search(10, "A", 20, "B", "2026-09-10", "08:00", "10:00")
    dep = datetime.datetime(2026, 9, 10, 8, 30, tzinfo=IST)
    arr = datetime.datetime(2026, 9, 10, 9, 30, tzinfo=IST)
    trains = [TrainAvailability(train_id=1, train_name="T", train_number="1", departure_at=dep, arrival_at=arr, economy_available=0)]
    tcdd = FakeTcdd(trains=trains)
    notifier = FakeNotifier()
    mon = MonitoringService(svc, tcdd, notifier, config=MonitoringConfig(60, 90), now_fn=lambda: datetime.datetime(2026, 9, 10, 7, 0, tzinfo=IST))
    await mon.run_once()
    assert tcdd.calls[0] == (10, 20, "2026-09-10")


# 3.3 no-match leaves ACTIVE
@pytest.mark.asyncio
async def test_no_match_leaves_active():
    conn = sqlite3.connect(":memory:")
    repo = TicketSearchRepository(conn)
    svc = TicketSearchService(repo, now=lambda: datetime.datetime(2026, 9, 10, 7, 0, tzinfo=IST))
    s = svc.create_search(10, "A", 20, "B", "2026-09-10", "08:00", "10:00")
    dep = datetime.datetime(2026, 9, 10, 8, 30, tzinfo=IST)
    arr = datetime.datetime(2026, 9, 10, 9, 30, tzinfo=IST)
    tcdd = FakeTcdd(trains=[TrainAvailability(train_id=1, train_name="T", train_number="1", departure_at=dep, arrival_at=arr, economy_available=0)])
    notifier = FakeNotifier()
    mon = MonitoringService(svc, tcdd, notifier, config=MonitoringConfig(60, 90), now_fn=lambda: datetime.datetime(2026, 9, 10, 7, 0, tzinfo=IST))
    res = await mon.run_once()
    assert res == "no_match"
    assert repo.get_by_id(s.id).status == TicketSearchStatus.ACTIVE
    assert notifier.found_calls == []


# 3.4 found -> FOUND -> COMPLETED
@pytest.mark.asyncio
async def test_found_completes_after_notification():
    conn = sqlite3.connect(":memory:")
    repo = TicketSearchRepository(conn)
    svc = TicketSearchService(repo, now=lambda: datetime.datetime(2026, 9, 10, 7, 0, tzinfo=IST))
    s = svc.create_search(10, "A", 20, "B", "2026-09-10", "08:00", "10:00")
    dep = datetime.datetime(2026, 9, 10, 8, 30, tzinfo=IST)
    arr = datetime.datetime(2026, 9, 10, 9, 30, tzinfo=IST)
    tcdd = FakeTcdd(trains=[TrainAvailability(train_id=1, train_name="T", train_number="1", departure_at=dep, arrival_at=arr, economy_available=3)])
    notifier = FakeNotifier()
    mon = MonitoringService(svc, tcdd, notifier, config=MonitoringConfig(60, 90), now_fn=lambda: datetime.datetime(2026, 9, 10, 7, 0, tzinfo=IST))
    res = await mon.run_once()
    assert res == "found"
    persisted = repo.get_by_id(s.id)
    assert persisted.status == TicketSearchStatus.COMPLETED
    assert persisted.found_at is not None
    assert persisted.completed_at is not None
    assert len(notifier.found_calls) == 1


# 3.5 notification failure leaves FOUND
@pytest.mark.asyncio
async def test_notification_failure_leaves_found():
    conn = sqlite3.connect(":memory:")
    repo = TicketSearchRepository(conn)
    svc = TicketSearchService(repo, now=lambda: datetime.datetime(2026, 9, 10, 7, 0, tzinfo=IST))
    s = svc.create_search(10, "A", 20, "B", "2026-09-10", "08:00", "10:00")
    dep = datetime.datetime(2026, 9, 10, 8, 30, tzinfo=IST)
    arr = datetime.datetime(2026, 9, 10, 9, 30, tzinfo=IST)
    tcdd = FakeTcdd(trains=[TrainAvailability(train_id=1, train_name="T", train_number="1", departure_at=dep, arrival_at=arr, economy_available=3)])
    notifier = FakeNotifier(fail_found=True)
    mon = MonitoringService(svc, tcdd, notifier, config=MonitoringConfig(60, 90), now_fn=lambda: datetime.datetime(2026, 9, 10, 7, 0, tzinfo=IST))
    with pytest.raises(RuntimeError):
        await mon.run_once()
    persisted = repo.get_by_id(s.id)
    assert persisted.status == TicketSearchStatus.FOUND
    assert persisted.completed_at is None


# 3.6 expiration
@pytest.mark.asyncio
async def test_expiration_transitions_and_no_tcdd():
    conn = sqlite3.connect(":memory:")
    repo = TicketSearchRepository(conn)
    svc_create = TicketSearchService(repo, now=lambda: datetime.datetime(2026, 9, 10, 9, 0, tzinfo=IST))
    s = svc_create.create_search(10, "A", 20, "B", "2026-09-10", "08:00", "10:00")
    svc_expire = TicketSearchService(repo, now=lambda: datetime.datetime(2026, 9, 10, 11, 0, tzinfo=IST))
    tcdd = FakeTcdd()
    notifier = FakeNotifier()
    mon = MonitoringService(svc_expire, tcdd, notifier, config=MonitoringConfig(60, 90), now_fn=lambda: datetime.datetime(2026, 9, 10, 11, 0, tzinfo=IST))
    res = await mon.run_once()
    assert res == "expired"
    assert tcdd.calls == []
    assert repo.get_by_id(s.id).status == TicketSearchStatus.EXPIRED
    assert len(notifier.expired_calls) == 1


@pytest.mark.asyncio
async def test_expiration_boundary_not_expired():
    conn = sqlite3.connect(":memory:")
    repo = TicketSearchRepository(conn)
    svc = TicketSearchService(repo, now=lambda: datetime.datetime(2026, 9, 10, 9, 0, tzinfo=IST))
    s = svc.create_search(10, "A", 20, "B", "2026-09-10", "08:00", "10:00")
    dep = datetime.datetime(2026, 9, 10, 9, 0, tzinfo=IST)
    arr = datetime.datetime(2026, 9, 10, 10, 0, tzinfo=IST)
    tcdd = FakeTcdd(trains=[TrainAvailability(train_id=1, train_name="T", train_number="1", departure_at=dep, arrival_at=arr, economy_available=1)])
    notifier = FakeNotifier()
    # now exactly at 10:00 inclusive -> not expired
    mon = MonitoringService(
        TicketSearchService(repo, now=lambda: datetime.datetime(2026, 9, 10, 10, 0, tzinfo=IST)),
        tcdd,
        notifier,
        config=MonitoringConfig(60, 90),
        now_fn=lambda: datetime.datetime(2026, 9, 10, 10, 0, tzinfo=IST),
    )
    res = await mon.run_once()
    assert res != "expired"
    assert repo.get_by_id(s.id).status != TicketSearchStatus.EXPIRED


# 3.6 TCDD error not treated as empty
@pytest.mark.asyncio
async def test_tcdd_error_not_treated_as_empty():
    conn = sqlite3.connect(":memory:")
    repo = TicketSearchRepository(conn)
    svc = TicketSearchService(repo, now=lambda: datetime.datetime(2026, 9, 10, 7, 0, tzinfo=IST))
    s = svc.create_search(10, "A", 20, "B", "2026-09-10", "08:00", "10:00")
    tcdd = FakeTcdd(raise_err=RuntimeError("timeout"))
    notifier = FakeNotifier()
    mon = MonitoringService(svc, tcdd, notifier, config=MonitoringConfig(60, 90), now_fn=lambda: datetime.datetime(2026, 9, 10, 7, 0, tzinfo=IST))
    with pytest.raises(RuntimeError):
        await mon.run_once()
    assert repo.get_by_id(s.id).status == TicketSearchStatus.ACTIVE


# 4.1 found formatting multi-train
def test_found_message_multi_train():
    from app.telegram.formatting import format_found_tickets_message, build_found_keyboard

    search = TicketSearch(id=42, origin_station_id=1, origin_station_name="İSTANBUL(SÖĞÜTLÜÇEŞME)", destination_station_id=98, destination_station_name="ANKARA GAR", travel_date="2026-09-10", departure_time_from="08:00", departure_time_to="10:00", status=TicketSearchStatus.ACTIVE)
    dep1 = datetime.datetime(2026, 9, 10, 8, 15, tzinfo=IST)
    dep2 = datetime.datetime(2026, 9, 10, 9, 30, tzinfo=IST)
    arr = datetime.datetime(2026, 9, 10, 10, 0, tzinfo=IST)
    trains = [
        TrainAvailability(train_id=1, train_name="81002 İSTANBUL-ANKARA", train_number="81002", departure_at=dep1, arrival_at=arr, economy_available=5),
        TrainAvailability(train_id=2, train_name="81006 İSTANBUL-ANKARA", train_number="81006", departure_at=dep2, arrival_at=arr, economy_available=2),
    ]
    msg = format_found_tickets_message(search, trains)
    assert "İSTANBUL(SÖĞÜTLÜÇEŞME) → ANKARA GAR" in msg
    assert "10.09.2026" in msg
    assert "81002" in msg and "81006" in msg
    assert "08:15" in msg and "09:30" in msg
    assert "Ekonomi: 5" in msg and "Ekonomi: 2" in msg
    kbd = build_found_keyboard(42)
    texts = [b.text for row in kbd.inline_keyboard for b in row]
    assert "TCDD'den Bilet Al" in texts
    assert "Bileti Alamadım - Tekrar Ara" in texts
    restart_btn = next(b for row in kbd.inline_keyboard for b in row if "Tekrar Ara" in b.text)
    assert restart_btn.callback_data == "restart:42"


def test_expiration_message():
    from app.telegram.formatting import format_expired_message

    search = TicketSearch(id=1, origin_station_id=1, origin_station_name="A", destination_station_id=2, destination_station_name="B", travel_date="2026-09-10", departure_time_from="08:00", departure_time_to="10:00", status=TicketSearchStatus.ACTIVE)
    msg = format_expired_message(search)
    assert "Arama süresi doldu" in msg
    assert "10.09.2026" in msg


# 4.4 / 4.5 / 4.6 restart callback guards
class FakeUser:
    def __init__(self, uid):
        self.id = uid


class FakeMessage:
    def __init__(self):
        self.replies = []
        self.edits = []

    async def reply_text(self, text):
        self.replies.append(text)

    async def edit_message_text(self, text):
        self.edits.append(text)


class FakeCallbackQuery:
    def __init__(self, data, message):
        self.data = data
        self.message = message
        self.answered = False

    async def answer(self):
        self.answered = True


class FakeUpdate:
    def __init__(self, uid, callback_data):
        self.effective_user = FakeUser(uid)
        self.callback_query = FakeCallbackQuery(callback_data, FakeMessage())
        self.effective_message = self.callback_query.message
        self.message = None


class FakeContext:
    def __init__(self):
        self.user_data = {}


@pytest.mark.asyncio
async def test_restart_callback_valid():
    from app.telegram.callbacks import RestartCallbackHandler

    conn = sqlite3.connect(":memory:")
    repo = TicketSearchRepository(conn)
    svc = TicketSearchService(repo, now=lambda: datetime.datetime(2026, 9, 10, 9, 0, tzinfo=IST))
    s = svc.create_search(1, "A", 2, "B", "2026-09-10", "08:00", "10:00")
    svc.mark_found(s.id)
    svc.mark_completed(s.id)
    handler = RestartCallbackHandler(svc, allowed_user_id=123, now_fn=lambda: datetime.datetime(2026, 9, 10, 9, 30, tzinfo=IST))
    upd = FakeUpdate(123, f"restart:{s.id}")
    ctx = FakeContext()
    ctx.user_data["wizard_token"] = "stale"
    await handler.handle(upd, ctx)
    assert repo.get_by_id(s.id).status == TicketSearchStatus.ACTIVE
    assert any("yeniden başlatıldı" in r for r in upd.callback_query.message.replies)
    # ensure not relying on user_data – handler should succeed despite stale wizard_token
    assert "wizard_token" in ctx.user_data


@pytest.mark.asyncio
async def test_restart_unauthorized():
    from app.telegram.callbacks import RestartCallbackHandler

    conn = sqlite3.connect(":memory:")
    repo = TicketSearchRepository(conn)
    svc = TicketSearchService(repo, now=lambda: datetime.datetime(2026, 9, 10, 9, 0, tzinfo=IST))
    s = svc.create_search(1, "A", 2, "B", "2026-09-10", "08:00", "10:00")
    svc.mark_found(s.id)
    svc.mark_completed(s.id)
    handler = RestartCallbackHandler(svc, allowed_user_id=123, now_fn=lambda: datetime.datetime(2026, 9, 10, 9, 30, tzinfo=IST))
    upd = FakeUpdate(999, f"restart:{s.id}")
    await handler.handle(upd, FakeContext())
    assert repo.get_by_id(s.id).status == TicketSearchStatus.COMPLETED


@pytest.mark.asyncio
async def test_restart_wrong_status():
    from app.telegram.callbacks import RestartCallbackHandler

    conn = sqlite3.connect(":memory:")
    repo = TicketSearchRepository(conn)
    svc = TicketSearchService(repo, now=lambda: datetime.datetime(2026, 9, 10, 9, 0, tzinfo=IST))
    s = svc.create_search(1, "A", 2, "B", "2026-09-10", "08:00", "10:00")  # ACTIVE
    handler = RestartCallbackHandler(svc, allowed_user_id=123, now_fn=lambda: datetime.datetime(2026, 9, 10, 9, 30, tzinfo=IST))
    upd = FakeUpdate(123, f"restart:{s.id}")
    await handler.handle(upd, FakeContext())
    assert repo.get_by_id(s.id).status == TicketSearchStatus.ACTIVE
    assert any("geçerli değil" in r for r in upd.callback_query.message.replies)


@pytest.mark.asyncio
async def test_restart_expired_window():
    from app.telegram.callbacks import RestartCallbackHandler

    conn = sqlite3.connect(":memory:")
    repo = TicketSearchRepository(conn)
    svc = TicketSearchService(repo, now=lambda: datetime.datetime(2026, 9, 10, 9, 0, tzinfo=IST))
    s = svc.create_search(1, "A", 2, "B", "2026-09-10", "08:00", "10:00")
    svc.mark_found(s.id)
    svc.mark_completed(s.id)
    handler = RestartCallbackHandler(svc, allowed_user_id=123, now_fn=lambda: datetime.datetime(2026, 9, 10, 11, 0, tzinfo=IST))
    upd = FakeUpdate(123, f"restart:{s.id}")
    await handler.handle(upd, FakeContext())
    assert repo.get_by_id(s.id).status == TicketSearchStatus.COMPLETED


@pytest.mark.asyncio
async def test_restart_stale_wrong_id():
    from app.telegram.callbacks import RestartCallbackHandler

    conn = sqlite3.connect(":memory:")
    repo = TicketSearchRepository(conn)
    svc = TicketSearchService(repo, now=lambda: datetime.datetime(2026, 9, 10, 9, 0, tzinfo=IST))
    s = svc.create_search(1, "A", 2, "B", "2026-09-10", "08:00", "10:00")
    svc.mark_found(s.id)
    svc.mark_completed(s.id)
    s2 = svc.create_search(3, "C", 4, "D", "2026-09-11", "09:00", "11:00")
    handler = RestartCallbackHandler(svc, allowed_user_id=123, now_fn=lambda: datetime.datetime(2026, 9, 10, 9, 30, tzinfo=IST))
    upd = FakeUpdate(123, "restart:9999")
    await handler.handle(upd, FakeContext())
    assert repo.get_by_id(s.id).status == TicketSearchStatus.COMPLETED
    assert repo.get_by_id(s2.id).status == TicketSearchStatus.ACTIVE


@pytest.mark.asyncio
async def test_restart_allows_monitoring_pickup():
    from app.telegram.callbacks import RestartCallbackHandler

    conn = sqlite3.connect(":memory:")
    repo = TicketSearchRepository(conn)
    svc = TicketSearchService(repo, now=lambda: datetime.datetime(2026, 9, 10, 9, 30, tzinfo=IST))
    s = svc.create_search(1, "A", 2, "B", "2026-09-10", "08:00", "10:00")
    svc.mark_found(s.id)
    svc.mark_completed(s.id)
    handler = RestartCallbackHandler(svc, allowed_user_id=123, now_fn=lambda: datetime.datetime(2026, 9, 10, 9, 30, tzinfo=IST))
    upd = FakeUpdate(123, f"restart:{s.id}")
    await handler.handle(upd, FakeContext())
    assert repo.get_by_id(s.id).status == TicketSearchStatus.ACTIVE
    dep = datetime.datetime(2026, 9, 10, 9, 45, tzinfo=IST)
    arr = datetime.datetime(2026, 9, 10, 10, 45, tzinfo=IST)
    tcdd = FakeTcdd(trains=[TrainAvailability(train_id=1, train_name="T", train_number="1", departure_at=dep, arrival_at=arr, economy_available=5)])
    notifier = FakeNotifier()
    mon = MonitoringService(svc, tcdd, notifier, now_fn=lambda: datetime.datetime(2026, 9, 10, 9, 30, tzinfo=IST))
    res = await mon.run_once()
    assert res == "found"


# 5.1 wiring keeps handlers testable without starting worker
def test_wiring_handler_construction_without_worker():
    from app.telegram.bot import build_application, build_application_with_monitoring

    conn = sqlite3.connect(":memory:")
    repo = TicketSearchRepository(conn)
    svc = TicketSearchService(repo, now=lambda: datetime.datetime(2026, 9, 10, 7, 0, tzinfo=IST))

    class DummyProvider:
        def search_stations(self, q):
            return []

    tcdd = FakeTcdd()

    # build_application should work without monitoring
    app = build_application("123:FAKE", 123, svc, DummyProvider())
    assert app is not None
    # build with monitoring should not start loop
    app2, mon = build_application_with_monitoring("123:FAKE", 123, svc, DummyProvider(), tcdd)
    assert app2 is not None
    assert mon is not None
    # monitoring not started – no sleeping yet; allow either attribute or bot_data
    has_service = hasattr(app2, "monitoring_service") or "monitoring_service" in getattr(app2, "bot_data", {})
    assert has_service


# 5.2 polling interval range already covered by test_polling_loop_uses_random_interval

def test_monitoring_preserves_boundaries_no_direct_sql():
    import pathlib

    text = pathlib.Path("app/monitoring/service.py").read_text()
    assert "import sqlite" not in text.lower()
    assert "execute(" not in text or "ticket_service" in text
    # Ensure uses ticket_service.get_active_search etc.
    assert "get_active_search" in text
    assert "search_trains" in text
    assert "notify_found" in text


def test_monitor_uses_normalized_train_availability():
    import pathlib

    text = pathlib.Path("app/monitoring/filtering.py").read_text()
    assert "TrainAvailability" in text
    assert "economy_available" in text
    assert "bookingClass" not in text
    assert "raw" not in text.lower() or "TrainAvailability" in text
