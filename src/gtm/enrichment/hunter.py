"""Hunter.io enrichment — company size and domain signals."""

import asyncio
import logging
import random

import httpx
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from gtm.config import settings
from gtm.exceptions import ConfigurationError
from gtm.models.company import CompanyData
from gtm.models.lead import RawLead
from gtm.utils.cache import FileCache

logger = logging.getLogger(__name__)

DELAY_MIN: float = 1.0
DELAY_MAX: float = 3.0
TIMEOUT_SECONDS: float = 15.0
MAX_RETRIES: int = 3
HUNTER_BASE_URL: str = "https://api.hunter.io/v2/domain-search"


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
    resp = await client.get(HUNTER_BASE_URL, params=params, timeout=TIMEOUT_SECONDS)
    if resp.status_code == 429 or resp.status_code >= 500:
        resp.raise_for_status()
    return resp


def _extract_domain(email: str) -> str | None:
    """Extract domain from an email address."""
    if "@" not in email:
        return None
    return email.split("@", 1)[1].lower().strip()


def _parse_count(value: object) -> int | None:
    """Parse employee count from a string, range, or int."""
    if value is None:
        return None
    try:
        # Handles "501-1000", "5000+", "500", 500
        return int(str(value).replace("+", "").split("-")[0].strip())
    except (ValueError, AttributeError):
        return None


async def enrich(lead: RawLead, client: httpx.AsyncClient, cache: FileCache) -> CompanyData:
    """Fetch company size and domain signals from Hunter.io."""
    if not settings.hunter_api_key:
        logger.warning("Hunter: no API key configured, skipping")
        return CompanyData()

    domain = _extract_domain(lead.email)
    if not domain:
        logger.warning("Hunter: could not extract domain from '%s'", lead.email)
        return CompanyData()

    cache_key = f"hunter:{domain}"
    cached = cache.get(cache_key)
    if cached:
        return CompanyData(**cached)

    await asyncio.sleep(random.uniform(DELAY_MIN, DELAY_MAX))

    try:
        logger.info("Hunter: querying domain '%s'", domain)
        resp = await _fetch(client, {"domain": domain, "api_key": settings.hunter_api_key})
        if resp.status_code in (401, 403):
            logger.error("Hunter: invalid API key (HTTP %s)", resp.status_code)
            raise ConfigurationError(f"Hunter API key invalid (HTTP {resp.status_code})")
        if resp.status_code == 404:
            logger.info("Hunter: no data for domain '%s'", domain)
            return CompanyData()
        result = _parse(resp.json(), domain)
        cache.set(cache_key, result.model_dump())
        logger.info("Hunter: enrichment done for domain '%s'", domain)
        return result
    except ConfigurationError:
        raise
    except httpx.TimeoutException as exc:
        logger.warning("Hunter: timeout for '%s': %s", domain, exc)
    except httpx.HTTPStatusError as exc:
        logger.warning("Hunter: HTTP %s for '%s'", exc.response.status_code, domain)
    except (ValueError, KeyError, TypeError) as exc:
        logger.warning("Hunter: parse error for '%s': %s", domain, exc)
    return CompanyData()


def _parse(data: dict, domain: str) -> CompanyData:
    """Parse Hunter domain-search response into CompanyData."""
    payload = data.get("data") or {}
    raw_count = payload.get("headcount") or payload.get("size")
    return CompanyData(
        hunter_domain=payload.get("domain") or domain,
        hunter_organization=payload.get("organization"),
        hunter_employee_count=_parse_count(raw_count),
    )
