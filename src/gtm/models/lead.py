"""Raw lead shape from CSV input."""

from pydantic import BaseModel, Field, field_validator


class RawLead(BaseModel):
    """One inbound lead row from `data/leads_input.csv`."""

    name: str = Field(default="", description="Contact full name")
    email: str = Field(default="", description="Contact email")
    company: str = Field(default="", description="Company name")
    property_address: str = Field(default="", description="Street address of a property")
    city: str = Field(default="", description="City for market anchoring")
    state: str = Field(default="", description="Two-letter US state")

    @field_validator("state", mode="before")
    @classmethod
    def normalize_state(cls, v: object) -> str:
        if v is None:
            return ""
        s = str(v).strip().upper()
        return s[:2] if len(s) >= 2 else s
