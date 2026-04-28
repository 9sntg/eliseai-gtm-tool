"""Score breakdown for a single lead."""

from pydantic import BaseModel, Field


class ScoreBreakdown(BaseModel):
    """Scoring detail for one lead.

    Individual signal fields are raw weights in [0.0, 1.0].
    The three category subtotals (market_score, company_score, person_score)
    are normalized to [0.0, 100.0] to match the overall score scale.
    """

    renter_units: float = 0.0
    renter_rate: float = 0.0
    median_rent: float = 0.0
    population_growth: float = 0.0
    economic_momentum: float = 0.0

    job_postings: float = 0.0
    portfolio_news: float = 0.0
    tech_stack: float = 0.0
    employee_count: float = 0.0
    company_age: float = 0.0

    seniority: float = 0.0
    department_function: float = 0.0
    corporate_email: float = 0.0

    market_score: float = Field(default=0.0, description="Market Fit subtotal 0–100")
    company_score: float = Field(default=0.0, description="Company Fit subtotal 0–100")
    person_score: float = Field(default=0.0, description="Person Fit subtotal 0–100")
