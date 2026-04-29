"""Enrichment module tests — happy path and degradation for all active modules."""

import httpx
import pytest

from gtm.enrichment import builtwith, census, datausa, edgar, pdl, serper, yelp
from gtm.models.building import BuildingData
from gtm.models.company import CompanyData
from gtm.models.market import MarketData
from gtm.models.person import PersonData
from gtm.utils.cache import FileCache
from gtm.utils.geocoder import FipsResult

FIPS = FipsResult(state_fips="48", place_fips="05000")


def _mock_resp(mocker, status: int, body):
    resp = mocker.MagicMock()
    resp.status_code = status
    resp.json.return_value = body
    return resp


def _http_error(mocker, status: int) -> httpx.HTTPStatusError:
    req = httpx.Request("GET", "https://example.com")
    return httpx.HTTPStatusError("err", request=req, response=httpx.Response(status, request=req))


# ---------------------------------------------------------------------------
# Census
# ---------------------------------------------------------------------------

async def test_census_happy_path(tmp_path, mocker, raw_lead, census_response):
    cache = FileCache(tmp_path)
    mocker.patch("gtm.enrichment.census.get_fips", return_value=FIPS)
    mocker.patch("gtm.enrichment.census.asyncio.sleep")
    mocker.patch("gtm.enrichment.census._fetch", mocker.AsyncMock(
        return_value=_mock_resp(mocker, 200, census_response)
    ))

    result = await census.enrich(raw_lead, mocker.AsyncMock(), cache)

    assert isinstance(result, MarketData)
    assert result.renter_occupied_units == 180_000
    assert result.total_housing_units == 350_000
    assert result.renter_rate == pytest.approx(180_000 / 350_000, abs=1e-4)
    assert result.median_gross_rent == 1650
    assert result.total_population == 978_908


async def test_census_fips_failure_returns_empty(tmp_path, mocker, raw_lead):
    cache = FileCache(tmp_path)
    mocker.patch("gtm.enrichment.census.get_fips", return_value=None)

    result = await census.enrich(raw_lead, mocker.AsyncMock(), cache)
    assert result == MarketData()


async def test_census_404_returns_empty(tmp_path, mocker, raw_lead):
    cache = FileCache(tmp_path)
    mocker.patch("gtm.enrichment.census.get_fips", return_value=FIPS)
    mocker.patch("gtm.enrichment.census.asyncio.sleep")
    mocker.patch("gtm.enrichment.census._fetch", mocker.AsyncMock(
        return_value=_mock_resp(mocker, 404, {})
    ))

    result = await census.enrich(raw_lead, mocker.AsyncMock(), cache)
    assert result == MarketData()


# ---------------------------------------------------------------------------
# DataUSA
# ---------------------------------------------------------------------------

async def test_datausa_happy_path(tmp_path, mocker, raw_lead, datausa_pop_response, datausa_income_response):
    cache = FileCache(tmp_path)
    mocker.patch("gtm.enrichment.datausa.get_fips", return_value=FIPS)
    mocker.patch("gtm.enrichment.datausa.asyncio.sleep")
    # side_effect order: current year first, prior year second (asyncio.gather order)
    mocker.patch("gtm.enrichment.datausa._fetch_acs_year", mocker.AsyncMock(side_effect=[
        _mock_resp(mocker, 200, datausa_pop_response),
        _mock_resp(mocker, 200, datausa_income_response),
    ]))

    result = await datausa.enrich(raw_lead, mocker.AsyncMock(), cache)

    assert isinstance(result, MarketData)
    assert result.population_growth_yoy is not None
    assert result.median_household_income == 80_000
    assert result.median_income_growth_yoy is not None


async def test_datausa_fips_failure_returns_empty(tmp_path, mocker, raw_lead):
    cache = FileCache(tmp_path)
    mocker.patch("gtm.enrichment.datausa.get_fips", return_value=None)

    result = await datausa.enrich(raw_lead, mocker.AsyncMock(), cache)
    assert result == MarketData()


async def test_datausa_fetch_error_returns_empty(tmp_path, mocker, raw_lead):
    cache = FileCache(tmp_path)
    mocker.patch("gtm.enrichment.datausa.get_fips", return_value=FIPS)
    mocker.patch("gtm.enrichment.datausa.asyncio.sleep")
    mocker.patch("gtm.enrichment.datausa._fetch_acs_year", mocker.AsyncMock(
        side_effect=httpx.TimeoutException("timed out")
    ))

    result = await datausa.enrich(raw_lead, mocker.AsyncMock(), cache)
    assert result == MarketData()


# ---------------------------------------------------------------------------
# Serper (2 queries: PM, LinkedIn)
# ---------------------------------------------------------------------------

async def test_serper_happy_path(
    tmp_path, mocker, raw_lead,
    serper_pm_response, serper_linkedin_response,
):
    cache = FileCache(tmp_path)
    mocker.patch("gtm.enrichment.serper.asyncio.sleep")
    mocker.patch("gtm.enrichment.serper._post", mocker.AsyncMock(side_effect=[
        _mock_resp(mocker, 200, serper_pm_response),
        _mock_resp(mocker, 200, serper_linkedin_response),
    ]))
    mocker.patch("gtm.enrichment.serper.settings.serper_api_key", "test-key")
    mocker.patch("gtm.enrichment.serper.extract_company_profile", mocker.AsyncMock(
        return_value={"employee_count": 10_001, "founded_year": 1993, "portfolio_size": 3_600}
    ))

    result = await serper.enrich(raw_lead, mocker.AsyncMock(), cache)

    assert isinstance(result, CompanyData)
    assert len(result.serper_property_management.organic) == 2
    assert result.serper_property_management.knowledge_graph_title == "Greystar"
    assert len(result.serper_linkedin.organic) == 1
    assert result.linkedin_employee_count == 10_001
    assert result.founded_year == 1993
    assert result.portfolio_size == 3_600
    assert result.yelp_alias == "greystar-austin"  # extracted from yelp.com/biz/greystar-austin


async def test_serper_no_key_returns_empty(tmp_path, mocker, raw_lead):
    cache = FileCache(tmp_path)
    mocker.patch("gtm.enrichment.serper.settings.serper_api_key", None)

    result = await serper.enrich(raw_lead, mocker.AsyncMock(), cache)
    assert result == CompanyData()


# ---------------------------------------------------------------------------
# EDGAR
# ---------------------------------------------------------------------------

async def test_edgar_public_company(tmp_path, mocker, raw_lead, edgar_public_response):
    cache = FileCache(tmp_path)
    client = mocker.AsyncMock()
    client.get = mocker.AsyncMock(
        return_value=_mock_resp(mocker, 200, edgar_public_response)
    )

    result = await edgar.enrich(raw_lead, client, cache)

    assert isinstance(result, CompanyData)
    assert result.is_publicly_traded is True


async def test_edgar_private_company(tmp_path, mocker, raw_lead, edgar_private_response):
    cache = FileCache(tmp_path)
    client = mocker.AsyncMock()
    client.get = mocker.AsyncMock(
        return_value=_mock_resp(mocker, 200, edgar_private_response)
    )

    result = await edgar.enrich(raw_lead, client, cache)

    assert result.is_publicly_traded is False


async def test_edgar_timeout_returns_empty(tmp_path, mocker, raw_lead):
    cache = FileCache(tmp_path)
    client = mocker.AsyncMock()
    client.get = mocker.AsyncMock(side_effect=httpx.TimeoutException("timed out"))

    result = await edgar.enrich(raw_lead, client, cache)
    assert result == CompanyData()


# ---------------------------------------------------------------------------
# BuiltWith
# ---------------------------------------------------------------------------

async def test_builtwith_happy_path(tmp_path, mocker, raw_lead, builtwith_response):
    cache = FileCache(tmp_path)
    mocker.patch("gtm.enrichment.builtwith.asyncio.sleep")
    mocker.patch("gtm.enrichment.builtwith.settings.builtwith_api_key", "test-key")
    mocker.patch("gtm.enrichment.builtwith._fetch", mocker.AsyncMock(
        return_value=_mock_resp(mocker, 200, builtwith_response)
    ))

    result = await builtwith.enrich(raw_lead, mocker.AsyncMock(), cache)

    assert isinstance(result, CompanyData)
    assert "Yardi Voyager" in result.tech_stack
    assert "Google Analytics" in result.tech_stack
    assert len(result.tech_stack) == 2


async def test_builtwith_no_key_returns_empty(tmp_path, mocker, raw_lead):
    cache = FileCache(tmp_path)
    mocker.patch("gtm.enrichment.builtwith.settings.builtwith_api_key", None)

    result = await builtwith.enrich(raw_lead, mocker.AsyncMock(), cache)
    assert result == CompanyData()


# ---------------------------------------------------------------------------
# PDL
# ---------------------------------------------------------------------------

async def test_pdl_happy_path(tmp_path, mocker, raw_lead, pdl_response):
    cache = FileCache(tmp_path)
    mocker.patch("gtm.enrichment.pdl.asyncio.sleep")
    mocker.patch("gtm.enrichment.pdl.settings.pdl_api_key", "test-key")
    mocker.patch("gtm.enrichment.pdl._fetch", mocker.AsyncMock(
        return_value=_mock_resp(mocker, 200, pdl_response)
    ))

    result = await pdl.enrich(raw_lead, mocker.AsyncMock(), cache)

    assert isinstance(result, PersonData)
    assert result.job_title == "VP of Operations"
    assert result.seniority == "vp"
    assert result.department == "operations"
    assert result.pdl_likelihood == 8
    assert result.is_corporate_email is True  # greystar.com is corporate


async def test_pdl_404_returns_email_signal_only(tmp_path, mocker, raw_lead):
    cache = FileCache(tmp_path)
    mocker.patch("gtm.enrichment.pdl.asyncio.sleep")
    mocker.patch("gtm.enrichment.pdl.settings.pdl_api_key", "test-key")
    mocker.patch("gtm.enrichment.pdl._fetch", mocker.AsyncMock(
        return_value=_mock_resp(mocker, 404, {})
    ))

    result = await pdl.enrich(raw_lead, mocker.AsyncMock(), cache)

    assert result.seniority is None
    assert result.is_corporate_email is True  # derived locally, still populated


async def test_pdl_no_key_returns_email_signal_only(tmp_path, mocker, raw_lead):
    cache = FileCache(tmp_path)
    mocker.patch("gtm.enrichment.pdl.settings.pdl_api_key", None)

    result = await pdl.enrich(raw_lead, mocker.AsyncMock(), cache)

    assert result.seniority is None
    assert result.is_corporate_email is True


# ---------------------------------------------------------------------------
# Yelp enrichment
# ---------------------------------------------------------------------------

async def test_yelp_enrich_company_happy_path(
    tmp_path, mocker, raw_lead,
    yelp_search_response, yelp_profile_response,
    yelp_reviews_response, yelp_highlights_response, yelp_comparables_response,
):
    cache = FileCache(tmp_path)
    mocker.patch("gtm.enrichment.yelp.settings.yelp_api_key", "fake-key")
    mocker.patch("gtm.enrichment.yelp_helpers.settings.anthropic_api_key", None)
    mocker.patch("gtm.enrichment.yelp.asyncio.sleep")

    call_count = 0
    search_responses = [yelp_search_response, yelp_comparables_response]

    async def mock_get(url, **kwargs):
        nonlocal call_count
        if "/search" in url:
            body = search_responses[min(call_count, 1)]
            call_count += 1
        elif "/review_highlights" in url:
            body = yelp_highlights_response
        elif "/reviews" in url:
            body = yelp_reviews_response
        else:
            body = yelp_profile_response
        return _mock_resp(mocker, 200, body)

    client = mocker.AsyncMock()
    client.get = mock_get

    result = await yelp.enrich_company(raw_lead, client, cache)

    assert result.yelp_rating == 3.2
    assert result.yelp_review_count == 45
    assert result.yelp_alias == "greystar-austin"
    assert result.yelp_year_established == 2003
    assert result.yelp_market_avg_rating == pytest.approx(4.0)


async def test_yelp_enrich_company_no_key_returns_empty(tmp_path, mocker, raw_lead):
    cache = FileCache(tmp_path)
    mocker.patch("gtm.enrichment.yelp.settings.yelp_api_key", None)

    result = await yelp.enrich_company(raw_lead, mocker.AsyncMock(), cache)

    assert isinstance(result, CompanyData)
    assert result.yelp_rating is None


async def test_yelp_enrich_building_happy_path(
    tmp_path, mocker, raw_lead,
    yelp_search_response, yelp_profile_response,
    yelp_reviews_response, yelp_highlights_response,
):
    cache = FileCache(tmp_path)
    mocker.patch("gtm.enrichment.yelp.settings.yelp_api_key", "fake-key")
    mocker.patch("gtm.enrichment.yelp_helpers.settings.anthropic_api_key", None)
    mocker.patch("gtm.enrichment.yelp.asyncio.sleep")

    async def mock_get(url, **kwargs):
        if "/search" in url:
            return _mock_resp(mocker, 200, yelp_search_response)
        if "/review_highlights" in url:
            return _mock_resp(mocker, 200, yelp_highlights_response)
        if "/reviews" in url:
            return _mock_resp(mocker, 200, yelp_reviews_response)
        return _mock_resp(mocker, 200, yelp_profile_response)

    client = mocker.AsyncMock()
    client.get = mock_get

    result = await yelp.enrich_building(raw_lead, client, cache)

    assert isinstance(result, BuildingData)
    assert result.yelp_rating == 3.2
    assert result.yelp_review_count == 45
    assert result.yelp_alias == "greystar-austin"


async def test_yelp_enrich_building_no_match_returns_empty(tmp_path, mocker, raw_lead):
    cache = FileCache(tmp_path)
    mocker.patch("gtm.enrichment.yelp.settings.yelp_api_key", "fake-key")
    mocker.patch("gtm.enrichment.yelp.asyncio.sleep")

    async def mock_get(url, **kwargs):
        return _mock_resp(mocker, 200, {"businesses": []})

    client = mocker.AsyncMock()
    client.get = mock_get

    result = await yelp.enrich_building(raw_lead, client, cache)

    assert isinstance(result, BuildingData)
    assert result.yelp_rating is None
