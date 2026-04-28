"""Normalized company-level enrichment (Serper, OpenCorporates, Hunter, BuiltWith)."""

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
    opencorporates_name: str | None = None
    opencorporates_jurisdiction: str | None = None
    opencorporates_company_number: str | None = None
    opencorporates_incorporation_date: str | None = None
    opencorporates_current_status: str | None = None
    hunter_organization: str | None = Field(default=None, description="Organization name from Hunter")
    hunter_employee_count: int | None = Field(
        default=None,
        description="Employee estimate when API returns it (field varies by plan)",
    )
    hunter_domain: str | None = None
    tech_stack: list[str] = Field(
        default_factory=list,
        description="Technology names from BuiltWith (Yardi, RealPage, Entrata, …)",
    )
