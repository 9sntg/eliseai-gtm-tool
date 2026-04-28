"""BuiltWith enrichment — tech stack detection (optional, paid key required)."""

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
BUILTWITH_BASE_URL: str = "https://api.builtwith.com/v21/api.json"


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
    resp = await client.get(BUILTWITH_BASE_URL, params=params, timeout=TIMEOUT_SECONDS)
    if resp.status_code == 429 or resp.status_code >= 500:
        resp.raise_for_status()
    return resp


def _extract_domain(email: str) -> str | None:
    """Extract domain from an email address."""
    if "@" not in email:
        return None
    return email.split("@", 1)[1].lower().strip()


async def enrich(lead: RawLead, client: httpx.AsyncClient, cache: FileCache) -> CompanyData:
    """Detect tech stack from lead domain via BuiltWith. Skips if no key configured."""
    if not settings.builtwith_api_key:
        logger.debug("BuiltWith: no API key configured, skipping")
        return CompanyData()

    domain = _extract_domain(lead.email)
    if not domain:
        logger.warning("BuiltWith: could not extract domain from '%s'", lead.email)
        return CompanyData()

    cache_key = f"builtwith:{domain}"
    cached = cache.get(cache_key)
    if cached:
        return CompanyData(**cached)

    await asyncio.sleep(random.uniform(DELAY_MIN, DELAY_MAX))

    try:
        logger.info("BuiltWith: querying domain '%s'", domain)
        resp = await _fetch(client, {"KEY": settings.builtwith_api_key, "LOOKUP": domain})
        if resp.status_code in (401, 403):
            logger.error("BuiltWith: invalid API key (HTTP %s)", resp.status_code)
            raise ConfigurationError(f"BuiltWith API key invalid (HTTP {resp.status_code})")
        if resp.status_code == 404:
            logger.info("BuiltWith: no data for domain '%s'", domain)
            return CompanyData()
        result = _parse(resp.json())
        cache.set(cache_key, result.model_dump())
        logger.info("BuiltWith: found %d technologies for '%s'", len(result.tech_stack), domain)
        return result
    except ConfigurationError:
        raise
    except httpx.TimeoutException as exc:
        logger.warning("BuiltWith: timeout for '%s': %s", domain, exc)
    except httpx.HTTPStatusError as exc:
        logger.warning("BuiltWith: HTTP %s for '%s'", exc.response.status_code, domain)
    except (ValueError, KeyError, TypeError) as exc:
        logger.warning("BuiltWith: parse error for '%s': %s", domain, exc)
    return CompanyData()


def _parse(data: dict) -> CompanyData:
    """Extract deduplicated technology names from BuiltWith response."""
    seen: set[str] = set()
    tech_names: list[str] = []
    for result in data.get("Results", []):
        for path in result.get("Paths", []):
            for tech in path.get("Technologies", []):
                name = tech.get("Name")
                if name and name not in seen:
                    seen.add(name)
                    tech_names.append(name)
    return CompanyData(tech_stack=tech_names)
