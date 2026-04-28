"""Serper API response parsing helpers.

Shared by ``serper.py`` to keep the main module under the 200-line limit.
Converts raw Serper JSON into typed ``SerperSearchBucket`` objects.
"""

from gtm.models.company import SerperOrganicItem, SerperSearchBucket


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
