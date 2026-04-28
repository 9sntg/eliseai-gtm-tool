"""Lead scorer — additive point model, returns a score and full signal breakdown.

Public entry point::

    overall, tier, breakdown = score_lead(enriched_lead)
    insights = generate_insights(enriched_lead, breakdown)

Each signal contributes 0–N points when it fires, 0 when data is absent.
Missing signals do not affect other signals. Baseline max = 100 pts.
"""

from __future__ import annotations

import logging

from gtm.config import (
    POINTS_COMPANY_AGE,
    POINTS_CORPORATE_EMAIL,
    POINTS_DEPARTMENT_FUNCTION,
    POINTS_ECONOMIC_MOMENTUM,
    POINTS_EMPLOYEE_COUNT,
    POINTS_JOB_POSTINGS,
    POINTS_MEDIAN_RENT,
    POINTS_POPULATION_GROWTH,
    POINTS_PORTFOLIO_NEWS,
    POINTS_PORTFOLIO_SIZE,
    POINTS_RENTER_RATE,
    POINTS_RENTER_UNITS,
    POINTS_SENIORITY,
    POINTS_SOCIAL_PRESENCE,
    POINTS_TECH_STACK,
    TIER_LOW_MAX_SCORE,
    TIER_MEDIUM_MAX_SCORE,
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
    score_portfolio_size,
    score_renter_rate,
    score_renter_units,
    score_seniority,
    score_social_presence,
    score_tech_stack,
)

logger = logging.getLogger(__name__)

# Category maximums — used to normalise subtotals to 0–100 for display
_MARKET_MAX: float = (
    POINTS_RENTER_UNITS + POINTS_RENTER_RATE + POINTS_MEDIAN_RENT
    + POINTS_POPULATION_GROWTH + POINTS_ECONOMIC_MOMENTUM
)
_COMPANY_MAX: float = (
    POINTS_JOB_POSTINGS + POINTS_PORTFOLIO_NEWS + POINTS_TECH_STACK
    + POINTS_EMPLOYEE_COUNT + POINTS_COMPANY_AGE
)
_PERSON_MAX: float = POINTS_SENIORITY + POINTS_DEPARTMENT_FUNCTION + POINTS_CORPORATE_EMAIL


def compute_tier(score: float) -> ScoreTier:
    """Map a score to a Low / Medium / High tier."""
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
    if c.portfolio_size:
        bullets.append(f"Manages ~{c.portfolio_size:,} units/communities — significant automation opportunity.")
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
    """Score an enriched lead and return tier and full signal breakdown.

    Each signal fires independently. Absent data contributes 0 pts without
    affecting other signals.
    """
    m, c, p = lead.market, lead.company, lead.person

    # Market signals
    sig_renter_units = score_renter_units(m.renter_occupied_units)
    sig_renter_rate  = score_renter_rate(m.renter_rate)
    sig_median_rent  = score_median_rent(m.median_gross_rent)
    sig_pop_growth   = score_population_growth(m.population_growth_yoy)
    sig_econ         = score_economic_momentum(m.median_income_growth_yoy)

    # Company signals — each fires independently, no redistribution
    _job_count = c.job_count if c.job_count is not None else len(c.serper_jobs.organic)
    sig_jobs  = score_job_postings(_job_count)
    sig_news  = score_portfolio_news(
        len(c.serper_property_management.organic),
        bool(c.serper_property_management.knowledge_graph_title),
    )
    sig_tech  = score_tech_stack(c.tech_stack)
    sig_emp   = score_employee_count(c.linkedin_employee_count)
    sig_age   = score_company_age(c.founded_year)

    # Person signals
    sig_seniority = score_seniority(p.seniority)
    sig_dept      = score_department_function(p.department)
    sig_email     = score_corporate_email(p.is_corporate_email)

    # Bonus signals — fire when data available; 0 when absent (no redistribution needed)
    sig_portfolio_size   = score_portfolio_size(c.portfolio_size)
    sig_social_presence  = score_social_presence(c.social_platform_count)

    market_raw = (
        sig_renter_units * POINTS_RENTER_UNITS
        + sig_renter_rate  * POINTS_RENTER_RATE
        + sig_median_rent  * POINTS_MEDIAN_RENT
        + sig_pop_growth   * POINTS_POPULATION_GROWTH
        + sig_econ         * POINTS_ECONOMIC_MOMENTUM
    )
    company_raw = (
        sig_jobs  * POINTS_JOB_POSTINGS
        + sig_news  * POINTS_PORTFOLIO_NEWS
        + sig_tech  * POINTS_TECH_STACK
        + sig_emp   * POINTS_EMPLOYEE_COUNT
        + sig_age   * POINTS_COMPANY_AGE
    )
    person_raw = (
        sig_seniority * POINTS_SENIORITY
        + sig_dept      * POINTS_DEPARTMENT_FUNCTION
        + sig_email     * POINTS_CORPORATE_EMAIL
    )
    bonus_raw = (
        sig_portfolio_size  * POINTS_PORTFOLIO_SIZE
        + sig_social_presence * POINTS_SOCIAL_PRESENCE
    )

    overall = round(market_raw + company_raw + person_raw + bonus_raw, 2)
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
        portfolio_size=sig_portfolio_size,
        social_presence=sig_social_presence,
        market_score=round(market_raw / _MARKET_MAX * 100, 2),
        company_score=round(company_raw / _COMPANY_MAX * 100, 2),
        person_score=round(person_raw / _PERSON_MAX * 100, 2),
    )
    logger.info(
        "scored lead: %.1f/100 %s — %s, %s",
        overall, tier, lead.raw.company, lead.raw.city,
    )
    return overall, tier, breakdown
