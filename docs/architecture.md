# Architecture

> This document is a living record. It is updated at the end of each implementation phase to reflect what was built, why, and any decisions made.


## System Overview

The EliseAI GTM Lead Enrichment Tool is a data pipeline with a lightweight web frontend. It takes raw inbound leads (property management companies) and produces enriched, scored, email-ready records — one per lead — stored as structured files on disk.

The pipeline is designed to run incrementally: it only processes leads that don't already have an output folder, so re-running is always safe and idempotent.


## High-Level Data Flow

```
data/leads_input.csv
        │
        ▼
  [Read & Parse]
  RawLead objects (Pydantic)
        │
        ▼ for each new lead (no output folder yet)
  ┌─────────────────────────────────────────────────┐
  │           Enrichment Layer (async)              │
  │                                                 │
  │  Market:   census.py ──────── datausa.py        │
  │  Company:  serper.py ─────── builtwith.py       │
  │            edgar.py ──────── yelp.py (company) │
  │  Person:   pdl.py                               │
  │  Building: yelp.py (building)                   │
  │                                                 │
  │  All 8 calls fire concurrently via              │
  │  asyncio.gather() — ~2–3s per lead              │
  └─────────────────────────────────────────────────┘
        │
        ▼
  [Scoring Layer]
  scorer.py → 0–119 pts score + ScoreBreakdown
  (Market: 38 pts, Company: 60 pts, Person: 21 pts, Building: up to 20 pts)
        │
        ▼
  [Email Generation]
  email_generator.py → Claude Sonnet 4.6
  (system prompt cached across batch)
        │
        ▼
  outputs/{slug}/
    enrichment.json
    assessment.json
    email.txt
        │
        ▼
  [Streamlit Dashboard]
  app.py — Add leads, run pipeline, browse results
```


## Components

### `src/gtm/config.py`
Centralized settings via `pydantic-settings`. Loads all API keys from `.env` (including `YELP_API_KEY`). Defines all scoring point values as named constants (`POINTS_RENTER_UNITS`, `POINTS_SENIORITY`, etc.) so no magic numbers appear in scoring logic. An assertion at module level confirms that the 22 core signals sum to exactly 119 pts. The four Building Fit signals (`POINTS_BUILDING_RATING`, `POINTS_BUILDING_REVIEWS`, `POINTS_BUILDING_PRICE_TIER`, `POINTS_BUILDING_PAIN_THEMES`) add up to 20 pts on top of that.

### `src/gtm/models/`
Pydantic models for every data shape in the system (one module per concern, re-exported from `gtm.models`):
- `RawLead`: raw input from CSV
- `MarketData`: Census and DataUSA fields (all optional, default None)
- `CompanyData`: Serper (2 buckets), LinkedIn-extracted employee count and founded year, Haiku-extracted portfolio size, Yelp alias, Yelp rating/review/market-avg/pain-themes/year-established/competitor-rank-pct, Google rating, Serper pain themes, social platform count, EDGAR public flag, BuiltWith tech stack (all optional)
- `BuildingData`: Yelp building-level data including name (resolved via Serper), address, alias, rating, review count, price tier, and pain themes (all optional)
- `PersonData`: PDL fields plus `is_corporate_email` (derived locally)
- `ScoreBreakdown`: one float per signal plus `market_score`, `company_score`, `person_score`, and `building_score` subtotals
- `EnrichedLead`: full record combining raw lead, all enrichment models, building data, score, insights, email draft, and slug

### `src/gtm/utils/geocoder.py`
Converts `city + state` to `(state_fips, place_fips)` using the Census Geocoder API (free, no key required). This step is required before any Census or DataUSA queries because those APIs use numeric FIPS codes, not city names. Results are cached to avoid redundant calls for repeated cities.

### `src/gtm/utils/slug.py`
Generates the output folder name for each lead in the format `{company}-{address}-{city}-{state}` (lowercased, non-alphanumeric stripped, spaces to hyphens). Including the address ensures that the same company can have multiple leads for different buildings without slug collision. Handles remaining collisions by appending `-2`, `-3`, etc.

### `src/gtm/utils/cache.py`
Simple JSON file cache backed by `.cache/`. Keyed by SHA-256 of the cache key string. TTL of 24 hours. Used by all enrichment modules to avoid re-hitting APIs during development or re-runs.

### `src/gtm/enrichment/*.py`
Eight modules, one per API. All share the same async interface:
```python
async def enrich(lead: RawLead, client: httpx.AsyncClient) -> DataType
```
All wrap API calls in `try/except`. All return an empty or default model on failure and never raise. Each logs a warning when data is missing.

| Module | API | Returns | Notes |
|---|---|---|---|
| `census.py` | U.S. Census ACS5 | `MarketData` partial | Requires FIPS from geocoder |
| `datausa.py` | Census ACS5 (multi-year) | `MarketData` (growth fields) | Compares 2022 vs 2021 ACS for YoY growth |
| `serper.py` | Serper (Google) | `CompanyData` partial | 2 queries: PM presence, LinkedIn profile; Google rating from knowledgeGraph |
| `edgar.py` | SEC EDGAR EFTS | `CompanyData` partial | Public company detection; insight only, not scored |
| `builtwith.py` | BuiltWith | `CompanyData` partial | Optional (paid key required) |
| `pdl.py` | People Data Labs | `PersonData` | Email-only lookup |
| `yelp.py` | Yelp Fusion v3 | `CompanyData` + `BuildingData` | `enrich_company`: rating, reviews, market avg, pain themes. `enrich_building`: building-level Yelp data. Both are optional and require `YELP_API_KEY`. |

### `src/gtm/scoring/scorer_signals.py`
All 22 signal functions and their threshold constants. Each function takes one or two enrichment fields and returns a `float` in `[0.0, 1.0]`. A None input always returns `0.0`. There is no I/O or config reads; this is pure computation. Threshold constants are named at module level so no magic numbers appear in function bodies.

### `src/gtm/scoring/scorer.py`
Orchestrates signal functions into a final score using an additive point model. Each signal contributes 0 to N points when it fires, and 0 when data is absent. No redistribution is needed. Baseline max is 119 pts across three categories; Building Fit adds up to 20 pts when Yelp building data is available. Computes category subtotals (normalised to 0–100 for display), maps the score to a tier, and generates SDR insight bullets. Public entry point: `score_lead(lead) → (score, tier, breakdown)`.

**Scoring signals:**

| Category | Points | Signals |
|---|---|---|
| Market Fit | 38 pts | Renter units (15), renter rate (8), median rent (5), population growth (5), economic momentum (5) |
| Company Fit | 60 pts | Portfolio news (8), tech stack (8), employee count (8), company age (5), portfolio size (6), social media presence (5), Yelp company rating vs. market avg (6), Google company rating (4), company pain themes / Yelp+Serper (5), competitor rank on Yelp (5) |
| Person Fit | 21 pts | Seniority (10), function/department (7), corporate email (4) |
| Building Fit | up to 20 pts | Building rating inverted (8), building review count (4), building price tier (4), building pain themes (4). Scores 0 when Yelp building data is absent. |

### `src/gtm/outreach/email_generator.py`
Drafts a personalized 150–200 word outreach email and three SDR insight bullets via Claude Sonnet 4.6. Public entry point: `generate_outreach(lead, breakdown) → (str | None, list[str])`.

- `_build_context(lead)` assembles a structured user message from non-None enrichment fields only (contact, market signals, company signals, score). Fields that are None are silently omitted so the email is grounded only in data that was actually retrieved.
- The system prompt (EliseAI context, tone guidelines, no-hallucination constraint, word count) is loaded from `system_prompt.md` and sent with `cache_control: {"type": "ephemeral"}`. One cache hit covers all leads in a batch.
- Returns `(None, [])` on any failure (missing key, API error, empty response). Never returns a generic template.

### `src/gtm/pipeline/runner.py`
Async orchestration layer:
- `enrich_lead(lead, outputs_dir)`: generates slug, skips if output folder exists, fires all 8 enrichment calls concurrently (including `yelp.enrich_company` and `yelp.enrich_building`), scores, generates email, writes 3 output files.
- `run_pipeline(leads, outputs_dir)`: processes leads sequentially in the outer loop (to respect API rate limits), async within each lead.

### `main.py`
CLI entry point. Reads `data/leads_input.csv`, calls `run_pipeline()`, renders a Rich progress bar and summary table. Three mutually exclusive run modes:

- Default (no flag): runs once and exits.
- `--watch`: re-runs whenever `leads_input.csv` changes, using `watchdog`.
- `--schedule HH:MM`: runs immediately on startup, then sleeps until the next daily occurrence of the specified time and repeats. Uses `_seconds_until()` (stdlib `datetime` only, no external scheduler library).

### `src/gtm/dashboard/helpers.py`
Rendering helpers and sync pipeline runner for the Streamlit dashboard. Keeps `app.py` under 200 lines by extracting all reusable logic:
- `load_leads_from_csv` / `append_lead_to_csv` — CSV I/O with error suppression
- `list_output_folders` / `load_lead_data` — filesystem navigation for the results tab
- `run_pipeline_sync` — runs the async pipeline in a dedicated thread to avoid Streamlit's event-loop conflict
- `render_*` helpers — score header, 4-category metrics (Market/Company/Person/Building), signal table, market/company/person/building/email sections

### `app.py`
Streamlit dashboard with 3 tabs:
- **Add Lead** — form to append a new row to `leads_input.csv`
- **Run Pipeline** — lists pending leads, runs enrichment on unprocessed ones, shows progress spinner
- **View Results** — selectbox over processed leads; renders score, tier, Market/Company/Person/Building subtotals, 23-signal breakdown table, enrichment data (including Yelp company + building sections with Google rating, pain themes, competitor rank, price tier), and email draft in a 2-column layout


## Output Structure

```
outputs/
  {company}-{city}-{state}/
    enrichment.json   ← MarketData + CompanyData + PersonData as serialized JSON
    assessment.json   ← score, tier, ScoreBreakdown, insights (list of 3–5 bullet strings)
    email.txt         ← plain-text outreach draft
```

**Slug examples:** `greystar-austin-tx`, `lincoln-property-company-charlotte-nc`

The pipeline checks for slug folder existence before processing any lead. This is the idempotency mechanism: safe to re-run at any time.


## Key Architectural Decisions

### Why async?
From the pipeline runner's perspective, all 8 enrichment calls per lead are fully independent of each other. `runner.py` fires them concurrently via `asyncio.gather()`, bringing per-lead enrichment time from approximately 8 seconds (sequential) to 2–3 seconds. The outer loop stays sequential to respect API rate limits.

Internally, some modules have sequential steps that are invisible to the caller. `census.py` and `datausa.py` both call the Census Geocoder first, then issue their ACS queries. `yelp.enrich_company` runs a search, then fires profile, reviews, and highlights concurrently with an internal `asyncio.gather()`. These internal sequences are each module's private concern and do not block other modules from running.

### Why file-based output instead of a database?
For an MVP with tens to low-hundreds of leads, a filesystem is the most portable and inspectable option. Each lead's folder is self-contained, with no schema migrations or connection strings required. An SDR can open any file directly. A future production version would push these records into a CRM via API.

### Why per-lead folders instead of a flat CSV?
A CSV cell cannot cleanly hold a multi-paragraph email, a full enrichment JSON, and a score breakdown simultaneously. Per-lead folders give each piece of data its natural format (`.json` for structured data, `.txt` for prose) while remaining trivially readable and portable.

### Why BuiltWith is optional
BuiltWith's free tier does not expose named technology detections, only group counts. Detecting Yardi/RealPage/Entrata requires a paid plan. Rather than hardcoding a broken signal, the tool treats BuiltWith as an enhancement that is present if a key is configured and returning data, and absent otherwise. In the additive model, absent signals simply contribute 0 pts. No redistribution is needed.

### Why prompt caching for email generation?
All leads in a batch share the same system prompt (EliseAI context, tone, constraints). Anthropic's `cache_control: ephemeral` caches this token block across requests within the 5-minute TTL window. For a 5-lead batch, this cuts input tokens by approximately 80% on leads 2 through 5.

### Why Census Geocoder as a prerequisite step?
The Census ACS API requires FIPS place codes. The Geocoder API converts free-text city names to FIPS codes. It is a free, keyless API with generous rate limits. The result is cached per city so repeat cities (common in a real lead list) only pay the geocoding cost once.


## Technology Choices

| Concern | Choice | Reason |
|---|---|---|
| HTTP client | `httpx` | Async-native, clean API, works with `asyncio.gather()` |
| Data models | `pydantic` v2 | Type safety, IDE support, built-in JSON serialization |
| Config | `pydantic-settings` | `.env` loading with type validation and defaults |
| AI | `anthropic` SDK | Required for Claude API; prompt caching built-in |
| Dashboard | `streamlit` | Fast to build, no frontend knowledge needed, good for internal tools |
| Package manager | `uv` | Lockfile-based, fast, drop-in pip replacement |
| Linting | `ruff` | Single tool replacing flake8 + isort + black |
| Testing | `pytest` + `pytest-asyncio` + `pytest-mock` | Standard Python testing; async support; easy mocking |

Per-API endpoints, quirks, and response envelopes are summarized in [`api-notes.md`](./api-notes.md).


## Phase Log

| Phase | What was built | Status |
|---|---|---|
| Phase 0 | Scaffolding: pyproject.toml, .env.example, .gitignore, CLAUDE.md, sample CSV, docs stub | ✅ Done |
| Phase 1 | Config + Models (`src/gtm/config.py`, `src/gtm/models/`, import path `gtm`) | ✅ Done |
| Phase 2 | Utilities: `geocoder.py`, `slug.py`, `cache.py` + `tests/conftest.py` | ✅ Done |
| Phase 3 | Enrichment: 7 modules + `exceptions.py` + `utils/email.py` + `test_enrichment.py` | ✅ Done |
| Phase 4 | Scoring: `src/gtm/scoring/scorer.py`, `scorer_signals.py`, `tests/test_scorer.py`, `docs/scoring-logic.md` | ✅ Done |
| Phase 5 | Email generation: `src/gtm/outreach/email_generator.py`, `tests/test_email_generator.py` | ✅ Done |
| Phase 6 | Pipeline runner + main.py: `src/gtm/pipeline/runner.py` (`enrich_lead`, `run_pipeline`, merge helpers, file writer), `main.py` (CLI, Rich progress, `--watch`) + `tests/test_pipeline.py` | ✅ Done |
| Phase 7 | API migration: removed Hunter + OpenCorporates; added `serper.py` LinkedIn 3rd query + Claude Haiku extraction (`founded_year`, `linkedin_employee_count`); added `edgar.py` (SEC EDGAR public company flag); EDGAR `User-Agent` fix; geocoder places fallback; `_safe()` wrapper in runner; Census ACS multi-year in `datausa.py` | ✅ Done |
| Phase 8 | Streamlit dashboard: `app.py` (3-tab UI), `src/gtm/dashboard/helpers.py` (render helpers, sync pipeline runner, CSV I/O) | ✅ Done |
| Phase 9 | Additive point scoring model, Serper signal expansion (job_count regex, portfolio_size via Haiku, yelp_alias, social_platform_count), bonus signals (portfolio_size +6 pts, social_presence +5 pts), ICP documentation, docs + rollout plan | ✅ Done |
| Phase 10 | Yelp Fusion enrichment (company: rating/reviews/market avg/pain themes; building: rating/reviews/pain themes), BuildingData model, Company Fit expanded to 58 pts (portfolio_size + social_presence moved into baseline; yelp_company_rating +6 pts), Building Fit bonus (+12 pts), baseline max 100→117 pts, Serper Google rating extraction, Yelp fallback for founded_year, dashboard and email updated for 4-category model | ✅ Done |
| Phase 11 | Full signal utilisation: 5 new scoring signals (google_company_rating +4 pts, company_pain_themes +5 pts, competitor_rank +5 pts, building_price_tier +4 pts, building_pain_themes +4 pts), Serper pain theme extraction via Haiku, building name resolution via Serper → Yelp, address-aware slug for per-building idempotency, baseline max 117→131 pts, Building bonus 12→20 pts, dashboard 18→23 signals, email context updated | ✅ Done |
| Phase 12 | Dashboard UI overhaul (sidebar stats + integrations, Overview table with score bars, Lead Details with inner Enrichment/Scoring/Outreach tabs, tag chips for categorical fields, consistent HTML table style across all 8 tables, category mini-cards, signal table with per-signal bars and reason sentences); output format restructure (`enrichment.json`: 4 sections — contact/market/company/building; `assessment.json`: lead_score, tier, key_observations, market_fit/company_fit/person_fit/building_fit, signals list with name/category/points/max_points/reason); new `src/gtm/scoring/reasons.py` shared by pipeline writer and dashboard | ✅ Done |
| Phase 13 | AI-generated outreach: `generate_email` replaced by `generate_outreach(lead, breakdown)` returning `(email, insights)`; system prompt moved to `src/gtm/outreach/system_prompt.md` with rich EliseAI context (products, named customer outcomes, pain points), combined email + 3 SDR insights task, no-dashes rule; scoring breakdown injected into Claude context; rule-based `generate_insights()` kept as fallback; `test_email_generator.py` rewritten for new interface | ✅ Done |
| Phase 14 | Signal accuracy + outreach polish: `score_seniority(None)` and `score_department_function(None)` fixed to return 0.0 (no data = no points); `signal_reason()` threshold fixed (`> 0.1` not `>= 0.1`) so absent-data signals display correct reason tier; Claude Haiku fallback in `pdl.py` infers seniority from job title when PDL returns none; email prompt updated with standalone greeting line (`Hi [Name],`) and explicit sign-off (`Best, / EliseAI`) | ✅ Done |
| Phase 15 | Job postings signal removed (unreliable board-level counts from Serper job query): `POINTS_JOB_POSTINGS` removed from config, `score_job_postings` removed from scorer_signals, Serper reduced to 2 queries/lead, Company Fit baseline 72→60 pts, total baseline 131→119 pts; tier thresholds documented (Low 0–40 / Medium 41–70 / High 71+); enterprise lead batch added (Greystar, RPM Living, Lincoln Property, BH Management, Bell Partners) with real apartment building addresses; all docs, tests, and dashboard helpers updated for 119-pt model | ✅ Done |
| Phase 16 | Daily scheduler: `--schedule HH:MM` CLI flag added to `main.py` (mutually exclusive with `--watch`); runs pipeline immediately on startup then sleeps until the next daily occurrence of the specified time; `_seconds_until()` helper accepts optional `_now` param for testability without mocking datetime; `tests/test_scheduler.py` with 9 tests covering `_seconds_until` boundaries and `_schedule_loop` behavior; README and rollout-plan updated | ✅ Done |
