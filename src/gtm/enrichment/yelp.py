"""Yelp Fusion enrichment — company profile + comparables, and building fit."""

from __future__ import annotations

import asyncio
import logging
import random

import httpx
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from gtm.config import settings
from gtm.enrichment.yelp_helpers import extract_pain_themes, parse_market_avg_rating
from gtm.exceptions import ConfigurationError
from gtm.models.building import BuildingData
from gtm.models.company import CompanyData
from gtm.models.lead import RawLead
from gtm.utils.cache import FileCache

logger = logging.getLogger(__name__)

YELP_BASE: str = "https://api.yelp.com/v3/businesses"
DELAY_MIN: float = 0.5
DELAY_MAX: float = 1.5
TIMEOUT_SECONDS: float = 15.0
MAX_RETRIES: int = 3
COMPARABLES_LIMIT: int = 10


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
async def _get(
    client: httpx.AsyncClient, url: str, params: dict, headers: dict
) -> httpx.Response:
    resp = await client.get(url, params=params, headers=headers, timeout=TIMEOUT_SECONDS)
    if resp.status_code == 429 or resp.status_code >= 500:
        resp.raise_for_status()
    return resp


async def _fetch(
    client: httpx.AsyncClient,
    url: str,
    params: dict,
    headers: dict,
    cache_key: str,
    cache: FileCache,
) -> dict:
    """Fetch a Yelp endpoint with caching. Returns {} on any failure."""
    cached = cache.get(cache_key)
    if cached:
        logger.debug("cache hit: %s", cache_key)
        return cached
    try:
        resp = await _get(client, url, params, headers)
        if resp.status_code in (401, 403):
            raise ConfigurationError(f"Yelp API key invalid (HTTP {resp.status_code})")
        if resp.status_code == 404:
            logger.info("Yelp: 404 for %s", url)
            return {}
        if resp.status_code != 200:
            logger.warning("Yelp: HTTP %s for %s", resp.status_code, url)
            return {}
        data = resp.json()
        cache.set(cache_key, data)
        return data
    except ConfigurationError:
        raise
    except httpx.TimeoutException as exc:
        logger.warning("Yelp: timeout for %s: %s", url, exc)
    except httpx.HTTPStatusError as exc:
        logger.warning("Yelp: HTTP %s for %s", exc.response.status_code, url)
    except (ValueError, KeyError, TypeError) as exc:
        logger.warning("Yelp: parse error for %s: %s", url, exc)
    return {}


async def enrich_company(lead: RawLead, client: httpx.AsyncClient, cache: FileCache) -> CompanyData:
    """Fetch company Yelp profile, review highlights, comparables, and extract pain themes."""
    if not settings.yelp_api_key:
        logger.warning("Yelp: no API key configured, skipping company enrichment")
        return CompanyData()

    headers = {"Authorization": f"Bearer {settings.yelp_api_key}"}
    city_state = f"{lead.city}, {lead.state}"
    cache_slug = lead.company.lower().replace(" ", "_")

    # Find company on Yelp
    logger.info("Yelp: searching for company '%s' in %s", lead.company, city_state)
    search = await _fetch(
        client, YELP_BASE + "/search",
        {"term": lead.company, "location": city_state, "categories": "propertymgmt", "limit": 3},
        headers, f"yelp:co_search:{cache_slug}:{lead.city.lower()}", cache,
    )
    businesses = search.get("businesses", [])
    if not businesses:
        logger.info("Yelp: no company match for %s", lead.company)
        return CompanyData()

    alias = businesses[0]["alias"]
    await asyncio.sleep(random.uniform(DELAY_MIN, DELAY_MAX))

    # Fetch profile, reviews, highlights concurrently
    profile, reviews_data, highlights_data = await asyncio.gather(
        _fetch(client, f"{YELP_BASE}/{alias}", {}, headers, f"yelp:co_profile:{alias}", cache),
        _fetch(client, f"{YELP_BASE}/{alias}/reviews", {}, headers, f"yelp:co_reviews:{alias}", cache),
        _fetch(client, f"{YELP_BASE}/{alias}/review_highlights", {}, headers, f"yelp:co_highlights:{alias}", cache),
    )

    # Fetch comparables
    await asyncio.sleep(random.uniform(DELAY_MIN, DELAY_MAX))
    comparables = await _fetch(
        client, YELP_BASE + "/search",
        {"term": "property management", "location": city_state,
         "categories": "propertymgmt", "limit": COMPARABLES_LIMIT},
        headers, f"yelp:comparables:{lead.city.lower()}:{lead.state.lower()}", cache,
    )
    market_avg = parse_market_avg_rating(comparables.get("businesses", []))

    pain_themes = await extract_pain_themes(
        highlights_data.get("review_highlights", []),
        reviews_data.get("reviews", []),
        lead.company,
        context="company",
    )

    attrs = profile.get("attributes", {})
    raw_year = attrs.get("about_this_biz_year_established")
    try:
        year_established = int(raw_year) if raw_year else None
    except (ValueError, TypeError):
        year_established = None

    logger.info("Yelp: company enriched for %s (rating=%.1f)", lead.company, profile.get("rating") or 0)
    return CompanyData(
        yelp_alias=alias,
        yelp_rating=profile.get("rating"),
        yelp_review_count=profile.get("review_count"),
        yelp_market_avg_rating=market_avg,
        yelp_pain_themes=pain_themes,
        yelp_year_established=year_established,
    )


async def enrich_building(lead: RawLead, client: httpx.AsyncClient, cache: FileCache) -> BuildingData:
    """Search Yelp for the specific property and extract building fit signals."""
    if not settings.yelp_api_key or not lead.property_address:
        return BuildingData()

    headers = {"Authorization": f"Bearer {settings.yelp_api_key}"}
    location = f"{lead.property_address}, {lead.city}, {lead.state}"
    cache_slug = lead.property_address.lower().replace(" ", "_")[:40]

    logger.info("Yelp: searching for building '%s'", location)
    search = await _fetch(
        client, YELP_BASE + "/search",
        {"term": lead.property_address, "location": f"{lead.city}, {lead.state}",
         "categories": "apartments", "limit": 3},
        headers, f"yelp:bldg_search:{cache_slug}:{lead.city.lower()}", cache,
    )
    businesses = search.get("businesses", [])
    if not businesses:
        logger.info("Yelp: no building match for %s", lead.property_address)
        return BuildingData(address=lead.property_address)

    alias = businesses[0]["alias"]
    await asyncio.sleep(random.uniform(DELAY_MIN, DELAY_MAX))

    profile, reviews_data, highlights_data = await asyncio.gather(
        _fetch(client, f"{YELP_BASE}/{alias}", {}, headers, f"yelp:bldg_profile:{alias}", cache),
        _fetch(client, f"{YELP_BASE}/{alias}/reviews", {}, headers, f"yelp:bldg_reviews:{alias}", cache),
        _fetch(client, f"{YELP_BASE}/{alias}/review_highlights", {}, headers, f"yelp:bldg_highlights:{alias}", cache),
    )

    pain_themes = await extract_pain_themes(
        highlights_data.get("review_highlights", []),
        reviews_data.get("reviews", []),
        lead.property_address,
        context="building",
    )

    logger.info(
        "Yelp: building enriched for %s (rating=%s)",
        lead.property_address, profile.get("rating"),
    )
    return BuildingData(
        address=lead.property_address,
        yelp_alias=alias,
        yelp_rating=profile.get("rating"),
        yelp_review_count=profile.get("review_count"),
        pain_themes=pain_themes,
    )
