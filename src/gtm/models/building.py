"""Building-level enrichment from Yelp and Serper."""

from pydantic import BaseModel, Field


class BuildingData(BaseModel):
    """Signals for the specific property the lead manages."""

    address: str = Field(default="", description="Street address from RawLead")
    yelp_alias: str | None = Field(default=None, description="Yelp business alias for the building")
    yelp_rating: float | None = Field(
        default=None,
        description="Yelp rating 1–5 (inverted scoring: low = resident pain = strong pitch)",
    )
    yelp_review_count: int | None = Field(
        default=None,
        description="Number of Yelp reviews — volume signal for building activity",
    )
    pain_themes: list[str] = Field(
        default_factory=list,
        description="Resident pain themes extracted from Yelp review highlights via Haiku",
    )
    google_rating: float | None = Field(
        default=None,
        description="Google rating from Serper knowledge graph (when available)",
    )
