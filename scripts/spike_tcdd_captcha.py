#!/usr/bin/env python3
"""
TCDD web-api + CAPTCHA spike – validates the NEW browser flow without Playwright.

Browser evidence (2026-09-11, ebilet DevTools):
- Browser POSTs to web-api-prod (NOT gise-api):
    POST https://web-api-prod-ytp.tcddtasimacilik.gov.tr/tms/train/train-availability?environment=dev&userId=1
- Browser payload shape (differs from gise spike):
    {"searchRoutes": [{"departureStationId": 1325, "departureStationName": "...",
      "arrivalStationId": 93, "arrivalStationName": "...",
      "departureDate": "11-09-2026 21:00:00"}],
     "passengerTypeCounts": [{"id": 0, "count": 1}],
     "searchReservation": false, "searchType": "DOMESTIC",
     "blTrainTypes": ["TURISTIK_TREN"]}
- Browser extra headers: captcha-session, x-tms-xsrf-token (from /tms/csrf), cookies
- Without solved Turnstile, web-api returns:
    400 {"status": "BAD_REQUEST", "type": "CAPTCHA", "code": 3877201,
         "message": "Güvenlik doğrulaması gerekli."}
- gise-api with old payload returns 403 Forbidden JSON even from browser context.

Usage:
    python scripts/spike_tcdd_captcha.py --origin "Söğütlüçeşme" --destination "Eskişehir" --date 12.09.2026
    python scripts/spike_tcdd_captcha.py --origin "Söğütlüçeşme" --destination "Eskişehir" --date 12.09.2026 \
        --captcha-session <uuid> --xsrf-token <uuid>

Outcomes:
    STATION_LOOKUP_FAILURE | API_FAILURE | CAPTCHA_REQUIRED | VALID_EMPTY | VALID_WITH_TRAINS
No Playwright is used. Secrets are redacted in output.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import sys
import unicodedata

STATION_CDN_URL = "https://cdn-api-prod-ytp.tcddtasimacilik.gov.tr/datas/station-pairs-INTERNET.json"
WEB_API_URL = "https://web-api-prod-ytp.tcddtasimacilik.gov.tr/tms/train/train-availability"
CSRF_URL = "https://web-api-prod-ytp.tcddtasimacilik.gov.tr/tms/csrf"

OUTCOME_STATION_LOOKUP_FAILURE = "STATION_LOOKUP_FAILURE"
OUTCOME_API_FAILURE = "API_FAILURE"
OUTCOME_CAPTCHA_REQUIRED = "CAPTCHA_REQUIRED"
OUTCOME_VALID_EMPTY = "VALID_EMPTY"
OUTCOME_VALID_WITH_TRAINS = "VALID_WITH_TRAINS"


def normalize_query(s: str) -> str:
    s = s.strip().lower()
    s = s.replace("ı", "i").replace("ş", "s").replace("ğ", "g").replace("ü", "u").replace("ö", "o").replace("ç", "c")
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def find_stations(query: str, stations: list[dict]) -> list[dict]:
    qn = normalize_query(query)
    exact = [st for st in stations if normalize_query(st.get("name", "")) == qn]
    if exact:
        return exact
    return [st for st in stations if qn in normalize_query(st.get("name", ""))]


def parse_travel_date(date_str: str) -> tuple[str, str]:
    date_str = date_str.strip()
    for fmt in ("%d.%m.%Y", "%d-%m-%Y", "%Y-%m-%d", "%Y/%m/%d"):
        try:
            dt = datetime.datetime.strptime(date_str[:10], fmt)
            return dt.strftime("%d-%m-%Y 00:00:00"), dt.strftime("%Y-%m-%d")
        except ValueError:
            continue
    raise ValueError(f"Invalid date {date_str!r}")


def get_token(args_token: str | None) -> str:
    if args_token:
        return args_token.strip()
    env = os.environ.get("TCDD_TOKEN", "").strip()
    if env:
        return env
    print("missing TCDD_TOKEN (env or --token)", file=sys.stderr)
    sys.exit(2)


def redact(headers: dict) -> dict:
    out = {}
    for k, v in headers.items():
        kl = k.lower()
        if kl in ("authorization", "captcha-session", "x-tms-xsrf-token", "cookie", "set-cookie"):
            out[k] = "<redacted>"
        else:
            out[k] = v
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="TCDD web-api + CAPTCHA spike (no Playwright)")
    ap.add_argument("--origin", required=True)
    ap.add_argument("--destination", required=True)
    ap.add_argument("--date", required=True)
    ap.add_argument("--token", default=None)
    ap.add_argument("--captcha-session", default=None)
    ap.add_argument("--xsrf-token", default=None)
    args = ap.parse_args()

    token = get_token(args.token)
    try:
        api_date, norm_date = parse_travel_date(args.date)
    except Exception as e:
        print(f"{OUTCOME_STATION_LOOKUP_FAILURE}: invalid date: {e}", file=sys.stderr)
        sys.exit(2)
    print(f"Requested date: {norm_date} (API: {api_date})")

    try:
        import httpx
    except ImportError:
        print(f"{OUTCOME_API_FAILURE}: httpx not installed", file=sys.stderr)
        sys.exit(3)

    # 1. Station lookup via CDN (no auth)
    try:
        with httpx.Client(timeout=15) as c:
            r = c.get(STATION_CDN_URL, headers={"Accept": "application/json", "User-Agent": "Mozilla/5.0"})
            r.raise_for_status()
            stations = r.json()
        print(f"Fetched {len(stations)} stations from CDN")
    except Exception as e:
        print(f"{OUTCOME_API_FAILURE}: station CDN failed: {str(e)[:300]}", file=sys.stderr)
        sys.exit(3)

    om = find_stations(args.origin, stations)
    dm = find_stations(args.destination, stations)
    if not om or not dm:
        print(f"{OUTCOME_STATION_LOOKUP_FAILURE}: origin={len(om)} dest={len(dm)}", file=sys.stderr)
        sys.exit(2)
    origin, dest = om[0], dm[0]
    print(f"Origin: {origin['name']} (id={origin['id']})")
    print(f"Destination: {dest['name']} (id={dest['id']})")

    # 2. CSRF token (no auth, gives x-tms-xsrf-token)
    xsrf = args.xsrf_token
    if not xsrf:
        try:
            with httpx.Client(timeout=15) as c:
                r = c.get(f"{CSRF_URL}?environment=dev&userId=1", headers={"Accept": "application/json", "User-Agent": "Mozilla/5.0"})
                if r.status_code == 200:
                    xsrf = r.json().get("token")
                    print(f"CSRF token fetched: {'yes' if xsrf else 'no'}")
                else:
                    print(f"CSRF fetch HTTP {r.status_code}: {r.text[:200]}")
        except Exception as e:
            print(f"CSRF fetch failed (non-fatal): {str(e)[:200]}")

    # 3. Browser-like payload to web-api
    payload = {
        "searchRoutes": [{
            "departureStationId": int(origin["id"]),
            "departureStationName": origin["name"],
            "arrivalStationId": int(dest["id"]),
            "arrivalStationName": dest["name"],
            "departureDate": api_date,
        }],
        "passengerTypeCounts": [{"id": 0, "count": 1}],
        "searchReservation": False,
        "searchType": "DOMESTIC",
        "blTrainTypes": ["TURISTIK_TREN"],
    }
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/plain, */*",
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Origin": "https://ebilet.tcddtasimacilik.gov.tr",
        "Referer": "https://ebilet.tcddtasimacilik.gov.tr/",
        "Authorization": token,
        "unit-id": "3895",
    }
    if args.captcha_session:
        headers["captcha-session"] = args.captcha_session
    if xsrf:
        headers["x-tms-xsrf-token"] = xsrf

    print(f"\nPOST {WEB_API_URL}?environment=dev&userId=1")
    print(f"Headers: {json.dumps(redact(headers), ensure_ascii=False)}")
    print(f"Payload: {json.dumps(payload, ensure_ascii=False)}")

    status, body = None, ""
    try:
        with httpx.Client(timeout=20) as c:
            r = c.post(f"{WEB_API_URL}?environment=dev&userId=1", json=payload, headers=headers)
            status, body = r.status_code, r.text
    except Exception as e:
        print(f"httpx failed: {str(e)[:200]} – trying curl_cffi chrome impersonation")
    # nginx WAF via httpx → retry with browser TLS fingerprint
    if status == 403 and "nginx" in body.lower():
        try:
            from curl_cffi import requests as cr

            r2 = cr.post(f"{WEB_API_URL}?environment=dev&userId=1", json=payload, headers=headers,
                         impersonate="chrome120", timeout=20)
            status, body = r2.status_code, r2.text or ""
            print("(retried via curl_cffi chrome120)")
        except Exception as e:
            print(f"curl_cffi retry failed: {str(e)[:200]}", file=sys.stderr)

    if status is None:
        print(f"\n{OUTCOME_API_FAILURE}: network/timeout", file=sys.stderr)
        sys.exit(3)

    print(f"\nStatus: {status}")
    print(f"Body: {body[:800]}")

    # 4. Classify
    try:
        data = json.loads(body) if body else None
    except Exception:
        print(f"\n{OUTCOME_API_FAILURE}: invalid JSON", file=sys.stderr)
        sys.exit(3)

    if isinstance(data, dict) and data.get("type") == "CAPTCHA":
        print(f"\n=== FINAL OUTCOME: {OUTCOME_CAPTCHA_REQUIRED} ===")
        print(f"code={data.get('code')} message={data.get('message')}")
        print("Turnstile/captcha-session gerekli. Otomatik çözüm MVP dışıdır.")
        print("Manuel çözüm: gerçek Chrome'da aramayı yapıp Network'ten captcha-session + xsrf kopyalayıp --captcha-session/--xsrf-token ile tekrar dene.")
        sys.exit(0)

    if status in (401, 403) and not args.captcha_session:
        print(f"\n=== FINAL OUTCOME: {OUTCOME_CAPTCHA_REQUIRED} (no captcha-session; server 403) ===")
        print("Browser kanıtı: aynı token + captcha-session → 400 CAPTCHA, captcha-session yok → 403.")
        print("Manuel çözüm: gerçek Chrome'da Cloudflare'i geçip aramayı yap, Network'ten captcha-session + xsrf kopyalayıp --captcha-session/--xsrf-token ile tekrar dene.")
        sys.exit(0)

    if status in (401, 403):
        print(f"\n=== FINAL OUTCOME: {OUTCOME_API_FAILURE} (authentication_error) ===", file=sys.stderr)
        sys.exit(3)
    if status is not None and status >= 400:
        print(f"\n=== FINAL OUTCOME: {OUTCOME_API_FAILURE} (HTTP {status}) ===", file=sys.stderr)
        sys.exit(3)

    legs = data.get("trainLegs", []) if isinstance(data, dict) else []
    n_trains = sum(len(ta.get("trains", [])) for leg in legs for ta in leg.get("trainAvailabilities", []))
    if n_trains == 0:
        print(f"\n=== FINAL OUTCOME: {OUTCOME_VALID_EMPTY} ===")
    else:
        print(f"\n=== FINAL OUTCOME: {OUTCOME_VALID_WITH_TRAINS} ({n_trains} trains) ===")


if __name__ == "__main__":
    main()
