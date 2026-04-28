"""Tests for cache, slug, and geocoder utilities."""

import json

import httpx

from gtm.utils.cache import FileCache
from gtm.utils.geocoder import FipsResult, get_fips
from gtm.utils.slug import make_slug, unique_slug

# ---------------------------------------------------------------------------
# FileCache
# ---------------------------------------------------------------------------

def test_cache_miss(tmp_path):
    cache = FileCache(tmp_path)
    assert cache.get("missing-key") is None


def test_cache_roundtrip(tmp_path):
    cache = FileCache(tmp_path)
    payload = {"renter_units": 80_000, "state": "TX"}
    cache.set("census:48:05000", payload)
    assert cache.get("census:48:05000") == payload


def test_cache_expired(tmp_path, monkeypatch):
    cache = FileCache(tmp_path)
    cache.set("some-key", {"value": 42})
    # Rewind cached_at to 25 hours ago so TTL check fires
    path = list(tmp_path.iterdir())[0]
    envelope = json.loads(path.read_text())
    envelope["cached_at"] -= 90_000
    path.write_text(json.dumps(envelope))
    assert cache.get("some-key") is None


def test_cache_corrupted_file_returns_none(tmp_path):
    cache = FileCache(tmp_path)
    cache.set("key", {"x": 1})
    path = list(tmp_path.iterdir())[0]
    path.write_text("not json at all")
    assert cache.get("key") is None


# ---------------------------------------------------------------------------
# Slug
# ---------------------------------------------------------------------------

def test_make_slug_basic():
    assert make_slug("Greystar", "Austin", "TX") == "greystar-austin-tx"


def test_make_slug_multi_word_company():
    assert make_slug("Lincoln Property Company", "Charlotte", "NC") == "lincoln-property-company-charlotte-nc"


def test_make_slug_special_chars():
    assert make_slug("A&B Realty, LLC", "St. Louis", "MO") == "a-b-realty-llc-st-louis-mo"


def test_unique_slug_no_conflict(tmp_outputs):
    assert unique_slug("greystar-austin-tx", tmp_outputs) == "greystar-austin-tx"


def test_unique_slug_one_conflict(tmp_outputs):
    (tmp_outputs / "greystar-austin-tx").mkdir()
    assert unique_slug("greystar-austin-tx", tmp_outputs) == "greystar-austin-tx-2"


def test_unique_slug_multiple_conflicts(tmp_outputs):
    (tmp_outputs / "greystar-austin-tx").mkdir()
    (tmp_outputs / "greystar-austin-tx-2").mkdir()
    assert unique_slug("greystar-austin-tx", tmp_outputs) == "greystar-austin-tx-3"


# ---------------------------------------------------------------------------
# Geocoder
# ---------------------------------------------------------------------------

GEOCODER_RESPONSE = {
    "result": {
        "addressMatches": [
            {
                "matchedAddress": "AUSTIN, TX",
                "geographies": {
                    "Incorporated Places": [
                        {"STATE": "48", "PLACE": "05000", "NAME": "Austin"}
                    ]
                },
            }
        ]
    }
}


async def test_get_fips_happy_path(tmp_path, mocker):
    cache = FileCache(tmp_path)
    mock_resp = mocker.MagicMock()
    mock_resp.json.return_value = GEOCODER_RESPONSE
    mock_resp.raise_for_status = mocker.MagicMock()

    client = mocker.AsyncMock(spec=httpx.AsyncClient)
    client.get.return_value = mock_resp

    # Passing street triggers the geocoder address path, which returns GEOCODER_RESPONSE format
    result = await get_fips("Austin", "TX", client, cache, street="100 Congress Ave")
    assert result == FipsResult(state_fips="48", place_fips="05000")


async def test_get_fips_cache_hit(tmp_path, mocker):
    cache = FileCache(tmp_path)
    cache.set("geocoder:austin:tx", {"state_fips": "48", "place_fips": "05000"})

    client = mocker.AsyncMock(spec=httpx.AsyncClient)
    result = await get_fips("Austin", "TX", client, cache)

    assert result == FipsResult(state_fips="48", place_fips="05000")
    client.get.assert_not_called()


async def test_get_fips_no_matches(tmp_path, mocker):
    cache = FileCache(tmp_path)
    mock_resp = mocker.MagicMock()
    mock_resp.json.return_value = {"result": {"addressMatches": []}}
    mock_resp.raise_for_status = mocker.MagicMock()

    client = mocker.AsyncMock(spec=httpx.AsyncClient)
    client.get.return_value = mock_resp

    assert await get_fips("Nowhere", "XX", client, cache) is None


async def test_get_fips_timeout(tmp_path, mocker):
    cache = FileCache(tmp_path)
    client = mocker.AsyncMock(spec=httpx.AsyncClient)
    client.get.side_effect = httpx.TimeoutException("timed out")

    assert await get_fips("Austin", "TX", client, cache) is None


async def test_get_fips_http_error(tmp_path, mocker):
    cache = FileCache(tmp_path)
    client = mocker.AsyncMock(spec=httpx.AsyncClient)
    request = httpx.Request("GET", "https://example.com")
    client.get.side_effect = httpx.HTTPStatusError(
        "500", request=request, response=httpx.Response(500, request=request)
    )

    assert await get_fips("Austin", "TX", client, cache) is None
