"""Population growth and income momentum signals via Census ACS multi-year comparison.

Originally used the DataUSA API, which was retired in 2025. Now queries Census ACS5
for two consecutive years and computes YoY growth rates directly.
"""

import asyncio
import logging
import random

import httpx
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from gtm.config import settings
from gtm.models.lead import RawLead
from gtm.models.market import MarketData
from gtm.utils.cache import FileCache
from gtm.utils.geocoder import get_fips

logger = logging.getLogger(__name__)

DELAY_MIN: float = 1.0
DELAY_MAX: float = 3.0
TIMEOUT_SECONDS: float = 15.0
MAX_RETRIES: int = 3
ACS_BASE_URL: str = "https://api.census.gov/data/{year}/acs/acs5"
ACS_CURRENT_YEAR: int = 2022
ACS_PRIOR_YEAR: int = 2021
ACS_VARIABLES: str = "B01003_001E,B19013_001E"  # population, median household income


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
async def _fetch_acs_year(
    client: httpx.AsyncClient, year: int, state_fips: str, place_fips: str
) -> httpx.Response:
    params: dict[str, str] = {
        "get": ACS_VARIABLES,
        "for": f"place:{place_fips}",
        "in": f"state:{state_fips}",
    }
    if settings.census_api_key:
        params["key"] = settings.census_api_key
    url = ACS_BASE_URL.format(year=year)
    resp = await client.get(url, params=params, timeout=TIMEOUT_SECONDS)
    if resp.status_code == 429 or resp.status_code >= 500:
        resp.raise_for_status()
    return resp


async def enrich(lead: RawLead, client: httpx.AsyncClient, cache: FileCache) -> MarketData:
    """Fetch YoY population and income growth from Census ACS multi-year comparison."""
    fips = await get_fips(lead.city, lead.state, client, cache, street=lead.property_address)
    if fips is None:
        logger.warning("DataUSA: skipping %s, %s — FIPS lookup failed", lead.city, lead.state)
        return MarketData()

    cache_key = f"census_growth:{fips.state_fips}:{fips.place_fips}"
    cached = cache.get(cache_key)
    if cached:
        return MarketData(**cached)

    await asyncio.sleep(random.uniform(DELAY_MIN, DELAY_MAX))

    try:
        logger.info("Census growth: querying %s and %s ACS for %s, %s",
                    ACS_CURRENT_YEAR, ACS_PRIOR_YEAR, lead.city, lead.state)
        current_resp, prior_resp = await asyncio.gather(
            _fetch_acs_year(client, ACS_CURRENT_YEAR, fips.state_fips, fips.place_fips),
            _fetch_acs_year(client, ACS_PRIOR_YEAR, fips.state_fips, fips.place_fips),
        )
        result = _parse(current_resp.json(), prior_resp.json())
        cache.set(cache_key, result.model_dump())
        logger.info("Census growth: enrichment done for %s, %s", lead.city, lead.state)
        return result
    except httpx.TimeoutException as exc:
        logger.warning("Census growth: timeout for %s, %s: %s", lead.city, lead.state, exc)
    except httpx.HTTPStatusError as exc:
        logger.warning("Census growth: HTTP %s for %s, %s", exc.response.status_code, lead.city, lead.state)
    except (ValueError, KeyError, TypeError, IndexError) as exc:
        logger.warning("Census growth: parse error for %s, %s: %s", lead.city, lead.state, exc)
    return MarketData()


def _parse(current_rows: list, prior_rows: list) -> MarketData:
    """Compute YoY growth from two ACS response arrays."""
    if len(current_rows) < 2 or len(prior_rows) < 2:
        return MarketData()

    def val(rows: list, idx: int) -> float | None:
        v = rows[1][idx]
        return float(v) if v not in (None, "-1", "") else None

    # current_rows[0] = ["B01003_001E", "B19013_001E", "state", "place"]
    pop_cur, pop_pri = val(current_rows, 0), val(prior_rows, 0)
    inc_cur, inc_pri = val(current_rows, 1), val(prior_rows, 1)

    def growth(cur: float | None, pri: float | None) -> float | None:
        if cur is None or pri is None or pri == 0:
            return None
        return round((cur - pri) / pri, 4)

    return MarketData(
        population_growth_yoy=growth(pop_cur, pop_pri),
        median_household_income=int(inc_cur) if inc_cur else None,
        median_income_growth_yoy=growth(inc_cur, inc_pri),
    )
