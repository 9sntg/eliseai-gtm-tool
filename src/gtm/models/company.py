"""Normalized company-level enrichment (Serper, BuiltWith, EDGAR)."""

from pydantic import BaseModel, Field


class SerperOrganicItem(BaseModel):
    """One organic search result from Serper."""

    title: str = ""
    link: str = ""
    snippet: str = ""
    position: int | None = None


class SerperSearchBucket(BaseModel):
    """Parsed Serper response for a single query (e.g. PM search vs jobs search)."""

    query: str = ""
    organic: list[SerperOrganicItem] = Field(default_factory=list)
    knowledge_graph_title: str | None = None
    knowledge_graph_description: str | None = None
    knowledge_graph_rating: float | None = None


class CompanyData(BaseModel):
    """Company signals for scoring Company Fit."""

    serper_property_management: SerperSearchBucket = Field(
        default_factory=SerperSearchBucket,
        description="Results for company + property management style query",
    )
    serper_linkedin: SerperSearchBucket = Field(
        default_factory=SerperSearchBucket,
        description="Results for site:linkedin.com/company query",
    )
    linkedin_employee_count: int | None = Field(
        default=None,
        description="Employee count extracted from LinkedIn snippets via Haiku",
    )
    founded_year: int | None = Field(
        default=None,
        description="Year company was founded, extracted from LinkedIn snippets via Haiku",
    )
    is_publicly_traded: bool = Field(
        default=False,
        description="True if SEC EDGAR shows the company files 10-K reports",
    )
    portfolio_size: int | None = Field(
        default=None,
        description="Units/communities under management, extracted from search snippets via Haiku",
    )
    yelp_alias: str | None = Field(
        default=None,
        description="Yelp business alias extracted from Serper PM query results (yelp.com/biz/<alias>)",
    )
    social_platform_count: int = Field(
        default=0,
        description="Distinct non-LinkedIn social platforms detected in PM query results",
    )
    tech_stack: list[str] = Field(
        default_factory=list,
        description="Technology names from BuiltWith (Yardi, RealPage, Entrata, …)",
    )
    yelp_rating: float | None = Field(
        default=None,
        description="Yelp rating 1–5 for the company's Yelp listing",
    )
    yelp_review_count: int | None = Field(
        default=None,
        description="Number of Yelp reviews for the company",
    )
    yelp_market_avg_rating: float | None = Field(
        default=None,
        description="Average Yelp rating of comparable PM companies in the same city",
    )
    yelp_pain_themes: list[str] = Field(
        default_factory=list,
        description="Resident pain themes from company Yelp review highlights via Haiku",
    )
    yelp_year_established: int | None = Field(
        default=None,
        description="Year established from Yelp business attributes (fallback for founded_year)",
    )
    google_rating: float | None = Field(
        default=None,
        description="Google rating from Serper knowledge graph (when available)",
    )
    serper_pain_themes: list[str] = Field(
        default_factory=list,
        description="Resident/tenant pain themes extracted from Serper PM-query snippets via Haiku",
    )
    competitor_rank_pct: float | None = Field(
        default=None,
        description="Fraction of Yelp comparable PM companies that rate higher (0=best, 1=worst)",
    )
