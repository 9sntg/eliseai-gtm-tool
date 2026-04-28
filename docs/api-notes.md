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

## Data USA API

| | |
|---|---|
| **Base** | `https://datausa.io/api/data` (and related paths — confirm exact URL for your cube) |
| **Auth** | None |
| **Docs** | [Data USA API](https://datausa.io/about/api) |

**Response (JSON):** `{ “data”: [ { “ID Geography”: “…”, “Geography”: “…”, “Year”: “…”, <measure>: <value>, … }, … ], “source”: [ … ] }`. The `data` field is an array of **objects** (not arrays). Field names are human-readable strings, not codes.

**Notes:** Access values by field name directly — no column-zipping needed. Pick measures for population growth and income / momentum aligned with PRD scoring.

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

**Notes:** Two queries per lead (company + jobs). Knowledge graph may be absent. Snippets are the main signal for hiring and news.

---

## OpenCorporates

| | |
|---|---|
| **Base** | `https://api.opencorporates.com` (versioned path, e.g. `/v0.4/`) |
| **Auth** | API token query param on paid; free tier limits apply |
| **Search** | `GET .../companies/search?q=...` |

**Response (JSON):** `{ "api_version", "results": { "companies": [ { "company": { … } } ], …pagination… } }`

**Company object (typical):** `name`, `company_number`, `jurisdiction_code`, `incorporation_date`, `current_status`, `company_type`, links, etc.

**Notes:** Use fuzzy match / jurisdiction filters client-side per product rules. Pagination via `page` / `per_page`.

---

## Hunter.io (Domain Search)

| | |
|---|---|
| **Base** | `https://api.hunter.io/v2` |
| **Auth** | `api_key` query parameter |
| **Endpoint** | `GET /domain-search?domain=...` |

**Response (JSON):** `data` + `meta`. `data` includes `domain`, `organization`, pattern flags (`webmail`, `disposable`, `accept_all`), `emails[]` (each with `value`, `confidence`, `seniority`, `department`, `position`, …). `meta` includes `results`, `limit`, `offset`, `params`.

**Notes:** Employee count for the **organization** may not appear on all plans or endpoints; the PRD uses Hunter as a size signal — confirm which field your account returns and map it to `CompanyData.hunter_employee_count`. Do not log raw email payloads at INFO.

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

## Anthropic (Claude) — outreach only

| | |
|---|---|
| **SDK** | `anthropic` Python package |
| **Auth** | `ANTHROPIC_API_KEY` |
| **Model** | `claude-sonnet-4-6` per `.claude/rules/outreach.md` |

**Notes:** System prompt uses prompt caching (`cache_control: ephemeral`). Not used in enrichment Phase 3.

---

## Quick reference: env vars

| Variable | Used for |
|---|---|
| `SERPER_API_KEY` | Serper |
| `HUNTER_API_KEY` | Hunter |
| `PDL_API_KEY` | PDL |
| `ANTHROPIC_API_KEY` | Claude / email |
| `BUILTWITH_API_KEY` | BuiltWith (optional) |
| `CENSUS_API_KEY` | Census Data API (optional) |
