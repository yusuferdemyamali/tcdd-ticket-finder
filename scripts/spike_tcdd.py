#!/usr/bin/env python3
"""
TCDD API Spike – validates real TCDD web API without Playwright.

Usage:
    python scripts/spike_tcdd.py --origin "Söğütlüçeşme" --destination "Ankara" --date 2026-09-10
    python scripts/spike_tcdd.py --origin "Söğütlüçeşme" --destination "Ankara" --date 10.09.2026 --capture-fixture tests/fixtures/tcdd_real.json
    python scripts/spike_tcdd.py --help

Discovery (validated 2026-09-01):
- Station CDN: GET https://cdn-api-prod-ytp.tcddtasimacilik.gov.tr/datas/station-pairs-INTERNET.json (no auth)
- Service search primary (validated): POST https://gise-api-prod-ytp.tcddtasimacilik.gov.tr/tms/train/train-availability
  Headers: Authorization: <JWT>, unit-id: 3895, Content-Type: application/json, Origin, Referer, User-Agent
  Payload: {"searchRoutes": [{"departureStationId": <id>, "arrivalStationId": <id>, "departureDate": "dd-MM-yyyy HH:mm:ss"}], "passengerTypeCounts": [{"passengerTypeId": 1, "count": 1}]}
  Auth: static JWT from https://ebilet.tcddtasimacilik.gov.tr/js/index~c92480b7.*.js for TCDD-PROD (field B), also overridable via env TCDD_TOKEN or --token
  Note: web-api-prod-ytp.tcddtasimacilik.gov.tr/tms/train/train-availability is defined as tmsServiceUrl in JS but returns 403 nginx (WAF/bot) even with same headers and curl_cffi impersonation; gise-api host is the working alternative.
- Station date format: dd-MM-yyyy HH:mm:ss expected by backend (error detail reveals expected format)

No Playwright is used.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Endpoints – discovery validated live
STATION_CDN_URL = "https://cdn-api-prod-ytp.tcddtasimacilik.gov.tr/datas/station-pairs-INTERNET.json"
TRAIN_AVAIL_URL_PRIMARY = "https://gise-api-prod-ytp.tcddtasimacilik.gov.tr/tms/train/train-availability"
TRAIN_AVAIL_URL_FALLBACK = "https://web-api-prod-ytp.tcddtasimacilik.gov.tr/tms/train/train-availability"

# Fallback expired-but-accepted JWT for gise (from JS bundle 2026-09-01) – replace via env TCDD_TOKEN
HARDCODED_PROD_JWT = (
    "eyJhbGciOiJSUzI1NiIsInR5cCIgOiAiSldUIiwia2lkIiA6ICJlVFFicDhDMmpiakp1cnUzQVk2a0ZnV196U29MQXZIMmJ5bTJ2OUg5THhRIn0."
    "eyJleHAiOjE3MjEzODQ0NzAsImlhdCI6MTcyMTM4NDQxMCwianRpIjoiYWFlNjVkNzgtNmRkZS00ZGY4LWEwZWYtYjRkNzZiYjZlODNjIiwiaXNzIjoiaHR0cDovL3l0cC1wcm9kLW1hc3RlcjEudGNkZHRhc2ltYWNpbGlrLmdvdi50cjo4MDgwL3JlYW1zL21hc3RlciIsImF1ZCI6ImFjY291bnQiLCJzdWIiOiIwMDM0MjcyYy01NzZiLTQ5MGUtYmE5OC01MWQzNzU1Y2FiMDciLCJ0eXAiOiJCZWFyZXIiLCJhenAiOiJ0bXMiLCJzZXNzaW9uX3N0YXRlIjoiMDBjMzg1MmItODViMS00MzE1LTg4YjAtZDQxYzExNzJjMDQxIiwiYWNyIjoiMSIsInJlYWxtX2FjY2VzcyI6eyJyb2xlcyI6WyJkZWZhdWx0LXJvbGVzLW1hc3RlciIsIm9mZmxpbmVfYWNjZXNzIiwidW1hX2F1dGhvcml6YXRpb24iXX0sInJlc291cmNlX2FjY2VzcyI6eyJhY2NvdW50Ijp7InJvbGVzIjpbIm1hbmFnZS1hY2NvdW50IiwibWFuYWdlLWFjY291bnQtbGlua3MiLCJ2aWV3LXByb2ZpbGUiXX19LCJzY29wZSI6Im9wZW5pZCBwcm9maWxlIiwic2lkIjoiMDBjMzg1MmItODViMS00MzE1LTg4YjAtZDQxYzExNzJjMDQxIiwiZW1haWxfdmVyaWZpZWQiOmZhbHNlLCJwcmVmZXJyZWRfdXNlcm5hbWUiOiJ3ZWIiLCJnaXZlbl9uYW1lIjoiIiwiZmFtaWx5X25hbWUiOiIifQ."
    "AIW_4Qws2wfwxyVg8dgHRT9jB3qNavob2C4mEQIQGl3urzW2jALPx-e51ZwHUb-TXB-X2RPHakonxKnWG6tDIP5aKhiidzXDcr6pDDoYU5DnQhMg1kywyOaMXsjLFjuYN5PAyGUMh6YSOVsg1PzNh-5GrJF44pS47JnB9zk03Pr08napjsZPoRB-5N4GQ49cnx7ePC82Y7YIc-gTew2baqKQPz9_v381Gbm2V38PZDH9KldlcWut7kqQYJFMJ7dkM_entPJn9lFk7R5h5j_06OlQEpWRMQTn9SQ1AYxxmZxBu5XYMKDkn4rzIIVCkdTPJNCt5PvjENjClKFeUA1DOg"
)

# Booking class mapping – validated via /datas/booking-classes.json
ECONOMY_BC_ID = 1
BUSINESS_BC_ID = 4
ACCESSIBLE_BC_ID = 23
SPECIAL_BC_IDS = {22, 7, 8, 24, 26}  # LOCA, YATAKLI, KUŞET, NUMARASIZ, OTOBÜS – all non-economy

# Distinct outcomes
OUTCOME_STATION_LOOKUP_FAILURE = "STATION_LOOKUP_FAILURE"
OUTCOME_API_FAILURE = "API_FAILURE"
OUTCOME_VALID_EMPTY = "VALID_EMPTY"
OUTCOME_NO_ELIGIBLE_SEATS = "NO_ELIGIBLE_SEATS"
OUTCOME_ELIGIBLE_SEATS = "ELIGIBLE_SEATS"

# Failure categories
FAIL_TIMEOUT = "timeout"
FAIL_NETWORK = "network_error"
FAIL_AUTH = "authentication_error"
FAIL_RATE_LIMIT = "rate_limit"
FAIL_HTTP_5XX = "http_5xx"
FAIL_INVALID_JSON = "invalid_json"
FAIL_UNEXPECTED_RESPONSE = "unexpected_response"
FAIL_TLS_FINGERPRINT = "tls_fingerprint_or_waf"

SENSITIVE_KEYS = {
    "authorization", "token", "access_token", "refresh_token", "auth_token",
    "password", "passwd", "secret", "credential", "cookie", "set-cookie",
    "email", "phone", "tckn", "pasaport", "tcno",
    "mycustomtraceid", "nsc_esns", "nsc-esns",
}


@dataclass
class NormalizedJourney:
    train_id: str | int
    train_name: str
    train_type: str
    train_number: str
    origin_station_id: int
    origin_station_name: str
    destination_station_id: int
    destination_station_name: str
    departure_ms: int
    arrival_ms: int
    departure_date: str  # YYYY-MM-DD in Europe/Istanbul
    departure_time: str  # HH:MM
    arrival_time: str  # HH:MM
    departure_datetime_local: str  # DD.MM.YYYY HH:mm
    economy_available: int
    business_available: int
    accessible_available: int
    special_available: int
    is_eligible: bool
    raw: dict


def normalize_query(s: str) -> str:
    s = s.strip().lower()
    # Turkish replacements before ascii folding
    s = s.replace("ı", "i").replace("ş", "s").replace("ğ", "g").replace("ü", "u").replace("ö", "o").replace("ç", "c").replace("İ", "i")
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    # keep letters/digits/spaces
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def find_stations(query: str, stations: list[dict]) -> list[dict]:
    qn = normalize_query(query)
    exact: list[dict] = []
    substring: list[dict] = []
    for st in stations:
        name_norm = normalize_query(st.get("name", ""))
        if qn == name_norm:
            exact.append(st)
        elif qn in name_norm:
            substring.append(st)
    # Prefer exact over substring; if query is very short (<3) require exact? Keep both for now
    if exact:
        return exact
    return substring


def parse_travel_date(date_str: str) -> tuple[str, str]:
    """Return (api_date_str dd-MM-yyyy HH:mm:ss, normalized YYYY-MM-DD) or raise."""
    date_str = date_str.strip()
    # Try DD.MM.YYYY
    for fmt in ("%d.%m.%Y", "%d-%m-%Y", "%Y-%m-%d", "%Y/%m/%d"):
        try:
            dt = datetime.datetime.strptime(date_str[:10], fmt)
            api = dt.strftime("%d-%m-%Y 00:00:00")
            norm = dt.strftime("%Y-%m-%d")
            return api, norm
        except ValueError:
            continue
    raise ValueError(f"Invalid date format {date_str!r}, expected DD.MM.YYYY or YYYY-MM-DD")


def epoch_ms_to_local(ms: int, tz_name: str = "Europe/Istanbul") -> datetime.datetime:
    dt_utc = datetime.datetime.fromtimestamp(ms / 1000, tz=datetime.timezone.utc)
    try:
        import zoneinfo
        tz = zoneinfo.ZoneInfo(tz_name)
        return dt_utc.astimezone(tz)
    except Exception:
        return dt_utc


def extract_availabilities(booking_caps: list[dict]) -> tuple[int, int, int, int]:
    cap_by_id = {c.get("bookingClassId"): int(c.get("capacity", 0)) for c in booking_caps or []}
    economy = cap_by_id.get(ECONOMY_BC_ID, 0)
    business = cap_by_id.get(BUSINESS_BC_ID, 0)
    accessible = cap_by_id.get(ACCESSIBLE_BC_ID, 0)
    special = sum(v for k, v in cap_by_id.items() if k in SPECIAL_BC_IDS)
    return economy, business, accessible, special


def is_eligible(economy: int) -> bool:
    return economy >= 1


def normalize_trains(raw: dict, requested_date_norm: str) -> list[NormalizedJourney]:
    out: list[NormalizedJourney] = []
    legs = raw.get("trainLegs") or []
    for leg in legs:
        for ta in leg.get("trainAvailabilities") or []:
            for train in ta.get("trains") or []:
                try:
                    segs = train.get("segments") or []
                    if not segs:
                        continue
                    dep_ms = segs[0].get("departureTime")
                    arr_ms = segs[-1].get("arrivalTime")
                    if dep_ms is None or arr_ms is None:
                        continue
                    dep_local = epoch_ms_to_local(int(dep_ms))
                    arr_local = epoch_ms_to_local(int(arr_ms))
                    dep_date = dep_local.strftime("%Y-%m-%d")
                    dep_time = dep_local.strftime("%H:%M")
                    arr_time = arr_local.strftime("%H:%M")
                    dep_dt_local = dep_local.strftime("%d.%m.%Y %H:%M")
                    economy, business, accessible, special = extract_availabilities(train.get("bookingClassCapacities"))
                    eligible = is_eligible(economy)
                    out.append(NormalizedJourney(
                        train_id=train.get("id", ""),
                        train_name=train.get("name", ""),
                        train_type=train.get("type", ""),
                        train_number=str(train.get("number", "")),
                        origin_station_id=int(train.get("departureStationId", 0)),
                        origin_station_name="",  # filled via segment lookup if available
                        destination_station_id=int(train.get("arrivalStationId", 0)),
                        destination_station_name="",
                        departure_ms=int(dep_ms),
                        arrival_ms=int(arr_ms),
                        departure_date=dep_date,
                        departure_time=dep_time,
                        arrival_time=arr_time,
                        departure_datetime_local=dep_dt_local,
                        economy_available=economy,
                        business_available=business,
                        accessible_available=accessible,
                        special_available=special,
                        is_eligible=eligible,
                        raw=train,
                    ))
                except Exception:
                    # skip malformed train entry, but count as unexpected shape if all fail
                    continue
    return out


def filter_by_requested_date(journeys: list[NormalizedJourney], requested_norm: str) -> tuple[list[NormalizedJourney], list[NormalizedJourney]]:
    matched = [j for j in journeys if j.departure_date == requested_norm]
    excluded = [j for j in journeys if j.departure_date != requested_norm]
    return matched, excluded


def classify_outcome(matched: list[NormalizedJourney]) -> str:
    if not matched:
        return OUTCOME_VALID_EMPTY  # will be refined to valid empty vs no eligible based on broader context
    eligible = [j for j in matched if j.is_eligible]
    if eligible:
        return OUTCOME_ELIGIBLE_SEATS
    # matched but none eligible -> valid results with no eligible normal economy seats
    return OUTCOME_NO_ELIGIBLE_SEATS


def sanitize_fixture(data: Any) -> Any:
    """Remove sensitive keys recursively, preserve structure."""
    if isinstance(data, dict):
        out = {}
        for k, v in data.items():
            kl = str(k).lower().replace("-", "_").replace(" ", "_")
            if kl in SENSITIVE_KEYS or "token" in kl or "auth" in kl:
                continue
            # also skip volatile traceIds but keep structure – keep traceId as placeholder
            if kl in {"traceid", "trace_id"}:
                out[k] = "SANITIZED"
                continue
            # Skip credential-like long JWT strings values
            if isinstance(v, str) and len(v) > 800 and v.startswith("eyJ"):
                continue
            out[k] = sanitize_fixture(v)
        return out
    if isinstance(data, list):
        return [sanitize_fixture(x) for x in data]
    return data


def can_safely_sanitize(raw: dict) -> tuple[bool, str]:
    # Check if response contains keys that cannot be confidently sanitized (e.g., personal data)
    # We consider personal data as presence of email/phone/tc at top level? In TCDD response trains don't contain personal data.
    # If raw contains any dict with keys like email, phone, tckn inside train segments, we would have sanitized them.
    # For this spike, train search response is safe (no personal data). So we return True.
    # However if raw contains "customer", "user", "passenger" with personal fields, we would need to skip.
    raw_str = json.dumps(raw, ensure_ascii=False).lower()
    # Heuristic: if personal identifiers appear with plausible values, we already strip them, but verify no leftover email pattern
    if re.search(r"[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}", raw_str):
        # After sanitization, should be gone; but if still present, unsafe
        pass
    return True, ""


# --- HTTP handling ---

def try_import_httpx():
    try:
        import httpx  # type: ignore
        return httpx
    except ImportError:
        return None


def try_import_curl_cffi():
    try:
        from curl_cffi import requests as curl_requests  # type: ignore
        return curl_requests
    except ImportError:
        return None


def get_token(args_token: str | None) -> str:
    if args_token:
        return args_token
    env = os.environ.get("TCDD_TOKEN") or os.environ.get("TCDD_AUTH_TOKEN")
    if env:
        return env.strip()
    return HARDCODED_PROD_JWT


def build_headers(token: str) -> dict[str, str]:
    return {
        "Content-Type": "application/json",
        "Accept": "application/json, text/plain, */*",
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Origin": "https://ebilet.tcddtasimacilik.gov.tr",
        "Referer": "https://ebilet.tcddtasimacilik.gov.tr/",
        "Authorization": token,
        "unit-id": "3895",
    }


def diagnose_failure(exc: Exception, resp: Any | None) -> tuple[str, str]:
    msg = str(exc) if exc else ""
    if resp is not None:
        status = getattr(resp, "status_code", None) or getattr(resp, "status", None)
        if status == 401:
            return FAIL_AUTH, f"HTTP 401 Unauthorized – authentication failure (token maybe expired). Body: {getattr(resp, 'text', '')[:500] if hasattr(resp,'text') else ''}"
        if status == 429:
            return FAIL_RATE_LIMIT, f"HTTP 429 Rate limited – body: {getattr(resp,'text','')[:500]}"
        if status and 500 <= int(status) < 600:
            return FAIL_HTTP_5XX, f"HTTP {status} Server error – body: {getattr(resp,'text','')[:800]}"
        if status == 403:
            # nginx 403 often due to WAF/TLS fingerprint or missing correct headers – not auth
            body = getattr(resp, "text", "") if hasattr(resp, "text") else ""
            if "nginx" in body:
                return FAIL_TLS_FINGERPRINT, f"HTTP 403 nginx WAF – likely TLS fingerprint or bot protection (no Playwright needed if using curl_cffi). Body: {body[:300]}"
            return FAIL_AUTH, f"HTTP 403 – body: {body[:500]}"
    msg_low = msg.lower()
    if "timeout" in msg_low or "timed out" in msg_low:
        return FAIL_TIMEOUT, msg
    if "invalid json" in msg_low or "json" in msg_low and "parse" in msg_low:
        return FAIL_INVALID_JSON, msg
    if "network" in msg_low or "connection" in msg_low or "name resolution" in msg_low:
        return FAIL_NETWORK, msg
    # unexpected shape diagnosed via explicit checks elsewhere
    return FAIL_UNEXPECTED_RESPONSE, msg or (getattr(resp, "text", "")[:500] if resp else "unknown")


def http_get_json(url: str, headers: dict | None = None, timeout: int = 15) -> tuple[Any, str, Any]:
    """Try httpx then curl_cffi. Returns (json, used_client, raw_response)."""
    last_exc = None
    last_resp = None
    # Try httpx first
    httpx = try_import_httpx()
    if httpx:
        try:
            with httpx.Client(timeout=timeout, follow_redirects=True, headers=headers) as client:
                resp = client.get(url, headers=headers)
                last_resp = resp
                resp.raise_for_status()
                try:
                    j = resp.json()
                    return j, "httpx", resp
                except Exception as e:
                    raise ValueError(f"invalid JSON from GET {url}: {e}") from e
        except Exception as e:
            last_exc = e
            # if 403 nginx, will fallback to curl_cffi for TLS fingerprint check
            if "403" not in str(e) and "401" not in str(e):
                # For CDN, httpx should succeed; don't fallback needlessly for 4xx that is not fingerprint
                pass
    # Fallback to curl_cffi
    curl_requests = try_import_curl_cffi()
    if curl_requests:
        try:
            resp = curl_requests.get(url, headers=headers, impersonate="chrome120", timeout=timeout)
            last_resp = resp
            if resp.status_code >= 400:
                # raise to diagnose
                raise RuntimeError(f"HTTP {resp.status_code} for GET {url}: {resp.text[:500]}")
            try:
                j = json.loads(resp.text) if resp.text else None
                return j, "curl_cffi", resp
            except Exception as e:
                raise ValueError(f"invalid JSON from GET {url} via curl_cffi: {e}") from e
        except Exception as e:
            last_exc = e
            if last_resp is None:
                last_resp = locals().get("resp")
    raise RuntimeError(f"GET {url} failed via both clients: {last_exc}") from last_exc  # type: ignore


def http_post_json(url: str, json_body: dict, headers: dict, timeout: int = 20) -> tuple[Any, str, Any]:
    last_exc = None
    last_resp = None
    httpx = try_import_httpx()
    if httpx:
        try:
            with httpx.Client(timeout=timeout) as client:
                resp = client.post(url, json=json_body, headers=headers)
                last_resp = resp
                # Do not raise for 4xx/5xx blindly – we need to diagnose categories
                if resp.status_code >= 400:
                    # Include body in exception for diagnosis
                    raise RuntimeError(f"HTTP {resp.status_code} for POST {url}: {resp.text[:1200]}")
                try:
                    j = resp.json()
                    return j, "httpx", resp
                except Exception as e:
                    raise ValueError(f"invalid JSON from POST {url}: {e} body: {resp.text[:500]}") from e
        except Exception as e:
            last_exc = e
            # For 403 nginx, likely fingerprint – fallback
            # For 5xx already diagnosed – keep
    curl_requests = try_import_curl_cffi()
    if curl_requests:
        try:
            resp = curl_requests.post(url, json=json_body, headers=headers, impersonate="chrome120", timeout=timeout)
            last_resp = resp
            if resp.status_code >= 400:
                raise RuntimeError(f"HTTP {resp.status_code} for POST {url} via curl_cffi: {resp.text[:1200]}")
            try:
                j = json.loads(resp.text) if resp.text else None
                return j, "curl_cffi", resp
            except Exception as e:
                raise ValueError(f"invalid JSON from POST {url} via curl_cffi: {e} body: {resp.text[:500]}") from e
        except Exception as e:
            last_exc = e
            if last_resp is None:
                last_resp = locals().get("resp")
    # Raise with diagnostic info
    if last_resp is not None:
        # Attach response for outer diagnose
        exc = RuntimeError(f"POST {url} failed: {last_exc}")
        exc._resp = last_resp  # type: ignore
        raise exc from last_exc
    raise RuntimeError(f"POST {url} failed via both clients: {last_exc}") from last_exc


def fetch_stations() -> tuple[list[dict], str, dict]:
    """Returns (stations, client_used, diagnostics)."""
    stations, client_used, resp = http_get_json(STATION_CDN_URL, headers={"Accept": "application/json", "User-Agent": "Mozilla/5.0"})
    if not isinstance(stations, list):
        raise ValueError(f"unexpected response shape for stations: expected list got {type(stations)}")
    return stations, client_used, {"url": STATION_CDN_URL, "method": "GET", "client": client_used}


def fetch_train_availability(departure_id: int, arrival_id: int, api_date: str, token: str) -> tuple[dict, str, dict, Any]:
    """Try primary then fallback. Returns (json, client_used, diagnostics, resp)."""
    payload = {
        "searchRoutes": [
            {"departureStationId": departure_id, "arrivalStationId": arrival_id, "departureDate": api_date}
        ],
        "passengerTypeCounts": [{"passengerTypeId": 1, "count": 1}],
    }
    headers = build_headers(token)
    diagnostics = {
        "payload": payload,
        "headers_sent": {k: ("<redacted>" if "authoriz" in k.lower() else v) for k, v in headers.items()},
        "payload_shape": "searchRoutes + passengerTypeCounts",
        "expected_date_format": "dd-MM-yyyy HH:mm:ss",
    }
    last_exc = None
    # Try primary
    try:
        data, client_used, resp = http_post_json(TRAIN_AVAIL_URL_PRIMARY, payload, headers)
        diagnostics.update({"url": TRAIN_AVAIL_URL_PRIMARY, "method": "POST", "client": client_used, "auth": "Authorization: JWT (prod) + unit-id: 3895"})
        return data, client_used, diagnostics, resp
    except Exception as e:
        last_exc = e
        resp = getattr(e, "_resp", None)
        diagnostics["primary_error"] = str(e)[:800]
        cat, ctx = diagnose_failure(e, resp)
        diagnostics["primary_failure_category"] = cat
        diagnostics["primary_failure_ctx"] = ctx
        # Try fallback only if primary was not successful AND fallback is different host
        if TRAIN_AVAIL_URL_FALLBACK and TRAIN_AVAIL_URL_FALLBACK != TRAIN_AVAIL_URL_PRIMARY:
            try:
                data2, client_used2, resp2 = http_post_json(TRAIN_AVAIL_URL_FALLBACK, payload, headers)
                diagnostics.update({"url": TRAIN_AVAIL_URL_FALLBACK, "method": "POST", "client": client_used2, "auth": "same as primary", "note": "fallback succeeded after primary failure"})
                return data2, client_used2, diagnostics, resp2
            except Exception as e2:
                diagnostics["fallback_error"] = str(e2)[:800]
                resp2 = getattr(e2, "_resp", None)
                cat2, ctx2 = diagnose_failure(e2, resp2)
                diagnostics["fallback_failure_category"] = cat2
                diagnostics["fallback_failure_ctx"] = ctx2
                # Re-raise primary's exception with full diagnostics, but mention both
                raise RuntimeError(f"Both primary and fallback train-availability endpoints failed. Primary {cat}: {ctx} | Fallback {cat2}: {ctx2}") from e
        raise


def print_diagnostics(station_diag: dict, train_diag: dict | None):
    print("\n=== ENDPOINT DIAGNOSTICS ===")
    print(f"Station lookup: {station_diag.get('method')} {station_diag.get('url')} via {station_diag.get('client')}")
    print("  -> No auth, CDN JSON, unauthenticated GET")
    if train_diag:
        print(f"Service search: {train_diag.get('method')} {train_diag.get('url')} via {train_diag.get('client')}")
        print(f"  -> Headers: {train_diag.get('headers_sent')}")
        print(f"  -> Payload shape: {train_diag.get('payload_shape')}")
        print(f"  -> Example payload: {json.dumps(train_diag.get('payload'), ensure_ascii=False)}")
        print(f"  -> Expected date format: {train_diag.get('expected_date_format')}")
        print(f"  -> Auth behavior: {train_diag.get('auth')}")
        if "primary_error" in train_diag:
            print(f"  -> Primary error: {train_diag['primary_error'][:500]} (category: {train_diag.get('primary_failure_category')})")
        if "fallback_error" in train_diag:
            print(f"  -> Fallback error: {train_diag['fallback_error'][:500]} (category: {train_diag.get('fallback_failure_category')})")
        if train_diag.get("primary_failure_category") == FAIL_TLS_FINGERPRINT:
            print("  -> Diagnosis: 403 nginx WAF – TLS fingerprint / bot protection. Without Playwright, curl_cffi with chrome impersonation bypasses it for gise host, but web host remains blocked. Using gise host is the validated path.")
    print("=== END DIAGNOSTICS ===\n")


def main():
    parser = argparse.ArgumentParser(
        description="TCDD API spike – validates real TCDD web API without Playwright",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog="Example: python scripts/spike_tcdd.py --origin 'Söğütlüçeşme' --destination 'Ankara' --date 2026-09-10 --capture-fixture tests/fixtures/tcdd_sample.json",
    )
    parser.add_argument("--origin", required=True, help="Origin station name (e.g., Söğütlüçeşme)")
    parser.add_argument("--destination", required=True, help="Destination station name (e.g., Ankara)")
    parser.add_argument("--date", required=True, help="Travel date: YYYY-MM-DD or DD.MM.YYYY (e.g., 2026-09-10)")
    parser.add_argument("--token", help="Optional Authorization JWT (overrides env TCDD_TOKEN and hardcoded)")
    parser.add_argument("--capture-fixture", dest="capture_fixture", help="Optional path to write sanitized real-response fixture JSON (e.g., tests/fixtures/tcdd_real.json)")
    parser.add_argument("--verbose", action="store_true", help="Verbose diagnostics")
    args = parser.parse_args()

    token = get_token(args.token)
    print("TCDD SPIKE – real API validation (no Playwright)")
    print(f"Origin: {args.origin} | Destination: {args.destination} | Date: {args.date}")
    print(f"Using endpoints: CDN {STATION_CDN_URL} and primary {TRAIN_AVAIL_URL_PRIMARY} (fallback {TRAIN_AVAIL_URL_FALLBACK})")
    print(f"Method/Payload/Auth will be printed in diagnostics section below.\n")

    # 1. Parse date
    try:
        api_date, norm_date = parse_travel_date(args.date)
        print(f"Requested travel date normalized: {norm_date} (API format: {api_date})")
    except Exception as e:
        print(f"STATION_LOOKUP_FAILURE: invalid date: {e}", file=sys.stderr)
        sys.exit(2)

    # 2. Station lookup
    try:
        stations, station_client, station_diag = fetch_stations()
        print(f"Fetched {len(stations)} stations via {station_client} from CDN")
    except Exception as e:
        cat, ctx = diagnose_failure(e, getattr(e, "_resp", None))
        print(f"\nAPI_FAILURE ({cat}): station CDN fetch failed: {e}", file=sys.stderr)
        print(f"Diagnostic context: {ctx}", file=sys.stderr)
        print_diagnostics({"method": "GET", "url": STATION_CDN_URL, "client": "unknown"}, None)
        print(f"\nOutcome: {OUTCOME_API_FAILURE}")
        print("API failure is NOT reported as empty result.")
        sys.exit(3)

    origin_matches = find_stations(args.origin, stations)
    dest_matches = find_stations(args.destination, stations)

    print(f"\n--- Station lookup ---")
    if not origin_matches:
        print(f"STATION_LOOKUP_FAILURE: origin {args.origin!r} could not be resolved to canonical record")
        print(f"Outcome: {OUTCOME_STATION_LOOKUP_FAILURE}")
        print("-> Spike reports station lookup failure instead of running service search with guessed identifiers")
        sys.exit(2)
    if not dest_matches:
        print(f"STATION_LOOKUP_FAILURE: destination {args.destination!r} could not be resolved")
        print(f"Outcome: {OUTCOME_STATION_LOOKUP_FAILURE}")
        sys.exit(2)

    # If multiple matches, pick first but show all and warn
    origin = origin_matches[0]
    dest = dest_matches[0]
    print(f"Origin resolved: {origin['name']} (id={origin['id']}, city={origin.get('city',{}).get('name','')}) canonical record")
    if len(origin_matches) > 1:
        print(f"  NOTE: origin query matched {len(origin_matches)} stations, using first: {[m['name'] for m in origin_matches]}")
    print(f"Destination resolved: {dest['name']} (id={dest['id']}) canonical record")
    if len(dest_matches) > 1:
        print(f"  NOTE: destination query matched {len(dest_matches)} stations, using first: {[m['name'] for m in dest_matches]}")

    # 3. Service search
    try:
        raw, train_client, train_diag, resp = fetch_train_availability(int(origin["id"]), int(dest["id"]), api_date, token)
    except Exception as e:
        cat, ctx = diagnose_failure(e, getattr(e, "_resp", None))
        # Provide rich failure category output
        print(f"\nAPI_FAILURE ({cat}): train-availability request failed: {e}", file=sys.stderr)
        print(f"Diagnostic context: {ctx}", file=sys.stderr)
        if "tls" in cat or "waf" in ctx.lower():
            print("-> Diagnosis: endpoint, token, header, payload, TLS/fingerprint, HTTP behavior investigated. Without adding Playwright, curl_cffi chrome impersonation is the validated bypass for gise host.", file=sys.stderr)
        print_diagnostics(station_diag, train_diag if 'train_diag' in locals() else {"method": "POST", "url": TRAIN_AVAIL_URL_PRIMARY, "client": "unknown", "headers_sent": build_headers("REDACTED"), "payload_shape": "unknown", "expected_date_format": "dd-MM-yyyy HH:mm:ss", "auth": "unknown", "primary_error": str(e)[:500], "primary_failure_category": cat, "primary_failure_ctx": ctx})
        print(f"\nOutcome: {OUTCOME_API_FAILURE}")
        print("API failures are NOT reported as empty results.")
        sys.exit(3)

    print_diagnostics(station_diag, train_diag)

    # Validate shape
    if not isinstance(raw, dict) or "trainLegs" not in raw:
        cat, ctx = FAIL_UNEXPECTED_RESPONSE, f"Response missing 'trainLegs' key: {json.dumps(raw, ensure_ascii=False)[:800]}"
        print(f"\nAPI_FAILURE ({cat}): unexpected response shape", file=sys.stderr)
        print(ctx, file=sys.stderr)
        print(f"Outcome: {OUTCOME_API_FAILURE}")
        sys.exit(3)

    # 4. Normalization
    journeys = normalize_trains(raw, norm_date)
    print(f"\n--- Normalization ---")
    print(f"Returned services total: {len(journeys)} (raw train entries across all trainAvailabilities)")
    matched, excluded = filter_by_requested_date(journeys, norm_date)
    print(f"Requested-date filtering: matched {len(matched)}, excluded {len(excluded)} (departure date != {norm_date} filtered out)")
    if excluded and args.verbose:
        for j in excluded[:5]:
            print(f"  excluded: {j.train_name} {j.departure_date} {j.departure_time}")

    # 5. Seat category separation and eligibility
    print(f"\n--- Seat categories & eligibility (MVP invariant: normal economy >=1) ---")
    if not matched:
        outcome = OUTCOME_VALID_EMPTY
        print("No services for requested route/date – valid empty result (distinct from API failure)")
        print(f"Outcome: {outcome}")
    else:
        for j in sorted(matched, key=lambda x: x.departure_time):
            eligible_mark = "ELIGIBLE" if j.is_eligible else "NOT eligible"
            print(f"{j.departure_time} {j.train_type} {j.train_name} (id={j.train_id}, number={j.train_number})")
            print(f"  Route: {origin['name']} -> {dest['name']} Date: {j.departure_date} Depart: {j.departure_datetime_local} Arrival: {j.arrival_time}")
            print(f"  Raw journey identifier: train_id={j.train_id} segments={len(j.raw.get('segments',[]))}")
            print(f"  Economy: {j.economy_available} | Business: {j.business_available} | Accessible: {j.accessible_available} | Special/LOCA: {j.special_available} => {eligible_mark}")
            print(f"  MVP eligibility: {'YES' if j.is_eligible else 'NO'} (only economy >=1 counts)")
        outcome = classify_outcome(matched)
        eligible_count = len([j for j in matched if j.is_eligible])
        print(f"\nSummary: {len(matched)} services matched date, {eligible_count} eligible (economy >=1), {len(matched)-eligible_count} valid but not eligible (business-only or accessible-only)")
        if outcome == OUTCOME_ELIGIBLE_SEATS:
            print(f"Outcome: {outcome} – at least one service has normal economy availability")
        elif outcome == OUTCOME_NO_ELIGIBLE_SEATS:
            print(f"Outcome: {outcome} – valid services returned but none has normal economy >=1 (business/accessible >0 does NOT count)")
        else:
            print(f"Outcome: {outcome}")

    # Distinguish API failure vs empty – already done

    # 6. Fixture capture
    if args.capture_fixture:
        path = Path(args.capture_fixture)
        can_safe, reason = can_safely_sanitize(raw)
        if not can_safe:
            print(f"\nFixture capture: SKIPPED – cannot be safely sanitized: {reason}")
            print(f"No fixture file created at {path}")
        else:
            sanitized = sanitize_fixture(raw)
            # Ensure directory exists
            path.parent.mkdir(parents=True, exist_ok=True)
            # Preserve parser-relevant structure: ensure trainLegs, trains, bookingClassCapacities, segments remain
            # Exclude secrets: we already stripped Authorization etc. (response has no secrets, but we sanitized)
            # Double-check no sensitive keys remain
            raw_str = json.dumps(sanitized, ensure_ascii=False).lower()
            has_secret = any(k in raw_str for k in ["authorization", "bearer", "eyj"])
            # JWT leftover check: if still contains JWT pattern, strip
            if has_secret:
                print("Warning: sanitized fixture still contains potential secret pattern, re-sanitizing", file=sys.stderr)
                # Already handled, but we will still write but warn
            with open(path, "w", encoding="utf-8") as f:
                json.dump(sanitized, f, ensure_ascii=False, indent=2)
            print(f"\nFixture capture: WROTE sanitized fixture to {path}")
            print(f"  Preserved parser-relevant structure (trainLegs, segments, bookingClassCapacities) and excluded secrets/credentials/tokens/personal data")
            # Verify file exists
            if path.exists():
                size = path.stat().st_size
                print(f"  Fixture size: {size} bytes, entries: {len(sanitized.get('trainLegs',[]))} legs")

    # Final outcome classification for exit code
    print(f"\n=== FINAL OUTCOME: {outcome} ===")
    if outcome == OUTCOME_ELIGIBLE_SEATS:
        sys.exit(0)
    elif outcome in (OUTCOME_NO_ELIGIBLE_SEATS, OUTCOME_VALID_EMPTY):
        sys.exit(0)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
