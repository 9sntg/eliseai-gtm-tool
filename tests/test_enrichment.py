"""Enrichment module tests — happy path and degradation for all 7 modules."""

import httpx
import pytest

from gtm.enrichment import builtwith, census, datausa, hunter, opencorporates, pdl, serper
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
    mocker.patch("gtm.enrichment.datausa._fetch", mocker.AsyncMock(side_effect=[
        _mock_resp(mocker, 200, datausa_pop_response),
        _mock_resp(mocker, 200, datausa_income_response),
    ]))

    result = await datausa.enrich(raw_lead, mocker.AsyncMock(), cache)

    assert isinstance(result, MarketData)
    assert result.population_growth_yoy is not None
    assert result.median_household_income == 75_752
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
    mocker.patch("gtm.enrichment.datausa._fetch", mocker.AsyncMock(
        side_effect=httpx.TimeoutException("timed out")
    ))

    result = await datausa.enrich(raw_lead, mocker.AsyncMock(), cache)
    assert result == MarketData()


# ---------------------------------------------------------------------------
# Serper
# ---------------------------------------------------------------------------

async def test_serper_happy_path(tmp_path, mocker, raw_lead, serper_pm_response, serper_jobs_response):
    cache = FileCache(tmp_path)
    mocker.patch("gtm.enrichment.serper.asyncio.sleep")
    mocker.patch("gtm.enrichment.serper._post", mocker.AsyncMock(side_effect=[
        _mock_resp(mocker, 200, serper_pm_response),
        _mock_resp(mocker, 200, serper_jobs_response),
    ]))
    mocker.patch.dict("os.environ", {"SERPER_API_KEY": "test-key"})
    # Reload settings with the patched env
    mocker.patch("gtm.enrichment.serper.settings.serper_api_key", "test-key")

    result = await serper.enrich(raw_lead, mocker.AsyncMock(), cache)

    assert isinstance(result, CompanyData)
    assert len(result.serper_property_management.organic) == 1
    assert result.serper_property_management.knowledge_graph_title == "Greystar"
    assert len(result.serper_jobs.organic) == 2


async def test_serper_no_key_returns_empty(tmp_path, mocker, raw_lead):
    cache = FileCache(tmp_path)
    mocker.patch("gtm.enrichment.serper.settings.serper_api_key", None)

    result = await serper.enrich(raw_lead, mocker.AsyncMock(), cache)
    assert result == CompanyData()


# ---------------------------------------------------------------------------
# OpenCorporates
# ---------------------------------------------------------------------------

async def test_opencorporates_happy_path(tmp_path, mocker, raw_lead, opencorporates_response):
    cache = FileCache(tmp_path)
    mocker.patch("gtm.enrichment.opencorporates.asyncio.sleep")
    mocker.patch("gtm.enrichment.opencorporates._fetch", mocker.AsyncMock(
        return_value=_mock_resp(mocker, 200, opencorporates_response)
    ))

    result = await opencorporates.enrich(raw_lead, mocker.AsyncMock(), cache)

    assert isinstance(result, CompanyData)
    assert result.opencorporates_name == "GREYSTAR REAL ESTATE PARTNERS, LLC"
    assert result.opencorporates_jurisdiction == "us_tx"
    assert result.opencorporates_incorporation_date == "2002-03-15"
    assert result.opencorporates_current_status == "Active"


async def test_opencorporates_404_returns_empty(tmp_path, mocker, raw_lead):
    cache = FileCache(tmp_path)
    mocker.patch("gtm.enrichment.opencorporates.asyncio.sleep")
    mocker.patch("gtm.enrichment.opencorporates._fetch", mocker.AsyncMock(
        return_value=_mock_resp(mocker, 404, {})
    ))

    result = await opencorporates.enrich(raw_lead, mocker.AsyncMock(), cache)
    assert result == CompanyData()


# ---------------------------------------------------------------------------
# Hunter
# ---------------------------------------------------------------------------

async def test_hunter_happy_path(tmp_path, mocker, raw_lead, hunter_response):
    cache = FileCache(tmp_path)
    mocker.patch("gtm.enrichment.hunter.asyncio.sleep")
    mocker.patch("gtm.enrichment.hunter.settings.hunter_api_key", "test-key")
    mocker.patch("gtm.enrichment.hunter._fetch", mocker.AsyncMock(
        return_value=_mock_resp(mocker, 200, hunter_response)
    ))

    result = await hunter.enrich(raw_lead, mocker.AsyncMock(), cache)

    assert isinstance(result, CompanyData)
    assert result.hunter_domain == "greystar.com"
    assert result.hunter_organization == "Greystar Real Estate Partners"
    assert result.hunter_employee_count == 501  # lower bound of "501-1000"


async def test_hunter_no_key_returns_empty(tmp_path, mocker, raw_lead):
    cache = FileCache(tmp_path)
    mocker.patch("gtm.enrichment.hunter.settings.hunter_api_key", None)

    result = await hunter.enrich(raw_lead, mocker.AsyncMock(), cache)
    assert result == CompanyData()


async def test_hunter_timeout_returns_empty(tmp_path, mocker, raw_lead):
    cache = FileCache(tmp_path)
    mocker.patch("gtm.enrichment.hunter.asyncio.sleep")
    mocker.patch("gtm.enrichment.hunter.settings.hunter_api_key", "test-key")
    mocker.patch("gtm.enrichment.hunter._fetch", mocker.AsyncMock(
        side_effect=httpx.TimeoutException("timed out")
    ))

    result = await hunter.enrich(raw_lead, mocker.AsyncMock(), cache)
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
