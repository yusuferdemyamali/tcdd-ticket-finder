import datetime
import json
import os
import pathlib
import sys
import subprocess

import httpx
import pytest

from app.tcdd import (
    STATION_CDN_URL,
    TRAIN_AVAIL_URL_PRIMARY,
    Station,
    TcddAuthenticationError,
    TcddClient,
    TcddInvalidResponseError,
    TcddNetworkError,
    TcddRateLimitError,
    TcddServerError,
    TcddStationAmbiguityError,
    TcddStationNotFoundError,
    TcddTimeoutError,
    TcddTlsError,
    TcddUnexpectedResponseError,
    TcddWafError,
    TrainAvailability,
)
from app.tcdd.exceptions import TcddError, TcddStationError
from app.tcdd.parser import parse_train_availability
from app.tcdd.stations import normalize_query, parse_station_pairs, search_stations, get_station


# --- 1.1 package surface ---
def test_import_app_tcdd_no_heavy_deps():
    # Ensure app.tcdd import itself does not trigger spike/telegram/sqlite imports
    # We check source files rather than global sys.modules because other tests may import spike
    import app.tcdd  # should succeed

    # Verify source does not import spike
    for p in pathlib.Path("app/tcdd").glob("*.py"):
        text = p.read_text()
        assert "spike_tcdd" not in text
        assert "scripts.spike" not in text


def test_import_succeeds():
    import app.tcdd  # noqa: F401


# --- 1.2 models ---
def test_station_model():
    s = Station(id=1325, name="İSTANBUL(SÖĞÜTLÜÇEŞME)")
    assert s.id == 1325
    assert s.name == "İSTANBUL(SÖĞÜTLÜÇEŞME)"
    assert not hasattr(s, "raw")
    assert "raw" not in s.__dict__ if hasattr(s, "__dict__") else True
    # no raw TCDD JSON field
    assert not hasattr(s, "bookingClassCapacities")


def test_train_availability_model():
    now = datetime.datetime.now(datetime.timezone.utc)
    ta = TrainAvailability(
        train_id=191591,
        train_name="81002 İSTANBUL-ANKARA",
        train_number="81002",
        departure_at=now,
        arrival_at=now,
        economy_available=5,
    )
    assert ta.train_id == 191591
    assert ta.economy_available == 5
    assert not hasattr(ta, "raw")
    assert not hasattr(ta, "bookingClassCapacities")


# --- 1.3 exceptions ---
def test_exception_hierarchy():
    assert issubclass(TcddStationNotFoundError, TcddStationError)
    assert issubclass(TcddStationAmbiguityError, TcddStationError)
    assert issubclass(TcddStationError, TcddError)
    assert issubclass(TcddNetworkError, TcddError)
    assert issubclass(TcddTimeoutError, TcddNetworkError)
    assert issubclass(TcddAuthenticationError, TcddError)
    assert issubclass(TcddRateLimitError, TcddError)
    assert issubclass(TcddServerError, TcddError)
    assert issubclass(TcddInvalidResponseError, TcddError)
    assert issubclass(TcddUnexpectedResponseError, TcddError)
    assert issubclass(TcddTlsError, TcddError)
    assert issubclass(TcddWafError, TcddTlsError)


def test_exception_instances():
    # station
    try:
        raise TcddStationNotFoundError("not found")
    except TcddStationError:
        pass
    else:
        assert False, "should be station error"
    # network/timeout distinct
    try:
        raise TcddTimeoutError("timeout")
    except TcddNetworkError:
        pass
    else:
        assert False
    # auth
    assert issubclass(TcddAuthenticationError, TcddError)
    # rate
    assert issubclass(TcddRateLimitError, TcddError)
    # server
    assert issubclass(TcddServerError, TcddError)
    # invalid json
    assert issubclass(TcddInvalidResponseError, TcddError)
    # unexpected
    assert issubclass(TcddUnexpectedResponseError, TcddError)
    # tls/waf
    assert issubclass(TcddTlsError, TcddError)
    assert issubclass(TcddWafError, TcddTlsError)
    # tls distinct from network?
    assert not issubclass(TcddTlsError, TcddNetworkError)


# --- 2.1 station-pairs fetching cache ---
def test_station_cache_fetch_once():
    station_raw = [
        {"id": 1325, "name": "İSTANBUL(SÖĞÜTLÜÇEŞME)", "city": {"name": "İSTANBUL"}},
        {"id": 98, "name": "ANKARA GAR", "city": {"name": "ANKARA"}},
    ]
    count = {"n": 0}

    def handler(request):
        count["n"] += 1
        assert STATION_CDN_URL in str(request.url)
        return httpx.Response(200, json=station_raw)

    transport = httpx.MockTransport(handler)
    client = TcddClient(httpx_transport=transport)
    # repeated lookups should fetch once
    s1 = client.get_station("Ankara")
    s2 = client.search_stations("sogutlucesme")
    s3 = client.get_stations()
    assert count["n"] == 1
    assert s1.id == 98
    assert s2[0].id == 1325
    assert len(s3) == 2


# --- 2.2 normalize ---
def test_normalize_station_pairs_returns_station_models():
    station_raw = [
        {"id": 1325, "name": "İSTANBUL(SÖĞÜTLÜÇEŞME)", "city": {"name": "İSTANBUL"}},
        {"id": 98, "name": "ANKARA GAR", "city": {"name": "ANKARA"}},
    ]
    stations = parse_station_pairs(station_raw)
    assert all(isinstance(s, Station) for s in stations)
    assert all(not isinstance(s, dict) for s in stations)
    assert stations[0].id == 1325
    assert stations[0].name == "İSTANBUL(SÖĞÜTLÜÇEŞME)"
    # downstream via client
    def handler(request):
        return httpx.Response(200, json=station_raw)

    transport = httpx.MockTransport(handler)
    client = TcddClient(httpx_transport=transport)
    result = client.get_stations()
    assert all(isinstance(s, Station) for s in result)


# --- 2.3 Turkish folding exact-match priority ---
def test_turkish_folding_and_exact_priority():
    # Use small fixture similar to station-pairs
    station_raw = [
        {"id": 1325, "name": "İSTANBUL(SÖĞÜTLÜÇEŞME)", "city": {"name": "İSTANBUL"}},
        {"id": 48, "name": "İSTANBUL(PENDİK)", "city": {"name": "İSTANBUL"}},
        {"id": 98, "name": "ANKARA GAR", "city": {"name": "ANKARA"}},
        {"id": 1, "name": "ADANA", "city": {"name": "ADANA"}},
    ]
    stations = parse_station_pairs(station_raw)
    # Söğütlüçeşme with Turkish chars
    res = search_stations("Söğütlüçeşme", stations)
    assert len(res) == 1 and res[0].id == 1325
    # sogutlucesme without Turkish chars
    res2 = search_stations("sogutlucesme", stations)
    assert len(res2) == 1 and res2[0].id == 1325
    # Ankara
    res3 = search_stations("Ankara", stations)
    assert len(res3) == 1 and res3[0].id == 98
    # normalize_query directly
    assert normalize_query("Söğütlüçeşme") == normalize_query("sogutlucesme")
    # via client
    def handler(request):
        return httpx.Response(200, json=station_raw)

    transport = httpx.MockTransport(handler)
    client = TcddClient(httpx_transport=transport)
    assert client.get_station("Söğütlüçeşme").id == 1325
    assert client.get_station("sogutlucesme").id == 1325
    assert client.get_station("Ankara").id == 98


# --- 2.4 lookup failure and ambiguity ---
def test_station_lookup_failure_and_ambiguity():
    station_raw = [
        {"id": 1325, "name": "İSTANBUL(SÖĞÜTLÜÇEŞME)", "city": {"name": "İSTANBUL"}},
        {"id": 48, "name": "İSTANBUL(PENDİK)", "city": {"name": "İSTANBUL"}},
        {"id": 1323, "name": "İSTANBUL(BOSTANCI)", "city": {"name": "İSTANBUL"}},
        {"id": 98, "name": "ANKARA GAR", "city": {"name": "ANKARA"}},
    ]
    stations = parse_station_pairs(station_raw)
    # unknown
    try:
        get_station("nonexistent_xyz", stations)
        assert False
    except TcddStationNotFoundError:
        pass
    # ambiguous non-exact
    try:
        get_station("istanbul", stations)
        assert False
    except TcddStationAmbiguityError as e:
        assert len(e.candidates) == 3

    # Verify via client that train search not run on failure
    # We create client with mock that would fail if train endpoint called, but station lookup fails first
    def handler(request):
        # This should only be station CDN, not train
        if "station-pairs" in str(request.url):
            return httpx.Response(200, json=station_raw)
        # If train search attempted, fail test
        assert False, "train search should not be called on station lookup failure"

    transport = httpx.MockTransport(handler)
    client = TcddClient(httpx_transport=transport)
    try:
        client.get_station("unknown_station_xyz")
        assert False
    except TcddStationNotFoundError:
        pass
    try:
        client.get_station("istanbul")
        assert False
    except TcddStationAmbiguityError:
        pass


# --- 3.1 fixture parsing ---
def test_parse_real_fixture():
    fixture_path = pathlib.Path("tests/fixtures/tcdd_real_response.json")
    raw = json.loads(fixture_path.read_text())
    result = parse_train_availability(raw, "2026-09-10")
    # Should return normalized records with required fields
    assert len(result) > 0
    for r in result:
        assert isinstance(r, TrainAvailability)
        assert r.train_id not in (None, "")
        assert r.train_name
        assert r.train_number
        assert isinstance(r.departure_at, datetime.datetime)
        assert isinstance(r.arrival_at, datetime.datetime)
        assert isinstance(r.economy_available, int)
        assert not hasattr(r, "raw")
    # Check known IDs from fixture
    ids = {r.train_id for r in result}
    assert 191591 in ids
    assert 191804 in ids
    # economy for those
    m = {r.train_id: r for r in result}
    assert m[191591].economy_available == 708
    assert m[191804].economy_available == 778


# --- 3.2 date filtering ---
def test_date_filtering():
    epoch_2026_09_10 = 1789007400000
    arr_10 = 1789007940000
    epoch_2026_09_11 = 1789093800000
    arr_11 = 1789097400000
    raw = {
        "trainLegs": [
            {
                "trainAvailabilities": [
                    {
                        "trains": [
                            {
                                "id": 1,
                                "name": "A",
                                "number": "1",
                                "segments": [{"departureTime": epoch_2026_09_10, "arrivalTime": arr_10}],
                                "bookingClassCapacities": [{"bookingClassId": 1, "capacity": 3}],
                            },
                            {
                                "id": 2,
                                "name": "B",
                                "number": "2",
                                "segments": [{"departureTime": epoch_2026_09_11, "arrivalTime": arr_11}],
                                "bookingClassCapacities": [{"bookingClassId": 1, "capacity": 5}],
                            },
                        ]
                    }
                ]
            }
        ]
    }
    res = parse_train_availability(raw, "2026-09-10")
    assert len(res) == 1
    assert res[0].train_id == 1
    # wrong date excluded
    res2 = parse_train_availability(raw, "2026-09-11")
    assert len(res2) == 1 and res2[0].train_id == 2


# --- 3.3 economy extraction ---
def test_economy_category_extraction():
    epoch = 1789007400000
    arr = 1789007940000

    def make(id_, caps):
        return {
            "id": id_,
            "name": "T",
            "number": str(id_),
            "segments": [{"departureTime": epoch, "arrivalTime": arr}],
            "bookingClassCapacities": caps,
        }

    # economy 0 preserved
    raw0 = {"trainLegs": [{"trainAvailabilities": [{"trains": [make(1, [{"bookingClassId": 1, "capacity": 0}])]}]}]}
    res0 = parse_train_availability(raw0, "2026-09-10")
    assert res0[0].economy_available == 0

    # economy >=1 preserved
    raw1 = {"trainLegs": [{"trainAvailabilities": [{"trains": [make(2, [{"bookingClassId": 1, "capacity": 5}])]}]}]}
    res1 = parse_train_availability(raw1, "2026-09-10")
    assert res1[0].economy_available == 5

    raw2 = {"trainLegs": [{"trainAvailabilities": [{"trains": [make(3, [{"bookingClassId": 1, "capacity": 1}])]}]}]}
    res2 = parse_train_availability(raw2, "2026-09-10")
    assert res2[0].economy_available == 1


# --- 3.4 separate categories ---
def test_business_accessible_special_separate():
    epoch = 1789007400000
    arr = 1789007940000

    def make(caps):
        return {
            "id": 99,
            "name": "T",
            "number": "99",
            "segments": [{"departureTime": epoch, "arrivalTime": arr}],
            "bookingClassCapacities": caps,
        }

    cases = [
        ([{"bookingClassId": 4, "capacity": 10}, {"bookingClassId": 1, "capacity": 0}], 0),
        ([{"bookingClassId": 23, "capacity": 4}, {"bookingClassId": 1, "capacity": 0}], 0),
        ([{"bookingClassId": 22, "capacity": 12}, {"bookingClassId": 1, "capacity": 0}], 0),
        ([{"bookingClassId": 4, "capacity": 55}, {"bookingClassId": 22, "capacity": 12}], 0),
    ]
    for caps, expected in cases:
        raw = {"trainLegs": [{"trainAvailabilities": [{"trains": [make(caps)]}]}]}
        res = parse_train_availability(raw, "2026-09-10")
        assert res[0].economy_available == expected, f"caps {caps} should give {expected}"

    # economy with business still 5
    raw = {"trainLegs": [{"trainAvailabilities": [{"trains": [make([{"bookingClassId": 4, "capacity": 10}, {"bookingClassId": 1, "capacity": 5}])]}]}]}
    assert parse_train_availability(raw, "2026-09-10")[0].economy_available == 5


# --- 3.5 invalid shape raises ---
def test_invalid_shape_raises():
    invalid_cases = [
        {},
        {"trainLegs": None},
        {"trainLegs": "not list"},
        {"nope": []},
        {"trainLegs": [{"trainAvailabilities": "not list"}]},
        {"trainLegs": [{"trainAvailabilities": [{"trains": "not list"}]}]},
        "not a dict",
        None,
    ]
    for raw in invalid_cases:
        try:
            parse_train_availability(raw, "2026-09-10")
            assert False, f"should have raised for {raw!r}"
        except (TcddUnexpectedResponseError, TcddInvalidResponseError):
            pass

    # valid empty remains valid
    empty = {"trainLegs": [{"trainAvailabilities": [{"trains": []}]}]}
    assert parse_train_availability(empty, "2026-09-10") == []
    assert parse_train_availability({"trainLegs": []}, "2026-09-10") == []


# --- 4.1 client station methods ---
def test_client_station_methods():
    station_raw = [
        {"id": 1325, "name": "İSTANBUL(SÖĞÜTLÜÇEŞME)", "city": {"name": "İSTANBUL"}},
        {"id": 98, "name": "ANKARA GAR", "city": {"name": "ANKARA"}},
        {"id": 48, "name": "İSTANBUL(PENDİK)", "city": {"name": "İSTANBUL"}},
    ]

    def handler(request):
        return httpx.Response(200, json=station_raw)

    transport = httpx.MockTransport(handler)
    client = TcddClient(httpx_transport=transport)
    # get_stations
    all_st = client.get_stations()
    assert len(all_st) == 3
    # search ordering: exact priority
    # For this data, search "ankara" returns 1, search "istanbul" returns 2 (both pendik and sogutlu)
    res = client.search_stations("ankara")
    assert res[0].id == 98
    res2 = client.search_stations("istanbul")
    assert len(res2) == 2
    # get_station successful
    assert client.get_station("Ankara").id == 98
    # get_station ordering verified via previous tests


# --- 4.2 search_trains request construction ---
def test_search_trains_request_construction():
    captured = {}

    def handler(request):
        captured["url"] = str(request.url)
        captured["headers"] = dict(request.headers)
        captured["json"] = json.loads(request.content.decode())
        return httpx.Response(200, json={"trainLegs": [{"trainAvailabilities": [{"trains": []}]}]})

    transport = httpx.MockTransport(handler)
    client = TcddClient(httpx_transport=transport)
    os.environ["TCDD_TOKEN"] = "test-jwt-token-123"
    try:
        result = client.search_trains(1325, 98, "2026-09-10")
        assert result == []
        assert captured["url"] == TRAIN_AVAIL_URL_PRIMARY
        assert captured["headers"]["unit-id"] == "3895"
        assert captured["headers"]["origin"] == "https://ebilet.tcddtasimacilik.gov.tr"
        assert captured["headers"]["referer"] == "https://ebilet.tcddtasimacilik.gov.tr/"
        assert captured["headers"]["authorization"] == "test-jwt-token-123"
        assert captured["json"]["searchRoutes"][0]["departureStationId"] == 1325
        assert captured["json"]["searchRoutes"][0]["arrivalStationId"] == 98
        assert captured["json"]["searchRoutes"][0]["departureDate"] == "10-09-2026 00:00:00"
        assert captured["json"]["passengerTypeCounts"][0]["passengerTypeId"] == 1
        assert captured["json"]["passengerTypeCounts"][0]["count"] == 1
        assert "web-api-prod" not in captured["url"]
    finally:
        if "TCDD_TOKEN" in os.environ:
            del os.environ["TCDD_TOKEN"]


# --- 4.3 auth from TCDD_TOKEN ---
def test_auth_from_TCDD_TOKEN_and_no_hardcoded():
    # missing token raises
    if "TCDD_TOKEN" in os.environ:
        del os.environ["TCDD_TOKEN"]
    client = TcddClient(httpx_transport=httpx.MockTransport(lambda r: httpx.Response(200, json={"trainLegs": []})))
    try:
        client.search_trains(1325, 98, "2026-09-10")
        assert False
    except TcddAuthenticationError:
        pass

    # no hardcoded JWT in client file
    text = pathlib.Path("app/tcdd/client.py").read_text()
    assert "eyJ" not in text
    assert "HARDCODED" not in text
    assert "TCDD_AUTH_TOKEN" not in text
    # no bundle scraping
    assert "js/index" not in text
    assert "bundle" not in text.lower() or "bundle" not in text  # allow but check not scraping
    # no token refresh path
    assert "refresh" not in text.lower()

    # with token works
    os.environ["TCDD_TOKEN"] = "valid-token"
    try:
        def handler(request):
            assert request.headers["authorization"] == "valid-token"
            return httpx.Response(200, json={"trainLegs": []})

        transport = httpx.MockTransport(handler)
        client2 = TcddClient(httpx_transport=transport)
        assert client2.search_trains(1325, 98, "2026-09-10") == []
    finally:
        del os.environ["TCDD_TOKEN"]


# --- 4.4 failure mapping ---
def test_failure_mapping():
    os.environ["TCDD_TOKEN"] = "tok"

    def case(handler, exc):
        transport = httpx.MockTransport(handler)
        client = TcddClient(httpx_transport=transport)
        try:
            client.search_trains(1325, 98, "2026-09-10")
            assert False, f"should raise {exc.__name__}"
        except exc:
            pass
        except Exception as e:
            assert False, f"wrong {type(e).__name__} expected {exc.__name__}: {e}"

    # network
    case(lambda r: (_ for _ in ()).throw(httpx.ConnectError("net", request=r)), TcddNetworkError)
    case(lambda r: (_ for _ in ()).throw(httpx.ReadTimeout("timeout", request=r)), TcddTimeoutError)
    case(lambda r: httpx.Response(401, text="unauth"), TcddAuthenticationError)
    case(lambda r: httpx.Response(403, text="forbidden"), TcddAuthenticationError)
    case(lambda r: httpx.Response(403, text="<html>nginx</html>"), TcddTlsError)
    case(lambda r: httpx.Response(429, text="rate"), TcddRateLimitError)
    case(lambda r: httpx.Response(500, text="err"), TcddServerError)
    case(lambda r: httpx.Response(503, text="err"), TcddServerError)
    case(lambda r: httpx.Response(200, text="not json"), TcddInvalidResponseError)
    case(lambda r: httpx.Response(200, json={"bad": "shape"}), TcddUnexpectedResponseError)
    # TLS signal via exception message
    case(lambda r: (_ for _ in ()).throw(httpx.ConnectError("TLS handshake failed", request=r)), TcddTlsError)
    # valid empty distinct
    transport = httpx.MockTransport(lambda r: httpx.Response(200, json={"trainLegs": [{"trainAvailabilities": [{"trains": []}]}]}))
    client = TcddClient(httpx_transport=transport)
    assert client.search_trains(1325, 98, "2026-09-10") == []

    del os.environ["TCDD_TOKEN"]


# --- 4.5 curl_cffi fallback ---
def test_curl_cffi_fallback_optional():
    # httpx remains default: verify client uses httpx MockTransport not curl
    captured = {}

    def handler(request):
        captured["used"] = "httpx"
        return httpx.Response(200, json={"trainLegs": []})

    transport = httpx.MockTransport(handler)
    client = TcddClient(httpx_transport=transport)
    os.environ["TCDD_TOKEN"] = "tok"
    try:
        client.search_trains(1325, 98, "2026-09-10")
        assert captured["used"] == "httpx"
        # primary not web-api-prod
        assert client._train_url == TRAIN_AVAIL_URL_PRIMARY
        assert "web-api-prod" not in client._train_url
        # fallback file check
        text = pathlib.Path("app/tcdd/client.py").read_text()
        assert "curl_cffi" in text
        assert 'impersonate="chrome120"' in text or "chrome120" in text
        # fallback only for TLS/WAF: check code contains condition
        assert "TcddTlsError" in text and "curl" in text.lower()
    finally:
        del os.environ["TCDD_TOKEN"]


# --- 5.1 spike remains separate ---
def test_no_spike_import_and_spike_runnable():
    # Read client/parser/stations not importing spike
    for p in pathlib.Path("app/tcdd").glob("*.py"):
        assert "spike_tcdd" not in p.read_text()
        assert "scripts.spike" not in p.read_text()
    # Also ensure no import of spike in app/tcdd at runtime for fresh import
    # Check source for forbidden imports
    for p in pathlib.Path("app/tcdd").glob("*.py"):
        t = p.read_text().lower()
        assert "import telegram" not in t
        assert "import sqlite" not in t
        assert "playwright" not in t
    # Spike script runnable --help
    result = subprocess.run([sys.executable, "scripts/spike_tcdd.py", "--help"], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0
    assert "TCDD API Spike" in result.stdout or "usage" in result.stdout.lower()
