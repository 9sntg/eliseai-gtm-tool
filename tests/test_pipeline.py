"""Pipeline integration tests — all 7 enrichment modules mocked at the module level."""

import json

from gtm.models.company import CompanyData
from gtm.models.market import MarketData
from gtm.models.person import PersonData
from gtm.pipeline.runner import run_pipeline


def _patch_enrichment(mocker) -> None:
    """Patch all 7 enrichment calls and email generator to return safe defaults."""
    mocker.patch("gtm.pipeline.runner.census.enrich", return_value=MarketData())
    mocker.patch("gtm.pipeline.runner.datausa.enrich", return_value=MarketData())
    mocker.patch("gtm.pipeline.runner.serper.enrich", return_value=CompanyData())
    mocker.patch("gtm.pipeline.runner.opencorporates.enrich", return_value=CompanyData())
    mocker.patch("gtm.pipeline.runner.hunter.enrich", return_value=CompanyData())
    mocker.patch("gtm.pipeline.runner.builtwith.enrich", return_value=CompanyData())
    mocker.patch("gtm.pipeline.runner.pdl.enrich", return_value=PersonData())
    mocker.patch("gtm.pipeline.runner.generate_email", return_value=None)


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
    (tmp_path / "greystar-austin-tx").mkdir()

    results = await run_pipeline([raw_lead], tmp_path)

    assert results == []


async def test_run_pipeline_assessment_has_required_keys(tmp_path, mocker, raw_lead):
    """assessment.json contains score, tier, breakdown, and insights."""
    _patch_enrichment(mocker)

    results = await run_pipeline([raw_lead], tmp_path)
    lead_dir = tmp_path / results[0].slug
    assessment = json.loads((lead_dir / "assessment.json").read_text())

    assert "score" in assessment
    assert "tier" in assessment
    assert "breakdown" in assessment
    assert "insights" in assessment
