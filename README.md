# EliseAI GTM Lead Enrichment Tool

Automates the top-of-funnel SDR workflow for property management leads. Takes a raw lead list, enriches each lead with market, company, building, and person intelligence, scores it using an additive point model (119-pt baseline, up to +20 building bonus), and drafts a personalized outreach email. Reps act immediately instead of spending 20+ minutes researching each lead.

---

## What It Does

1. **Enriches** each lead across four layers using public APIs:
   - **Market:** renter density, rent levels, population growth (Census ACS5)
   - **Company:** portfolio signals, tech stack, employee count, Yelp rating, pain themes, social presence (Serper, BuiltWith, SEC EDGAR, Yelp Fusion)
   - **Building:** Yelp data for the specific apartment building the company manages (rating, price tier, resident pain themes)
   - **Person:** seniority, department, decision-maker signals (People Data Labs)

2. **Scores** each lead using an additive point model with 22 signals across four categories:
   - Market Fit (38 pts) · Company Fit (60 pts) · Person Fit (21 pts) · Building Fit bonus (up to +20 pts)

3. **Drafts** a personalized outreach email using Claude Sonnet, grounded only in enriched data

4. **Outputs** structured files per lead: enrichment data, score breakdown, and email draft

5. **Dashboard:** a Streamlit UI to add leads, run the pipeline, and browse results

---

## Quick Start

### Prerequisites

- Python 3.12+
- [`uv`](https://docs.astral.sh/uv/getting-started/installation/) — `curl -LsSf https://astral.sh/uv/install.sh | sh`

### Setup

```bash
# 1. Clone and enter the project
git clone <repo-url>
cd eliseai-gtm-tool

# 2. Install dependencies
uv sync

# 3. Configure API keys
cp .env.example .env
# Edit .env and fill in your keys (see API Keys section below)

# 4. Add your leads
# Edit data/leads_input.csv — or use the dashboard to add them one by one
```

### Run

```bash
# Process all new leads via CLI
uv run python main.py

# Or launch the dashboard
uv run streamlit run app.py
```

---

## API Keys

Add these to your `.env` file. The tool degrades gracefully when optional keys are missing — those signals score zero.

| Key | Required | Free Tier | Get It |
|---|---|---|---|
| `ANTHROPIC_API_KEY` | Yes | Pay-per-use | [console.anthropic.com](https://console.anthropic.com) |
| `SERPER_API_KEY` | Yes | 2,500 searches | [serper.dev](https://serper.dev) |
| `PDL_API_KEY` | Yes | 100 req/month | [peopledatalabs.com](https://peopledatalabs.com) |
| `BUILTWITH_API_KEY` | No | Paid only for tech stack | [builtwith.com/api](https://builtwith.com/api) |
| `CENSUS_API_KEY` | No | Generous without key | [api.census.gov](https://api.census.gov/data/key_signup.html) |

> **Note on BuiltWith:** The free tier does not expose named technology detections. Detecting Yardi/RealPage/Entrata requires a paid plan. When absent, the tech stack signal scores 0 — other signals are unaffected (additive model).

> **Note on SEC EDGAR:** Used for public company detection (free, no key required). Surfaces as an insight bullet only — not scored, since most PM companies are private.

---

## Usage

### CLI

```bash
# Process all leads in data/leads_input.csv (skips already-processed leads)
uv run python main.py

# Watch for new rows and process automatically
uv run python main.py --watch

# Process a specific input file
uv run python main.py --input path/to/leads.csv
```

### Dashboard

```bash
uv run streamlit run app.py
```

The dashboard has three tabs:

| Tab | What it does |
|---|---|
| Add Lead | Form to add a new lead. Appends a row to `data/leads_input.csv`. |
| Run Pipeline | Lists unprocessed leads. The run button enriches and scores all pending leads. |
| View Results | Browse all processed leads with score breakdown and email draft. |

---

## Input Format

`data/leads_input.csv` — one row per lead:

```
name,email,company,property_address,city,state
Sarah Mitchell,sarah.mitchell@greystar.com,Greystar Real Estate Partners,2700 Post Oak Blvd,Austin,TX
```

---

## Output Format

Each processed lead gets its own folder under `outputs/`:

```
outputs/
  greystar-3333-harry-hines-blvd-dallas-tx/
    enrichment.json    ← structured data from all 8 enrichment modules
    assessment.json    ← lead_score, tier, category subtotals, per-signal breakdown
    email.txt          ← personalized outreach draft
```

The pipeline is **incremental**: it checks for existing output folders before processing. Re-running is always safe.

The slug includes the property address so the same company can have multiple leads for different buildings without collision.

### Score Tiers

| Range | Tier | SDR Action |
|---|---|---|
| 71+ | High | Prioritize. Reach out today. |
| 41–70 | Medium | Worth outreach, not urgent. |
| 0–40 | Low | Nurture only. |

---

## Scoring Model

Additive point model: each signal contributes 0 to N points when it fires, and 0 when data is absent. Missing signals do not affect other signals. Baseline max is 119 pts across three categories. Four Building Fit bonus signals can push the total above 119 when Yelp building data is available.

**Market Fit (38 pts):** Is this market worth targeting?
- Renter-occupied units (15 pts), renter rate (8 pts), median rent (5 pts), population growth (5 pts), economic momentum (5 pts)

**Company Fit (60 pts):** Is this company a real opportunity?
- Portfolio news and web presence (8 pts), legacy tech stack (8 pts), employee count (8 pts), company age (5 pts), portfolio size (6 pts), social media presence (5 pts), Yelp rating vs. market average (6 pts), Google rating (4 pts), company pain themes (5 pts), competitor rank on Yelp (5 pts)

**Person Fit (21 pts):** Is this contact a decision maker?
- Seniority (10 pts), department and function (7 pts), corporate email domain (4 pts)

**Building Fit bonus (up to +20 pts):** Fires when Yelp building data is available. Absence never penalizes a lead.
- Building rating inverted (8 pts), review count (4 pts), price tier (4 pts), pain themes (4 pts)

Full threshold documentation: [`docs/scoring-logic.md`](docs/scoring-logic.md)

---

## Development

```bash
# Run tests (all external calls are mocked — no network required)
uv run pytest

# Lint and format
uv run ruff check .
uv run ruff format .
```

### Project Structure

```
eliseai-gtm-tool/
├── app.py                   # Streamlit dashboard
├── main.py                  # CLI entry point
├── data/leads_input.csv     # Lead input file
├── outputs/                 # Per-lead output folders
├── src/
│   └── gtm/                 # Installable package (import as `gtm`)
│       ├── config.py        # Settings and scoring point constants
│       ├── models/          # Pydantic models (lead, market, company, person, scoring, enriched)
│       ├── utils/           # Geocoder, slug generation, file cache
│       ├── enrichment/      # One module per API (7 total)
│       ├── scoring/         # Scoring logic
│       ├── outreach/        # Claude email generation
│       └── pipeline/        # Async orchestration
├── docs/
│   ├── architecture.md      # System design (updated each phase)
│   ├── api-notes.md         # Per-API quirks, endpoints, response shapes
│   ├── scoring-logic.md     # Signal thresholds and rationale
│   └── rollout-plan.md      # Sales org rollout plan
└── tests/                   # Fully mocked unit + integration tests
```

---

## Architecture

See [`docs/architecture.md`](docs/architecture.md) for the full system design including data flow, component responsibilities, and key architectural decisions.

---

## Rollout Plan

See [`docs/rollout-plan.md`](docs/rollout-plan.md) for the project plan covering how to test, roll out, and measure this tool in a real sales organization — including stakeholders, timeline, and success metrics.
