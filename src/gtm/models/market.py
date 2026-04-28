"""Normalized market-level enrichment (Census + DataUSA)."""

from pydantic import BaseModel, Field


class MarketData(BaseModel):
    """Market signals for scoring Market Fit. All fields optional until enrichment runs."""

    renter_occupied_units: int | None = Field(
        default=None,
        description="Renter-occupied housing units (Census)",
    )
    total_housing_units: int | None = Field(
        default=None,
        description="Total housing units (Census), for renter rate",
    )
    renter_rate: float | None = Field(
        default=None,
        description="Share of housing that is renter-occupied, 0–1 if derived",
    )
    median_gross_rent: int | None = Field(default=None, description="Median gross rent (Census)")
    total_population: int | None = Field(default=None, description="Population (Census)")
    population_growth_yoy: float | None = Field(
        default=None,
        description="Population growth year-over-year (DataUSA), fraction or percent per parser",
    )
    median_household_income: int | None = Field(
        default=None,
        description="Median household income (DataUSA)",
    )
    median_income_growth_yoy: float | None = Field(
        default=None,
        description="Income growth YoY proxy for economic momentum (DataUSA)",
    )
    real_estate_employment: int | None = Field(
        default=None,
        description="Real estate sector employment count if available (DataUSA)",
    )
    median_property_value: int | None = Field(
        default=None,
        description="Median property value if used as auxiliary signal (DataUSA)",
    )
