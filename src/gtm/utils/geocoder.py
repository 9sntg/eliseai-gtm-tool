"""Census Geocoder: city + state → (state_fips, place_fips)."""

import logging
from typing import NamedTuple

import httpx

from gtm.utils.cache import FileCache

logger = logging.getLogger(__name__)

GEOCODER_URL = "https://geocoding.geo.census.gov/geocoder/geographies/onelineaddress"
BENCHMARK = "Public_AR_Current"
VINTAGE = "Current_Current"
TIMEOUT_SECONDS: float = 15.0


class FipsResult(NamedTuple):
    state_fips: str
    place_fips: str


async def get_fips(
    city: str,
    state: str,
    client: httpx.AsyncClient,
    cache: FileCache,
) -> FipsResult | None:
    """Return (state_fips, place_fips) for city/state, or None if not found.

    Never raises — returns None on any failure and logs a warning.
    """
    cache_key = f"geocoder:{city.lower().strip()}:{state.lower().strip()}"
    cached = cache.get(cache_key)
    if cached:
        return FipsResult(**cached)

    params = {
        "address": f"{city}, {state}",
        "benchmark": BENCHMARK,
        "vintage": VINTAGE,
        "layers": "Incorporated Places",
        "format": "json",
    }

    try:
        logger.info("Geocoder: resolving '%s, %s'", city, state)
        resp = await client.get(GEOCODER_URL, params=params, timeout=TIMEOUT_SECONDS)
        resp.raise_for_status()
        data = resp.json()

        matches = data.get("result", {}).get("addressMatches", [])
        if not matches:
            logger.warning("Geocoder: no match for '%s, %s'", city, state)
            return None

        places = matches[0].get("geographies", {}).get("Incorporated Places", [])
        if not places:
            logger.warning("Geocoder: no Incorporated Places layer for '%s, %s'", city, state)
            return None

        result = FipsResult(state_fips=places[0]["STATE"], place_fips=places[0]["PLACE"])
        cache.set(cache_key, {"state_fips": result.state_fips, "place_fips": result.place_fips})
        logger.debug("Geocoder: %s, %s → state=%s place=%s", city, state, result.state_fips, result.place_fips)
        return result

    except httpx.TimeoutException as exc:
        logger.warning("Geocoder: timeout for '%s, %s': %s", city, state, exc)
    except httpx.HTTPStatusError as exc:
        logger.warning("Geocoder: HTTP %s for '%s, %s'", exc.response.status_code, city, state)
    except (ValueError, KeyError, TypeError) as exc:
        logger.warning("Geocoder: parse error for '%s, %s': %s", city, state, exc)
    return None
