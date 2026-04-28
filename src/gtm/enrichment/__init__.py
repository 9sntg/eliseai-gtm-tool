"""Enrichment modules — one per API data source.

Each module exposes a single public coroutine:

    async def enrich(lead: RawLead, client: httpx.AsyncClient, cache: FileCache) -> Model

All 7 modules are called concurrently by the pipeline runner via
``asyncio.gather()``. Every ``enrich()`` is guaranteed to return a valid
(possibly empty) Pydantic model and never raises.

Modules:
- ``census``          — ACS5 market data (renter units, rent, population)
- ``datausa``         — population growth and income trends
- ``serper``          — Google search signals (company presence, job postings)
- ``opencorporates``  — company registration, age, jurisdiction
- ``hunter``          — domain-based employee count
- ``builtwith``       — tech stack detection (optional; requires paid key)
- ``pdl``             — contact seniority and department
"""
