"""DataUSA enrichment — population growth and income momentum signals."""

import asyncio
import logging
import random

import httpx
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from gtm.models.lead import RawLead
from gtm.models.market import MarketData
from gtm.utils.cache import FileCache
from gtm.utils.geocoder import get_fips

logger = logging.getLogger(__name__)

DELAY_MIN: float = 1.0
DELAY_MAX: float = 3.0
TIMEOUT_SECONDS: float = 15.0
MAX_RETRIES: int = 3
DATAUSA_BASE_URL: str = "https://datausa.io/api/data"
PLACE_SUMLEV: str = "16000US"  # Census summary level prefix for incorporated places


def _geoid(state_fips: str, place_fips: str) -> str:
    return f"{PLACE_SUMLEV}{state_fips}{place_fips}"


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
    resp = await client.get(DATAUSA_BASE_URL, params=params, timeout=TIMEOUT_SECONDS)
    if resp.status_code == 429 or resp.status_code >= 500:
        resp.raise_for_status()
    return resp


async def enrich(lead: RawLead, client: httpx.AsyncClient, cache: FileCache) -> MarketData:
    """Fetch DataUSA population growth and income signals for the lead's city."""
    fips = await get_fips(lead.city, lead.state, client, cache)
    if fips is None:
        logger.warning("DataUSA: skipping %s, %s — FIPS lookup failed", lead.city, lead.state)
        return MarketData()

    geoid = _geoid(fips.state_fips, fips.place_fips)
    cache_key = f"datausa:{geoid}"
    cached = cache.get(cache_key)
    if cached:
        return MarketData(**cached)

    await asyncio.sleep(random.uniform(DELAY_MIN, DELAY_MAX))

    pop_rows = await _fetch_measure(client, geoid, "Population", lead)
    income_rows = await _fetch_measure(client, geoid, "Median Household Income", lead)

    result = _parse(pop_rows, income_rows)
    cache.set(cache_key, result.model_dump())
    logger.info("DataUSA: enrichment done for %s, %s", lead.city, lead.state)
    return result


async def _fetch_measure(
    client: httpx.AsyncClient, geoid: str, measure: str, lead: RawLead
) -> list[dict]:
    """Fetch one DataUSA measure; return empty list on any failure."""
    params = {"Geography": geoid, "drilldowns": "Place", "measures": measure}
    try:
        logger.info("DataUSA: querying '%s' for %s, %s", measure, lead.city, lead.state)
        resp = await _fetch(client, params)
        if resp.status_code != 200:
            logger.warning("DataUSA: HTTP %s for measure '%s'", resp.status_code, measure)
            return []
        return resp.json().get("data", [])
    except httpx.TimeoutException as exc:
        logger.warning("DataUSA: timeout for '%s': %s", measure, exc)
    except httpx.HTTPStatusError as exc:
        logger.warning("DataUSA: HTTP %s for '%s'", exc.response.status_code, measure)
    except (ValueError, KeyError, TypeError) as exc:
        logger.warning("DataUSA: parse error for '%s': %s", measure, exc)
    return []


def _parse(pop_rows: list[dict], income_rows: list[dict]) -> MarketData:
    """Compute YoY growth rates from two most-recent DataUSA records per measure."""
    pop_sorted = sorted(pop_rows, key=lambda r: r.get("ID Year", 0), reverse=True)
    inc_sorted = sorted(income_rows, key=lambda r: r.get("ID Year", 0), reverse=True)

    def latest_and_growth(rows: list[dict], key: str) -> tuple[int | None, float | None]:
        if not rows:
            return None, None
        latest = int(rows[0][key]) if rows[0].get(key) else None
        if len(rows) < 2 or not rows[1].get(key) or float(rows[1][key]) == 0:
            return latest, None
        growth = round((float(rows[0][key]) - float(rows[1][key])) / float(rows[1][key]), 4)
        return latest, growth

    _, pop_growth = latest_and_growth(pop_sorted, "Population")
    income, income_growth = latest_and_growth(inc_sorted, "Median Household Income")

    return MarketData(
        population_growth_yoy=pop_growth,
        median_household_income=income,
        median_income_growth_yoy=income_growth,
    )
