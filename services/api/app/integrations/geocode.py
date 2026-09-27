"""Place name for a GPS point: OpenStreetMap Nominatim (free, no key) with an offline
fallback to the nearest Tanzanian region, so farm registration works without internet.
GEOCODE_MODE=offline skips the network (tests, low-connectivity demos)."""

import logging
import math
from functools import lru_cache

import httpx

from ..config import get_settings

log = logging.getLogger(__name__)
NOMINATIM = "https://nominatim.openstreetmap.org/reverse"
# Nominatim's usage policy asks for an identifying User-Agent (max 1 request/second).
USER_AGENT = "ShambaniKifedha/0.2 (+https://github.com/Shemsanofly/AgriTrust-AI)"

# Regional headquarters of mainland Tanzania plus Zanzibar (approximate).
REGIONS = {
    "Arusha": (-3.37, 36.68),
    "Dar es Salaam": (-6.79, 39.21),
    "Dodoma": (-6.17, 35.74),
    "Geita": (-2.87, 32.23),
    "Iringa": (-7.77, 35.69),
    "Kagera": (-1.33, 31.81),
    "Katavi": (-6.34, 31.07),
    "Kigoma": (-4.88, 29.63),
    "Kilimanjaro": (-3.35, 37.34),
    "Lindi": (-10.00, 39.71),
    "Manyara": (-4.21, 35.75),
    "Mara": (-1.50, 33.80),
    "Mbeya": (-8.90, 33.46),
    "Morogoro": (-6.82, 37.66),
    "Mtwara": (-10.27, 40.18),
    "Mwanza": (-2.52, 32.90),
    "Njombe": (-9.33, 34.77),
    "Pwani": (-6.77, 38.92),
    "Rukwa": (-7.97, 31.62),
    "Ruvuma": (-10.68, 35.65),
    "Shinyanga": (-3.66, 33.42),
    "Simiyu": (-2.80, 33.99),
    "Singida": (-4.82, 34.74),
    "Songwe": (-9.11, 32.93),
    "Tabora": (-5.02, 32.80),
    "Tanga": (-5.07, 39.10),
    "Zanzibar": (-6.16, 39.19),
}
MAX_FALLBACK_KM = 300

# ISO 3166-2:TZ codes. OSM tags Tanzanian regions reliably by code; its "region" field
# holds the zone (e.g. "Central Zone"), and Dar es Salaam has no "state".
ISO_REGIONS = {
    "TZ-01": "Arusha", "TZ-02": "Dar es Salaam", "TZ-03": "Dodoma", "TZ-04": "Iringa", "TZ-05": "Kagera",
    "TZ-06": "Pemba North", "TZ-07": "Zanzibar North", "TZ-08": "Kigoma", "TZ-09": "Kilimanjaro", "TZ-10": "Pemba South",
    "TZ-11": "Zanzibar South", "TZ-12": "Lindi", "TZ-13": "Mara", "TZ-14": "Mbeya", "TZ-15": "Zanzibar West",
    "TZ-16": "Morogoro", "TZ-17": "Mtwara", "TZ-18": "Mwanza", "TZ-19": "Pwani", "TZ-20": "Rukwa",
    "TZ-21": "Ruvuma", "TZ-22": "Shinyanga", "TZ-23": "Singida", "TZ-24": "Tabora", "TZ-25": "Tanga",
    "TZ-26": "Manyara", "TZ-27": "Geita", "TZ-28": "Katavi", "TZ-29": "Njombe", "TZ-30": "Simiyu", "TZ-31": "Songwe",
}


def _km(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat1, lon1, lat2, lon2 = map(math.radians, (*a, *b))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(h))


def _clean_region(name: str | None) -> str | None:
    """'Dodoma Region' / 'Mkoa wa Dodoma' -> 'Dodoma'."""
    if not name:
        return None
    for prefix in ("Mkoa wa ",):
        name = name.removeprefix(prefix)
    for suffix in (" Region", " Mkoa"):
        name = name.removesuffix(suffix)
    return name.strip() or None


def _offline(lat: float, lon: float) -> dict:
    region, centre = min(REGIONS.items(), key=lambda kv: _km((lat, lon), kv[1]))
    if _km((lat, lon), centre) > MAX_FALLBACK_KM:
        return {"region": None, "district": None, "place": None, "country": None, "label": None, "source": "offline"}
    return {"region": region, "district": None, "place": None, "country": "Tanzania", "label": region, "source": "offline"}


@lru_cache(maxsize=512)
def _lookup(lat: float, lon: float) -> dict:
    if get_settings().geocode_mode != "live":
        return _offline(lat, lon)
    try:
        resp = httpx.get(
            NOMINATIM,
            params={"lat": lat, "lon": lon, "format": "jsonv2", "zoom": 14, "addressdetails": 1},
            headers={"User-Agent": USER_AGENT, "Accept-Language": "en"},
            timeout=6,
        )
        resp.raise_for_status()
        address = resp.json().get("address") or {}
    except (httpx.HTTPError, ValueError) as err:
        log.warning("Reverse geocoding failed, using nearest region: %s", err)
        return _offline(lat, lon)
    region = ISO_REGIONS.get(address.get("ISO3166-2-lvl4", "")) or _clean_region(address.get("state"))
    district = address.get("state_district") or address.get("county") or address.get("city_district")
    place = next((address[k] for k in ("village", "hamlet", "town", "suburb", "ward", "city") if address.get(k)), None)
    if not region and not place:
        return _offline(lat, lon)
    label = ", ".join(dict.fromkeys(x for x in (place, district, region) if x))
    return {"region": region, "district": district, "place": place, "country": address.get("country"), "label": label, "source": "osm"}


def reverse_geocode(lat: float, lon: float) -> dict:
    # ~100 m grid: nearby taps reuse the cached answer and respect Nominatim's rate limit.
    return _lookup(round(lat, 3), round(lon, 3))
