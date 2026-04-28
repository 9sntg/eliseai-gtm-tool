"""Serper API response parsing and LinkedIn profile extraction helpers.

Shared by ``serper.py`` to keep the main module under the 200-line limit.
"""

from __future__ import annotations

import json
import logging

import anthropic

from gtm.config import settings
from gtm.models.company import SerperOrganicItem, SerperSearchBucket

logger = logging.getLogger(__name__)

HAIKU_MODEL: str = "claude-haiku-4-5-20251001"
HAIKU_MAX_TOKENS: int = 100


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
    )


async def extract_company_profile(snippets: list[str], company_name: str) -> dict:
    """Extract employee_count and founded_year from LinkedIn snippets using Claude Haiku.

    Returns a dict with zero or more of: {"employee_count": int, "founded_year": int}.
    Returns {} on any failure or if no API key is configured.
    """
    if not settings.anthropic_api_key or not snippets:
        return {}

    combined = "\n".join(snippets[:5])
    prompt = (
        f"Extract information about {company_name} from these LinkedIn search result snippets:\n\n"
        f"{combined}\n\n"
        "Return ONLY a JSON object with these keys (use null if not found):\n"
        '{"employee_count": <integer or null>, "founded_year": <integer or null>}'
    )

    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    try:
        message = await client.messages.create(
            model=HAIKU_MODEL,
            max_tokens=HAIKU_MAX_TOKENS,
            messages=[{"role": "user", "content": prompt}],
        )
        text = message.content[0].text.strip()
        data = json.loads(text)
        result: dict = {}
        if data.get("employee_count") is not None:
            result["employee_count"] = int(data["employee_count"])
        if data.get("founded_year") is not None:
            result["founded_year"] = int(data["founded_year"])
        return result
    except Exception as exc:
        logger.debug("Haiku profile extraction failed for %s: %s", company_name, exc)
        return {}
