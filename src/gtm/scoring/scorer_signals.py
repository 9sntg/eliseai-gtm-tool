"""Signal evaluation functions and threshold constants for the lead scorer.

Each function maps a single enrichment field to a 0.0–1.0 value.
A None input always returns 0.0 — missing data scores zero; the enrichment
module already logged the warning when the field was unavailable.

File is ~369 lines — over the 200-line limit. All content is pure threshold
constants + one-purpose signal functions. Splitting into e.g. market/company/
person modules would add 3 import paths for no behavioural gain. Accepted as-is.
"""

from __future__ import annotations

from datetime import date

# --- Threshold constants — all boundary values live here, never inline in logic ---

# Market signals
RENTER_UNITS_LOW: int = 10_000
RENTER_UNITS_MID: int = 50_000
RENTER_UNITS_HIGH: int = 100_000
RENTER_UNITS_MAX: int = 200_000

RENTER_RATE_LOW: float = 0.35
RENTER_RATE_MID: float = 0.45
RENTER_RATE_HIGH: float = 0.55

MEDIAN_RENT_LOW: int = 1_000
MEDIAN_RENT_MID: int = 1_500
MEDIAN_RENT_HIGH: int = 2_000

GROWTH_FLAT: float = 0.0
GROWTH_HIGH: float = 0.02

# Company signals
JOB_POSTINGS_MID: int = 3
JOB_POSTINGS_HIGH: int = 5

EMPLOYEE_MIN: int = 20  # below this = solo/micro operator, EliseAI ROI marginal

COMPANY_AGE_YOUNG: int = 5
COMPANY_AGE_MATURE: int = 10

# Portfolio size (units/communities under management) — calibrate after more runs
PORTFOLIO_SIZE_SMALL: int = 100
PORTFOLIO_SIZE_MID: int = 1_000
PORTFOLIO_SIZE_LARGE: int = 10_000

# Social media presence (distinct non-LinkedIn platforms detected in Serper results)
SOCIAL_PLATFORMS_MID: int = 1
SOCIAL_PLATFORMS_HIGH: int = 2

# PM platforms are replacement targets; any match scores full marks.
PM_TECH: frozenset[str] = frozenset({"yardi", "realpage", "entrata", "mri", "appfolio"})

# Person signals — scored by lookup; anything not in the map scores 0.1
SENIORITY_SCORE: dict[str, float] = {
    "c_suite": 1.0, "owner": 1.0, "partner": 1.0,
    "vp": 0.85, "director": 0.70,
    "manager": 0.50, "senior": 0.30,
}
DEPARTMENT_SCORE: dict[str, float] = {
    "operations": 1.0, "property_management": 1.0,
    "real_estate": 0.80, "leasing": 0.80,
    "finance": 0.50, "accounting": 0.50,
}

# --- Market signal functions ---

def score_renter_units(units: int | None) -> float:
    """Score renter-occupied housing units (market size signal)."""
    if units is None:
        return 0.0
    if units >= RENTER_UNITS_MAX:
        return 1.0
    if units >= RENTER_UNITS_HIGH:
        return 0.75
    if units >= RENTER_UNITS_MID:
        return 0.5
    if units >= RENTER_UNITS_LOW:
        return 0.25
    return 0.0


def score_renter_rate(rate: float | None) -> float:
    """Score renter-occupancy rate (share of housing that is renter-occupied)."""
    if rate is None:
        return 0.0
    if rate >= RENTER_RATE_HIGH:
        return 1.0
    if rate >= RENTER_RATE_MID:
        return 0.75
    if rate >= RENTER_RATE_LOW:
        return 0.5
    return 0.25


def score_median_rent(rent: int | None) -> float:
    """Score median gross rent (higher rent = higher-value market for EliseAI)."""
    if rent is None:
        return 0.0
    if rent >= MEDIAN_RENT_HIGH:
        return 1.0
    if rent >= MEDIAN_RENT_MID:
        return 0.75
    if rent >= MEDIAN_RENT_LOW:
        return 0.4
    return 0.1


def score_population_growth(growth: float | None) -> float:
    """Score YoY population growth fraction (positive growth = rising renter demand)."""
    if growth is None:
        return 0.0
    if growth > GROWTH_HIGH:
        return 1.0
    if growth >= GROWTH_FLAT:
        return 0.5
    return 0.1


def score_economic_momentum(growth: float | None) -> float:
    """Score YoY income growth (proxy for improving economic conditions)."""
    return score_population_growth(growth)


# --- Company signal functions ---

def score_job_postings(organic_count: int) -> float:
    """Score leasing job posting count (active hiring = growth mode = likely buyer)."""
    if organic_count >= JOB_POSTINGS_HIGH:
        return 1.0
    if organic_count >= JOB_POSTINGS_MID:
        return 0.6
    if organic_count >= 1:
        return 0.3
    return 0.0


def score_portfolio_news(organic_count: int, has_knowledge_graph: bool) -> float:
    """Score company web presence from Serper (knowledge graph + organic results)."""
    if has_knowledge_graph and organic_count >= 3:
        return 1.0
    if has_knowledge_graph or organic_count >= 3:
        return 0.75
    if organic_count >= 1:
        return 0.5
    return 0.0


def score_tech_stack(tech_stack: list[str]) -> float:
    """Score tech stack: PM-specific tools = replacement pitch; any tech = established."""
    if not tech_stack:
        return 0.0
    lower_stack = [t.lower() for t in tech_stack]
    if any(pm in name for pm in PM_TECH for name in lower_stack):
        return 1.0
    return 0.5


def score_employee_count(count: int | None) -> float:
    """Score employee headcount. Any company past solo-operator scale scores full marks."""
    if count is None:
        return 0.0
    if count >= EMPLOYEE_MIN:
        return 1.0
    return 0.3


def score_company_age(founded_year: int | None) -> float:
    """Score company age by founding year; older = more legacy tech debt = stronger pitch."""
    if founded_year is None:
        return 0.0
    age_years = date.today().year - founded_year
    if age_years > COMPANY_AGE_MATURE:
        return 1.0
    if age_years >= COMPANY_AGE_YOUNG:
        return 0.6
    return 0.2


def score_portfolio_size(size: int | None) -> float:
    """Score managed portfolio size (units/communities); larger = more automation ROI."""
    if size is None:
        return 0.0
    if size >= PORTFOLIO_SIZE_LARGE:
        return 1.0
    if size >= PORTFOLIO_SIZE_MID:
        return 0.75
    if size >= PORTFOLIO_SIZE_SMALL:
        return 0.5
    return 0.2


def score_social_presence(platform_count: int) -> float:
    """Score distinct social media platforms detected in Serper results."""
    if platform_count >= SOCIAL_PLATFORMS_HIGH:
        return 1.0
    if platform_count >= SOCIAL_PLATFORMS_MID:
        return 0.5
    return 0.0


# --- Google company rating signal (independent of Yelp) ---
GOOGLE_RATING_VERY_LOW: float = 2.5
GOOGLE_RATING_LOW: float = 3.0
GOOGLE_RATING_MID: float = 3.5
GOOGLE_RATING_HIGH: float = 4.0

# --- Company pain theme density ---
PAIN_THEMES_MID: int = 1
PAIN_THEMES_HIGH: int = 2

# --- Competitor rank ---
COMPETITOR_RANK_BOTTOM_QUARTER: float = 0.75
COMPETITOR_RANK_BELOW_MEDIAN: float = 0.50
COMPETITOR_RANK_BELOW_AVERAGE: float = 0.25

# --- Building price tier ---
PRICE_TIER_MAP: dict[str, float] = {"$": 0.2, "$$": 0.5, "$$$": 0.75, "$$$$": 1.0}

# --- Building pain theme density ---
BUILDING_PAIN_THEMES_MID: int = 1
BUILDING_PAIN_THEMES_HIGH: int = 2


def score_google_company_rating(rating: float | None) -> float:
    """Score company Google rating — inverted, low rating = resident pain = strong pitch."""
    if rating is None:
        return 0.0
    if rating <= GOOGLE_RATING_VERY_LOW:
        return 1.0
    if rating <= GOOGLE_RATING_LOW:
        return 0.8
    if rating <= GOOGLE_RATING_MID:
        return 0.6
    if rating <= GOOGLE_RATING_HIGH:
        return 0.3
    return 0.1


def score_company_pain_themes(theme_count: int) -> float:
    """Score company pain theme density from Yelp + Serper snippets.

    More documented themes = more systematic management failures = stronger pitch.
    """
    if theme_count >= PAIN_THEMES_HIGH + 1:
        return 1.0
    if theme_count >= PAIN_THEMES_HIGH:
        return 0.7
    if theme_count >= PAIN_THEMES_MID:
        return 0.3
    return 0.0


def score_competitor_rank(pct_above: float | None) -> float:
    """Score % of Yelp comparables rating higher than this company.

    High pct_above = bottom of local market = most compelling pitch.
    """
    if pct_above is None:
        return 0.0
    if pct_above >= COMPETITOR_RANK_BOTTOM_QUARTER:
        return 1.0
    if pct_above >= COMPETITOR_RANK_BELOW_MEDIAN:
        return 0.7
    if pct_above >= COMPETITOR_RANK_BELOW_AVERAGE:
        return 0.4
    return 0.1


def score_building_price_tier(tier: str | None) -> float:
    """Score Yelp building price tier: higher tier = premium tenants with higher expectations."""
    if tier is None:
        return 0.0
    return PRICE_TIER_MAP.get(tier, 0.0)


def score_building_pain_themes(theme_count: int) -> float:
    """Score building pain theme density — building-specific tenant complaints."""
    if theme_count >= BUILDING_PAIN_THEMES_HIGH + 1:
        return 1.0
    if theme_count >= BUILDING_PAIN_THEMES_HIGH:
        return 0.7
    if theme_count >= BUILDING_PAIN_THEMES_MID:
        return 0.4
    return 0.0


# --- Yelp company signal ---

YELP_RATING_BELOW_MARKET: float = 0.5   # below market_avg by this much → max score

def score_yelp_company_rating(rating: float | None, market_avg: float | None) -> float:
    """Score company Yelp rating relative to local market average.

    A below-average rating signals resident dissatisfaction — a direct EliseAI pitch opportunity.
    None → 0.0 (company not on Yelp; no signal either way).
    """
    if rating is None or market_avg is None:
        return 0.0
    diff = market_avg - rating  # positive = below market
    if diff >= YELP_RATING_BELOW_MARKET:
        return 1.0  # noticeably below market — strong pain signal
    if diff > 0:
        return 0.6  # below market
    if diff == 0:
        return 0.3  # at market average
    return 0.1      # above market average (still valid target, less pain)


# --- Building signal functions ---

BUILDING_RATING_STRONG_PAIN: float = 3.0
BUILDING_RATING_MODERATE_PAIN: float = 3.5
BUILDING_RATING_MILD_PAIN: float = 4.0

BUILDING_REVIEWS_HIGH: int = 50
BUILDING_REVIEWS_MID: int = 20
BUILDING_REVIEWS_LOW: int = 5


def score_building_rating(rating: float | None) -> float:
    """Score building Yelp rating — inverted, low rating = resident pain = strong pitch."""
    if rating is None:
        return 0.0
    if rating <= BUILDING_RATING_STRONG_PAIN:
        return 1.0
    if rating <= BUILDING_RATING_MODERATE_PAIN:
        return 0.75
    if rating <= BUILDING_RATING_MILD_PAIN:
        return 0.5
    return 0.2


def score_building_reviews(review_count: int | None) -> float:
    """Score building review volume — more reviews = more resident activity = more automation need."""
    if review_count is None:
        return 0.0
    if review_count >= BUILDING_REVIEWS_HIGH:
        return 1.0
    if review_count >= BUILDING_REVIEWS_MID:
        return 0.75
    if review_count >= BUILDING_REVIEWS_LOW:
        return 0.5
    if review_count >= 1:
        return 0.25
    return 0.0


# --- Person signal functions ---

def score_seniority(seniority: str | None) -> float:
    """Score PDL seniority level (c_suite/vp/director have budget authority)."""
    if seniority is None:
        return 0.0
    return SENIORITY_SCORE.get(seniority.lower(), 0.1)


def score_department_function(department: str | None) -> float:
    """Score PDL department/function (operations and PM are the primary EliseAI buyers)."""
    if department is None:
        return 0.0
    return DEPARTMENT_SCORE.get(department.lower(), 0.1)


def score_corporate_email(is_corporate: bool) -> float:
    """Score email domain type (corporate = professional contact at established org)."""
    return 1.0 if is_corporate else 0.0
