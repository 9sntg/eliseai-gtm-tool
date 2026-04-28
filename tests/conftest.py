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
    # Census ACS format: [header_row, data_row] — used by the Census multi-year growth module
    return [
        ["B01003_001E", "B19013_001E", "state", "place"],
        ["978908", "80000", "48", "05000"],
    ]


@pytest.fixture
def datausa_income_response():
    # Prior-year ACS row for YoY growth comparison
    return [
        ["B01003_001E", "B19013_001E", "state", "place"],
        ["944658", "75752", "48", "05000"],
    ]


@pytest.fixture
def serper_pm_response():
    return {
        "organic": [
            {"title": "Greystar Real Estate", "link": "https://greystar.com",
             "snippet": "Leading PM firm with 500+ communities", "position": 1},
            {"title": "Greystar - Yelp", "link": "https://www.yelp.com/biz/greystar-austin",
             "snippet": "37 reviews of Greystar Real Estate", "position": 2},
        ],
        "knowledgeGraph": {"title": "Greystar", "description": "Global rental housing leader"},
    }


@pytest.fixture
def serper_jobs_response():
    return {
        "organic": [
            {"title": "Leasing Consultant - Greystar", "link": "https://jobs.greystar.com",
             "snippet": "Now hiring leasing consultants in Austin TX", "position": 1},
            {"title": "Greystar Leasing Jobs - Indeed", "link": "https://indeed.com/greystar",
             "snippet": "15 Greystar leasing consultant jobs available on Indeed.com",
             "position": 2},
        ],
        "knowledgeGraph": None,
    }


@pytest.fixture
def serper_linkedin_response():
    return {
        "organic": [
            {"title": "Greystar Real Estate Partners | LinkedIn",
             "link": "https://www.linkedin.com/company/greystar-real-estate-partners",
             "snippet": "Greystar Real Estate Partners | 47,527 followers on LinkedIn. "
                        "The leading rental housing company in the world. "
                        "Founded: 1993 · 10,001+ employees",
             "position": 1},
        ],
        "knowledgeGraph": None,
    }


@pytest.fixture
def edgar_public_response():
    return {
        "hits": {
            "total": {"value": 3, "relation": "eq"},
            "hits": [
                {"_source": {"entity_name": "Greystar Real Estate Partners LLC",
                             "file_date": "2024-03-15", "form_type": "10-K"}},
            ],
        }
    }


@pytest.fixture
def edgar_private_response():
    return {
        "hits": {
            "total": {"value": 0, "relation": "eq"},
            "hits": [],
        }
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


@pytest.fixture
def yelp_search_response():
    return {
        "businesses": [
            {
                "id": "abc123",
                "alias": "greystar-austin",
                "name": "Greystar",
                "rating": 3.2,
                "review_count": 45,
                "categories": [{"alias": "propertymgmt", "title": "Property Management"}],
                "location": {"city": "Austin", "state": "TX"},
            }
        ]
    }


@pytest.fixture
def yelp_profile_response():
    return {
        "id": "abc123",
        "alias": "greystar-austin",
        "name": "Greystar",
        "rating": 3.2,
        "review_count": 45,
        "is_claimed": True,
        "attributes": {"about_this_biz_year_established": "2003"},
    }


@pytest.fixture
def yelp_reviews_response():
    return {
        "reviews": [
            {"text": "Management never responds to maintenance requests.", "rating": 2},
            {"text": "Hard to reach anyone in the leasing office.", "rating": 1},
        ]
    }


@pytest.fixture
def yelp_highlights_response():
    return {
        "review_highlights": [
            {
                "sentence": "[[HIGHLIGHT]]Slow[[ENDHIGHLIGHT]] to respond to issues.",
                "review_count": 12,
            },
            {
                "sentence": "Leasing office is [[HIGHLIGHT]]hard to reach[[ENDHIGHLIGHT]].",
                "review_count": 8,
            },
        ]
    }


@pytest.fixture
def yelp_comparables_response():
    return {
        "businesses": [
            {"alias": "comp-a", "rating": 4.0, "review_count": 30},
            {"alias": "comp-b", "rating": 3.8, "review_count": 20},
            {"alias": "comp-c", "rating": 4.2, "review_count": 50},
        ]
    }
