"""Census Geocoder: city + state → (state_fips, place_fips).

Primary path: Census Geocoder `geographies/address` (requires a street address).
Fallback path: Census Data API place name search (city+state only, no street needed).
"""

import logging
from typing import NamedTuple

import httpx

from gtm.utils.cache import FileCache

logger = logging.getLogger(__name__)

GEOCODER_ADDRESS_URL = "https://geocoding.geo.census.gov/geocoder/geographies/address"
CENSUS_DATA_URL = "https://api.census.gov/data/2020/acs/acs5"
BENCHMARK = "Public_AR_Current"
VINTAGE = "Current_Current"
TIMEOUT_SECONDS: float = 15.0

STATE_FIPS: dict[str, str] = {
    "AL": "01", "AK": "02", "AZ": "04", "AR": "05", "CA": "06", "CO": "08",
    "CT": "09", "DE": "10", "DC": "11", "FL": "12", "GA": "13", "HI": "15",
    "ID": "16", "IL": "17", "IN": "18", "IA": "19", "KS": "20", "KY": "21",
    "LA": "22", "ME": "23", "MD": "24", "MA": "25", "MI": "26", "MN": "27",
    "MS": "28", "MO": "29", "MT": "30", "NE": "31", "NV": "32", "NH": "33",
    "NJ": "34", "NM": "35", "NY": "36", "NC": "37", "ND": "38", "OH": "39",
    "OK": "40", "OR": "41", "PA": "42", "RI": "44", "SC": "45", "SD": "46",
    "TN": "47", "TX": "48", "UT": "49", "VT": "50", "VA": "51", "WA": "53",
    "WV": "54", "WI": "55", "WY": "56",
}


class FipsResult(NamedTuple):
    state_fips: str
    place_fips: str


async def _geocoder_address(
    street: str, city: str, state: str, client: httpx.AsyncClient
) -> FipsResult | None:
    """Try the structured Census Geocoder address endpoint."""
    resp = await client.get(
        GEOCODER_ADDRESS_URL,
        params={
            "street": street, "city": city, "state": state,
            "benchmark": BENCHMARK, "vintage": VINTAGE,
            "layers": "Incorporated Places", "format": "json",
        },
        timeout=TIMEOUT_SECONDS,
    )
    resp.raise_for_status()
    matches = resp.json().get("result", {}).get("addressMatches", [])
    if not matches:
        return None
    places = matches[0].get("geographies", {}).get("Incorporated Places", [])
    if not places:
        return None
    return FipsResult(state_fips=places[0]["STATE"], place_fips=places[0]["PLACE"])


async def _census_places_lookup(
    city: str, state: str, client: httpx.AsyncClient
) -> FipsResult | None:
    """Fall back to Census Data API: search all places in state by city name."""
    state_fips = STATE_FIPS.get(state.upper())
    if not state_fips:
        return None
    resp = await client.get(
        CENSUS_DATA_URL,
        params={"get": "NAME,GEO_ID", "for": "place:*", "in": f"state:{state_fips}"},
        timeout=30.0,
    )
    resp.raise_for_status()
    rows = resp.json()  # [[header...], [row...], ...]
    city_lower = city.lower()
    for row in rows[1:]:
        # NAME format: "Austin city, Texas"  GEO_ID: "1600000US4805000"
        place_name = row[0].split(",")[0].lower().strip()
        if place_name == city_lower or place_name.startswith(city_lower + " "):
            geo_id = row[1]  # "1600000US{state(2)}{place(5)}"
            fips_str = geo_id[9:]  # strip "1600000US" prefix
            if len(fips_str) == 7:
                return FipsResult(state_fips=fips_str[:2], place_fips=fips_str[2:])
    return None


async def get_fips(
    city: str,
    state: str,
    client: httpx.AsyncClient,
    cache: FileCache,
    street: str = "",
) -> FipsResult | None:
    """Return (state_fips, place_fips) for city/state, or None if not found. Never raises."""
    cache_key = f"geocoder:{city.lower().strip()}:{state.lower().strip()}"
    cached = cache.get(cache_key)
    if cached:
        return FipsResult(**cached)

    logger.info("Geocoder: resolving '%s, %s'", city, state)
    try:
        result: FipsResult | None = None
        if street:
            result = await _geocoder_address(street, city, state, client)
        if result is None:
            result = await _census_places_lookup(city, state, client)
        if result:
            cache.set(cache_key, {"state_fips": result.state_fips, "place_fips": result.place_fips})
            logger.debug("Geocoder: %s, %s → state=%s place=%s", city, state, *result)
            return result
        logger.warning("Geocoder: no match for '%s, %s'", city, state)
    except httpx.TimeoutException as exc:
        logger.warning("Geocoder: timeout for '%s, %s': %s", city, state, exc)
    except httpx.HTTPStatusError as exc:
        logger.warning("Geocoder: HTTP %s for '%s, %s'", exc.response.status_code, city, state)
    except (ValueError, KeyError, TypeError, IndexError) as exc:
        logger.warning("Geocoder: parse error for '%s, %s': %s", city, state, exc)
    return None
