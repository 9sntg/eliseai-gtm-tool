"""Application settings and scoring point constants.

Scoring model: additive. Each signal contributes 0–N points when it fires,
0 when data is absent. No redistribution — missing signals simply don't score.
Baseline maximum (15 core signals at 1.0) = 119 pts.
Building Fit bonus signals (up to +20 pts) can push the score above 119.
Thresholds and point values marked # calibrate are provisional — revisit after
more lead runs.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict

# --- Score tier boundaries (absolute point thresholds) ---
TIER_LOW_MAX_SCORE: int = 40
TIER_MEDIUM_MAX_SCORE: int = 70

# --- Market Fit point values (baseline total = 38 pts) ---
POINTS_RENTER_UNITS: float = 15.0
POINTS_RENTER_RATE: float = 8.0
POINTS_MEDIAN_RENT: float = 5.0
POINTS_POPULATION_GROWTH: float = 5.0
POINTS_ECONOMIC_MOMENTUM: float = 5.0

# --- Company Fit point values (baseline total = 60 pts) ---
POINTS_PORTFOLIO_NEWS: float = 8.0
POINTS_TECH_STACK: float = 8.0
POINTS_EMPLOYEE_COUNT: float = 8.0
POINTS_COMPANY_AGE: float = 5.0
POINTS_PORTFOLIO_SIZE: float = 6.0        # calibrate after more runs
POINTS_SOCIAL_PRESENCE: float = 5.0      # calibrate after more runs
POINTS_YELP_COMPANY_RATING: float = 6.0  # rating vs. local market avg
POINTS_GOOGLE_COMPANY_RATING: float = 4.0  # independent Google rating signal (inverted)
POINTS_COMPANY_PAIN_THEMES: float = 5.0    # count of documented pain themes (Yelp + Serper)
POINTS_COMPETITOR_RANK: float = 5.0        # % of Yelp competitors rating higher

# --- Person Fit point values (baseline total = 21 pts) ---
POINTS_SENIORITY: float = 10.0
POINTS_DEPARTMENT_FUNCTION: float = 7.0
POINTS_CORPORATE_EMAIL: float = 4.0

# --- Building Fit point values (bonus; fire when building data available) ---
POINTS_BUILDING_RATING: float = 8.0        # inverted: low rating = strong pain signal
POINTS_BUILDING_REVIEWS: float = 4.0       # review volume = active, addressable building
POINTS_BUILDING_PRICE_TIER: float = 4.0    # higher tier = premium tenants, more at stake
POINTS_BUILDING_PAIN_THEMES: float = 4.0   # count of building-level pain themes

# Baseline max = 38 + 60 + 21 = 119 pts
BASELINE_MAX_SCORE: float = (
    POINTS_RENTER_UNITS + POINTS_RENTER_RATE + POINTS_MEDIAN_RENT
    + POINTS_POPULATION_GROWTH + POINTS_ECONOMIC_MOMENTUM
    + POINTS_PORTFOLIO_NEWS + POINTS_TECH_STACK
    + POINTS_EMPLOYEE_COUNT + POINTS_COMPANY_AGE
    + POINTS_PORTFOLIO_SIZE + POINTS_SOCIAL_PRESENCE + POINTS_YELP_COMPANY_RATING
    + POINTS_GOOGLE_COMPANY_RATING + POINTS_COMPANY_PAIN_THEMES + POINTS_COMPETITOR_RANK
    + POINTS_SENIORITY + POINTS_DEPARTMENT_FUNCTION + POINTS_CORPORATE_EMAIL
)

assert abs(BASELINE_MAX_SCORE - 119.0) < 1e-6, (
    f"Baseline point values must sum to 119, got {BASELINE_MAX_SCORE}"
)


class Settings(BaseSettings):
    """Loads configuration from environment / `.env`."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    serper_api_key: str | None = None
    pdl_api_key: str | None = None
    anthropic_api_key: str | None = None
    builtwith_api_key: str | None = None
    census_api_key: str | None = None
    yelp_api_key: str | None = None


settings = Settings()
