"""People Data Labs enrichment — person seniority and function signals."""

import asyncio
import logging
import random

import httpx
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from gtm.config import settings
from gtm.exceptions import ConfigurationError
from gtm.models.lead import RawLead
from gtm.models.person import PersonData
from gtm.utils.cache import FileCache
from gtm.utils.email import is_corporate_email

logger = logging.getLogger(__name__)

DELAY_MIN: float = 1.0
DELAY_MAX: float = 3.0
TIMEOUT_SECONDS: float = 15.0
MAX_RETRIES: int = 3
PDL_BASE_URL: str = "https://api.peopledatalabs.com/v5/person/enrich"


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
async def _fetch(
    client: httpx.AsyncClient, params: dict, headers: dict
) -> httpx.Response:
    resp = await client.get(PDL_BASE_URL, params=params, headers=headers, timeout=TIMEOUT_SECONDS)
    if resp.status_code == 429 or resp.status_code >= 500:
        resp.raise_for_status()
    return resp


async def enrich(lead: RawLead, client: httpx.AsyncClient, cache: FileCache) -> PersonData:
    """Fetch person seniority and function signals from People Data Labs."""
    corporate = is_corporate_email(lead.email)

    if not settings.pdl_api_key:
        logger.warning("PDL: no API key configured, returning email signal only")
        return PersonData(is_corporate_email=corporate)

    cache_key = f"pdl:{lead.email.lower()}"
    cached = cache.get(cache_key)
    if cached:
        return PersonData(**cached)

    await asyncio.sleep(random.uniform(DELAY_MIN, DELAY_MAX))

    # Log only the domain part to avoid logging PII
    safe_email = f"…@{lead.email.split('@')[-1]}" if "@" in lead.email else "unknown"
    try:
        logger.info("PDL: querying person for %s", safe_email)
        resp = await _fetch(
            client,
            params={"email": lead.email, "pretty": "false"},
            headers={"X-Api-Key": settings.pdl_api_key},
        )
        if resp.status_code in (401, 403):
            logger.error("PDL: invalid API key (HTTP %s)", resp.status_code)
            raise ConfigurationError(f"PDL API key invalid (HTTP {resp.status_code})")
        if resp.status_code == 404:
            logger.warning("PDL: no match for %s, seniority signal = 0", safe_email)
            return PersonData(is_corporate_email=corporate)
        result = _parse(resp.json(), corporate)
        cache.set(cache_key, result.model_dump())
        logger.info("PDL: enrichment done (likelihood=%s)", result.pdl_likelihood)
        return result
    except ConfigurationError:
        raise
    except httpx.TimeoutException as exc:
        logger.warning("PDL: timeout: %s", exc)
    except httpx.HTTPStatusError as exc:
        logger.warning("PDL: HTTP %s", exc.response.status_code)
    except (ValueError, KeyError, TypeError) as exc:
        logger.warning("PDL: parse error: %s", exc)
    return PersonData(is_corporate_email=corporate)


def _parse(data: dict, corporate: bool) -> PersonData:
    """Parse PDL enrich response into PersonData."""
    person = data.get("data") or {}
    levels: list = person.get("job_title_levels") or []
    return PersonData(
        job_title=person.get("job_title"),
        seniority=levels[0] if levels else None,
        department=person.get("job_title_role"),
        pdl_likelihood=data.get("likelihood"),
        is_corporate_email=corporate,
    )
