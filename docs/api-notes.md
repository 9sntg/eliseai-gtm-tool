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

**Notes:** Three queries per lead — `"{company} property management"`, `"{company} leasing consultant jobs"`, and `site:linkedin.com/company {company}`. Knowledge graph may be absent.

Post-fetch extractions from Serper results (all in `serper_helpers.py`):
- `extract_job_count`: regex `(\d[\d,]*)\s+(?:\w+\s+){0,3}jobs?` over jobs-query snippets; returns the largest real job count found (not organic result count)
- `extract_yelp_alias`: scans PM-query organic links for `yelp.com/biz/<alias>` pattern
- `extract_social_platforms`: counts distinct non-LinkedIn social domains (Facebook, Instagram, YouTube, Twitter/X, TikTok) in PM-query organic links
- `extract_company_profile` (Haiku): LinkedIn + PM snippets → JSON with `employee_count`, `founded_year`, `portfolio_size`
- `extract_serper_pain_themes` (Haiku): PM-query organic snippets often contain Google review excerpts from aggregator sites (apartments.com, Google Maps). Haiku returns only themes with direct evidence; returns `[]` if no negative resident experiences found. Result stored as `CompanyData.serper_pain_themes` and combined with `yelp_pain_themes` in the `company_pain_themes` scoring signal.

Building name resolution (in `yelp.py._resolve_building_name`): if `lead.property_address` is present, a Serper POST query (`{address} {city} {state} apartments`) is issued to resolve the street address to the apartment complex name (from knowledge graph title or first organic result). The resolved name is then used as the Yelp search term, dramatically improving match rates versus searching by raw address. Result is cached separately from the Yelp search.

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

**Notes:** Email system prompt uses `cache_control: ephemeral` — one cache hit covers all leads in a batch. Haiku extraction schema: `{"employee_count": int|null, "founded_year": int|null, "portfolio_size": int|null}` — extracts from combined LinkedIn + PM snippets (up to 8). Haiku sometimes wraps output in markdown code fences; `serper_helpers.py` strips them with `re.search(r"\{.*\}", text, re.DOTALL)` before `json.loads`. Returns `{}` on any failure. Haiku is also used for pain theme extraction (Yelp `review_highlights` + `reviews` → `list[str]`; Serper PM snippets → `list[str]`). Pain theme prompts instruct: return only themes with direct evidence, return `[]` if none present — do not invent themes or return a fixed count. Haiku is ~50× cheaper than Sonnet per token, appropriate for all extraction tasks.

---

## Yelp Fusion v3 (company + building enrichment)

| | |
|---|---|
| **Base** | `https://api.yelp.com/v3/businesses` |
| **Auth** | `Authorization: Bearer {YELP_API_KEY}` header |
| **Modules** | `yelp.py` (orchestration) + `yelp_helpers.py` (parsing + Haiku extraction) |

**Endpoints used:**

| Endpoint | Purpose |
|---|---|
| `GET /v3/businesses/search?term={name}&location={city,state}&categories=propertymgmt` | Find company by name → returns `businesses` array with `id`, `alias`, `rating`, `review_count` |
| `GET /v3/businesses/{id}` | Full profile: `is_claimed`, `attributes.about_this_biz_year_established`, full category list |
| `GET /v3/businesses/{id}/reviews` | Up to 3 recent reviews with text + star rating |
| `GET /v3/businesses/{id}/review_highlights` | Aggregated highlight sentences with `review_count`. Strips `[[HIGHLIGHT]]...[ENDHIGHLIGHT]]` tags before use. |
| `GET /v3/businesses/search?categories=apartments,propertymgmt&location={city,state}` | Comparables: 3–5 competitor businesses for `market_avg_rating` baseline |

**Response shapes:**

- `/search` → `{ "businesses": [{ "id", "alias", "name", "rating", "review_count", "categories", "location" }] }`
- `/businesses/{id}` → full Yelp business object; `attributes` dict includes `about_this_biz_year_established` (string year)
- `/reviews` → `{ "reviews": [{ "text", "rating" }] }`
- `/review_highlights` → `{ "review_highlights": [{ "sentence": "..[[HIGHLIGHT]]..[[ENDHIGHLIGHT]]..", "review_count": N }] }`

**Notes:**
- `yelp.enrich_company` does its own `/search` independently (does not depend on Serper running first), so both modules can run concurrently.
- `yelp.enrich_building` resolves `lead.property_address` to a building name via Serper first, then searches Yelp by that name + `categories=apartments`. Cache key uses the resolved name slug to avoid stale empty results from prior address-based searches.
- `yelp_alias` from Yelp's own response is authoritative; `serper.yelp_alias` is a fallback.
- `competitor_rank_pct`: fraction of `/search` comparables whose rating is strictly higher than the company's. Computed in `yelp_helpers.compute_competitor_rank`. Stored on `CompanyData.competitor_rank_pct`.
- `price_tier`: Yelp `price` field (`$`–`$$$$`) from either the building profile or the first search result. Stored on `BuildingData.price_tier` and scored as `building_price_tier`.
- `yelp_year_established` (from attributes) is used as a fallback for `founded_year` in `scorer.py`: `c.founded_year or c.yelp_year_established`.
- Pain themes are extracted from `review_highlights` + `reviews` by Claude Haiku (`claude-haiku-4-5-20251001`). If `ANTHROPIC_API_KEY` is absent, pain themes default to `[]`.
- Market avg rating computed from `/search` comparables (excluding the target company's own alias). Used in `score_yelp_company_rating` to produce a relative performance signal.
- All Yelp calls are cached via `FileCache`. Keys: `yelp:search:{company}:{city}:{state}`, `yelp:biz:{id}`, etc.

---

## Quick reference: env vars

| Variable | Used for |
|---|---|
| `SERPER_API_KEY` | Serper (3 queries/lead — required) |
| `PDL_API_KEY` | People Data Labs — person enrichment |
| `ANTHROPIC_API_KEY` | Claude Sonnet (email) + Claude Haiku (LinkedIn extraction + Yelp pain theme extraction) |
| `BUILTWITH_API_KEY` | BuiltWith tech stack (optional — paid key required) |
| `CENSUS_API_KEY` | Census Data API rate limit boost (optional) |
| `YELP_API_KEY` | Yelp Fusion — company rating, reviews, building data (optional — absent signals score 0) |
