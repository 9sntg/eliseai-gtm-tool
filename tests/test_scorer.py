"""Scorer tests — signal boundaries, point constant validation, and additive model."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

import gtm.config as cfg
from gtm.models import CompanyData, EnrichedLead, MarketData, PersonData, RawLead
from gtm.models.company import SerperOrganicItem, SerperSearchBucket
from gtm.scoring.scorer import compute_tier, generate_insights, score_lead
from gtm.scoring.scorer_signals import (
    BUILDING_REVIEWS_HIGH,
    BUILDING_REVIEWS_LOW,
    BUILDING_REVIEWS_MID,
    COMPETITOR_RANK_BELOW_AVERAGE,
    COMPETITOR_RANK_BELOW_MEDIAN,
    COMPETITOR_RANK_BOTTOM_QUARTER,
    EMPLOYEE_MIN,
    GOOGLE_RATING_HIGH,
    GOOGLE_RATING_LOW,
    GOOGLE_RATING_MID,
    GOOGLE_RATING_VERY_LOW,
    MEDIAN_RENT_HIGH,
    MEDIAN_RENT_LOW,
    MEDIAN_RENT_MID,
    PAIN_THEMES_HIGH,
    PAIN_THEMES_MID,
    PORTFOLIO_SIZE_LARGE,
    PORTFOLIO_SIZE_MID,
    PORTFOLIO_SIZE_SMALL,
    RENTER_UNITS_HIGH,
    RENTER_UNITS_LOW,
    RENTER_UNITS_MAX,
    RENTER_UNITS_MID,
    SOCIAL_PLATFORMS_HIGH,
    SOCIAL_PLATFORMS_MID,
    score_building_pain_themes,
    score_building_price_tier,
    score_building_rating,
    score_building_reviews,
    score_company_age,
    score_company_pain_themes,
    score_competitor_rank,
    score_corporate_email,
    score_department_function,
    score_economic_momentum,
    score_employee_count,
    score_google_company_rating,
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
    score_yelp_company_rating,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_lead(**kwargs) -> EnrichedLead:
    """Build a minimal EnrichedLead for scoring tests."""
    return EnrichedLead(
        raw=RawLead(name="Jane", email="jane@corp.com", company="Corp", city="Austin", state="TX"),
        **kwargs,
    )


def _inc_date(years_ago: float) -> str:
    """Return an ISO date string approximately `years_ago` years in the past."""
    return (date.today() - timedelta(days=int(years_ago * 365.25))).isoformat()


# ---------------------------------------------------------------------------
# Point constant validation
# ---------------------------------------------------------------------------

def test_baseline_points_sum_to_131():
    total = (
        cfg.POINTS_RENTER_UNITS + cfg.POINTS_RENTER_RATE + cfg.POINTS_MEDIAN_RENT
        + cfg.POINTS_POPULATION_GROWTH + cfg.POINTS_ECONOMIC_MOMENTUM
        + cfg.POINTS_JOB_POSTINGS + cfg.POINTS_PORTFOLIO_NEWS + cfg.POINTS_TECH_STACK
        + cfg.POINTS_EMPLOYEE_COUNT + cfg.POINTS_COMPANY_AGE
        + cfg.POINTS_PORTFOLIO_SIZE + cfg.POINTS_SOCIAL_PRESENCE + cfg.POINTS_YELP_COMPANY_RATING
        + cfg.POINTS_GOOGLE_COMPANY_RATING + cfg.POINTS_COMPANY_PAIN_THEMES + cfg.POINTS_COMPETITOR_RANK
        + cfg.POINTS_SENIORITY + cfg.POINTS_DEPARTMENT_FUNCTION + cfg.POINTS_CORPORATE_EMAIL
    )
    assert abs(total - 131.0) < 1e-6


# ---------------------------------------------------------------------------
# Market signal boundaries
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("units,expected", [
    (None, 0.0),
    (0, 0.0),
    (RENTER_UNITS_LOW - 1, 0.0),
    (RENTER_UNITS_LOW, 0.25),
    (RENTER_UNITS_MID - 1, 0.25),
    (RENTER_UNITS_MID, 0.5),
    (RENTER_UNITS_HIGH - 1, 0.5),
    (RENTER_UNITS_HIGH, 0.75),
    (RENTER_UNITS_MAX - 1, 0.75),
    (RENTER_UNITS_MAX, 1.0),
    (RENTER_UNITS_MAX + 1, 1.0),
])
def test_score_renter_units(units, expected):
    assert score_renter_units(units) == pytest.approx(expected)


@pytest.mark.parametrize("rate,expected", [
    (None, 0.0),
    (0.0, 0.25),
    (0.34, 0.25),
    (0.35, 0.5),
    (0.45, 0.75),
    (0.55, 1.0),
    (0.70, 1.0),
])
def test_score_renter_rate(rate, expected):
    assert score_renter_rate(rate) == pytest.approx(expected)


@pytest.mark.parametrize("rent,expected", [
    (None, 0.0),
    (500, 0.1),
    (MEDIAN_RENT_LOW - 1, 0.1),
    (MEDIAN_RENT_LOW, 0.4),
    (MEDIAN_RENT_MID - 1, 0.4),
    (MEDIAN_RENT_MID, 0.75),
    (MEDIAN_RENT_HIGH - 1, 0.75),
    (MEDIAN_RENT_HIGH, 1.0),
    (3000, 1.0),
])
def test_score_median_rent(rent, expected):
    assert score_median_rent(rent) == pytest.approx(expected)


@pytest.mark.parametrize("growth,expected", [
    (None, 0.0),
    (-0.05, 0.1),
    (0.0, 0.5),
    (0.01, 0.5),
    (0.02, 0.5),
    (0.021, 1.0),
    (0.05, 1.0),
])
def test_score_population_growth(growth, expected):
    assert score_population_growth(growth) == pytest.approx(expected)


def test_score_economic_momentum_delegates():
    assert score_economic_momentum(0.03) == score_population_growth(0.03)
    assert score_economic_momentum(None) == 0.0


# ---------------------------------------------------------------------------
# Company signal boundaries
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("count,expected", [
    (0, 0.0),
    (1, 0.3),
    (2, 0.3),
    (3, 0.6),
    (4, 0.6),
    (5, 1.0),
    (10, 1.0),
])
def test_score_job_postings(count, expected):
    assert score_job_postings(count) == pytest.approx(expected)


@pytest.mark.parametrize("organic,has_kg,expected", [
    (0, False, 0.0),
    (1, False, 0.5),
    (3, False, 0.75),
    (0, True, 0.75),
    (1, True, 0.75),
    (3, True, 1.0),
    (5, True, 1.0),
])
def test_score_portfolio_news(organic, has_kg, expected):
    assert score_portfolio_news(organic, has_kg) == pytest.approx(expected)


@pytest.mark.parametrize("stack,expected", [
    ([], 0.0),
    (["Salesforce", "HubSpot"], 0.5),
    (["Yardi Voyager"], 1.0),
    (["RealPage"], 1.0),
    (["Entrata"], 1.0),
    (["MRI Software", "Google Analytics"], 1.0),
])
def test_score_tech_stack(stack, expected):
    assert score_tech_stack(stack) == pytest.approx(expected)


@pytest.mark.parametrize("count,expected", [
    (None,          0.0),
    (5,             0.3),
    (19,            0.3),
    (EMPLOYEE_MIN,  1.0),
    (100,           1.0),
    (5000,          1.0),
])
def test_score_employee_count(count, expected):
    assert score_employee_count(count) == pytest.approx(expected)


def test_score_company_age_mature():
    assert score_company_age(date.today().year - 15) == pytest.approx(1.0)


def test_score_company_age_growing():
    assert score_company_age(date.today().year - 7) == pytest.approx(0.6)


def test_score_company_age_young():
    assert score_company_age(date.today().year - 2) == pytest.approx(0.2)


def test_score_company_age_none():
    assert score_company_age(None) == 0.0


# ---------------------------------------------------------------------------
# Person signal boundaries
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("seniority,expected", [
    (None, 0.1),
    ("unknown_level", 0.1),
    ("senior", 0.30),
    ("manager", 0.50),
    ("director", 0.70),
    ("vp", 0.85),
    ("c_suite", 1.0),
    ("owner", 1.0),
    ("partner", 1.0),
])
def test_score_seniority(seniority, expected):
    assert score_seniority(seniority) == pytest.approx(expected)


@pytest.mark.parametrize("dept,expected", [
    (None, 0.1),
    ("marketing", 0.1),
    ("finance", 0.50),
    ("accounting", 0.50),
    ("leasing", 0.80),
    ("real_estate", 0.80),
    ("operations", 1.0),
    ("property_management", 1.0),
])
def test_score_department_function(dept, expected):
    assert score_department_function(dept) == pytest.approx(expected)


def test_score_corporate_email_true():
    assert score_corporate_email(True) == pytest.approx(1.0)


def test_score_corporate_email_false():
    assert score_corporate_email(False) == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# New signal boundaries (Phase 11)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("rating,expected", [
    (None, 0.0),
    (GOOGLE_RATING_VERY_LOW, 1.0),
    (GOOGLE_RATING_VERY_LOW - 0.1, 1.0),
    (GOOGLE_RATING_LOW, 0.8),
    (GOOGLE_RATING_MID, 0.6),
    (GOOGLE_RATING_HIGH, 0.3),
    (4.5, 0.1),
    (5.0, 0.1),
])
def test_score_google_company_rating(rating, expected):
    assert score_google_company_rating(rating) == pytest.approx(expected)


@pytest.mark.parametrize("count,expected", [
    (0, 0.0),
    (PAIN_THEMES_MID, 0.3),
    (PAIN_THEMES_HIGH, 0.7),
    (PAIN_THEMES_HIGH + 1, 1.0),
    (5, 1.0),
])
def test_score_company_pain_themes(count, expected):
    assert score_company_pain_themes(count) == pytest.approx(expected)


@pytest.mark.parametrize("pct,expected", [
    (None, 0.0),
    (0.0, 0.1),
    (COMPETITOR_RANK_BELOW_AVERAGE, 0.4),
    (COMPETITOR_RANK_BELOW_MEDIAN, 0.7),
    (COMPETITOR_RANK_BOTTOM_QUARTER, 1.0),
    (0.9, 1.0),
])
def test_score_competitor_rank(pct, expected):
    assert score_competitor_rank(pct) == pytest.approx(expected)


@pytest.mark.parametrize("tier,expected", [
    (None, 0.0),
    ("$", 0.2),
    ("$$", 0.5),
    ("$$$", 0.75),
    ("$$$$", 1.0),
    ("?????", 0.0),
])
def test_score_building_price_tier(tier, expected):
    assert score_building_price_tier(tier) == pytest.approx(expected)


@pytest.mark.parametrize("count,expected", [
    (0, 0.0),
    (1, 0.4),
    (2, 0.7),
    (3, 1.0),
    (10, 1.0),
])
def test_score_building_pain_themes(count, expected):
    assert score_building_pain_themes(count) == pytest.approx(expected)


# ---------------------------------------------------------------------------
# score_lead integration
# ---------------------------------------------------------------------------

def test_score_lead_returns_all_components():
    lead = _make_lead()
    overall, tier, breakdown = score_lead(lead)

    assert 0.0 <= overall <= 100.0
    assert tier in ("Low", "Medium", "High")
    assert breakdown is not None
    assert 0.0 <= breakdown.market_score <= 100.0
    assert 0.0 <= breakdown.company_score <= 100.0
    assert 0.0 <= breakdown.person_score <= 100.0


def test_score_lead_all_zeros_on_empty_enrichment():
    lead = _make_lead()
    overall, tier, _ = score_lead(lead)
    # PersonData defaults: is_corporate_email=False → 0, seniority=None → 0.1
    # so score won't be exactly 0, but should be very low
    assert overall < 20.0
    assert tier == "Low"


def test_score_lead_full_enrichment_produces_high_score():
    org = SerperOrganicItem(title="X", link="https://x.com", snippet="s", position=1)
    lead = _make_lead(
        market=MarketData(
            renter_occupied_units=200_000,
            renter_rate=0.6,
            median_gross_rent=2_500,
            population_growth_yoy=0.03,
            median_income_growth_yoy=0.03,
        ),
        company=CompanyData(
            serper_property_management=SerperSearchBucket(
                query="q", organic=[org, org, org], knowledge_graph_title="BigPM"
            ),
            serper_jobs=SerperSearchBucket(query="q", organic=[org, org, org, org, org]),
            tech_stack=["Yardi Voyager"],
            linkedin_employee_count=1_500,
            founded_year=date.today().year - 15,
        ),
        person=PersonData(
            job_title="VP of Operations",
            seniority="vp",
            department="operations",
            is_corporate_email=True,
        ),
    )
    overall, tier, breakdown = score_lead(lead)
    assert overall >= 75.0
    assert tier == "High"


# ---------------------------------------------------------------------------
# Additive model — absent signals do not affect other signals
# ---------------------------------------------------------------------------

def test_tech_stack_absent_does_not_affect_other_signals():
    """Missing tech_stack contributes 0 pts but leaves all other signals unchanged."""
    org = SerperOrganicItem(title="X", link="https://x.com", snippet="s", position=1)
    pm_bucket = SerperSearchBucket(
        query="q", organic=[org, org, org], knowledge_graph_title="BigPM"
    )
    base = CompanyData(serper_property_management=pm_bucket, tech_stack=[])
    lead_no_tech = _make_lead(company=base)

    with_tech = base.model_copy(update={"tech_stack": ["Salesforce"]})
    lead_with_tech = _make_lead(company=with_tech)

    score_no_tech, _, bd_no_tech = score_lead(lead_no_tech)
    score_with_tech, _, bd_with_tech = score_lead(lead_with_tech)

    # tech_stack adds points when present — score with tech must be higher
    assert score_with_tech > score_no_tech
    # portfolio_news signal must be identical regardless of tech_stack presence
    assert bd_no_tech.portfolio_news == bd_with_tech.portfolio_news


# ---------------------------------------------------------------------------
# Tier boundaries
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("score,expected_tier", [
    (0.0, "Low"),
    (40.0, "Low"),
    (40.1, "Medium"),
    (70.0, "Medium"),
    (70.1, "High"),
    (100.0, "High"),
])
def test_compute_tier(score, expected_tier):
    assert compute_tier(score) == expected_tier


# ---------------------------------------------------------------------------
# generate_insights
# ---------------------------------------------------------------------------

def test_generate_insights_fallback_on_empty_data():
    lead = _make_lead()
    _, _, breakdown = score_lead(lead)
    bullets = generate_insights(lead, breakdown)
    assert len(bullets) >= 1
    assert any("manual research" in b for b in bullets)


# ---------------------------------------------------------------------------
# Bonus signal boundaries
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("size,expected", [
    (None, 0.0),
    (0, 0.2),
    (PORTFOLIO_SIZE_SMALL - 1, 0.2),
    (PORTFOLIO_SIZE_SMALL, 0.5),
    (PORTFOLIO_SIZE_MID - 1, 0.5),
    (PORTFOLIO_SIZE_MID, 0.75),
    (PORTFOLIO_SIZE_LARGE - 1, 0.75),
    (PORTFOLIO_SIZE_LARGE, 1.0),
    (50_000, 1.0),
])
def test_score_portfolio_size(size, expected):
    assert score_portfolio_size(size) == pytest.approx(expected)


@pytest.mark.parametrize("count,expected", [
    (0, 0.0),
    (SOCIAL_PLATFORMS_MID - 1, 0.0),
    (SOCIAL_PLATFORMS_MID, 0.5),
    (SOCIAL_PLATFORMS_HIGH - 1, 0.5),
    (SOCIAL_PLATFORMS_HIGH, 1.0),
    (5, 1.0),
])
def test_score_social_presence(count, expected):
    assert score_social_presence(count) == pytest.approx(expected)


@pytest.mark.parametrize("rating,market_avg,expected", [
    (None,  None,  0.0),
    (None,  4.0,   0.0),
    (4.0,   None,  0.0),
    (4.0,   4.0,   0.3),   # at market average
    (3.9,   4.0,   0.6),   # slightly below market
    (3.4,   4.0,   1.0),   # noticeably below market (diff >= 0.5)
    (4.5,   4.0,   0.1),   # above market
])
def test_score_yelp_company_rating(rating, market_avg, expected):
    assert score_yelp_company_rating(rating, market_avg) == pytest.approx(expected)


@pytest.mark.parametrize("rating,expected", [
    (None, 0.0),
    (2.5,  1.0),
    (3.0,  1.0),
    (3.1,  0.75),
    (3.5,  0.75),
    (3.6,  0.5),
    (4.0,  0.5),
    (4.1,  0.2),
    (5.0,  0.2),
])
def test_score_building_rating(rating, expected):
    assert score_building_rating(rating) == pytest.approx(expected)


@pytest.mark.parametrize("count,expected", [
    (None,                    0.0),
    (0,                       0.0),
    (1,                       0.25),
    (BUILDING_REVIEWS_LOW,    0.5),
    (BUILDING_REVIEWS_MID,    0.75),
    (BUILDING_REVIEWS_HIGH,   1.0),
    (200,                     1.0),
])
def test_score_building_reviews(count, expected):
    assert score_building_reviews(count) == pytest.approx(expected)


def test_bonus_signals_push_score_above_100():
    """Bonus signals can push the final score above the 100-pt baseline."""
    org = SerperOrganicItem(title="X", link="https://x.com", snippet="s", position=1)
    lead = _make_lead(
        market=MarketData(
            renter_occupied_units=200_000, renter_rate=0.6,
            median_gross_rent=2_500, population_growth_yoy=0.03,
            median_income_growth_yoy=0.03,
        ),
        company=CompanyData(
            serper_property_management=SerperSearchBucket(
                query="q", organic=[org, org, org], knowledge_graph_title="BigPM"
            ),
            serper_jobs=SerperSearchBucket(query="q", organic=[org, org, org, org, org]),
            tech_stack=["Yardi Voyager"],
            linkedin_employee_count=1_500,
            founded_year=date.today().year - 15,
            portfolio_size=PORTFOLIO_SIZE_LARGE,
            social_platform_count=SOCIAL_PLATFORMS_HIGH,
        ),
        person=PersonData(
            job_title="VP of Operations",
            seniority="vp",
            department="operations",
            is_corporate_email=True,
        ),
    )
    overall, _, breakdown = score_lead(lead)
    assert overall > 100.0
    assert breakdown.portfolio_size == pytest.approx(1.0)
    assert breakdown.social_presence == pytest.approx(1.0)


def test_generate_insights_max_five_bullets():
    org = SerperOrganicItem(title="X", link="https://x.com", snippet="s", position=1)
    lead = _make_lead(
        market=MarketData(renter_occupied_units=200_000, median_gross_rent=2_000),
        company=CompanyData(
            serper_property_management=SerperSearchBucket(
                query="q", organic=[org, org, org], knowledge_graph_title="BigPM"
            ),
            tech_stack=["Yardi Voyager"],
        ),
        person=PersonData(job_title="VP of Operations", seniority="vp", is_corporate_email=True),
    )
    _, _, breakdown = score_lead(lead)
    bullets = generate_insights(lead, breakdown)
    assert 1 <= len(bullets) <= 5
