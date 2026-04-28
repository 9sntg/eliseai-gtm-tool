"""Census ACS5 enrichment — housing and population market signals."""

import asyncio
import logging
import random

import httpx
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from gtm.config import settings
from gtm.exceptions import ConfigurationError
from gtm.models.lead import RawLead
from gtm.models.market import MarketData
from gtm.utils.cache import FileCache
from gtm.utils.geocoder import get_fips

logger = logging.getLogger(__name__)

DELAY_MIN: float = 1.0
DELAY_MAX: float = 3.0
TIMEOUT_SECONDS: float = 15.0
MAX_RETRIES: int = 3
ACS_YEAR: str = "2022"
ACS_BASE_URL: str = f"https://api.census.gov/data/{ACS_YEAR}/acs/acs5"
ACS_VARIABLES: str = ",".join([
    "B25003_002E",  # renter-occupied units
    "B25001_001E",  # total housing units
    "B25064_001E",  # median gross rent
    "B01003_001E",  # total population
])


def _is_retryable(exc: BaseException) -> bool:
    return isinstance(exc, httpx.HTTPStatusError) and (
        exc.response.status_code == 429 or exc.response.status_code >= 500
    )


@retry(
    retry=retry_if_exception(_is_retryable),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    stop=stop_after_attempt(MAX_RETRIES),
    reraise=True,
)
async def _fetch(client: httpx.AsyncClient, params: dict) -> httpx.Response:
    resp = await client.get(ACS_BASE_URL, params=params, timeout=TIMEOUT_SECONDS)
    if resp.status_code == 429 or resp.status_code >= 500:
        resp.raise_for_status()
    return resp


async def enrich(lead: RawLead, client: httpx.AsyncClient, cache: FileCache) -> MarketData:
    """Fetch Census ACS5 housing and population signals for the lead's city."""
    fips = await get_fips(lead.city, lead.state, client, cache, street=lead.property_address)
    if fips is None:
        logger.warning("Census: skipping %s, %s — FIPS lookup failed", lead.city, lead.state)
        return MarketData()

    cache_key = f"census:{fips.state_fips}:{fips.place_fips}"
    cached = cache.get(cache_key)
    if cached:
        return MarketData(**cached)

    params: dict[str, str] = {
        "get": ACS_VARIABLES,
        "for": f"place:{fips.place_fips}",
        "in": f"state:{fips.state_fips}",
    }
    if settings.census_api_key:
        params["key"] = settings.census_api_key

    await asyncio.sleep(random.uniform(DELAY_MIN, DELAY_MAX))

    try:
        logger.info("Census: querying ACS5 for %s, %s", lead.city, lead.state)
        resp = await _fetch(client, params)
        if resp.status_code in (401, 403):
            logger.error("Census: invalid API key (HTTP %s)", resp.status_code)
            raise ConfigurationError(f"Census API key invalid (HTTP {resp.status_code})")
        if resp.status_code == 404:
            logger.info("Census: no ACS data for %s, %s", lead.city, lead.state)
            return MarketData()
        result = _parse(resp.json())
        cache.set(cache_key, result.model_dump())
        logger.info("Census: enrichment done for %s, %s", lead.city, lead.state)
        return result
    except ConfigurationError:
        raise
    except httpx.TimeoutException as exc:
        logger.warning("Census: timeout for %s, %s: %s", lead.city, lead.state, exc)
    except httpx.HTTPStatusError as exc:
        logger.warning("Census: HTTP %s for %s, %s", exc.response.status_code, lead.city, lead.state)
    except (ValueError, KeyError, TypeError, IndexError) as exc:
        logger.warning("Census: parse error for %s, %s: %s", lead.city, lead.state, exc)
    return MarketData()


def _parse(rows: list) -> MarketData:
    """Parse ACS5 2D-array response (header row + data row) into MarketData."""
    if len(rows) < 2:
        return MarketData()
    data = dict(zip(rows[0], rows[1], strict=False))

    def int_or_none(key: str) -> int | None:
        val = data.get(key)
        return int(val) if val not in (None, "-1", "") else None

    renter = int_or_none("B25003_002E")
    total = int_or_none("B25001_001E")
    renter_rate = round(renter / total, 4) if renter and total else None

    return MarketData(
        renter_occupied_units=renter,
        total_housing_units=total,
        renter_rate=renter_rate,
        median_gross_rent=int_or_none("B25064_001E"),
        total_population=int_or_none("B01003_001E"),
    )
