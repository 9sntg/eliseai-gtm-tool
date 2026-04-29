"""Yelp Fusion enrichment — company profile + comparables, and building fit.

File is ~264 lines — over the 200-line limit. enrich_company and
enrich_building are closely coupled (share _fetch, headers, cache key helpers,
and building-name resolution via Serper) and separating them would not reduce
complexity. Accepted as-is.
"""

from __future__ import annotations

import asyncio
import logging
import random

import httpx
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from gtm.config import settings
from gtm.enrichment.yelp_helpers import (
    compute_competitor_rank,
    extract_pain_themes,
    parse_market_avg_rating,
)
from gtm.exceptions import ConfigurationError
from gtm.models.building import BuildingData
from gtm.models.company import CompanyData
from gtm.models.lead import RawLead
from gtm.utils.cache import FileCache

logger = logging.getLogger(__name__)

YELP_BASE: str = "https://api.yelp.com/v3/businesses"
SERPER_URL: str = "https://google.serper.dev/search"
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
        if resp.status_code == 401:
            raise ConfigurationError(f"Yelp API key invalid (HTTP 401)")
        if resp.status_code == 403:
            logger.warning("Yelp: 403 for %s — business restricted, skipping", url)
            return {}
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
    comp_businesses = comparables.get("businesses", [])
    market_avg = parse_market_avg_rating(comp_businesses)
    company_rating = profile.get("rating")
    competitor_rank_pct = (
        compute_competitor_rank(comp_businesses, alias, company_rating)
        if company_rating is not None else None
    )

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

    logger.info("Yelp: company enriched for %s (rating=%.1f)", lead.company, company_rating or 0)
    return CompanyData(
        yelp_alias=alias,
        yelp_rating=company_rating,
        yelp_review_count=profile.get("review_count"),
        yelp_market_avg_rating=market_avg,
        yelp_pain_themes=pain_themes,
        yelp_year_established=year_established,
        competitor_rank_pct=competitor_rank_pct,
    )


async def _resolve_building_name(
    lead: RawLead, client: httpx.AsyncClient, cache: FileCache
) -> str | None:
    """Use Serper to resolve a street address to an apartment complex name."""
    if not settings.serper_api_key or not lead.property_address:
        return None
    cache_key = f"serper:bldg_name:{lead.property_address.lower().replace(' ', '_')}:{lead.city.lower()}"
    cached = cache.get(cache_key)
    if cached:
        logger.debug("cache hit: %s", cache_key)
        return cached.get("name")
    query = f"{lead.property_address} {lead.city} {lead.state} apartments"
    logger.info("Serper: resolving building name for '%s'", lead.property_address)
    try:
        resp = await client.post(
            SERPER_URL,
            json={"q": query, "num": 3},
            headers={"X-API-KEY": settings.serper_api_key, "Content-Type": "application/json"},
            timeout=15.0,
        )
        if resp.status_code != 200:
            logger.warning("Serper: HTTP %s resolving building name", resp.status_code)
            return None
        data = resp.json()
        # Prefer knowledge graph title; fall back to first organic result title
        kg_title = (data.get("knowledgeGraph") or {}).get("title")
        organic = data.get("organic", [])
        name = kg_title or (organic[0]["title"].split(" - ")[0].split(" | ")[0] if organic else None)
        cache.set(cache_key, {"name": name})
        logger.info("Serper: resolved building '%s' → '%s'", lead.property_address, name)
        return name
    except Exception as exc:
        logger.warning("Serper: building name resolution failed: %s", exc)
        return None


async def enrich_building(lead: RawLead, client: httpx.AsyncClient, cache: FileCache) -> BuildingData:
    """Search Yelp for the specific property and extract building fit signals."""
    if not settings.yelp_api_key or not lead.property_address:
        return BuildingData()

    headers = {"Authorization": f"Bearer {settings.yelp_api_key}"}

    # Resolve street address → building name via Serper, then search Yelp by name
    building_name = await _resolve_building_name(lead, client, cache)
    search_term = building_name or lead.property_address
    # Cache key uses the resolved search term so a name-based search isn't served
    # a stale empty result from a previous address-based search.
    term_slug = search_term.lower().replace(" ", "_")[:40]
    await asyncio.sleep(random.uniform(DELAY_MIN, DELAY_MAX))

    logger.info("Yelp: searching for building '%s' in %s, %s", search_term, lead.city, lead.state)
    search = await _fetch(
        client, YELP_BASE + "/search",
        {"term": search_term, "location": f"{lead.city}, {lead.state}",
         "categories": "apartments", "limit": 3},
        headers, f"yelp:bldg_search:{term_slug}:{lead.city.lower()}", cache,
    )
    businesses = search.get("businesses", [])
    if not businesses:
        logger.info("Yelp: no building match for '%s'", search_term)
        return BuildingData(address=lead.property_address, name=building_name)

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

    price_tier = profile.get("price") or businesses[0].get("price")
    logger.info(
        "Yelp: building enriched for '%s' (rating=%s, price=%s)",
        search_term, profile.get("rating"), price_tier,
    )
    return BuildingData(
        address=lead.property_address,
        name=building_name,
        yelp_alias=alias,
        yelp_rating=profile.get("rating"),
        yelp_review_count=profile.get("review_count"),
        price_tier=price_tier,
        pain_themes=pain_themes,
    )
