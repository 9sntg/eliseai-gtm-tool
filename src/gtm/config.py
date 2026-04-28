"""Application settings and scoring point constants.

Scoring model: additive. Each signal contributes 0–N points when it fires,
0 when data is absent. No redistribution — missing signals simply don't score.
Baseline maximum (13 core signals at 1.0) = 100 pts.
Bonus signals (portfolio_size, social_presence) can push the score above 100.
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

# --- Company Fit point values (baseline total = 41 pts) ---
POINTS_JOB_POSTINGS: float = 12.0
POINTS_PORTFOLIO_NEWS: float = 8.0
POINTS_TECH_STACK: float = 8.0
POINTS_EMPLOYEE_COUNT: float = 8.0
POINTS_COMPANY_AGE: float = 5.0

# --- Person Fit point values (baseline total = 21 pts) ---
POINTS_SENIORITY: float = 10.0
POINTS_DEPARTMENT_FUNCTION: float = 7.0
POINTS_CORPORATE_EMAIL: float = 4.0

# --- Bonus signal point values (fire when data available; 0 when absent) ---
# These sit outside the 100-pt baseline so their absence never penalises a lead.
POINTS_PORTFOLIO_SIZE: float = 6.0    # calibrate after more runs
POINTS_SOCIAL_PRESENCE: float = 5.0  # calibrate after more runs

# Baseline max = 38 + 41 + 21 = 100 pts
BASELINE_MAX_SCORE: float = (
    POINTS_RENTER_UNITS + POINTS_RENTER_RATE + POINTS_MEDIAN_RENT
    + POINTS_POPULATION_GROWTH + POINTS_ECONOMIC_MOMENTUM
    + POINTS_JOB_POSTINGS + POINTS_PORTFOLIO_NEWS + POINTS_TECH_STACK
    + POINTS_EMPLOYEE_COUNT + POINTS_COMPANY_AGE
    + POINTS_SENIORITY + POINTS_DEPARTMENT_FUNCTION + POINTS_CORPORATE_EMAIL
)

assert abs(BASELINE_MAX_SCORE - 100.0) < 1e-6, (
    f"Baseline point values must sum to 100, got {BASELINE_MAX_SCORE}"
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


settings = Settings()
