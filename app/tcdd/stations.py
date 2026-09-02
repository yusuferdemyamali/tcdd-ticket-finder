from __future__ import annotations

import re
import unicodedata
from typing import Any

from .exceptions import TcddStationAmbiguityError, TcddStationNotFoundError
from .models import Station

STATION_CDN_URL = "https://cdn-api-prod-ytp.tcddtasimacilik.gov.tr/datas/station-pairs-INTERNET.json"


def normalize_query(s: str) -> str:
    s = s.strip().lower()
    # Turkish replacements before ascii folding – map to ascii equivalents
    s = s.replace("ı", "i").replace("ş", "s").replace("ğ", "g").replace("ü", "u").replace("ö", "o").replace("ç", "c").replace("İ", "i")
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _station_name_norm(station: Station) -> str:
    return normalize_query(station.name)


def parse_station_pairs(raw_list: Any) -> list[Station]:
    """Normalize raw station-pairs list into Station objects.

    Does not expose raw dictionaries outside the integration layer.
    """
    from .exceptions import TcddUnexpectedResponseError

    if not isinstance(raw_list, list):
        raise TcddUnexpectedResponseError(f"station-pairs expected list, got {type(raw_list).__name__}")

    stations: list[Station] = []
    for item in raw_list:
        if not isinstance(item, dict):
            continue
        sid = item.get("id")
        name = item.get("name")
        if sid is None or not name:
            continue
        try:
            sid_int = int(sid)
        except Exception:
            continue
        # optional city
        city_name = None
        city = item.get("city")
        if isinstance(city, dict):
            city_name = city.get("name")
        # district city fallback
        if not city_name:
            district = item.get("district")
            if isinstance(district, dict):
                c = district.get("city")
                if isinstance(c, dict):
                    city_name = c.get("name")
        stations.append(Station(id=sid_int, name=str(name), city_name=city_name))
    return stations


def search_stations(query: str, stations: list[Station]) -> list[Station]:
    """Return candidate stations for query with Turkish folding and exact-match priority.

    - Normalized exact matches are returned if any exist.
    - Otherwise substring matches are returned.
    - Returns empty list if no match.
    """
    qn = normalize_query(query)
    if not qn:
        return []
    exact: list[Station] = []
    substring: list[Station] = []
    for st in stations:
        name_norm = _station_name_norm(st)
        if qn == name_norm:
            exact.append(st)
        elif qn in name_norm:
            substring.append(st)
    if exact:
        return exact
    return substring


def get_station(query: str, stations: list[Station]) -> Station:
    """Resolve query to a single canonical Station or raise explicit error.

    Raises TcddStationNotFoundError if no match.
    Raises TcddStationAmbiguityError if multiple candidates without exact winner.
    """
    candidates = search_stations(query, stations)
    if not candidates:
        raise TcddStationNotFoundError(f"station not found for query {query!r}")
    if len(candidates) > 1:
        # search_stations already prioritizes exact; if len>1 it means either multiple exact or multiple substring
        raise TcddStationAmbiguityError(
            f"ambiguous station query {query!r}: {len(candidates)} candidates",
            candidates=candidates,
        )
    return candidates[0]
