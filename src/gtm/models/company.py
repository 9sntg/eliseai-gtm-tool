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


class CompanyData(BaseModel):
    """Company signals for scoring Company Fit."""

    serper_property_management: SerperSearchBucket = Field(
        default_factory=SerperSearchBucket,
        description="Results for company + property management style query",
    )
    serper_jobs: SerperSearchBucket = Field(
        default_factory=SerperSearchBucket,
        description="Results for leasing / jobs style query",
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
    tech_stack: list[str] = Field(
        default_factory=list,
        description="Technology names from BuiltWith (Yardi, RealPage, Entrata, …)",
    )
