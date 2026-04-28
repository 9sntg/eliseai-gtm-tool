"""Draft personalized outreach emails using Claude Sonnet with prompt caching.

The system prompt (EliseAI context, tone, constraints) is sent with
cache_control=ephemeral so one cache hit covers all leads in a batch.
"""

from __future__ import annotations

import logging
from datetime import date

import anthropic

from gtm.config import settings
from gtm.models.enriched import EnrichedLead

logger = logging.getLogger(__name__)

MODEL: str = "claude-sonnet-4-6"
TEMPERATURE: float = 0.7
MAX_TOKENS: int = 400

SYSTEM_PROMPT: str = (
    "You are an AI assistant helping EliseAI's sales development representatives "
    "craft personalized outreach emails to property management companies.\n\n"
    "EliseAI is an AI-powered platform that automates the leasing process — handling "
    "prospect inquiries, scheduling tours, screening applicants, and following up — "
    "so property management teams can focus on residents instead of repetitive tasks. "
    "Clients typically reduce leasing staff time by 30–50% and close leases faster.\n\n"
    "Write a brief, personalized outreach email from an EliseAI SDR to the contact "
    "provided. The email must:\n"
    "- Open with a specific hook from the lead data (market context, company activity, "
    "or contact role — never a generic opener like 'I hope this finds you well')\n"
    "- Briefly explain why EliseAI is relevant to this specific company\n"
    "- End with a single, low-friction call to action (e.g. 'Would a 15-minute call "
    "make sense?')\n"
    "- Be exactly 150–200 words\n"
    "- Use plain text only — no markdown, no bullet points, no subject line\n\n"
    "Only use data provided in the lead context. Do not invent statistics, company "
    "claims, market figures, or any detail not explicitly given."
)


def _build_context(lead: EnrichedLead) -> str:
    """Build a structured lead context string for the Claude user message."""
    lines: list[str] = []
    r, m, c, p = lead.raw, lead.market, lead.company, lead.person

    lines.append(f"Contact name: {r.name}")
    if p.job_title:
        lines.append(f"Title: {p.job_title}")
    lines.append(f"Company: {r.company}")
    lines.append(f"Location: {r.city}, {r.state}")

    if m.renter_occupied_units:
        lines.append(f"Renter-occupied units in market: {m.renter_occupied_units:,}")
    if m.median_gross_rent:
        lines.append(f"Median gross rent: ${m.median_gross_rent:,}/month")
    if m.population_growth_yoy is not None:
        lines.append(f"Population growth (YoY): {m.population_growth_yoy * 100:+.1f}%")

    if c.linkedin_employee_count:
        lines.append(f"Estimated employees: {c.linkedin_employee_count:,}+")
    if c.portfolio_size:
        lines.append(f"Portfolio: ~{c.portfolio_size:,} units/communities under management")
    if c.founded_year:
        age = date.today().year - c.founded_year
        lines.append(f"Founded: {c.founded_year} (~{age} years ago)")
    if c.tech_stack:
        lines.append(f"Tech stack detected: {', '.join(c.tech_stack)}")
    job_count = c.job_count if c.job_count is not None else len(c.serper_jobs.organic)
    if job_count:
        lines.append(f"Open leasing job postings: {job_count}")
    if c.serper_property_management.knowledge_graph_title:
        lines.append(
            f"Web presence: Google Knowledge Graph entry for "
            f"'{c.serper_property_management.knowledge_graph_title}'"
        )

    if lead.score is not None:
        lines.append(f"Lead score: {lead.score:.0f}/100 ({lead.tier})")

    return "\n".join(lines)


def generate_email(lead: EnrichedLead) -> str | None:
    """Draft a personalized outreach email using Claude. Returns None on any failure."""
    if not settings.anthropic_api_key:
        logger.debug(
            "ANTHROPIC_API_KEY not configured — skipping email generation for %s",
            lead.raw.company,
        )
        return None

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    context = _build_context(lead)

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
        draft = message.content[0].text.strip()
        logger.info("email drafted for %s (%d chars)", lead.raw.company, len(draft))
        return draft
    except Exception as exc:  # all failures share the same recovery: log + return None
        logger.warning("email generation failed for %s: %s", lead.raw.company, exc)
        return None
