"""Shared fixtures for all test modules."""

import pytest

from gtm.models import RawLead


@pytest.fixture
def raw_lead() -> RawLead:
    return RawLead(
        name="Jane Smith",
        email="jane@greystar.com",
        company="Greystar",
        property_address="1234 Main St",
        city="Austin",
        state="TX",
    )


@pytest.fixture
def tmp_outputs(tmp_path):
    """Temporary outputs directory, created fresh per test."""
    d = tmp_path / "outputs"
    d.mkdir()
    return d
