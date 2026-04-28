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


# ---------------------------------------------------------------------------
# Mock API response payloads — realistic but fake
# ---------------------------------------------------------------------------

@pytest.fixture
def census_response():
    return [
        ["B25003_002E", "B25001_001E", "B25064_001E", "B01003_001E", "state", "place"],
        ["180000", "350000", "1650", "978908", "48", "05000"],
    ]


@pytest.fixture
def datausa_pop_response():
    return {
        "data": [
            {"ID Geography": "16000US4805000", "Geography": "Austin, TX",
             "ID Year": 2021, "Year": "2021", "Population": 978908},
            {"ID Geography": "16000US4805000", "Geography": "Austin, TX",
             "ID Year": 2020, "Year": "2020", "Population": 961855},
        ],
        "source": [],
    }


@pytest.fixture
def datausa_income_response():
    return {
        "data": [
            {"ID Geography": "16000US4805000", "Geography": "Austin, TX",
             "ID Year": 2021, "Year": "2021", "Median Household Income": 75752},
            {"ID Geography": "16000US4805000", "Geography": "Austin, TX",
             "ID Year": 2020, "Year": "2020", "Median Household Income": 71000},
        ],
        "source": [],
    }


@pytest.fixture
def serper_pm_response():
    return {
        "organic": [
            {"title": "Greystar Real Estate", "link": "https://greystar.com",
             "snippet": "Leading PM firm with 500+ communities", "position": 1},
        ],
        "knowledgeGraph": {"title": "Greystar", "description": "Global rental housing leader"},
    }


@pytest.fixture
def serper_jobs_response():
    return {
        "organic": [
            {"title": "Leasing Consultant - Greystar", "link": "https://jobs.greystar.com",
             "snippet": "Now hiring leasing consultants in Austin TX", "position": 1},
            {"title": "Leasing Agent - Austin", "link": "https://indeed.com/greystar",
             "snippet": "Greystar hiring leasing consultants", "position": 2},
        ],
        "knowledgeGraph": None,
    }


@pytest.fixture
def opencorporates_response():
    return {
        "results": {
            "companies": [
                {"company": {
                    "name": "GREYSTAR REAL ESTATE PARTNERS, LLC",
                    "company_number": "4536728",
                    "jurisdiction_code": "us_tx",
                    "incorporation_date": "2002-03-15",
                    "current_status": "Active",
                }}
            ]
        }
    }


@pytest.fixture
def hunter_response():
    return {
        "data": {
            "domain": "greystar.com",
            "organization": "Greystar Real Estate Partners",
            "headcount": "501-1000",
        },
        "meta": {"results": 0},
    }


@pytest.fixture
def builtwith_response():
    return {
        "Results": [
            {
                "Lookup": "greystar.com",
                "Paths": [
                    {"Technologies": [
                        {"Name": "Yardi Voyager", "Tag": "property-management"},
                        {"Name": "Google Analytics", "Tag": "analytics"},
                    ]}
                ],
            }
        ]
    }


@pytest.fixture
def pdl_response():
    return {
        "status": 200,
        "likelihood": 8,
        "data": {
            "job_title": "VP of Operations",
            "job_title_levels": ["vp"],
            "job_title_role": "operations",
        },
    }
