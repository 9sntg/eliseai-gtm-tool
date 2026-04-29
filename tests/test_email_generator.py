"""Outreach generator tests — happy path, degradation, prompt caching, context builder."""

import json

from gtm.models import EnrichedLead, RawLead
from gtm.models.company import CompanyData, SerperOrganicItem, SerperSearchBucket
from gtm.models.market import MarketData
from gtm.models.person import PersonData
from gtm.outreach.email_generator import _build_context, generate_outreach


def _make_lead(**kwargs) -> EnrichedLead:
    return EnrichedLead(
        raw=RawLead(
            name="Jane Smith", email="jane@greystar.com",
            company="Greystar", city="Austin", state="TX",
        ),
        **kwargs,
    )


def _json_response(email: str, insights: list[str] | None = None) -> str:
    return json.dumps({
        "email": email,
        "insights": insights or [
            "Strong leasing activity detected.",
            "No PM software found in tech stack.",
            "Contact role suggests operational authority.",
        ],
    })


def _mock_client(mocker, response_text: str | None = None):
    """Return a mock Anthropic client whose messages.create returns response_text."""
    if response_text is None:
        response_text = _json_response("Hi Jane, reaching out about EliseAI...")
    mock_msg = mocker.MagicMock()
    mock_msg.content = [mocker.MagicMock(text=response_text)]
    mock_client = mocker.MagicMock()
    mock_client.messages.create.return_value = mock_msg
    mocker.patch("gtm.outreach.email_generator.anthropic.Anthropic", return_value=mock_client)
    return mock_client


# ---------------------------------------------------------------------------
# Key presence gate
# ---------------------------------------------------------------------------

def test_generate_outreach_no_key_returns_empty(mocker):
    mocker.patch("gtm.outreach.email_generator.settings.anthropic_api_key", None)
    email, insights = generate_outreach(_make_lead(), None)
    assert email is None
    assert insights == []


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

def test_generate_outreach_happy_path(mocker):
    expected_email = "Hi Jane, I noticed Greystar is actively growing its Austin portfolio..."
    expected_insights = ["Signal A.", "Signal B.", "Signal C."]
    _mock_client(mocker, _json_response(expected_email, expected_insights))
    mocker.patch("gtm.outreach.email_generator.settings.anthropic_api_key", "test-key")

    email, insights = generate_outreach(_make_lead(), None)

    assert email == expected_email
    assert insights == expected_insights


def test_generate_outreach_strips_email_whitespace(mocker):
    _mock_client(mocker, _json_response("  Hi Jane...  \n"))
    mocker.patch("gtm.outreach.email_generator.settings.anthropic_api_key", "test-key")

    email, _ = generate_outreach(_make_lead(), None)
    assert email == "Hi Jane..."


# ---------------------------------------------------------------------------
# Degradation paths
# ---------------------------------------------------------------------------

def test_generate_outreach_api_error_returns_empty(mocker):
    mock_client = mocker.MagicMock()
    mock_client.messages.create.side_effect = Exception("connection error")
    mocker.patch("gtm.outreach.email_generator.anthropic.Anthropic", return_value=mock_client)
    mocker.patch("gtm.outreach.email_generator.settings.anthropic_api_key", "test-key")

    email, insights = generate_outreach(_make_lead(), None)
    assert email is None
    assert insights == []


def test_generate_outreach_invalid_json_returns_empty(mocker):
    mock_msg = mocker.MagicMock()
    mock_msg.content = [mocker.MagicMock(text="not valid json")]
    mock_client = mocker.MagicMock()
    mock_client.messages.create.return_value = mock_msg
    mocker.patch("gtm.outreach.email_generator.anthropic.Anthropic", return_value=mock_client)
    mocker.patch("gtm.outreach.email_generator.settings.anthropic_api_key", "test-key")

    email, insights = generate_outreach(_make_lead(), None)
    assert email is None
    assert insights == []


def test_generate_outreach_empty_content_returns_empty(mocker):
    mock_msg = mocker.MagicMock()
    mock_msg.content = []
    mock_client = mocker.MagicMock()
    mock_client.messages.create.return_value = mock_msg
    mocker.patch("gtm.outreach.email_generator.anthropic.Anthropic", return_value=mock_client)
    mocker.patch("gtm.outreach.email_generator.settings.anthropic_api_key", "test-key")

    email, insights = generate_outreach(_make_lead(), None)
    assert email is None
    assert insights == []


# ---------------------------------------------------------------------------
# Prompt caching
# ---------------------------------------------------------------------------

def test_generate_outreach_uses_prompt_caching(mocker):
    mock_client = _mock_client(mocker)
    mocker.patch("gtm.outreach.email_generator.settings.anthropic_api_key", "test-key")

    generate_outreach(_make_lead(), None)

    call_kwargs = mock_client.messages.create.call_args.kwargs
    system_blocks = call_kwargs["system"]
    assert any(
        b.get("cache_control", {}).get("type") == "ephemeral"
        for b in system_blocks
    )


def test_generate_outreach_uses_correct_model(mocker):
    mock_client = _mock_client(mocker)
    mocker.patch("gtm.outreach.email_generator.settings.anthropic_api_key", "test-key")

    generate_outreach(_make_lead(), None)

    call_kwargs = mock_client.messages.create.call_args.kwargs
    assert call_kwargs["model"] == "claude-sonnet-4-6"
    assert call_kwargs["temperature"] == 0.7
    assert call_kwargs["max_tokens"] == 700


# ---------------------------------------------------------------------------
# Context builder
# ---------------------------------------------------------------------------

def test_build_context_always_includes_name_company_location():
    lead = _make_lead()
    context = _build_context(lead, None)
    assert "Jane Smith" in context
    assert "Greystar" in context
    assert "Austin" in context
    assert "TX" in context


def test_build_context_omits_absent_optional_fields():
    lead = _make_lead()
    context = _build_context(lead, None)
    assert "renter-occupied" not in context.lower()
    assert "employee" not in context.lower()
    assert "portfolio" not in context.lower()


def test_build_context_includes_present_fields():
    lead = _make_lead(
        market=MarketData(renter_occupied_units=180_000, median_gross_rent=1_650),
        company=CompanyData(
            tech_stack=["Yardi Voyager"],
            linkedin_employee_count=501,
            founded_year=2002,
            serper_jobs=SerperSearchBucket(
                query="q",
                organic=[SerperOrganicItem(title="Leasing Agent", link="https://x.com", snippet="s")],
            ),
        ),
        person=PersonData(job_title="VP of Operations"),
        score=74.0,
        tier="High",
    )
    context = _build_context(lead, None)
    assert "180,000" in context
    assert "1,650" in context
    assert "Yardi Voyager" in context
    assert "501" in context
    assert "VP of Operations" in context


def test_build_context_notes_absent_tech_stack():
    lead = _make_lead()
    context = _build_context(lead, None)
    assert "none detected" in context.lower()
