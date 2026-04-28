"""SEC EDGAR enrichment — detect whether a company files public 10-K reports.

Uses the EDGAR full-text search API to find 10-K filings where the company
appears as the filer entity. Property management companies are almost always
private; a positive result is an informational insight, not scored.
"""

import logging

import httpx

from gtm.models.company import CompanyData
from gtm.models.lead import RawLead
from gtm.utils.cache import FileCache

logger = logging.getLogger(__name__)

EDGAR_SEARCH_URL: str = "https://efts.sec.gov/LATEST/search-index"
TIMEOUT_SECONDS: float = 10.0
# EDGAR fair-use policy requires a descriptive User-Agent: https://www.sec.gov/os/webmaster-faq#developers
EDGAR_HEADERS: dict[str, str] = {"User-Agent": "EliseAI GTM Tool santiagbv@gmail.com"}


async def enrich(lead: RawLead, client: httpx.AsyncClient, cache: FileCache) -> CompanyData:
    """Check SEC EDGAR for 10-K filings to infer whether the company is publicly traded."""
    cache_key = f"edgar:{lead.company.lower()}"
    cached = cache.get(cache_key)
    if cached:
        return CompanyData(**cached)

    try:
        params = {"q": f'"{lead.company}"', "forms": "10-K"}
        logger.info("EDGAR: checking public filing status for %s", lead.company)
        resp = await client.get(EDGAR_SEARCH_URL, params=params, headers=EDGAR_HEADERS, timeout=TIMEOUT_SECONDS)
        if resp.status_code != 200:
            logger.warning("EDGAR: HTTP %s for %s", resp.status_code, lead.company)
            return CompanyData()

        data = resp.json()
        hits_list = data.get("hits", {}).get("hits", [])
        company_lower = lead.company.lower()
        is_public = any(
            company_lower in hit.get("_source", {}).get("entity_name", "").lower()
            for hit in hits_list
        )
        result = CompanyData(is_publicly_traded=is_public)
        cache.set(cache_key, result.model_dump())
        logger.info("EDGAR: %s is_publicly_traded=%s", lead.company, is_public)
        return result
    except httpx.TimeoutException as exc:
        logger.warning("EDGAR: timeout for %s: %s", lead.company, exc)
    except (ValueError, KeyError, TypeError) as exc:
        logger.warning("EDGAR: parse error for %s: %s", lead.company, exc)
    return CompanyData()
