"""Signal metadata and per-tier reason sentences.

Used by both the pipeline writer (assessment.json) and the dashboard signal table.

File exceeds the 200-line limit. The bulk is the _REASONS dict: 23 signals × 3 reason
strings each. Splitting this dict across files would gain nothing — all 23 signals belong
to a single coherent concept. Accepted as-is.
"""

from __future__ import annotations

from gtm.config import (
    POINTS_BUILDING_PAIN_THEMES,
    POINTS_BUILDING_PRICE_TIER,
    POINTS_BUILDING_RATING,
    POINTS_BUILDING_REVIEWS,
    POINTS_COMPANY_AGE,
    POINTS_COMPANY_PAIN_THEMES,
    POINTS_COMPETITOR_RANK,
    POINTS_CORPORATE_EMAIL,
    POINTS_DEPARTMENT_FUNCTION,
    POINTS_ECONOMIC_MOMENTUM,
    POINTS_EMPLOYEE_COUNT,
    POINTS_GOOGLE_COMPANY_RATING,
    POINTS_MEDIAN_RENT,
    POINTS_POPULATION_GROWTH,
    POINTS_PORTFOLIO_NEWS,
    POINTS_PORTFOLIO_SIZE,
    POINTS_RENTER_RATE,
    POINTS_RENTER_UNITS,
    POINTS_SENIORITY,
    POINTS_SOCIAL_PRESENCE,
    POINTS_TECH_STACK,
    POINTS_YELP_COMPANY_RATING,
)

# (key, display_name, category) — defines signal order throughout the app
SIGNAL_META: list[tuple[str, str, str]] = [
    ("renter_units",          "Renter-Occupied Units",      "Market"),
    ("renter_rate",           "Renter Rate",                "Market"),
    ("median_rent",           "Median Gross Rent",          "Market"),
    ("population_growth",     "Population Growth YoY",      "Market"),
    ("economic_momentum",     "Economic Momentum",          "Market"),
    ("portfolio_news",        "Portfolio / Web Presence",   "Company"),
    ("tech_stack",            "Tech Stack",                 "Company"),
    ("employee_count",        "Employee Count",             "Company"),
    ("company_age",           "Company Age",                "Company"),
    ("portfolio_size",        "Portfolio Size",             "Company"),
    ("social_presence",       "Social Media Presence",      "Company"),
    ("yelp_company_rating",   "Yelp Rating vs. Market",     "Company"),
    ("google_company_rating", "Google Rating",              "Company"),
    ("company_pain_themes",   "Resident Pain Themes",       "Company"),
    ("competitor_rank",       "Competitor Rank (Yelp)",     "Company"),
    ("seniority",             "Contact Seniority",          "Person"),
    ("department_function",   "Department / Function",      "Person"),
    ("corporate_email",       "Corporate Email",            "Person"),
    ("building_rating",       "Building Yelp Rating",       "Building"),
    ("building_reviews",      "Building Review Volume",     "Building"),
    ("building_price_tier",   "Building Price Tier",        "Building"),
    ("building_pain_themes",  "Building Pain Themes",       "Building"),
]

SIGNAL_POINTS: dict[str, float] = {
    "renter_units":          POINTS_RENTER_UNITS,
    "renter_rate":           POINTS_RENTER_RATE,
    "median_rent":           POINTS_MEDIAN_RENT,
    "population_growth":     POINTS_POPULATION_GROWTH,
    "economic_momentum":     POINTS_ECONOMIC_MOMENTUM,
    "portfolio_news":        POINTS_PORTFOLIO_NEWS,
    "tech_stack":            POINTS_TECH_STACK,
    "employee_count":        POINTS_EMPLOYEE_COUNT,
    "company_age":           POINTS_COMPANY_AGE,
    "portfolio_size":        POINTS_PORTFOLIO_SIZE,
    "social_presence":       POINTS_SOCIAL_PRESENCE,
    "yelp_company_rating":   POINTS_YELP_COMPANY_RATING,
    "google_company_rating": POINTS_GOOGLE_COMPANY_RATING,
    "company_pain_themes":   POINTS_COMPANY_PAIN_THEMES,
    "competitor_rank":       POINTS_COMPETITOR_RANK,
    "seniority":             POINTS_SENIORITY,
    "department_function":   POINTS_DEPARTMENT_FUNCTION,
    "corporate_email":       POINTS_CORPORATE_EMAIL,
    "building_rating":       POINTS_BUILDING_RATING,
    "building_reviews":      POINTS_BUILDING_REVIEWS,
    "building_price_tier":   POINTS_BUILDING_PRICE_TIER,
    "building_pain_themes":  POINTS_BUILDING_PAIN_THEMES,
}

# Per-signal reasons: (strong ≥0.75, partial 0.1–0.74, none/no-data <0.1)
_REASONS: dict[str, tuple[str, str, str]] = {
    "renter_units": (
        "Large rental market with high unit count. Top threshold met for full points.",
        "Moderate rental market by unit count. Partial score based on size tier.",
        "Insufficient Census data or unit count is below the minimum threshold.",
    ),
    "renter_rate": (
        "High share of housing is renter-occupied. Strong property management market.",
        "Moderate renter rate in this city. Some PM opportunity present.",
        "Low renter rate or no Census data available for this city.",
    ),
    "median_rent": (
        "Above-average median gross rent. High-value market with strong PM opportunity.",
        "Median rent falls in the mid range, representing an average US rental market.",
        "Below-average median rent or no Census data returned for this city.",
    ),
    "population_growth": (
        "Fast-growing city with strong year-over-year population increase. Rising renter demand.",
        "Stable population growth. Steady market conditions.",
        "Flat or declining population. Market may face lower future demand.",
    ),
    "economic_momentum": (
        "Strong year-over-year income growth. Healthy economic trajectory for the city.",
        "Moderate income growth. Stable market conditions present.",
        "Flat or declining income growth. Weaker economic signal for this market.",
    ),
    "portfolio_news": (
        "Strong web presence with a verified Google Knowledge Graph entry. Established brand.",
        "Some web presence found. Company has online visibility.",
        "Minimal web presence. Limited search results returned for this company.",
    ),
    "tech_stack": (
        "Legacy property management software detected. Strong replacement pitch opportunity.",
        "Some PM-related technology detected in the tech stack.",
        "No tech stack data. BuiltWith key not configured or no tools detected.",
    ),
    "employee_count": (
        "Company is above the minimum employee threshold. Qualifies as a target account.",
        "Company is above the minimum threshold and qualifies as a target.",
        "Company is below the minimum headcount threshold or LinkedIn data is unavailable.",
    ),
    "company_age": (
        "Established company with significant operating history. Likely carries legacy tech debt.",
        "Mid-stage company that may be open to growth tools and automation.",
        "Early-stage company or no founding year data is available.",
    ),
    "portfolio_size": (
        "Large portfolio detected. Significant automation opportunity at scale.",
        "Moderate portfolio size. Meaningful automation opportunity present.",
        "No portfolio size data could be extracted.",
    ),
    "social_presence": (
        "Active on multiple social platforms. Engaged digital presence.",
        "Some social media presence detected.",
        "No social media platforms detected for this company.",
    ),
    "yelp_company_rating": (
        "Yelp rating is notably below the local market average. Strong resident pain signal.",
        "Yelp rating is near or slightly below the market average.",
        "No Yelp data available or rating is at or above the market average.",
    ),
    "google_company_rating": (
        "Low Google star rating indicating resident dissatisfaction. Pain signal for the pitch.",
        "Below-average Google rating. Moderate resident dissatisfaction signal.",
        "No Google rating data available or rating is above the scoring threshold.",
    ),
    "company_pain_themes": (
        "Multiple resident complaint themes identified from reviews. Clear pain points for pitch.",
        "Some resident complaint themes identified from Yelp or web reviews.",
        "No complaint themes were extracted from reviews.",
    ),
    "competitor_rank": (
        "Most local competitors are rated higher on Yelp. Strong relative pain signal.",
        "Some competitors are rated higher on Yelp. Moderate competitive gap.",
        "No competitor data available or company ranks well relative to competitors.",
    ),
    "seniority": (
        "Contact is at C-suite, VP, Director, or Owner level. Budget authority confirmed.",
        "Contact has seniority that influences purchasing decisions.",
        "No seniority data from PDL or contact is below the decision-maker threshold.",
    ),
    "department_function": (
        "Contact works directly in property management. Direct decision-maker for this product.",
        "Contact is in a related function with influence over PM decisions.",
        "No department data available or contact is outside the property management function.",
    ),
    "corporate_email": (
        "Email uses a verified company domain. Contact legitimacy confirmed.",
        "Email domain partially matches the company.",
        "Personal email detected or no email domain data is available.",
    ),
    "building_rating": (
        "Building Yelp rating is low. Residents are unhappy, creating a strong pitch angle.",
        "Building has a below-average Yelp rating. Some resident dissatisfaction present.",
        "No building Yelp data available or the building is well-rated.",
    ),
    "building_reviews": (
        "High review volume for this building. Signal is statistically reliable.",
        "Moderate review volume present for this building.",
        "Low review count or no building Yelp data is available.",
    ),
    "building_price_tier": (
        "Mid or high price tier detected. Quality-sensitive tenant base present.",
        "Building price tier data is available and above the base tier.",
        "No price tier data from Yelp or the building is at the budget tier.",
    ),
    "building_pain_themes": (
        "Multiple complaint themes found in building-specific reviews.",
        "Some complaint themes found for this specific building.",
        "No building-level complaint themes were extracted from reviews.",
    ),
}


def signal_reason(key: str, val: float) -> str:
    """Return a full-sentence reason explaining why the signal earned its score."""
    tiers = _REASONS.get(key)
    if tiers is None:
        return f"Signal scored at {val * 100:.0f}% of maximum." if val > 0 else "Signal did not fire."
    if val >= 0.75:
        return tiers[0]
    if val > 0.1:
        return tiers[1]
    return tiers[2]
