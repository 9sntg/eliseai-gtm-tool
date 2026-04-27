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

# Launch the Streamlit dashboard
streamlit run app.py
```

## Architecture at a Glance

```
leads_input.csv
      ↓
pipeline/runner.py        ← orchestrates everything
      ↓ asyncio.gather()
┌─────────────────────────────────────┐
│  census.py    datausa.py            │  ← Market signals
│  serper.py    opencorporates.py     │  ← Company signals
│  hunter.py    builtwith.py  pdl.py  │  ← Company + Person signals
└─────────────────────────────────────┘
      ↓
scoring/scorer.py         ← 0–100 score, 3-category breakdown
      ↓
outreach/email_generator.py  ← Claude API draft email
      ↓
outputs/{company}-{city}-{state}/
  enrichment.json
  assessment.json
  email.txt
```

## Scoring Model (3 Categories)

| Category | Weight | Signals |
|---|---|---|
| Market Fit | 38% | Renter units, renter rate, median rent, population growth, economic momentum |
| Company Fit | 41% | Job postings, portfolio news, tech stack, employee count, company age |
| Person Fit | 21% | Seniority, department, corporate email domain |

Tiers: 0–40 Low · 41–70 Medium · 71–100 High

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

- **All API calls are async** (`asyncio` + `httpx`): 7 enrichment calls fire concurrently per lead
- **All API calls wrap in try/except**: missing data scores zero, pipeline never crashes
- **BuiltWith is optional**: if no key, its 8% weight redistributes to Serper company signal
- **Census requires FIPS codes**: `src/utils/geocoder.py` converts city+state → FIPS before Census/DataUSA calls
- **OpenCorporates uses fuzzy matching**: `difflib` similarity filter (0.6 threshold) to avoid false company matches
- **Claude prompt is cached**: system prompt uses `cache_control: ephemeral` — one cache hit covers all leads in a batch
- **No magic numbers in scoring**: all weights and thresholds are named constants in `src/config.py`

## Environment Variables

See `.env.example` for the full list. Required for production:
- `SERPER_API_KEY` — company search + hiring signals
- `HUNTER_API_KEY` — employee count from domain
- `PDL_API_KEY` — contact seniority and function
- `ANTHROPIC_API_KEY` — email draft generation

Optional (tool works without these, signals score zero):
- `BUILTWITH_API_KEY` — tech stack detection
- `CENSUS_API_KEY` — higher rate limits on Census API

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

- `docs/architecture.md` — full system design, updated after each implementation phase
- `docs/scoring-logic.md` — threshold rationale for every signal
- `docs/api-notes.md` — per-API quirks, endpoints, rate limits
- `docs/rollout-plan.md` — how to roll this out in a real sales org (Part B of assessment)
