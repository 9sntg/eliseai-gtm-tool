"""Application settings and scoring weight constants."""

from typing import Self

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# --- Score tier boundaries (overall 0–100 score) ---
TIER_LOW_MAX_SCORE: int = 40
TIER_MEDIUM_MAX_SCORE: int = 70

# --- Market Fit weights (sum = 0.38) ---
WEIGHT_RENTER_UNITS: float = 0.15
WEIGHT_RENTER_RATE: float = 0.08
WEIGHT_MEDIAN_RENT: float = 0.05
WEIGHT_POPULATION_GROWTH: float = 0.05
WEIGHT_ECONOMIC_MOMENTUM: float = 0.05

# --- Company Fit weights (sum = 0.41) ---
WEIGHT_JOB_POSTINGS: float = 0.12
WEIGHT_PORTFOLIO_NEWS: float = 0.08
WEIGHT_TECH_STACK: float = 0.08
WEIGHT_EMPLOYEE_COUNT: float = 0.08
WEIGHT_COMPANY_AGE: float = 0.05

# --- Person Fit weights (sum = 0.21) ---
WEIGHT_SENIORITY: float = 0.10
WEIGHT_DEPARTMENT_FUNCTION: float = 0.07
WEIGHT_CORPORATE_EMAIL: float = 0.04


class Settings(BaseSettings):
    """Loads configuration from environment / `.env`."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    serper_api_key: str | None = None
    hunter_api_key: str | None = None
    pdl_api_key: str | None = None
    anthropic_api_key: str | None = None
    builtwith_api_key: str | None = None
    census_api_key: str | None = None

    @model_validator(mode="after")
    def weights_sum_to_one(self) -> Self:
        market = (
            WEIGHT_RENTER_UNITS
            + WEIGHT_RENTER_RATE
            + WEIGHT_MEDIAN_RENT
            + WEIGHT_POPULATION_GROWTH
            + WEIGHT_ECONOMIC_MOMENTUM
        )
        company = (
            WEIGHT_JOB_POSTINGS
            + WEIGHT_PORTFOLIO_NEWS
            + WEIGHT_TECH_STACK
            + WEIGHT_EMPLOYEE_COUNT
            + WEIGHT_COMPANY_AGE
        )
        person = WEIGHT_SENIORITY + WEIGHT_DEPARTMENT_FUNCTION + WEIGHT_CORPORATE_EMAIL
        total = market + company + person
        if abs(total - 1.0) > 1e-6:
            msg = f"Scoring weights must sum to 1.0, got {total}"
            raise ValueError(msg)
        return self


settings = Settings()
