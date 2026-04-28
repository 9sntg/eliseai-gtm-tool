"""Lead scorer — orchestrates signal functions and returns a 0–100 score.

Public entry point::

    overall, tier, breakdown = score_lead(enriched_lead)
    insights = generate_insights(enriched_lead, breakdown)
"""

from __future__ import annotations

import logging

from gtm.config import (
    TIER_LOW_MAX_SCORE,
    TIER_MEDIUM_MAX_SCORE,
    WEIGHT_COMPANY_AGE,
    WEIGHT_CORPORATE_EMAIL,
    WEIGHT_DEPARTMENT_FUNCTION,
    WEIGHT_ECONOMIC_MOMENTUM,
    WEIGHT_EMPLOYEE_COUNT,
    WEIGHT_JOB_POSTINGS,
    WEIGHT_MEDIAN_RENT,
    WEIGHT_POPULATION_GROWTH,
    WEIGHT_PORTFOLIO_NEWS,
    WEIGHT_RENTER_RATE,
    WEIGHT_RENTER_UNITS,
    WEIGHT_SENIORITY,
    WEIGHT_TECH_STACK,
)
from gtm.models.enriched import EnrichedLead, ScoreTier
from gtm.models.scoring import ScoreBreakdown
from gtm.scoring.scorer_signals import (
    MEDIAN_RENT_MID,
    PM_TECH,
    score_company_age,
    score_corporate_email,
    score_department_function,
    score_economic_momentum,
    score_employee_count,
    score_job_postings,
    score_median_rent,
    score_population_growth,
    score_portfolio_news,
    score_renter_rate,
    score_renter_units,
    score_seniority,
    score_tech_stack,
)

logger = logging.getLogger(__name__)

# Category weight totals — used to normalise subtotals to 0–100
_MARKET_W: float = (
    WEIGHT_RENTER_UNITS + WEIGHT_RENTER_RATE + WEIGHT_MEDIAN_RENT
    + WEIGHT_POPULATION_GROWTH + WEIGHT_ECONOMIC_MOMENTUM
)
_COMPANY_W: float = (
    WEIGHT_JOB_POSTINGS + WEIGHT_PORTFOLIO_NEWS + WEIGHT_TECH_STACK
    + WEIGHT_EMPLOYEE_COUNT + WEIGHT_COMPANY_AGE
)
_PERSON_W: float = WEIGHT_SENIORITY + WEIGHT_DEPARTMENT_FUNCTION + WEIGHT_CORPORATE_EMAIL


def compute_tier(score: float) -> ScoreTier:
    """Map a 0–100 score to a Low / Medium / High tier."""
    if score <= TIER_LOW_MAX_SCORE:
        return "Low"
    if score <= TIER_MEDIUM_MAX_SCORE:
        return "Medium"
    return "High"


def generate_insights(lead: EnrichedLead, breakdown: ScoreBreakdown) -> list[str]:
    """Return 3–5 plain-English bullets summarising the lead's key strengths."""
    bullets: list[str] = []
    m, c, p = lead.market, lead.company, lead.person

    if m.renter_occupied_units:
        bullets.append(
            f"Large rental market: {m.renter_occupied_units:,} renter-occupied units "
            f"in {lead.raw.city}, {lead.raw.state}."
        )
    if m.median_gross_rent:
        label = "above" if m.median_gross_rent >= MEDIAN_RENT_MID else "below"
        bullets.append(f"Median gross rent ${m.median_gross_rent:,}/mo — {label}-average market.")
    if c.serper_property_management.knowledge_graph_title:
        bullets.append(
            f"Established brand: '{c.serper_property_management.knowledge_graph_title}' "
            "has a Google Knowledge Graph entry."
        )
    if c.tech_stack:
        pm_found = [t for t in c.tech_stack if t.lower() in PM_TECH]
        if pm_found:
            bullets.append(f"Uses legacy PM tech ({', '.join(pm_found)}) — strong replacement pitch.")
        else:
            bullets.append(f"Tech-forward org: {len(c.tech_stack)} technology/tools detected.")
    if c.is_publicly_traded:
        bullets.append("Publicly traded company — executive contacts have fiduciary accountability.")
    if p.job_title and p.seniority in {"c_suite", "vp", "director", "owner", "partner"}:
        bullets.append(f"Decision-maker contact: {p.job_title} is a budget-authority role.")
    if not bullets:
        bullets.append("Limited enrichment data available — manual research recommended.")
    return bullets[:5]


def score_lead(lead: EnrichedLead) -> tuple[float, ScoreTier, ScoreBreakdown]:
    """Score an enriched lead 0–100 and return tier and full signal breakdown."""
    m, c, p = lead.market, lead.company, lead.person

    sig_renter_units = score_renter_units(m.renter_occupied_units)
    sig_renter_rate = score_renter_rate(m.renter_rate)
    sig_median_rent = score_median_rent(m.median_gross_rent)
    sig_pop_growth = score_population_growth(m.population_growth_yoy)
    sig_econ = score_economic_momentum(m.median_income_growth_yoy)

    sig_jobs = score_job_postings(len(c.serper_jobs.organic))
    sig_news = score_portfolio_news(
        len(c.serper_property_management.organic),
        bool(c.serper_property_management.knowledge_graph_title),
    )
    sig_tech = score_tech_stack(c.tech_stack)
    sig_emp = score_employee_count(c.linkedin_employee_count)
    sig_age = score_company_age(c.founded_year)

    sig_seniority = score_seniority(p.seniority)
    sig_dept = score_department_function(p.department)
    sig_email = score_corporate_email(p.is_corporate_email)

    # Redistribute BuiltWith weight to portfolio_news when no tech data is available
    w_news = WEIGHT_PORTFOLIO_NEWS + (WEIGHT_TECH_STACK if not c.tech_stack else 0.0)
    w_tech = 0.0 if not c.tech_stack else WEIGHT_TECH_STACK

    market_raw = (
        sig_renter_units * WEIGHT_RENTER_UNITS
        + sig_renter_rate * WEIGHT_RENTER_RATE
        + sig_median_rent * WEIGHT_MEDIAN_RENT
        + sig_pop_growth * WEIGHT_POPULATION_GROWTH
        + sig_econ * WEIGHT_ECONOMIC_MOMENTUM
    )
    company_raw = (
        sig_jobs * WEIGHT_JOB_POSTINGS
        + sig_news * w_news
        + sig_tech * w_tech
        + sig_emp * WEIGHT_EMPLOYEE_COUNT
        + sig_age * WEIGHT_COMPANY_AGE
    )
    person_raw = (
        sig_seniority * WEIGHT_SENIORITY
        + sig_dept * WEIGHT_DEPARTMENT_FUNCTION
        + sig_email * WEIGHT_CORPORATE_EMAIL
    )

    overall = round((market_raw + company_raw + person_raw) * 100, 2)
    tier = compute_tier(overall)
    breakdown = ScoreBreakdown(
        renter_units=sig_renter_units,
        renter_rate=sig_renter_rate,
        median_rent=sig_median_rent,
        population_growth=sig_pop_growth,
        economic_momentum=sig_econ,
        job_postings=sig_jobs,
        portfolio_news=sig_news,
        tech_stack=sig_tech,
        employee_count=sig_emp,
        company_age=sig_age,
        seniority=sig_seniority,
        department_function=sig_dept,
        corporate_email=sig_email,
        market_score=round(market_raw / _MARKET_W * 100, 2),
        company_score=round(company_raw / _COMPANY_W * 100, 2),
        person_score=round(person_raw / _PERSON_W * 100, 2),
    )
    logger.info(
        "scored lead: %.1f/100 %s — %s, %s",
        overall, tier, lead.raw.company, lead.raw.city,
    )
    return overall, tier, breakdown
