"""Score breakdown for a single lead."""

from pydantic import BaseModel, Field


class ScoreBreakdown(BaseModel):
    """Scoring detail for one lead.

    Individual signal fields are raw weights in [0.0, 1.0].
    The three category subtotals (market_score, company_score, person_score)
    are normalized to [0.0, 100.0] to match the overall score scale.
    """

    renter_units: float = Field(default=0.0, description="Renter-occupied units signal [0–1]")
    renter_rate: float = Field(default=0.0, description="Renter-occupancy rate signal [0–1]")
    median_rent: float = Field(default=0.0, description="Median gross rent signal [0–1]")
    population_growth: float = Field(default=0.0, description="YoY population growth signal [0–1]")
    economic_momentum: float = Field(default=0.0, description="Median income growth signal [0–1]")

    job_postings: float = Field(default=0.0, description="Open leasing job postings signal [0–1]")
    portfolio_news: float = Field(default=0.0, description="Portfolio/company news signal [0–1]; absorbs BuiltWith weight when tech_stack is absent")
    tech_stack: float = Field(default=0.0, description="Property-management tech stack signal [0–1]; 0 when BuiltWith key absent")
    employee_count: float = Field(default=0.0, description="Employee headcount signal [0–1]")
    company_age: float = Field(default=0.0, description="Company age / maturity signal [0–1]")

    seniority: float = Field(default=0.0, description="Contact seniority level signal [0–1]")
    department_function: float = Field(default=0.0, description="Contact department / function relevance signal [0–1]")
    corporate_email: float = Field(default=0.0, description="Corporate (non-free-provider) email signal [0–1]")

    portfolio_size: float = Field(default=0.0, description="Managed portfolio size signal [0–1]")
    social_presence: float = Field(default=0.0, description="Social media platform presence signal [0–1]")
    yelp_company_rating: float = Field(default=0.0, description="Company Yelp rating vs. local market avg [0–1]")

    building_rating: float = Field(default=0.0, description="Building Yelp rating signal [0–1]; bonus, 0 when absent")
    building_reviews: float = Field(default=0.0, description="Building review volume signal [0–1]; bonus, 0 when absent")

    market_score: float = Field(default=0.0, description="Market Fit subtotal 0–100")
    company_score: float = Field(default=0.0, description="Company Fit subtotal 0–100")
    person_score: float = Field(default=0.0, description="Person Fit subtotal 0–100")
    building_score: float = Field(default=0.0, description="Building Fit bonus subtotal 0–100")
