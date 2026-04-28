"""Email generator tests — happy path, degradation, and prompt caching."""

from gtm.models import EnrichedLead, RawLead
from gtm.models.company import CompanyData, SerperOrganicItem, SerperSearchBucket
from gtm.models.market import MarketData
from gtm.models.person import PersonData
from gtm.outreach.email_generator import _build_context, generate_email


def _make_lead(**kwargs) -> EnrichedLead:
    return EnrichedLead(
        raw=RawLead(
            name="Jane Smith", email="jane@greystar.com",
            company="Greystar", city="Austin", state="TX",
        ),
        **kwargs,
    )


def _mock_client(mocker, text: str = "Hi Jane, reaching out about EliseAI..."):
    """Return a mock Anthropic client whose messages.create returns `text`."""
    mock_msg = mocker.MagicMock()
    mock_msg.content = [mocker.MagicMock(text=text)]
    mock_client = mocker.MagicMock()
    mock_client.messages.create.return_value = mock_msg
    mocker.patch("gtm.outreach.email_generator.anthropic.Anthropic", return_value=mock_client)
    return mock_client


# ---------------------------------------------------------------------------
# Key presence gate
# ---------------------------------------------------------------------------

def test_generate_email_no_key_returns_none(mocker):
    mocker.patch("gtm.outreach.email_generator.settings.anthropic_api_key", None)
    assert generate_email(_make_lead()) is None


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

def test_generate_email_happy_path(mocker):
    expected = "Hi Jane, I noticed Greystar is actively growing its Austin portfolio..."
    mock_client = _mock_client(mocker, text=expected)
    mocker.patch("gtm.outreach.email_generator.settings.anthropic_api_key", "test-key")

    result = generate_email(_make_lead())

    assert result == expected
    mock_client.messages.create.assert_called_once()


def test_generate_email_returns_stripped_text(mocker):
    _mock_client(mocker, text="  Hi Jane...  \n")
    mocker.patch("gtm.outreach.email_generator.settings.anthropic_api_key", "test-key")

    result = generate_email(_make_lead())
    assert result == "Hi Jane..."


# ---------------------------------------------------------------------------
# Degradation paths
# ---------------------------------------------------------------------------

def test_generate_email_api_error_returns_none(mocker):
    mock_client = mocker.MagicMock()
    mock_client.messages.create.side_effect = Exception("connection error")
    mocker.patch("gtm.outreach.email_generator.anthropic.Anthropic", return_value=mock_client)
    mocker.patch("gtm.outreach.email_generator.settings.anthropic_api_key", "test-key")

    assert generate_email(_make_lead()) is None


def test_generate_email_empty_content_returns_none(mocker):
    mock_msg = mocker.MagicMock()
    mock_msg.content = []  # empty — IndexError when accessing [0]
    mock_client = mocker.MagicMock()
    mock_client.messages.create.return_value = mock_msg
    mocker.patch("gtm.outreach.email_generator.anthropic.Anthropic", return_value=mock_client)
    mocker.patch("gtm.outreach.email_generator.settings.anthropic_api_key", "test-key")

    assert generate_email(_make_lead()) is None


# ---------------------------------------------------------------------------
# Prompt caching
# ---------------------------------------------------------------------------

def test_generate_email_uses_prompt_caching(mocker):
    mock_client = _mock_client(mocker)
    mocker.patch("gtm.outreach.email_generator.settings.anthropic_api_key", "test-key")

    generate_email(_make_lead())

    call_kwargs = mock_client.messages.create.call_args.kwargs
    system_blocks = call_kwargs["system"]
    assert any(
        b.get("cache_control", {}).get("type") == "ephemeral"
        for b in system_blocks
    )


def test_generate_email_uses_correct_model(mocker):
    mock_client = _mock_client(mocker)
    mocker.patch("gtm.outreach.email_generator.settings.anthropic_api_key", "test-key")

    generate_email(_make_lead())

    call_kwargs = mock_client.messages.create.call_args.kwargs
    assert call_kwargs["model"] == "claude-sonnet-4-6"
    assert call_kwargs["temperature"] == 0.7
    assert call_kwargs["max_tokens"] == 400


# ---------------------------------------------------------------------------
# Context builder
# ---------------------------------------------------------------------------

def test_build_context_omits_none_fields():
    lead = _make_lead()
    context = _build_context(lead)
    assert "renter-occupied" not in context.lower()
    assert "tech stack" not in context.lower()
    assert "employee" not in context.lower()


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
    context = _build_context(lead)
    assert "180,000" in context
    assert "1,650" in context
    assert "Yardi Voyager" in context
    assert "501" in context
    assert "VP of Operations" in context
    assert "74/117" in context
    assert "High" in context


def test_build_context_always_includes_name_company_location():
    lead = _make_lead()
    context = _build_context(lead)
    assert "Jane Smith" in context
    assert "Greystar" in context
    assert "Austin" in context
    assert "TX" in context
