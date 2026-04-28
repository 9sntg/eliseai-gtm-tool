# Architecture

> This document is a living record. It is updated at the end of each implementation phase to reflect what was built, why, and any decisions made.

---

## System Overview

The EliseAI GTM Lead Enrichment Tool is a data pipeline with a lightweight web frontend. It takes raw inbound leads (property management companies) and produces enriched, scored, email-ready records — one per lead — stored as structured files on disk.

The pipeline is designed to run incrementally: it only processes leads that don't already have an output folder, so re-running is always safe and idempotent.

---

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
  │            edgar.py                             │
  │  Person:   pdl.py                               │
  │                                                 │
  │  All 6 calls fire concurrently via              │
  │  asyncio.gather() — ~2s per lead                │
  └─────────────────────────────────────────────────┘
        │
        ▼
  [Scoring Layer]
  scorer.py → 0–100 score + ScoreBreakdown
  (Market: 38%, Company: 41%, Person: 21%)
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

---

## Components

### `src/gtm/config.py`
Centralized settings via `pydantic-settings`. Loads all API keys from `.env`. Defines all scoring weights as named constants (`WEIGHT_RENTER_UNITS`, `WEIGHT_SENIORITY`, etc.) so no magic numbers appear in scoring logic. `Settings` validates that category weights sum to 1.0 at instantiation.

### `src/gtm/models/`
Pydantic models for every data shape in the system (one module per concern, re-exported from `gtm.models`):
- `RawLead` — raw input from CSV
- `MarketData` — Census + DataUSA fields (all optional, default None)
- `CompanyData` — Serper (3 buckets), LinkedIn-extracted employee count + founded year, EDGAR public flag, BuiltWith tech stack (all optional)
- `PersonData` — PDL fields + `is_corporate_email` (derived locally)
- `ScoreBreakdown` — one float per signal + `market_score`, `company_score`, `person_score` subtotals
- `EnrichedLead` — full record: raw lead + all enrichment + score + insights + email draft + slug

### `src/gtm/utils/geocoder.py`
Converts `city + state` → `(state_fips, place_fips)` using the Census Geocoder API (free). Required before any Census or DataUSA queries because those APIs use numeric FIPS codes, not city names. Results are cached to avoid redundant calls for repeated cities.

### `src/gtm/utils/slug.py`
Generates the output folder name for each lead: `{company}-{city}-{state}` (lowercased, non-alphanumeric stripped, spaces to hyphens). Handles slug collisions by appending `-2`, `-3`, etc.

### `src/gtm/utils/cache.py`
Simple JSON file cache backed by `.cache/`. Keyed by SHA-256 of the cache key string. TTL of 24 hours. Used by all enrichment modules to avoid re-hitting APIs during development or re-runs.

### `src/gtm/enrichment/*.py`
Seven modules, one per API. All share the same async interface:
```python
async def enrich(lead: RawLead, client: httpx.AsyncClient) -> DataType
```
All wrap API calls in `try/except`. All return an empty/default model on failure — never raise. Each logs a warning when data is missing.

| Module | API | Returns | Notes |
|---|---|---|---|
| `census.py` | U.S. Census ACS5 | `MarketData` partial | Requires FIPS from geocoder |
| `datausa.py` | Census ACS5 (multi-year) | `MarketData` (growth fields) | Compares 2022 vs 2021 ACS for YoY growth |
| `serper.py` | Serper (Google) | `CompanyData` partial | 3 queries: PM presence, jobs, LinkedIn profile |
| `edgar.py` | SEC EDGAR EFTS | `CompanyData` partial | Public company detection; insight only, not scored |
| `builtwith.py` | BuiltWith | `CompanyData` partial | Optional (paid key required) |
| `pdl.py` | People Data Labs | `PersonData` | Email-only lookup |

### `src/gtm/scoring/scorer_signals.py`
All 13 signal functions and their threshold constants. Each function takes one or two enrichment fields and returns a `float` in `[0.0, 1.0]`. None input always returns `0.0`. No I/O, no config reads — pure computation. Threshold constants are named at module level (no magic numbers in function bodies).

### `src/gtm/scoring/scorer.py`
Orchestrates the 13 signal functions into a final 0–100 score. Handles BuiltWith weight redistribution, computes category subtotals (normalised to 0–100), maps the score to a tier, and generates 3–5 insight bullets. Public entry point: `score_lead(lead) → (score, tier, breakdown)`.

**Scoring categories:**

| Category | Weight | Signals |
|---|---|---|
| Market Fit | 38% | Renter units (15%), renter rate (8%), median rent (5%), population growth (5%), economic momentum (5%) |
| Company Fit | 41% | Job postings (12%), portfolio news (8%), tech stack (8%), employee count (8%), company age (5%) |
| Person Fit | 21% | Seniority (10%), function/department (7%), corporate email (4%) |

### `src/gtm/outreach/email_generator.py`
Drafts a personalized 150–200 word outreach email via Claude Sonnet 4.6. Public entry point: `generate_email(lead) → str | None`.

- `_build_context(lead)` assembles a structured user message from non-None enrichment fields only (contact, market signals, company signals, score). Fields that are None are silently omitted — the email is grounded only in data that was actually retrieved.
- The system prompt (EliseAI context, tone guidelines, no-hallucination constraint, word count) is a module-level constant sent with `cache_control: {"type": "ephemeral"}` — one cache hit covers all leads in a batch.
- Returns `None` on any failure (missing key, API error, empty response). Never returns a generic template.

### `src/gtm/pipeline/runner.py`
Async orchestration layer:
- `enrich_lead(lead, outputs_dir)`: generates slug, skips if output folder exists, fires all 6 enrichment calls concurrently, scores, generates email, writes 3 output files
- `run_pipeline(leads, outputs_dir)`: processes leads sequentially (outer loop respects rate limits), async within each lead

### `main.py`
CLI entry point. Reads `data/leads_input.csv`, calls `run_pipeline()`, renders a Rich progress bar and summary table. Optional `--watch` flag wraps the pipeline in a `watchdog` file-watch loop.

### `app.py`
Streamlit dashboard with 3 tabs:
- **Add Lead** — form to append a new row to `leads_input.csv`
- **Run Pipeline** — lists pending leads, runs enrichment on unprocessed ones
- **View Results** — browse output folders; shows score, Market/Company/Person bar chart, signal breakdown, and email draft

---

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

---

## Key Architectural Decisions

### Why async?
All 6 enrichment calls per lead are fully independent of each other. Firing them concurrently via `asyncio.gather()` brings per-lead enrichment time from ~6s (sequential) to ~2s. The outer loop stays sequential to respect API rate limits.

### Why file-based output instead of a database?
For an MVP with tens to low-hundreds of leads, a filesystem is the most portable and inspectable option. Each lead's folder is self-contained — no schema migrations, no connection strings, and an SDR can open any file directly. A future production version would push these records into a CRM via API.

### Why per-lead folders instead of a flat CSV?
A CSV cell cannot cleanly hold a multi-paragraph email, a full enrichment JSON, and a score breakdown simultaneously. Per-lead folders give each piece of data its natural format (`.json` for structured data, `.txt` for prose) while remaining trivially readable and portable.

### Why BuiltWith is optional
BuiltWith's free tier does not expose named technology detections (only group counts). Detecting Yardi/RealPage/Entrata requires a paid plan. Rather than hardcoding a broken signal, the tool treats BuiltWith as an enhancement: present if a key is configured and returning data, absent otherwise. Its weight redistributes to Serper when absent.

### Why prompt caching for email generation?
All leads in a batch share the same system prompt (EliseAI context, tone, constraints). Anthropic's `cache_control: ephemeral` caches this token block across requests within the 5-minute TTL window. For a 5-lead batch, this cuts input tokens ~80% on leads 2–5.

### Why Census Geocoder as a prerequisite step?
The Census ACS API requires FIPS place codes. The Geocoder API converts free-text city names to FIPS codes. This is a free, keyless API with generous rate limits. The result is cached per city so repeat cities (common in a real lead list) only pay the cost once.

---

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

---

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
| Phase 8 | Streamlit dashboard | — |
| Phase 9 | Docs + README polish + rollout plan (Part B) | — |
