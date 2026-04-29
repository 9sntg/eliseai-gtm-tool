"""Serper API response parsing and LinkedIn profile extraction helpers.

Shared by ``serper.py`` to keep the main module under the 200-line limit.
"""

from __future__ import annotations

import json
import logging
import re

import anthropic

from gtm.config import settings
from gtm.models.company import SerperOrganicItem, SerperSearchBucket

logger = logging.getLogger(__name__)

HAIKU_MODEL: str = "claude-haiku-4-5-20251001"
HAIKU_MAX_TOKENS: int = 150       # enough for 3-field JSON response
HAIKU_PAIN_MAX_TOKENS: int = 150  # enough for a variable-length pain theme array



def extract_yelp_alias(organic_items: list[SerperOrganicItem]) -> str | None:
    """Extract Yelp business alias from Serper organic result links."""
    for item in organic_items:
        match = re.search(r"yelp\.com/biz/([a-z0-9-]+)", item.link, re.IGNORECASE)
        if match:
            return match.group(1)
    return None


_SOCIAL_DOMAINS: frozenset[str] = frozenset({
    "facebook.com", "instagram.com", "youtube.com",
    "twitter.com", "x.com", "tiktok.com",
})


def extract_social_platforms(organic_items: list[SerperOrganicItem]) -> int:
    """Count distinct non-LinkedIn social platforms in PM query organic links."""
    found: set[str] = set()
    for item in organic_items:
        for domain in _SOCIAL_DOMAINS:
            if domain in item.link.lower():
                found.add(domain)
    return len(found)


def extract_google_rating(kg: dict) -> float | None:
    """Extract Google rating from Serper knowledge graph attributes if present."""
    if not kg:
        return None
    rating = kg.get("rating")
    if rating is not None:
        try:
            return float(rating)
        except (ValueError, TypeError):
            return None
    return None


def parse_serper_response(raw: dict, query: str) -> SerperSearchBucket:
    """Parse a raw Serper JSON response into a SerperSearchBucket."""
    organic = [
        SerperOrganicItem(
            title=item.get("title", ""),
            link=item.get("link", ""),
            snippet=item.get("snippet", ""),
            position=item.get("position"),
        )
        for item in raw.get("organic", [])
    ]
    kg = raw.get("knowledgeGraph") or {}
    return SerperSearchBucket(
        query=query,
        organic=organic,
        knowledge_graph_title=kg.get("title"),
        knowledge_graph_description=kg.get("description"),
        knowledge_graph_rating=extract_google_rating(kg),
    )


async def extract_serper_pain_themes(snippets: list[str], company_name: str) -> list[str]:
    """Extract tenant pain themes from Serper PM-query organic snippets via Haiku.

    Snippets often contain review excerpts from Google, Yelp aggregators, and
    apartments.com — this surfaces Google-sourced pain without a separate API.
    Returns only themes with clear evidence. May return [].
    """
    if not settings.anthropic_api_key or not snippets:
        return []

    combined = "\n".join(f"- {s}" for s in snippets[:10] if s.strip())
    if not combined:
        return []

    prompt = (
        f"These are Google search result snippets about {company_name}, a property management company.\n\n"
        f"{combined}\n\n"
        "Some snippets may contain tenant review excerpts or star ratings. "
        "List ONLY the resident pain themes you find direct evidence for — "
        "leasing, communication, maintenance, or staff availability issues. "
        "Do not invent themes. If snippets contain no negative resident experiences, return []. "
        "Return ONLY a JSON array of short strings. "
        'Example: ["slow to respond", "maintenance requests ignored"]. '
        "Return [] if no clear pain is present."
    )

    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    try:
        message = await client.messages.create(
            model=HAIKU_MODEL,
            max_tokens=HAIKU_PAIN_MAX_TOKENS,
            messages=[{"role": "user", "content": prompt}],
        )
        text = message.content[0].text.strip()
        match = re.search(r"\[.*\]", text, re.DOTALL)
        if not match:
            return []
        return json.loads(match.group(0))
    except Exception as exc:
        logger.debug("Haiku Serper pain extraction failed for %s: %s", company_name, exc)
        return []


async def extract_company_profile(snippets: list[str], company_name: str) -> dict:
    """Extract employee_count and founded_year from LinkedIn snippets using Claude Haiku.

    Returns a dict with zero or more of: {"employee_count": int, "founded_year": int}.
    Returns {} on any failure or if no API key is configured.
    """
    if not settings.anthropic_api_key or not snippets:
        return {}

    combined = "\n".join(snippets[:8])
    prompt = (
        f"Extract information about {company_name} from these search result snippets.\n\n"
        f"IMPORTANT: Only use snippets that clearly describe {company_name} as a property "
        f"management company. Ignore snippets about unrelated companies with similar names.\n\n"
        f"{combined}\n\n"
        "Return ONLY a JSON object with these keys (use null if not found):\n"
        '{"employee_count": <integer or null>, '
        '"founded_year": <integer or null>, '
        '"portfolio_size": <integer: total units/communities/properties managed, or null>}'
    )

    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    try:
        message = await client.messages.create(
            model=HAIKU_MODEL,
            max_tokens=HAIKU_MAX_TOKENS,
            messages=[{"role": "user", "content": prompt}],
        )
        text = message.content[0].text.strip()
        # Haiku sometimes wraps output in markdown code fences — extract raw JSON
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            logger.debug("Haiku: no JSON object found in response for %s", company_name)
            return {}
        data = json.loads(match.group(0))
        result: dict = {}
        if data.get("employee_count") is not None:
            result["employee_count"] = int(data["employee_count"])
        if data.get("founded_year") is not None:
            result["founded_year"] = int(data["founded_year"])
        if data.get("portfolio_size") is not None:
            result["portfolio_size"] = int(data["portfolio_size"])
        return result
    except Exception as exc:
        logger.debug("Haiku profile extraction failed for %s: %s", company_name, exc)
        return {}
