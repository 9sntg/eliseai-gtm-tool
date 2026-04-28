"""OpenCorporates enrichment — company legitimacy and age signals."""

import asyncio
import difflib
import logging
import random

import httpx
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from gtm.exceptions import ConfigurationError
from gtm.models.company import CompanyData
from gtm.models.lead import RawLead
from gtm.utils.cache import FileCache

logger = logging.getLogger(__name__)

DELAY_MIN: float = 1.0
DELAY_MAX: float = 3.0
TIMEOUT_SECONDS: float = 15.0
MAX_RETRIES: int = 3
SIMILARITY_THRESHOLD: float = 0.6
OC_SEARCH_URL: str = "https://api.opencorporates.com/v0.4/companies/search"


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
    resp = await client.get(OC_SEARCH_URL, params=params, timeout=TIMEOUT_SECONDS)
    if resp.status_code == 429 or resp.status_code >= 500:
        resp.raise_for_status()
    return resp


async def enrich(lead: RawLead, client: httpx.AsyncClient, cache: FileCache) -> CompanyData:
    """Fetch company registration signals from OpenCorporates."""
    cache_key = f"opencorporates:{lead.company.lower()}"
    cached = cache.get(cache_key)
    if cached:
        return CompanyData(**cached)

    await asyncio.sleep(random.uniform(DELAY_MIN, DELAY_MAX))

    try:
        logger.info("OpenCorporates: querying '%s'", lead.company)
        resp = await _fetch(client, {"q": lead.company, "format": "json"})
        if resp.status_code in (401, 403):
            logger.error("OpenCorporates: auth error (HTTP %s)", resp.status_code)
            raise ConfigurationError(f"OpenCorporates auth failed (HTTP {resp.status_code})")
        if resp.status_code == 404:
            logger.info("OpenCorporates: no results for '%s'", lead.company)
            return CompanyData()
        result = _parse(resp.json(), lead.company)
        if result.opencorporates_name:
            cache.set(cache_key, result.model_dump())
            logger.info("OpenCorporates: matched '%s'", result.opencorporates_name)
        return result
    except ConfigurationError:
        raise
    except httpx.TimeoutException as exc:
        logger.warning("OpenCorporates: timeout for '%s': %s", lead.company, exc)
    except httpx.HTTPStatusError as exc:
        logger.warning("OpenCorporates: HTTP %s for '%s'", exc.response.status_code, lead.company)
    except (ValueError, KeyError, TypeError) as exc:
        logger.warning("OpenCorporates: parse error for '%s': %s", lead.company, exc)
    return CompanyData()


def _similarity(query: str, name: str) -> float:
    """Return the best similarity score between query and name.

    Takes the max of full-string ratio and prefix ratio to handle the common
    case where lead.company is a short form of the full legal name
    (e.g. "Greystar" vs "Greystar Real Estate Partners, LLC").
    """
    q, n = query.lower(), name.lower()
    full = difflib.SequenceMatcher(None, q, n).ratio()
    prefix = difflib.SequenceMatcher(None, q, n[: len(q)]).ratio()
    return max(full, prefix)


def _parse(data: dict, query: str) -> CompanyData:
    """Return the best fuzzy-matched company from OpenCorporates results."""
    companies = data.get("results", {}).get("companies", [])
    best: dict | None = None
    best_score = 0.0
    for entry in companies:
        company = entry.get("company", {})
        name = company.get("name", "")
        score = _similarity(query, name)
        if score > best_score and score >= SIMILARITY_THRESHOLD:
            best_score = score
            best = company
    if best is None:
        logger.info("OpenCorporates: no match above %.2f for '%s'", SIMILARITY_THRESHOLD, query)
        return CompanyData()
    return CompanyData(
        opencorporates_name=best.get("name"),
        opencorporates_jurisdiction=best.get("jurisdiction_code"),
        opencorporates_company_number=best.get("company_number"),
        opencorporates_incorporation_date=best.get("incorporation_date"),
        opencorporates_current_status=best.get("current_status"),
    )
