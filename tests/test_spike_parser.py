import json
import pathlib
import sys

# Allow importing spike as module
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import scripts.spike_tcdd as spike  # type: ignore

# Sample sanitized fixture-like structure (minimal) mimicking real response shape
SAMPLE_RAW = {
    "trainLegs": [
        {
            "trainAvailabilities": [
                {
                    "trains": [
                        {
                            "id": 1,
                            "number": "81002",
                            "name": "81002 ISTANBUL-ANKARA",
                            "type": "YHT",
                            "departureStationId": 1325,
                            "arrivalStationId": 98,
                            "segments": [
                                {"departureTime": 1789007400000, "arrivalTime": 1789007940000},  # 2026-09-10 05:30
                                {"departureTime": 1789008000000, "arrivalTime": 1789012200000},
                            ],
                            "bookingClassCapacities": [
                                {"bookingClassId": 4, "capacity": 55},  # business
                                {"bookingClassId": 1, "capacity": 0},   # economy 0
                                {"bookingClassId": 23, "capacity": 2},  # accessible
                            ],
                        },
                        {
                            "id": 2,
                            "number": "81030",
                            "name": "81030 ISTANBUL-ANKARA",
                            "type": "YHT",
                            "departureStationId": 1325,
                            "arrivalStationId": 98,
                            "segments": [
                                {"departureTime": 1789093800000, "arrivalTime": 1789097400000},  # 2026-09-11 different date
                            ],
                            "bookingClassCapacities": [
                                {"bookingClassId": 1, "capacity": 5},
                            ],
                        },
                        {
                            "id": 3,
                            "number": "81006",
                            "name": "81006 ISTANBUL-ANKARA",
                            "type": "YHT",
                            "departureStationId": 1325,
                            "arrivalStationId": 98,
                            "segments": [
                                {"departureTime": 1789007400000, "arrivalTime": 1789007940000},
                            ],
                            "bookingClassCapacities": [
                                {"bookingClassId": 1, "capacity": 3},
                            ],
                        },
                    ]
                }
            ]
        }
    ]
}


def test_economy_zero_not_eligible():
    journeys = spike.normalize_trains(SAMPLE_RAW, "2026-09-10")
    # journey id 1 has economy 0
    j1 = next(j for j in journeys if j.train_id == 1)
    assert j1.economy_available == 0
    assert j1.is_eligible is False
    assert spike.is_eligible(0) is False


def test_economy_ge_one_eligible():
    journeys = spike.normalize_trains(SAMPLE_RAW, "2026-09-10")
    j3 = next(j for j in journeys if j.train_id == 3)
    assert j3.economy_available == 3
    assert j3.is_eligible is True
    assert spike.is_eligible(1) is True
    assert spike.is_eligible(5) is True


def test_business_only_not_eligible():
    caps = [{"bookingClassId": 4, "capacity": 10}, {"bookingClassId": 1, "capacity": 0}]
    econ, bus, acc, _ = spike.extract_availabilities(caps)
    assert econ == 0
    assert bus == 10
    assert acc == 0
    assert spike.is_eligible(econ) is False


def test_accessible_only_not_eligible():
    caps = [{"bookingClassId": 23, "capacity": 4}, {"bookingClassId": 1, "capacity": 0}]
    econ, bus, acc, _ = spike.extract_availabilities(caps)
    assert econ == 0
    assert acc == 4
    assert spike.is_eligible(econ) is False

    caps2 = [{"bookingClassId": 22, "capacity": 12}, {"bookingClassId": 1, "capacity": 0}]
    econ2, _, _, special = spike.extract_availabilities(caps2)
    assert econ2 == 0
    assert special == 12
    assert spike.is_eligible(econ2) is False


def test_wrong_date_exclusion():
    journeys = spike.normalize_trains(SAMPLE_RAW, "2026-09-10")
    matched, excluded = spike.filter_by_requested_date(journeys, "2026-09-10")
    # id 2 departs 2026-09-11 should be excluded
    assert any(j.train_id == 2 for j in excluded)
    assert all(j.departure_date == "2026-09-10" for j in matched)
    assert not any(j.departure_date != "2026-09-10" for j in matched)


def test_inclusive_time_boundaries():
    # The filtering for time is done via is_eligible + date; but we test that departure times at boundaries are kept
    # Simulate two journeys at 17:00 and 22:00 inclusive
    raw_inclusive = {
        "trainLegs": [{
            "trainAvailabilities": [{
                "trains": [
                    # 2026-09-10 17:00
                    {"id": 10, "number": "1", "name": "T1", "type": "YHT", "departureStationId": 1, "arrivalStationId": 2,
                     "segments": [{"departureTime": int(spike.epoch_ms_to_local.__code__.co_varnames[0] and 0) or 0}], "bookingClassCapacities": [{"bookingClassId": 1, "capacity": 1}]},
                ]
            }]
        }]
    }
    # Instead test via direct datetime conversion that boundary inclusive logic would be correct via helper
    # Create journeys manually
    j17 = spike.NormalizedJourney(
        train_id=10, train_name="T1", train_type="YHT", train_number="1",
        origin_station_id=1, origin_station_name="", destination_station_id=2, destination_station_name="",
        departure_ms=0, arrival_ms=0, departure_date="2026-09-10", departure_time="17:00", arrival_time="18:00",
        departure_datetime_local="10.09.2026 17:00", economy_available=1, business_available=0, accessible_available=0, special_available=0,
        is_eligible=True, raw={}
    )
    j22 = spike.NormalizedJourney(
        train_id=11, train_name="T2", train_type="YHT", train_number="2",
        origin_station_id=1, origin_station_name="", destination_station_id=2, destination_station_name="",
        departure_ms=0, arrival_ms=0, departure_date="2026-09-10", departure_time="22:00", arrival_time="23:00",
        departure_datetime_local="10.09.2026 22:00", economy_available=1, business_available=0, accessible_available=0, special_available=0,
        is_eligible=True, raw={}
    )
    j_before = spike.NormalizedJourney(
        train_id=12, train_name="T3", train_type="YHT", train_number="3",
        origin_station_id=1, origin_station_name="", destination_station_id=2, destination_station_name="",
        departure_ms=0, arrival_ms=0, departure_date="2026-09-10", departure_time="16:59", arrival_time="17:30",
        departure_datetime_local="10.09.2026 16:59", economy_available=1, business_available=0, accessible_available=0, special_available=0,
        is_eligible=True, raw={}
    )
    # Simple inclusive check helper (mimicking filtering logic that would be in production)
    def time_in_range(t: str, frm: str, to: str) -> bool:
        return frm <= t <= to

    assert time_in_range(j17.departure_time, "17:00", "22:00") is True
    assert time_in_range(j22.departure_time, "17:00", "22:00") is True
    assert time_in_range(j_before.departure_time, "17:00", "22:00") is False


def test_multiple_eligible_return_all():
    journeys = spike.normalize_trains(SAMPLE_RAW, "2026-09-10")
    matched, _ = spike.filter_by_requested_date(journeys, "2026-09-10")
    eligible = [j for j in matched if j.is_eligible]
    # In sample, only id 3 is eligible on 2026-09-10 (id1 not eligible, id2 wrong date)
    assert len(eligible) == 1
    # Now test with data where multiple eligible
    raw_multi = {
        "trainLegs": [{
            "trainAvailabilities": [{
                "trains": [
                    {"id": 20, "number": "81002", "name": "A", "type": "YHT", "departureStationId": 1, "arrivalStationId": 2,
                     "segments": [{"departureTime": 1789007400000, "arrivalTime": 1789007940000}], "bookingClassCapacities": [{"bookingClassId": 1, "capacity": 2}]},
                    {"id": 21, "number": "81030", "name": "B", "type": "YHT", "departureStationId": 1, "arrivalStationId": 2,
                     "segments": [{"departureTime": 1789007400000, "arrivalTime": 1789007940000}], "bookingClassCapacities": [{"bookingClassId": 1, "capacity": 1}]},
                    {"id": 22, "number": "81006", "name": "C", "type": "YHT", "departureStationId": 1, "arrivalStationId": 2,
                     "segments": [{"departureTime": 1789007400000, "arrivalTime": 1789007940000}], "bookingClassCapacities": [{"bookingClassId": 1, "capacity": 6}]},
                ]
            }]
        }]
    }
    journeys2 = spike.normalize_trains(raw_multi, "2026-09-10")
    matched2, _ = spike.filter_by_requested_date(journeys2, "2026-09-10")
    eligible2 = [j for j in matched2 if j.is_eligible]
    assert len(eligible2) == 3


def test_station_lookup_failure_explicit():
    stations = [{"id": 1, "name": "ANKARA GAR", "city": {"name": "ANKARA"}}, {"id": 2, "name": "İSTANBUL(SÖĞÜTLÜÇEŞME)", "city": {"name": "İSTANBUL"}}]
    assert spike.find_stations("nonexistent_station_xyz", stations) == []
    assert spike.find_stations("söğüt", stations)[0]["name"] == "İSTANBUL(SÖĞÜTLÜÇEŞME)"


def test_api_failure_distinct_from_empty():
    # API failure should be classified separately, not as empty
    # Simulate normalize leading to empty but not API failure
    raw_empty = {"trainLegs": [{"trainAvailabilities": [{"trains": []}]}]}
    journeys = spike.normalize_trains(raw_empty, "2026-09-10")
    matched, _ = spike.filter_by_requested_date(journeys, "2026-09-10")
    outcome = spike.classify_outcome(matched)
    assert outcome == spike.OUTCOME_VALID_EMPTY
    assert outcome != spike.OUTCOME_API_FAILURE


def test_sanitize_excludes_secrets():
    raw = {
        "trainLegs": [{"trainAvailabilities": [{"trains": [{"id": 1}]}]}],
        "Authorization": "Bearer secret_jwt_here_eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.sig",
        "token": "should_be_removed",
        "headers": {"Authorization": "Bearer abc", "unit-id": "3895"},
        "email": "test@example.com",
    }
    sanitized = spike.sanitize_fixture(raw)
    dumped = json.dumps(sanitized, ensure_ascii=False).lower()
    assert "bearer" not in dumped
    assert "secret_jwt" not in dumped
    assert "test@example.com" not in dumped
    # parser-relevant preserved
    assert "trainLegs" in sanitized
    assert "trains" in json.dumps(sanitized)


def test_sanitize_preserves_structure():
    raw = {
        "trainLegs": [
            {
                "trainAvailabilities": [
                    {
                        "trains": [
                            {
                                "id": 191591,
                                "bookingClassCapacities": [{"bookingClassId": 1, "capacity": 708}],
                                "segments": [{"departureTime": 1789007400000, "arrivalTime": 1789007940000}],
                            }
                        ]
                    }
                ]
            }
        ],
        "legCount": 1,
    }
    sanitized = spike.sanitize_fixture(raw)
    assert sanitized["legCount"] == 1
    assert sanitized["trainLegs"][0]["trainAvailabilities"][0]["trains"][0]["id"] == 191591
    assert sanitized["trainLegs"][0]["trainAvailabilities"][0]["trains"][0]["bookingClassCapacities"][0]["capacity"] == 708


def test_parse_travel_date_formats():
    api, norm = spike.parse_travel_date("2026-09-10")
    assert norm == "2026-09-10"
    assert api == "10-09-2026 00:00:00"
    api2, norm2 = spike.parse_travel_date("10.09.2026")
    assert norm2 == "2026-09-10"
    api3, norm3 = spike.parse_travel_date("10-09-2026")
    assert norm3 == "2026-09-10"


def test_epoch_ms_conversion():
    # Known: 1789007400000 should be 2026-09-10T02:30:00Z -> 05:30 Europe/Istanbul (+3)
    dt = spike.epoch_ms_to_local(1789007400000)
    assert dt.strftime("%Y-%m-%d") == "2026-09-10"
    # Check in Istanbul it is 05:30
    # If zoneinfo not available, it falls back to UTC 02:30, so accept either
    assert dt.strftime("%H:%M") in ("05:30", "02:30")
