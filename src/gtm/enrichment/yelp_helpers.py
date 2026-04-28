"""Yelp response parsing and Haiku pain-theme extraction helpers."""

from __future__ import annotations

import json
import logging
import re

import anthropic

from gtm.config import settings

logger = logging.getLogger(__name__)

HAIKU_MODEL: str = "claude-haiku-4-5-20251001"
HAIKU_PAIN_MAX_TOKENS: int = 150


def parse_market_avg_rating(businesses: list[dict]) -> float | None:
    """Compute mean Yelp rating from a list of comparable business dicts."""
    ratings = [b["rating"] for b in businesses if b.get("rating") is not None]
    if not ratings:
        return None
    return round(sum(ratings) / len(ratings), 2)


def compute_competitor_rank(
    businesses: list[dict], company_alias: str, company_rating: float
) -> float | None:
    """Return fraction of comparable businesses that rate strictly higher than this company.

    0.0 = best in market, 1.0 = worst in market. Returns None when no comparables available.
    """
    others = [
        b["rating"] for b in businesses
        if b.get("alias") != company_alias and b.get("rating") is not None
    ]
    if not others:
        return None
    pct_above = sum(1 for r in others if r > company_rating) / len(others)
    return round(pct_above, 3)


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

    Returns only themes with clear evidence in the text. May return [] if no pain is present.
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
        "List ONLY the resident pain themes you find direct evidence for in the text above. "
        "Focus on leasing, communication, maintenance responsiveness, or staff availability issues. "
        "Do not invent themes — if the text is neutral or positive, return []. "
        "Return ONLY a JSON array of short strings. "
        'Examples: ["slow maintenance response", "hard to reach leasing office"]. '
        "Return [] if no clear negative experiences are present."
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
        logger.debug("Haiku pain extraction failed for %s: %s", entity_name, exc)
        return []
