"""Tests for settings and weight constants."""

import pytest

from gtm.config import (
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
    Settings,
)


def test_all_weights_sum_to_one() -> None:
    total = (
        WEIGHT_RENTER_UNITS
        + WEIGHT_RENTER_RATE
        + WEIGHT_MEDIAN_RENT
        + WEIGHT_POPULATION_GROWTH
        + WEIGHT_ECONOMIC_MOMENTUM
        + WEIGHT_JOB_POSTINGS
        + WEIGHT_PORTFOLIO_NEWS
        + WEIGHT_TECH_STACK
        + WEIGHT_EMPLOYEE_COUNT
        + WEIGHT_COMPANY_AGE
        + WEIGHT_SENIORITY
        + WEIGHT_DEPARTMENT_FUNCTION
        + WEIGHT_CORPORATE_EMAIL
    )
    assert abs(total - 1.0) < 1e-9


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


def test_settings_rejects_broken_weights(monkeypatch: pytest.MonkeyPatch) -> None:
    """If module weights were tampered with, Settings validator should fail."""
    import gtm.config as cfg

    monkeypatch.setattr(cfg, "WEIGHT_RENTER_UNITS", 0.99)
    with pytest.raises(ValueError, match="sum to 1.0"):
        Settings()
