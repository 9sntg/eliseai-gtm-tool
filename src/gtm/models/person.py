"""Normalized person-level enrichment (PDL + derived email signals)."""

from pydantic import BaseModel, Field


class PersonData(BaseModel):
    """Person signals for scoring Person Fit."""

    job_title: str | None = None
    seniority: str | None = Field(
        default=None,
        description="Seniority bucket from PDL (e.g. c_suite, vp, director)",
    )
    department: str | None = Field(default=None, description="Department / function from PDL")
    years_experience: int | None = None
    pdl_likelihood: int | None = Field(default=None, description="PDL match confidence 1–10")
    is_corporate_email: bool = Field(
        default=False,
        description="True if email domain looks corporate (derived locally)",
    )
