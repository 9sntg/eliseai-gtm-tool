"""Yelp response parsing and Haiku pain-theme extraction helpers."""

from __future__ import annotations

import json
import logging
import re

import anthropic

from gtm.config import settings

logger = logging.getLogger(__name__)

HAIKU_MODEL: str = "claude-haiku-4-5-20251001"
HAIKU_MAX_TOKENS: int = 100


def parse_market_avg_rating(businesses: list[dict]) -> float | None:
    """Compute mean Yelp rating from a list of comparable business dicts."""
    ratings = [b["rating"] for b in businesses if b.get("rating") is not None]
    if not ratings:
        return None
    return round(sum(ratings) / len(ratings), 2)


def strip_highlights(sentence: str) -> str:
    """Remove [[HIGHLIGHT]] / [[ENDHIGHLIGHT]] tags from a review_highlights sentence."""
    return re.sub(r"\[\[HIGHLIGHT\]\]|\[\[ENDHIGHLIGHT\]\]", "", sentence).strip()


async def extract_pain_themes(
    highlights: list[dict],
    reviews: list[dict],
    entity_name: str,
    context: str = "company",
) -> list[str]:
    """Extract resident pain themes from Yelp review_highlights + review snippets via Haiku.

    Returns a list of short theme strings (e.g. ["slow maintenance response", "hard to reach"]).
    Returns [] on any failure or if no API key is configured.
    """
    if not settings.anthropic_api_key:
        return []

    texts: list[str] = []
    for h in highlights[:5]:
        sentence = strip_highlights(h.get("sentence", ""))
        if sentence:
            texts.append(sentence)
    for r in reviews[:3]:
        text = r.get("text", "").strip()
        if text:
            texts.append(text)

    if not texts:
        return []

    combined = "\n".join(f"- {t}" for t in texts)
    prompt = (
        f"These are review excerpts about a property management {context} called {entity_name}.\n\n"
        f"{combined}\n\n"
        "List up to 3 short resident pain themes that relate to leasing, communication, "
        "maintenance responsiveness, or staff availability. "
        "Only include themes that are clearly negative resident experiences. "
        'Return ONLY a JSON array of short strings, e.g. ["slow to respond", "hard to reach"]. '
        "Return [] if no pain themes are present."
    )

    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    try:
        message = await client.messages.create(
            model=HAIKU_MODEL,
            max_tokens=HAIKU_MAX_TOKENS,
            messages=[{"role": "user", "content": prompt}],
        )
        text = message.content[0].text.strip()
        match = re.search(r"\[.*\]", text, re.DOTALL)
        if not match:
            return []
        return json.loads(match.group(0))
    except Exception as exc:
        logger.debug("Haiku pain extraction failed for %s: %s", entity_name, exc)
        return []
