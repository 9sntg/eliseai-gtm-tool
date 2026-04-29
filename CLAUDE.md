# EliseAI GTM Lead Enrichment Tool

## What This Is

A pipeline that takes raw inbound leads (property management companies) and automatically enriches, scores, and drafts outreach for each one. SDRs get a scored lead with a ready-to-send email instead of spending 20+ minutes researching manually.

## How to Run

```bash
# Install dependencies
uv sync

# Copy and fill in API keys
cp .env.example .env

# Process all new leads in leads_input.csv
python main.py

# Keep watching for new rows
python main.py --watch

# Run on a daily schedule at a fixed time (e.g. every day at 9am)
python main.py --schedule 09:00

# Launch the Streamlit dashboard
streamlit run app.py
```

## Architecture at a Glance

```
leads_input.csv
      ↓
pipeline/runner.py        ← orchestrates everything
      ↓ asyncio.gather() — 8 calls concurrent
┌──────────────────────────────────────────────┐
│  census.py      datausa.py                   │  ← Market signals
│  serper.py      builtwith.py                 │  ← Company signals
│  edgar.py       pdl.py                       │  ← Company + Person signals
│  yelp.py (company)  yelp.py (building)       │  ← Company + Building signals
└──────────────────────────────────────────────┘
      ↓
scoring/scorer.py         ← 0–119 pts score (up to +20 from Building Fit), 4-category breakdown
      ↓
outreach/email_generator.py  ← Claude Sonnet email + SDR insights
      ↓
outputs/{company}-{address}-{city}-{state}/
  enrichment.json
  assessment.json
  email.txt
```

## Ideal Customer Profile (ICP)

EliseAI's documented customer base spans **mid-market to enterprise property management companies** — not solo operators. Named customers include Greystar, Landmark Properties, Summit Property Management (10,000+ units), and GoldOller. The company serves 1-in-6 rental units in the US across 150+ PM companies.

**Scoring implications:**
- Large companies (Greystar-scale) are valid targets. Do not penalize for size.
- The floor for meaningful interest is approximately 20 employees (past solo-operator scale).
- Student housing, affordable housing, and single-family rental are all in-scope asset types.
- Company age (legacy tech debt) and Yelp rating vs. market average are the strongest company-level signals regardless of size.


## Scoring Model (4 Categories, Additive Point Model)

| Category | Points | Signals |
|---|---|---|
| Market Fit | 38 pts | Renter units (15), renter rate (8), median rent (5), population growth (5), economic momentum (5) |
| Company Fit | 60 pts | Portfolio news (8), tech stack (8), employee count (8), company age (5), portfolio size (6), social presence (5), Yelp rating vs. market avg (6), Google rating (4), pain themes (5), competitor rank (5) |
| Person Fit | 21 pts | Seniority (10), department (7), corporate email (4) |
| Building Fit | 20 pts | Building rating inverted (8), review count (4), price tier (4), pain themes (4). Scores 0 when Yelp building data is unavailable. |

Tiers: 0–40 Low · 41–70 Medium · 71+ High

## Output Structure

Each processed lead gets its own folder under `outputs/`:
```
outputs/greystar-austin-tx/
  enrichment.json   ← raw structured API data
  assessment.json   ← score, breakdown, insights
  email.txt         ← personalized outreach draft
```

Pipeline skips any lead whose output folder already exists (incremental processing).

## Key Design Decisions

- **All API calls are async** (`asyncio` + `httpx`): all 8 enrichment calls fire concurrently per lead via `asyncio.gather()` in `pipeline/runner.py`. Some modules (census, datausa) have internal sequential steps (geocoder runs first), but these are invisible to the caller.
- **All API calls wrap in try/except**: missing data scores zero, pipeline never crashes.
- **BuiltWith is optional**: if no key is present, its signal scores zero in the additive model. No redistribution is needed because absent signals simply contribute 0 pts.
- **Census requires FIPS codes**: `src/gtm/utils/geocoder.py` converts city+state to FIPS before any Census or DataUSA calls. Results are cached per city.
- **Claude prompt is cached**: the system prompt uses `cache_control: ephemeral`, so one cache hit covers all leads in a batch.
- **No magic numbers in scoring**: all point values and thresholds are named constants in `src/gtm/config.py`.
- **Haiku for extraction**: LinkedIn and PM snippets are passed to Claude Haiku to extract `founded_year`, `linkedin_employee_count`, and `portfolio_size`. Pain themes from Yelp and Serper are also extracted via Haiku. Responses are stripped of markdown fences before JSON parsing.

## Environment Variables

See `.env.example` for the full list. Required for production:
- `SERPER_API_KEY`: company search and LinkedIn signals (2 queries per lead)
- `PDL_API_KEY`: contact seniority and function
- `ANTHROPIC_API_KEY`: email draft (Sonnet) and extraction tasks (Haiku)

Optional (tool works without these; signals score zero when absent):
- `BUILTWITH_API_KEY`: tech stack detection
- `YELP_API_KEY`: company and building Yelp signals
- `CENSUS_API_KEY`: higher rate limits on the Census API

## Rules for This Codebase

Full rules live in `.claude/rules/`. Summary:

- **File size**: max 200 lines per file; one responsibility per file
- **Functions**: max ~30 lines; type hints and docstrings on all public functions
- **Logging**: `logging` module everywhere in `src/`; never `print()` except in `main.py` and `app.py`; never log API keys or PII
- **Constants**: no magic numbers; thresholds and weights are named constants
- **Enrichment**: every API call in `try/except`; return empty model on failure; randomized delays; use `FileCache`; handle HTTP status codes per `.claude/rules/enrichment.md`
- **Scoring**: all weights referenced by name from `config.py`; all thresholds named in `scorer.py`; weights must sum to 1.0
- **Outreach**: only use data present in `EnrichedLead`; never hallucinate; system prompt is cached
- **Tests**: mock all external calls; no test touches the network; every module independently testable
- **Reproducibility**: no hardcoded paths; `mkdir(parents=True, exist_ok=True)` everywhere; API keys from `.env` only

## Docs

- [`docs/architecture.md`](docs/architecture.md): full system design, updated after each implementation phase
- [`docs/scoring-logic.md`](docs/scoring-logic.md): threshold rationale for every signal
- [`docs/api-notes.md`](docs/api-notes.md): per-API quirks, endpoints, response shapes, rate limits
- [`docs/rollout-plan.md`](docs/rollout-plan.md): how to roll this out in a real sales org (Part B of assessment)
