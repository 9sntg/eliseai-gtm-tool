# API Notes

Per-source quirks, endpoints, response shapes, and rate-limit notes for enrichment. Use this when implementing parsers in [`src/gtm/enrichment/`](../src/gtm/enrichment/).


## Census Geocoder (prerequisite for Census + DataUSA)

**Why we use it:** The Census ACS API requires numeric FIPS place codes, not city names. The Geocoder is the only free, keyless, officially-supported way to convert a `city + state` string into the `(state_fips, place_fips)` pair required by ACS queries. Without it, Census and DataUSA enrichment cannot run.

| | |
|---|---|
| **Base** | `https://geocoding.geo.census.gov/geocoder/` |
| **Typical endpoint** | `geographies/onelineaddress` or `geographies/address` |
| **Auth** | None |
| **Purpose** | Resolve city/address to Census geographies with FIPS (`STATE`, `PLACE`, `GEOID`, etc.) |

**Response (JSON):** Top-level `result` contains `addressMatches` (array). Each match includes matched address text and `geographies`: an object whose keys are geography layer names (e.g. Incorporated Places) mapping to arrays of objects with FIPS-related fields (`GEOID`, `STATE`, `PLACE`, and others depending on layer).

**Notes:** Requires `benchmark` and `vintage` query params (e.g. `Public_AR_Current`, `Current_Current`). Parse the **Place** layer for `state` and `place` FIPS codes used by ACS.


## U.S. Census Data API (ACS 5-year, place)

**Why we use it:** The Census ACS5 survey is the most granular, publicly available source of housing market data at the city level. It provides renter-occupied unit counts, renter rates, median gross rent, and population — the core Market Fit signals for EliseAI's scoring model. No other free API provides this data at the FIPS-place level.

| | |
|---|---|
| **Base** | `https://api.census.gov/data/` |
| **Auth** | Optional `CENSUS_API_KEY` query param for higher limits |
| **Geography** | `place` level using `for=place:{place_fips}&in=state:{state_fips}` |

**Response (JSON):** A 2D JSON array where the first row is column headers (variable names plus geography columns) and each following row is one record. All cell values are strings; cast to int/float in enrichment.

**Notes:** Variable codes are ACS table-specific (e.g. housing tenure, median gross rent, population). See `census.py` docstring for the exact variable list used.


## Census ACS Multi-Year (replaces defunct DataUSA API)

**Why we use it:** EliseAI needs year-over-year growth signals (population growth, income growth) to identify fast-growing markets where rental demand is rising. The DataUSA.io API was retired in 2025. Querying Census ACS directly for two consecutive years and computing the ratio gives identical data with better reliability.

| | |
|---|---|
| **Base** | `https://api.census.gov/data/{year}/acs/acs5` |
| **Auth** | Optional `CENSUS_API_KEY` query param |
| **Variables** | `B01003_001E` (population), `B19013_001E` (median household income) |
| **Geography** | `for=place:{place_fips}&in=state:{state_fips}` |

**Response (JSON):** Same 2D array format as Census ACS5. All values are strings.

**Notes:** `datausa.py` fetches two consecutive years (2022 and 2021) concurrently via `asyncio.gather()`, then computes `(cur - prior) / prior` for population and income year-over-year growth.


## Serper (Google Search)

**Why we use it:** Serper provides programmatic access to Google Search results, including the knowledge graph (which surfaces Google star ratings, company descriptions, and attributes) and organic results (which contain LinkedIn snippets, Yelp links, social media profiles, and review excerpts from aggregator sites). It is the most cost-effective way to gather company web presence, Google rating, LinkedIn data, and pain theme signals in a single API.

| | |
|---|---|
| **Base** | `https://google.serper.dev` |
| **Auth** | `X-API-KEY` header (`SERPER_API_KEY`) |
| **Endpoint** | `POST /search` (JSON body: `q`, `num`, `gl`, `hl`, etc.) |

**Response (JSON):** Common keys:

- `organic`: `[{ "title", "link", "snippet", "position", ... }]`
- `knowledgeGraph`: optional `{ "title", "type", "description", "website", "attributes", ... }`
- `searchParameters`, `relatedSearches`, `credits`, etc.

**Notes:** Two queries per lead: `"{company} property management"` and `site:linkedin.com/company {company}`. The knowledge graph entry may be absent for smaller companies.

Post-fetch extractions from Serper results (all in [`src/gtm/enrichment/serper_helpers.py`](../src/gtm/enrichment/serper_helpers.py)):
- `extract_yelp_alias`: scans PM-query organic links for `yelp.com/biz/<alias>` pattern
- `extract_social_platforms`: counts distinct non-LinkedIn social domains (Facebook, Instagram, YouTube, Twitter/X, TikTok) in PM-query organic links
- `extract_company_profile` (Haiku): LinkedIn and PM snippets produce JSON with `employee_count`, `founded_year`, and `portfolio_size`
- `extract_serper_pain_themes` (Haiku): PM-query organic snippets often contain Google review excerpts from aggregator sites (apartments.com, Google Maps). Haiku returns only themes with direct evidence; returns `[]` if no negative resident experiences are found. Result stored as `CompanyData.serper_pain_themes` and combined with `yelp_pain_themes` in the `company_pain_themes` scoring signal.

Building name resolution (in `yelp.py._resolve_building_name`): if `lead.property_address` is present, a Serper POST query (`{address} {city} {state} apartments`) resolves the street address to the apartment complex name using the knowledge graph title or first organic result title. The resolved name is then used as the Yelp search term, which dramatically improves match rates compared to searching by raw address.


## SEC EDGAR EFTS (public company detection)

**Why we use it:** Knowing whether a company is publicly traded is valuable SDR context. Public REITs have different buying processes (longer sales cycles, more stakeholders) than private operators. EDGAR is the only free, authoritative source for this signal without a paid data subscription.

| | |
|---|---|
| **Base** | `https://efts.sec.gov/LATEST/search-index` |
| **Auth** | None, but **requires `User-Agent` header** per EDGAR fair-use policy |
| **Endpoint** | `GET ?q="{company}"&forms=10-K` |

**Response (JSON):** `{ "hits": { "total": { "value": N }, "hits": [ { "_source": { "entity_name": "...", "file_date": "...", "form_type": "..." } } ] } }`

**Notes:** We check if any hit's `entity_name` contains the company name (case-insensitive). A match means the company files 10-K reports and is publicly traded. Property management companies are almost always private, so a positive result surfaces as an insight bullet only and is not scored. User-Agent format: `"EliseAI GTM Tool {contact_email}"`.


## BuiltWith (Domain API)

**Why we use it:** BuiltWith is the only widely-used source for detecting specific property management software (Yardi, RealPage, Entrata, MRI, AppFolio) running on a company's website. A company on legacy PM software is a direct displacement opportunity for EliseAI. This signal is one of the highest-value company fit indicators when data is available.

| | |
|---|---|
| **Base** | `https://api.builtwith.com` |
| **Auth** | `KEY` query parameter (`BUILTWITH_API_KEY`) |
| **Endpoint** | Domain API JSON (confirm current version in BuiltWith docs) |

**Response (JSON):** Root contains `Results` (array). Each item includes `Lookup`, `Paths` (array of path objects with `Technologies` arrays). Technology entries use PascalCase keys: `Name`, `Tag`, `Description`, etc.

**Notes:** The free tier does not expose named PM stack product names; detecting Yardi/RealPage/Entrata requires a paid plan. When the key is absent or the API returns no named technologies, the signal scores zero in the additive model. No redistribution is needed.


## People Data Labs (Person Enrichment)

**Why we use it:** PDL provides the most reliable programmatic source for B2B contact data (seniority, department, job title) from a single email address lookup. Knowing whether the contact is a C-suite executive versus a leasing coordinator changes the entire outreach strategy and is the single most important person-level signal.

| | |
|---|---|
| **Base** | `https://api.peopledatalabs.com/v5` |
| **Auth** | Header `X-Api-Key` (`PDL_API_KEY`) |
| **Endpoint** | `GET /person/enrich` with `email` (and optional hints) |

**Response (JSON):** `{ "status": <int>, "likelihood": <int>, "data": { ... } }`. The `data` object follows the PDL Person Schema (`job_title`, `job_company_name`, `job_seniority`, `job_title_role`, etc.). Absent fields are `null`.

**Notes:** Map seniority and department from PDL fields to the scorer's expected values. The `likelihood` field is match confidence (1–10). When PDL returns a job title but no seniority classification, Claude Haiku infers the level from the title text.


## Anthropic (Claude) — email generation + extraction

**Why we use it:** Claude is used for three tasks where structured rule-based extraction would be brittle. First, extracting `founded_year`, `employee_count`, and `portfolio_size` from unstructured LinkedIn snippets. Second, identifying resident pain themes from Yelp review highlights and Serper organic snippets. Third, generating the personalized outreach email and SDR insight bullets. Claude Haiku is used for extraction tasks (cheap, fast, sufficient accuracy); Claude Sonnet is used for email generation where output quality matters.

| | |
|---|---|
| **SDK** | `anthropic` Python package |
| **Auth** | `ANTHROPIC_API_KEY` |
| **Email model** | `claude-sonnet-4-6`: 150–200 word outreach draft per lead |
| **Extraction model** | `claude-haiku-4-5-20251001`: structured JSON extraction from LinkedIn snippets and pain theme lists |

**Notes:** The email system prompt uses `cache_control: ephemeral`. One cache hit covers all leads in a batch, reducing input token costs by approximately 80% for leads 2 through N. Haiku extraction schema: `{"employee_count": int|null, "founded_year": int|null, "portfolio_size": int|null}`. Haiku sometimes wraps output in markdown code fences; `serper_helpers.py` strips them with `re.search(r"\{.*\}", text, re.DOTALL)` before `json.loads`. Pain theme prompts instruct: return only themes with direct evidence, return `[]` if none are present. Haiku is approximately 50x cheaper than Sonnet per token, which makes it appropriate for all extraction tasks.


## Yelp Fusion v3 (company + building enrichment)

**Why we use it:** Yelp is the only free, structured source for resident-facing reviews of property management companies and apartment buildings. A company's Yelp rating relative to local competitors is a direct signal of resident dissatisfaction, which is precisely the pain that EliseAI's AI leasing agent addresses. Building-level Yelp data adds a second, independent signal tied to the specific property in the lead.

| | |
|---|---|
| **Base** | `https://api.yelp.com/v3/businesses` |
| **Auth** | `Authorization: Bearer {YELP_API_KEY}` header |
| **Modules** | [`yelp.py`](../src/gtm/enrichment/yelp.py) (orchestration) and [`yelp_helpers.py`](../src/gtm/enrichment/yelp_helpers.py) (parsing and Haiku extraction) |

**Endpoints used:**

| Endpoint | Purpose |
|---|---|
| `GET /v3/businesses/search?term={name}&location={city,state}&categories=propertymgmt` | Find company by name. Returns `businesses` array with `id`, `alias`, `rating`, `review_count`. |
| `GET /v3/businesses/{id}` | Full profile: `is_claimed`, `attributes.about_this_biz_year_established`, full category list. |
| `GET /v3/businesses/{id}/reviews` | Up to 3 recent reviews with text and star rating. |
| `GET /v3/businesses/{id}/review_highlights` | Aggregated highlight sentences with `review_count`. Strips `[[HIGHLIGHT]]...[ENDHIGHLIGHT]]` tags before use. |
| `GET /v3/businesses/search?categories=propertymgmt&location={city,state}` | Comparables: up to 10 competitor businesses for `market_avg_rating` baseline and competitor rank computation. |

**Response shapes:**

- `/search`: `{ "businesses": [{ "id", "alias", "name", "rating", "review_count", "categories", "location" }] }`
- `/businesses/{id}`: full Yelp business object; `attributes` dict includes `about_this_biz_year_established` (string year)
- `/reviews`: `{ "reviews": [{ "text", "rating" }] }`
- `/review_highlights`: `{ "review_highlights": [{ "sentence": "..[[HIGHLIGHT]]..[[ENDHIGHLIGHT]]..", "review_count": N }] }`

**Notes:**
- `yelp.enrich_company` does its own `/search` independently and does not depend on Serper running first, so both modules run concurrently.
- `yelp.enrich_building` resolves `lead.property_address` to a building name via Serper first, then searches Yelp by that name using `categories=apartments`. Cache key uses the resolved name slug to avoid stale empty results from prior address-based searches.
- `yelp_alias` from Yelp's own response is authoritative. The `serper.yelp_alias` value is used as a fallback only.
- `competitor_rank_pct`: fraction of comparables whose rating is strictly higher than the company's. Computed in `yelp_helpers.compute_competitor_rank`. Stored on `CompanyData.competitor_rank_pct`.
- `price_tier`: Yelp `price` field (`$` through `$$$$`) from either the building profile or the first search result. Stored on `BuildingData.price_tier` and scored as `building_price_tier`.
- `yelp_year_established` (from attributes) is used as a fallback for `founded_year` in `scorer.py`: `c.founded_year or c.yelp_year_established`.
- Pain themes are extracted from `review_highlights` and `reviews` by Claude Haiku. If `ANTHROPIC_API_KEY` is absent, pain themes default to `[]`.
- Market average rating is computed from the comparables search, excluding the target company's own alias. Used in `score_yelp_company_rating` to produce a relative performance signal.
- All Yelp calls are cached via `FileCache`. Cache keys use the format `yelp:co_search:{slug}:{city}`, `yelp:co_profile:{alias}`, etc.


## Quick reference: environment variables

| Variable | Used for |
|---|---|
| `SERPER_API_KEY` | Serper (2 queries per lead, required) |
| `PDL_API_KEY` | People Data Labs: person enrichment |
| `ANTHROPIC_API_KEY` | Claude Sonnet (email) and Claude Haiku (extraction and pain themes) |
| `BUILTWITH_API_KEY` | BuiltWith tech stack (optional; paid key required for named detections) |
| `CENSUS_API_KEY` | Census Data API rate limit boost (optional) |
| `YELP_API_KEY` | Yelp Fusion: company rating, reviews, building data (optional; absent signals score 0) |
