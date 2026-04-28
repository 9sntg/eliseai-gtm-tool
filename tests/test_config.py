"""Tests for settings and point constants."""

import pytest

from gtm.config import (
    BASELINE_MAX_SCORE,
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
    POINTS_YELP_COMPANY_RATING,
    Settings,
)


def test_baseline_points_sum_to_117() -> None:
    total = (
        POINTS_RENTER_UNITS + POINTS_RENTER_RATE + POINTS_MEDIAN_RENT
        + POINTS_POPULATION_GROWTH + POINTS_ECONOMIC_MOMENTUM
        + POINTS_JOB_POSTINGS + POINTS_PORTFOLIO_NEWS + POINTS_TECH_STACK
        + POINTS_EMPLOYEE_COUNT + POINTS_COMPANY_AGE
        + POINTS_PORTFOLIO_SIZE + POINTS_SOCIAL_PRESENCE + POINTS_YELP_COMPANY_RATING
        + POINTS_SENIORITY + POINTS_DEPARTMENT_FUNCTION + POINTS_CORPORATE_EMAIL
    )
    assert abs(total - 117.0) < 1e-9
    assert abs(BASELINE_MAX_SCORE - 117.0) < 1e-9


def test_settings_loads_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SERPER_API_KEY", "test-serper")
    monkeypatch.setenv("PDL_API_KEY", "test-pdl")
    s = Settings()
    assert s.serper_api_key == "test-serper"
    assert s.pdl_api_key == "test-pdl"


def test_settings_optional_keys_default_none(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in (
        "SERPER_API_KEY",
        "PDL_API_KEY",
        "ANTHROPIC_API_KEY",
        "BUILTWITH_API_KEY",
        "CENSUS_API_KEY",
    ):
        monkeypatch.delenv(key, raising=False)
    s = Settings(_env_file=None)
    assert s.builtwith_api_key is None
    assert s.census_api_key is None


def test_market_points_sum() -> None:
    market = (
        POINTS_RENTER_UNITS + POINTS_RENTER_RATE + POINTS_MEDIAN_RENT
        + POINTS_POPULATION_GROWTH + POINTS_ECONOMIC_MOMENTUM
    )
    assert abs(market - 38.0) < 1e-9


def test_company_points_sum() -> None:
    company = (
        POINTS_JOB_POSTINGS + POINTS_PORTFOLIO_NEWS + POINTS_TECH_STACK
        + POINTS_EMPLOYEE_COUNT + POINTS_COMPANY_AGE
        + POINTS_PORTFOLIO_SIZE + POINTS_SOCIAL_PRESENCE + POINTS_YELP_COMPANY_RATING
    )
    assert abs(company - 58.0) < 1e-9


def test_person_points_sum() -> None:
    person = POINTS_SENIORITY + POINTS_DEPARTMENT_FUNCTION + POINTS_CORPORATE_EMAIL
    assert abs(person - 21.0) < 1e-9
