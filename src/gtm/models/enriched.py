"""Full enriched lead record passed to scoring and outreach."""

from typing import Literal

from pydantic import BaseModel, Field

from gtm.models.building import BuildingData
from gtm.models.company import CompanyData
from gtm.models.lead import RawLead
from gtm.models.market import MarketData
from gtm.models.person import PersonData
from gtm.models.scoring import ScoreBreakdown

ScoreTier = Literal["Low", "Medium", "High"]


class EnrichedLead(BaseModel):
    """Raw lead plus enrichment, optional score, insights, and email draft."""

    raw: RawLead
    market: MarketData = Field(default_factory=MarketData)
    company: CompanyData = Field(default_factory=CompanyData)
    person: PersonData = Field(default_factory=PersonData)
    building: BuildingData = Field(default_factory=BuildingData)
    slug: str = Field(default="", description="Output folder slug: company-city-state")

    score: float | None = Field(default=None, description="Overall score 0–100")
    tier: ScoreTier | None = Field(default=None, description="Low / Medium / High from score")
    score_breakdown: ScoreBreakdown | None = None
    insights: list[str] = Field(default_factory=list, description="3–5 SDR-facing bullets")
    email_draft: str | None = Field(default=None, description="Plain-text outreach draft")
