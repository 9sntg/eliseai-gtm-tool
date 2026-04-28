# API Notes

Per-source quirks, endpoints, response shapes, and rate-limit notes for enrichment. Use this when implementing parsers in `src/gtm/enrichment/` (Phase 3).

---

## Census Geocoder (prerequisite for Census + DataUSA)

| | |
|---|---|
| **Base** | `https://geocoding.geo.census.gov/geocoder/` |
| **Typical endpoint** | `geographies/onelineaddress` or `geographies/address` |
| **Auth** | None |
| **Purpose** | Resolve city/address → Census geographies with FIPS (`STATE`, `PLACE`, `GEOID`, etc.) |

**Response (JSON):** Top-level `result` → `addressMatches` (array). Each match includes matched address text and `geographies`: an object whose keys are geography layer names (e.g. Incorporated Places) mapping to arrays of objects with FIPS-related fields (`GEOID`, `STATE`, `PLACE`, … depending on layer).

**Notes:** Requires `benchmark` and `vintage` query params (e.g. `Public_AR_Current`, `Current_Current`). Parse the **Place** layer for `state` + `place` FIPS used by ACS.

---

## U.S. Census Data API (ACS 5-year, place)

| | |
|---|---|
| **Base** | `https://api.census.gov/data/` |
| **Auth** | Optional `CENSUS_API_KEY` query param for higher limits |
| **Geography** | `place` level using `for=place:{place_fips}&in=state:{state_fips}` |

**Response (JSON):** A **2D JSON array**: first row is column headers (variable names + geography columns), each following row is one record. All cell values are **strings**; cast to int/float in enrichment.

**Notes:** Variable codes are ACS table-specific (e.g. housing tenure, median gross rent, population). Choose a single ACS year (e.g. latest ACS 5-year) and document chosen variables in `census.py` docstring.

---

## Census ACS Multi-Year (replaces defunct DataUSA API)

| | |
|---|---|
| **Base** | `https://api.census.gov/data/{year}/acs/acs5` |
| **Auth** | Optional `CENSUS_API_KEY` query param |
| **Variables** | `B01003_001E` (population), `B19013_001E` (median household income) |
| **Geography** | `for=place:{place_fips}&in=state:{state_fips}` |

**Response (JSON):** Same 2D array format as Census ACS5 — first row is headers, subsequent rows are data. All values are strings.

**Notes:** `datausa.py` fetches two consecutive years (2022 and 2021) concurrently via `asyncio.gather()`, then computes `(cur - prior) / prior` for population and income YoY growth. The DataUSA.io API was retired in 2025; this module now queries Census directly.

---

## Serper (Google Search)

| | |
|---|---|
| **Base** | `https://google.serper.dev` |
| **Auth** | `X-API-KEY` header (`SERPER_API_KEY`) |
| **Endpoint** | `POST /search` (JSON body: `q`, `num`, `gl`, `hl`, …) |

**Response (JSON):** Common keys:

- `organic`: `[{ "title", "link", "snippet", "position", … }]`
- `knowledgeGraph`: optional `{ "title", "type", "description", "website", "attributes", … }`
- `searchParameters`, `relatedSearches`, `credits`, …

**Notes:** Three queries per lead — `"{company} property management"`, `"{company} leasing consultant jobs"`, and `site:linkedin.com/company {company}`. Knowledge graph may be absent. LinkedIn snippets are passed to Claude Haiku to extract `employee_count` and `founded_year`.

---

## SEC EDGAR EFTS (public company detection)

| | |
|---|---|
| **Base** | `https://efts.sec.gov/LATEST/search-index` |
| **Auth** | None — but **requires `User-Agent` header** per EDGAR fair-use policy |
| **Endpoint** | `GET ?q="{company}"&forms=10-K` |

**Response (JSON):** `{ "hits": { "total": { "value": N }, "hits": [ { "_source": { "entity_name": "…", "file_date": "…", "form_type": "…" } } ] } }`

**Notes:** We check if any hit's `entity_name` contains the company name (case-insensitive). A match means the company files 10-K reports → publicly traded. Property management companies are almost always private; a positive result surfaces as an insight bullet only — not scored. User-Agent format: `"EliseAI GTM Tool {contact_email}"`.

---

## BuiltWith (Domain API)

| | |
|---|---|
| **Base** | `https://api.builtwith.com` |
| **Auth** | `KEY` query parameter (`BUILTWITH_API_KEY`) |
| **Endpoint** | Domain API JSON, e.g. `v21` or `v22` `api.json` (confirm current version in BuiltWith docs) |

**Response (JSON):** Root contains **`Results`** (array). Each item includes `Lookup`, `Paths` (array of path objects with `Technologies` arrays). Technology entries often use **PascalCase** keys: `Name`, `Tag`, `Description`, etc.

**Notes:** Free tier may not expose named PM stack products; optional key — empty technologies → scorer redistributes weight per `.claude/rules/scoring.md`.

---

## People Data Labs (Person Enrichment)

| | |
|---|---|
| **Base** | `https://api.peopledatalabs.com/v5` |
| **Auth** | Header `X-Api-Key` (`PDL_API_KEY`) |
| **Endpoint** | `GET /person/enrich` with `email` (and optional hints) |

**Response (JSON):** `{ "status": <int>, "likelihood": <int>, "data": { … } }`. The `data` object follows the [Person Schema](https://docs.peopledatalabs.com/docs/fields) (`job_title`, experience, job company fields, …). Absent fields are `null`.

**Notes:** Map seniority / department from PDL fields used by your scorer. `likelihood` is match confidence (1–10).

---

## Anthropic (Claude) — email generation + LinkedIn extraction

| | |
|---|---|
| **SDK** | `anthropic` Python package |
| **Auth** | `ANTHROPIC_API_KEY` |
| **Email model** | `claude-sonnet-4-6` — 150–200 word outreach draft per lead |
| **Extraction model** | `claude-haiku-4-5-20251001` — structured JSON extraction from LinkedIn snippets |

**Notes:** Email system prompt uses `cache_control: ephemeral` — one cache hit covers all leads in a batch. Haiku extraction parses `employee_count` (int) and `founded_year` (int) from raw LinkedIn search snippets; returns `{}` on any failure. Haiku is ~50× cheaper than Sonnet per token, appropriate for this simple extraction task.

---

## Quick reference: env vars

| Variable | Used for |
|---|---|
| `SERPER_API_KEY` | Serper (3 queries/lead — required) |
| `PDL_API_KEY` | People Data Labs — person enrichment |
| `ANTHROPIC_API_KEY` | Claude Sonnet (email) + Claude Haiku (LinkedIn extraction) |
| `BUILTWITH_API_KEY` | BuiltWith tech stack (optional — paid key required) |
| `CENSUS_API_KEY` | Census Data API rate limit boost (optional) |
