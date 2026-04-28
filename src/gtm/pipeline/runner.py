"""Async pipeline orchestrator — enriches, scores, and writes output for each lead."""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

import httpx

from gtm.enrichment import builtwith, census, datausa, hunter, opencorporates, pdl, serper
from gtm.models.company import CompanyData
from gtm.models.enriched import EnrichedLead
from gtm.models.lead import RawLead
from gtm.models.market import MarketData
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
    oc_data: CompanyData,
    hunter_data: CompanyData,
    bw_data: CompanyData,
) -> CompanyData:
    """Combine Serper, OpenCorporates, Hunter, and BuiltWith fields."""
    return CompanyData(
        serper_property_management=serper_data.serper_property_management,
        serper_jobs=serper_data.serper_jobs,
        opencorporates_name=oc_data.opencorporates_name,
        opencorporates_jurisdiction=oc_data.opencorporates_jurisdiction,
        opencorporates_company_number=oc_data.opencorporates_company_number,
        opencorporates_incorporation_date=oc_data.opencorporates_incorporation_date,
        opencorporates_current_status=oc_data.opencorporates_current_status,
        hunter_organization=hunter_data.hunter_organization,
        hunter_employee_count=hunter_data.hunter_employee_count,
        hunter_domain=hunter_data.hunter_domain,
        tech_stack=bw_data.tech_stack,
    )


def _write_outputs(lead: EnrichedLead, lead_dir: Path) -> None:
    """Write enrichment.json, assessment.json, and email.txt to lead_dir."""
    lead_dir.mkdir(parents=True, exist_ok=True)

    enrichment_payload = {
        "market": lead.market.model_dump(mode="json"),
        "company": lead.company.model_dump(mode="json"),
        "person": lead.person.model_dump(mode="json"),
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


async def enrich_lead(
    lead: RawLead,
    outputs_dir: Path,
    client: httpx.AsyncClient,
    cache: FileCache,
) -> EnrichedLead | None:
    """Enrich, score, and persist one lead. Returns None if output folder already exists."""
    base_slug = make_slug(lead.company, lead.city, lead.state)
    if (outputs_dir / base_slug).exists():
        logger.debug("skipping %s — output folder exists", base_slug)
        return None
    slug = unique_slug(base_slug, outputs_dir)

    logger.info("processing: %s (%s, %s)", lead.company, lead.city, lead.state)
    (
        census_data,
        datausa_data,
        serper_data,
        oc_data,
        hunter_data,
        bw_data,
        person_data,
    ) = await asyncio.gather(
        census.enrich(lead, client, cache),
        datausa.enrich(lead, client, cache),
        serper.enrich(lead, client, cache),
        opencorporates.enrich(lead, client, cache),
        hunter.enrich(lead, client, cache),
        builtwith.enrich(lead, client, cache),
        pdl.enrich(lead, client, cache),
    )

    market = _merge_market(census_data, datausa_data)
    company = _merge_company(serper_data, oc_data, hunter_data, bw_data)
    enriched = EnrichedLead(
        raw=lead, market=market, company=company, person=person_data, slug=slug,
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
