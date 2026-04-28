"""Tests for Pydantic models."""

import json

from gtm.models import (
    CompanyData,
    EnrichedLead,
    MarketData,
    PersonData,
    RawLead,
    ScoreBreakdown,
    SerperOrganicItem,
    SerperSearchBucket,
)


def test_raw_lead_normalizes_state() -> None:
    lead = RawLead(
        name="Jane",
        email="jane@example.com",
        company="Acme PM",
        property_address="1 Main",
        city="Austin",
        state="tx",
    )
    assert lead.state == "TX"


def test_enriched_lead_json_roundtrip() -> None:
    raw = RawLead(
        name="Jane",
        email="jane@acme.com",
        company="Acme",
        property_address="1 Main",
        city="Austin",
        state="TX",
    )
    market = MarketData(renter_occupied_units=50000, median_gross_rent=1500)
    company = CompanyData(
        hunter_organization="Acme",
        hunter_employee_count=200,
        tech_stack=["Yardi Voyager"],
        serper_property_management=SerperSearchBucket(
            query="Acme property management",
            organic=[
                SerperOrganicItem(title="Acme", link="https://acme.com", snippet="Portfolio news")
            ],
        ),
    )
    person = PersonData(
        job_title="VP Operations",
        seniority="vp",
        department="operations",
        is_corporate_email=True,
    )
    breakdown = ScoreBreakdown(
        renter_units=0.8,
        market_score=55.0,
        company_score=60.0,
        person_score=70.0,
    )
    enriched = EnrichedLead(
        raw=raw,
        market=market,
        company=company,
        person=person,
        slug="acme-austin-tx",
        score=62.5,
        tier="Medium",
        score_breakdown=breakdown,
        insights=["Strong renter market", "Legacy stack"],
        email_draft="Hello...",
    )
    dumped = enriched.model_dump(mode="json")
    json.dumps(dumped)
    assert dumped["slug"] == "acme-austin-tx"
    assert dumped["company"]["tech_stack"] == ["Yardi Voyager"]


def test_default_models_are_json_safe() -> None:
    lead = EnrichedLead(raw=RawLead())
    json.dumps(lead.model_dump(mode="json"))
