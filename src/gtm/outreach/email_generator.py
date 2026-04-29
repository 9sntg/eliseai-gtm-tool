"""Draft personalized outreach emails and SDR insights using Claude Sonnet.

The system prompt is loaded from system_prompt.md at import time.
It is sent with cache_control=ephemeral so one cache hit covers all leads
in a batch run.
"""

from __future__ import annotations

import json
import logging
from datetime import date
from pathlib import Path

import anthropic

from gtm.config import settings
from gtm.models.enriched import EnrichedLead
from gtm.models.scoring import ScoreBreakdown

logger = logging.getLogger(__name__)

MODEL: str = "claude-sonnet-4-6"
TEMPERATURE: float = 0.7
MAX_TOKENS: int = 700

_PROMPT_FILE = Path(__file__).parent / "system_prompt.md"
SYSTEM_PROMPT: str = _PROMPT_FILE.read_text(encoding="utf-8")


def _build_context(lead: EnrichedLead, breakdown: ScoreBreakdown | None) -> str:
    """Build structured lead context for the Claude user message."""
    lines: list[str] = []
    r, m, c, p, b = lead.raw, lead.market, lead.company, lead.person, lead.building

    lines.append("=== LEAD ENRICHMENT ===")
    lines.append(f"Contact: {r.name}")
    if p.job_title:
        lines.append(f"Title: {p.job_title}")
    if p.seniority:
        lines.append(f"Seniority: {p.seniority.replace('_', ' ')}")
    if p.department:
        lines.append(f"Department: {p.department.replace('_', ' ')}")
    lines.append(f"Company: {r.company}")
    lines.append(f"Location: {r.city}, {r.state}")

    if m.renter_occupied_units:
        lines.append(f"Renter-occupied units in city: {m.renter_occupied_units:,}")
    if m.median_gross_rent:
        lines.append(f"Median gross rent: ${m.median_gross_rent:,}/month")
    if m.population_growth_yoy is not None:
        lines.append(f"Population growth YoY: {m.population_growth_yoy * 100:+.1f}%")
    if m.median_income_growth_yoy is not None:
        lines.append(f"Income growth YoY: {m.median_income_growth_yoy * 100:+.1f}%")

    if c.linkedin_employee_count:
        lines.append(f"Estimated employees: {c.linkedin_employee_count:,}+")
    if c.portfolio_size:
        lines.append(f"Portfolio: ~{c.portfolio_size:,} units/communities managed")
    if c.founded_year:
        age = date.today().year - c.founded_year
        lines.append(f"Founded: {c.founded_year} ({age} years ago)")
    elif c.yelp_year_established:
        age = date.today().year - c.yelp_year_established
        lines.append(f"Established: {c.yelp_year_established} ({age} years ago)")
    if c.tech_stack:
        lines.append(f"Tech stack detected: {', '.join(c.tech_stack)}")
    else:
        lines.append("Tech stack: none detected")
    if c.serper_property_management.knowledge_graph_title:
        lines.append(
            f"Google presence: verified Knowledge Graph entry for "
            f"'{c.serper_property_management.knowledge_graph_title}'"
        )
    if c.is_publicly_traded:
        lines.append("Publicly traded: yes")

    if c.yelp_rating is not None:
        avg = f", market avg {c.yelp_market_avg_rating}/5" if c.yelp_market_avg_rating else ""
        lines.append(
            f"Yelp company rating: {c.yelp_rating}/5 "
            f"({c.yelp_review_count or 0} reviews{avg})"
        )
    if c.yelp_pain_themes:
        lines.append(f"Resident complaint themes from Yelp: {', '.join(c.yelp_pain_themes)}")
    if c.google_rating is not None:
        lines.append(f"Google rating: {c.google_rating}/5")
    if c.serper_pain_themes:
        lines.append(f"Resident complaint themes from Google: {', '.join(c.serper_pain_themes)}")
    if c.competitor_rank_pct is not None:
        lines.append(
            f"Competitor rank: {c.competitor_rank_pct:.0%} of local PM companies "
            "rate higher on Yelp"
        )

    if b.yelp_rating is not None:
        lines.append(
            f"Building Yelp rating: {b.yelp_rating}/5 "
            f"({b.yelp_review_count or 0} reviews) at {r.property_address}"
        )
    if b.price_tier:
        lines.append(f"Building price tier: {b.price_tier}")
    if b.pain_themes:
        lines.append(f"Building complaint themes: {', '.join(b.pain_themes)}")

    if breakdown:
        lines.append("")
        lines.append("=== SCORING ANALYSIS ===")
        if lead.score is not None:
            lines.append(f"Lead score: {lead.score:.1f}/119 ({lead.tier} priority)")
        lines.append(f"Market context score: {breakdown.market_score:.1f}%")
        lines.append(f"Company signals score: {breakdown.company_score:.1f}%")
        lines.append(f"Contact fit score: {breakdown.person_score:.1f}%")
        if breakdown.building_score > 0:
            lines.append(f"Building signals score: {breakdown.building_score:.1f}%")

    return "\n".join(lines)


def generate_outreach(
    lead: EnrichedLead,
    breakdown: ScoreBreakdown | None,
) -> tuple[str | None, list[str]]:
    """Generate a personalized email and 3 SDR insights using Claude.

    Returns (email_text, insights_list). On any failure returns (None, []).
    """
    if not settings.anthropic_api_key:
        logger.debug(
            "ANTHROPIC_API_KEY not configured — skipping outreach generation for %s",
            lead.raw.company,
        )
        return None, []

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    context = _build_context(lead, breakdown)

    try:
        message = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            temperature=TEMPERATURE,
            system=[{
                "type": "text",
                "text": SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }],
            messages=[{"role": "user", "content": context}],
        )
        raw = message.content[0].text.strip()
        # strip markdown code fences if Claude wrapped the JSON
        if raw.startswith("```"):
            raw = raw.split("```", 2)[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()
        parsed = json.loads(raw)
        email = parsed.get("email", "").strip() or None
        insights = [s for s in parsed.get("insights", []) if isinstance(s, str)]
        logger.info(
            "outreach generated for %s (%d chars email, %d insights)",
            lead.raw.company, len(email or ""), len(insights),
        )
        return email, insights
    except Exception as exc:
        logger.warning("outreach generation failed for %s: %s", lead.raw.company, exc)
        return None, []
