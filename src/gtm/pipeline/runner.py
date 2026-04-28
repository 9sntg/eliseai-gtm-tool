"""Async pipeline orchestrator — enriches, scores, and writes output for each lead."""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

import httpx

from gtm.enrichment import builtwith, census, datausa, edgar, pdl, serper, yelp
from gtm.models.building import BuildingData
from gtm.models.company import CompanyData
from gtm.models.enriched import EnrichedLead
from gtm.models.lead import RawLead
from gtm.models.market import MarketData
from gtm.models.person import PersonData
from gtm.outreach.email_generator import generate_email
from gtm.scoring.scorer import generate_insights, score_lead
from gtm.utils.cache import FileCache
from gtm.utils.slug import make_slug, unique_slug

logger = logging.getLogger(__name__)

TIMEOUT_SECONDS: float = 30.0


def _merge_market(census_data: MarketData, datausa_data: MarketData) -> MarketData:
    """Combine disjoint Census and DataUSA fields into one MarketData."""
    return MarketData(
        renter_occupied_units=census_data.renter_occupied_units,
        total_housing_units=census_data.total_housing_units,
        renter_rate=census_data.renter_rate,
        median_gross_rent=census_data.median_gross_rent,
        total_population=census_data.total_population,
        population_growth_yoy=datausa_data.population_growth_yoy,
        median_household_income=datausa_data.median_household_income,
        median_income_growth_yoy=datausa_data.median_income_growth_yoy,
        real_estate_employment=datausa_data.real_estate_employment,
        median_property_value=datausa_data.median_property_value,
    )


def _merge_company(
    serper_data: CompanyData,
    bw_data: CompanyData,
    edgar_data: CompanyData,
    yelp_data: CompanyData,
) -> CompanyData:
    """Combine Serper, BuiltWith, EDGAR, and Yelp fields into one CompanyData."""
    return CompanyData(
        serper_property_management=serper_data.serper_property_management,
        serper_jobs=serper_data.serper_jobs,
        serper_linkedin=serper_data.serper_linkedin,
        linkedin_employee_count=serper_data.linkedin_employee_count,
        founded_year=serper_data.founded_year,
        job_count=serper_data.job_count,
        portfolio_size=serper_data.portfolio_size,
        yelp_alias=yelp_data.yelp_alias or serper_data.yelp_alias,
        social_platform_count=serper_data.social_platform_count,
        google_rating=serper_data.google_rating,
        is_publicly_traded=edgar_data.is_publicly_traded,
        tech_stack=bw_data.tech_stack,
        yelp_rating=yelp_data.yelp_rating,
        yelp_review_count=yelp_data.yelp_review_count,
        yelp_market_avg_rating=yelp_data.yelp_market_avg_rating,
        yelp_pain_themes=yelp_data.yelp_pain_themes,
        yelp_year_established=yelp_data.yelp_year_established,
    )


def _write_outputs(lead: EnrichedLead, lead_dir: Path) -> None:
    """Write enrichment.json, assessment.json, and email.txt to lead_dir."""
    lead_dir.mkdir(parents=True, exist_ok=True)

    enrichment_payload = {
        "market": lead.market.model_dump(mode="json"),
        "company": lead.company.model_dump(mode="json"),
        "person": lead.person.model_dump(mode="json"),
        "building": lead.building.model_dump(mode="json"),
    }
    (lead_dir / "enrichment.json").write_text(json.dumps(enrichment_payload, indent=2))

    assessment_payload = {
        "score": lead.score,
        "tier": lead.tier,
        "breakdown": lead.score_breakdown.model_dump(mode="json") if lead.score_breakdown else None,
        "insights": lead.insights,
    }
    (lead_dir / "assessment.json").write_text(json.dumps(assessment_payload, indent=2))

    (lead_dir / "email.txt").write_text(lead.email_draft or "")
    logger.info("outputs written: %s", lead_dir.name)


async def _safe(coro, default):
    """Run a coroutine and return default if it raises, logging the failure."""
    try:
        return await coro
    except Exception as exc:
        logger.warning("enrichment failed (%s): %s", type(exc).__name__, exc)
        return default


async def enrich_lead(
    lead: RawLead,
    outputs_dir: Path,
    client: httpx.AsyncClient,
    cache: FileCache,
) -> EnrichedLead | None:
    """Enrich, score, and persist one lead. Returns None if output folder already exists."""
    base_slug = make_slug(lead.company, lead.city, lead.state, lead.property_address or "")
    if (outputs_dir / base_slug).exists():
        logger.debug("skipping %s — output folder exists", base_slug)
        return None
    slug = unique_slug(base_slug, outputs_dir)

    logger.info("processing: %s (%s, %s)", lead.company, lead.city, lead.state)
    (
        census_data,
        datausa_data,
        serper_data,
        bw_data,
        edgar_data,
        person_data,
        yelp_company_data,
        building_data,
    ) = await asyncio.gather(
        _safe(census.enrich(lead, client, cache), MarketData()),
        _safe(datausa.enrich(lead, client, cache), MarketData()),
        _safe(serper.enrich(lead, client, cache), CompanyData()),
        _safe(builtwith.enrich(lead, client, cache), CompanyData()),
        _safe(edgar.enrich(lead, client, cache), CompanyData()),
        _safe(pdl.enrich(lead, client, cache), PersonData()),
        _safe(yelp.enrich_company(lead, client, cache), CompanyData()),
        _safe(yelp.enrich_building(lead, client, cache), BuildingData()),
    )

    market = _merge_market(census_data, datausa_data)
    company = _merge_company(serper_data, bw_data, edgar_data, yelp_company_data)
    enriched = EnrichedLead(
        raw=lead, market=market, company=company, person=person_data,
        building=building_data, slug=slug,
    )
    overall, tier, breakdown = score_lead(enriched)
    insights = generate_insights(enriched, breakdown)
    email_draft = generate_email(enriched)

    enriched = enriched.model_copy(update={
        "score": overall,
        "tier": tier,
        "score_breakdown": breakdown,
        "insights": insights,
        "email_draft": email_draft,
    })
    _write_outputs(enriched, outputs_dir / slug)
    return enriched


async def run_pipeline(
    leads: list[RawLead],
    outputs_dir: Path,
) -> list[EnrichedLead]:
    """Process all leads sequentially. Returns newly processed leads; existing leads skipped."""
    outputs_dir.mkdir(parents=True, exist_ok=True)
    cache = FileCache()
    processed: list[EnrichedLead] = []

    async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
        for lead in leads:
            result = await enrich_lead(lead, outputs_dir, client, cache)
            if result is not None:
                processed.append(result)

    return processed
