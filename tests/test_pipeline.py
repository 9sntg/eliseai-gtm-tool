"""Pipeline integration tests — all 7 enrichment modules mocked at the module level."""

import json

from gtm.models.building import BuildingData
from gtm.models.company import CompanyData
from gtm.models.market import MarketData
from gtm.models.person import PersonData
from gtm.pipeline.runner import run_pipeline


def _patch_enrichment(mocker) -> None:
    """Patch all 8 enrichment calls and email generator to return safe defaults."""
    mocker.patch("gtm.pipeline.runner.census.enrich", return_value=MarketData())
    mocker.patch("gtm.pipeline.runner.datausa.enrich", return_value=MarketData())
    mocker.patch("gtm.pipeline.runner.serper.enrich", return_value=CompanyData())
    mocker.patch("gtm.pipeline.runner.builtwith.enrich", return_value=CompanyData())
    mocker.patch("gtm.pipeline.runner.edgar.enrich", return_value=CompanyData())
    mocker.patch("gtm.pipeline.runner.pdl.enrich", return_value=PersonData())
    mocker.patch("gtm.pipeline.runner.yelp.enrich_company", return_value=CompanyData())
    mocker.patch("gtm.pipeline.runner.yelp.enrich_building", return_value=BuildingData())
    mocker.patch("gtm.pipeline.runner.generate_outreach", return_value=(None, []))


async def test_run_pipeline_writes_three_files(tmp_path, mocker, raw_lead):
    """Full pipeline run produces enrichment.json, assessment.json, email.txt per lead."""
    _patch_enrichment(mocker)

    results = await run_pipeline([raw_lead], tmp_path)

    assert len(results) == 1
    lead_dir = tmp_path / results[0].slug
    assert (lead_dir / "enrichment.json").exists()
    assert (lead_dir / "assessment.json").exists()
    assert (lead_dir / "email.txt").exists()


async def test_run_pipeline_skips_existing_folder(tmp_path, mocker, raw_lead):
    """A lead whose base-slug folder already exists is not re-processed."""
    _patch_enrichment(mocker)
    (tmp_path / "greystar-1234-main-st-austin-tx").mkdir()

    results = await run_pipeline([raw_lead], tmp_path)

    assert results == []


async def test_run_pipeline_assessment_has_required_keys(tmp_path, mocker, raw_lead):
    """assessment.json contains lead_score, tier, category fits, signals, and key_observations."""
    _patch_enrichment(mocker)

    results = await run_pipeline([raw_lead], tmp_path)
    lead_dir = tmp_path / results[0].slug
    assessment = json.loads((lead_dir / "assessment.json").read_text())

    assert "lead_score" in assessment
    assert "tier" in assessment
    assert "market_fit" in assessment
    assert "company_fit" in assessment
    assert "person_fit" in assessment
    assert "building_fit" in assessment
    assert "signals" in assessment
    assert isinstance(assessment["signals"], list)
    assert "key_observations" in assessment


async def test_run_pipeline_enrichment_has_contact_section(tmp_path, mocker, raw_lead):
    """enrichment.json has contact, market, company, building sections (no raw/person keys)."""
    _patch_enrichment(mocker)

    results = await run_pipeline([raw_lead], tmp_path)
    lead_dir = tmp_path / results[0].slug
    enrichment = json.loads((lead_dir / "enrichment.json").read_text())

    assert "contact" in enrichment
    assert "market" in enrichment
    assert "company" in enrichment
    assert "building" in enrichment
    assert "raw" not in enrichment
    assert "person" not in enrichment


async def test_run_pipeline_signals_have_required_fields(tmp_path, mocker, raw_lead):
    """Each entry in assessment.json signals list has name, category, points, max_points, reason."""
    _patch_enrichment(mocker)

    results = await run_pipeline([raw_lead], tmp_path)
    lead_dir = tmp_path / results[0].slug
    assessment = json.loads((lead_dir / "assessment.json").read_text())

    for sig in assessment["signals"]:
        assert "name" in sig
        assert "category" in sig
        assert "points" in sig
        assert "max_points" in sig
        assert "reason" in sig
