"""Serper enrichment — company portfolio signals, hiring activity, and LinkedIn profile."""

import asyncio
import logging
import random

import httpx
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from gtm.config import settings
from gtm.enrichment.serper_helpers import (
    extract_company_profile,
    extract_job_count,
    extract_social_platforms,
    extract_yelp_alias,
    parse_serper_response,
)
from gtm.exceptions import ConfigurationError
from gtm.models.company import CompanyData, SerperSearchBucket
from gtm.models.lead import RawLead
from gtm.utils.cache import FileCache

logger = logging.getLogger(__name__)

DELAY_MIN: float = 1.0
DELAY_MAX: float = 3.0
TIMEOUT_SECONDS: float = 15.0
MAX_RETRIES: int = 3
SERPER_URL: str = "https://google.serper.dev/search"


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
async def _post(client: httpx.AsyncClient, payload: dict, headers: dict) -> httpx.Response:
    resp = await client.post(SERPER_URL, json=payload, headers=headers, timeout=TIMEOUT_SECONDS)
    if resp.status_code == 429 or resp.status_code >= 500:
        resp.raise_for_status()
    return resp


async def enrich(lead: RawLead, client: httpx.AsyncClient, cache: FileCache) -> CompanyData:
    """Run three Serper queries — portfolio signals, hiring signals, and LinkedIn profile."""
    if not settings.serper_api_key:
        logger.warning("Serper: no API key configured, skipping")
        return CompanyData()

    pm_query = f"{lead.company} property management"
    jobs_query = f"{lead.company} leasing consultant jobs"
    linkedin_query = f"site:linkedin.com/company {lead.company}"

    pm_bucket = await _query(client, cache, pm_query, f"pm:{lead.company.lower()}", req="1/3")
    await asyncio.sleep(random.uniform(DELAY_MIN, DELAY_MAX))
    jobs_bucket = await _query(client, cache, jobs_query, f"jobs:{lead.company.lower()}", req="2/3")
    await asyncio.sleep(random.uniform(DELAY_MIN, DELAY_MAX))
    linkedin_bucket = await _query(
        client, cache, linkedin_query, f"linkedin:{lead.company.lower()}", req="3/3"
    )

    # Combine LinkedIn + PM snippets for richer profile extraction; LinkedIn first (more structured)
    linkedin_snippets = [item.snippet for item in linkedin_bucket.organic if item.snippet]
    pm_snippets = [item.snippet for item in pm_bucket.organic if item.snippet]
    profile = await extract_company_profile(linkedin_snippets + pm_snippets, lead.company)

    jobs_snippets = [item.snippet for item in jobs_bucket.organic if item.snippet]
    job_count = extract_job_count(jobs_snippets)
    yelp_alias = extract_yelp_alias(pm_bucket.organic)
    social_platform_count = extract_social_platforms(pm_bucket.organic)

    return CompanyData(
        serper_property_management=pm_bucket,
        serper_jobs=jobs_bucket,
        serper_linkedin=linkedin_bucket,
        linkedin_employee_count=profile.get("employee_count"),
        founded_year=profile.get("founded_year"),
        job_count=job_count,
        portfolio_size=profile.get("portfolio_size"),
        yelp_alias=yelp_alias,
        social_platform_count=social_platform_count,
    )


async def _query(
    client: httpx.AsyncClient,
    cache: FileCache,
    query: str,
    cache_key: str,
    req: str,
) -> SerperSearchBucket:
    """Run one Serper search query; return empty bucket on any failure."""
    cached = cache.get(f"serper:{cache_key}")
    if cached:
        return SerperSearchBucket(**cached)

    headers = {"X-API-KEY": settings.serper_api_key or ""}
    try:
        logger.info("Serper: querying '%s' (req %s)", query, req)
        resp = await _post(client, {"q": query, "num": 10}, headers)
        if resp.status_code in (401, 403):
            logger.error("Serper: invalid API key (HTTP %s)", resp.status_code)
            raise ConfigurationError(f"Serper API key invalid (HTTP {resp.status_code})")
        if resp.status_code != 200:
            logger.warning("Serper: HTTP %s for query '%s'", resp.status_code, query)
            return SerperSearchBucket(query=query)
        bucket = parse_serper_response(resp.json(), query)
        cache.set(f"serper:{cache_key}", bucket.model_dump())
        return bucket
    except ConfigurationError:
        raise
    except httpx.TimeoutException as exc:
        logger.warning("Serper: timeout for '%s': %s", query, exc)
    except httpx.HTTPStatusError as exc:
        logger.warning("Serper: HTTP %s for '%s'", exc.response.status_code, query)
    except (ValueError, KeyError, TypeError) as exc:
        logger.warning("Serper: parse error for '%s': %s", query, exc)
    return SerperSearchBucket(query=query)
