# EliseAI GTM Lead Enrichment Tool

Automates the top-of-funnel SDR workflow for property management leads. Takes a raw lead list, enriches each lead with market and company intelligence, scores it 0–100, and drafts a personalized outreach email — so reps act immediately instead of spending 20+ minutes researching.

---

## What It Does

1. **Enriches** each lead across three layers using 7 public APIs:
   - **Market** — renter density, rent levels, population growth (Census, DataUSA)
   - **Company** — portfolio signals, hiring activity, tech stack, employee count, legitimacy (Serper, BuiltWith, Hunter.io, OpenCorporates)
   - **Person** — seniority, department, decision-maker signals (People Data Labs)

2. **Scores** each lead 0–100 across three categories:
   - Market Fit (38%) · Company Fit (41%) · Person Fit (21%)

3. **Drafts** a personalized outreach email using Claude, grounded only in enriched data

4. **Outputs** structured files per lead — enrichment data, score breakdown, and email draft

5. **Dashboard** — a Streamlit UI to add leads, run the pipeline, and browse results

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
| `HUNTER_API_KEY` | Yes | 25 req/month | [hunter.io](https://hunter.io) |
| `PDL_API_KEY` | Yes | 100 req/month | [peopledatalabs.com](https://peopledatalabs.com) |
| `BUILTWITH_API_KEY` | No | Paid only for tech stack | [builtwith.com/api](https://builtwith.com/api) |
| `CENSUS_API_KEY` | No | Generous without key | [api.census.gov](https://api.census.gov/data/key_signup.html) |

> **Note on BuiltWith:** The free tier does not expose named technology detections. Detecting Yardi/RealPage/Entrata requires a paid plan. When absent, the tool uses Serper search snippets as a proxy signal.

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
| Add Lead | Form to add a new lead — appends to `data/leads_input.csv` |
| Run Pipeline | Lists unprocessed leads; run button enriches and scores them |
| View Results | Browse all processed leads with score breakdown and email draft |

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
  greystar-austin-tx/
    enrichment.json    ← structured data from all 7 API modules
    assessment.json    ← score (0–100), tier, category breakdown, insights
    email.txt          ← personalized outreach draft
```

The pipeline is **incremental** — it checks for existing output folders before processing. Re-running is always safe.

### Score Tiers

| Range | Tier | SDR Action |
|---|---|---|
| 71–100 | High | Prioritize — reach out today |
| 41–70 | Medium | Worth outreach, not urgent |
| 0–40 | Low | Nurture only |

---

## Scoring Model

Thirteen signals across three categories:

**Market Fit (38%)** — Is this market worth targeting?
- Renter-occupied units (15%), renter rate (8%), median rent (5%), population growth (5%), economic momentum (5%)

**Company Fit (41%)** — Is this company a real opportunity?
- Active leasing job postings (12%), portfolio news (8%), legacy tech stack (8%), employee count (8%), company age (5%)

**Person Fit (21%)** — Is this contact a decision maker?
- Seniority (10%), department/function (7%), corporate email domain (4%)

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
│   ├── config.py            # Settings and scoring weight constants
│   ├── models.py            # Pydantic models
│   ├── utils/               # Geocoder, slug generation, file cache
│   ├── enrichment/          # One module per API (7 total)
│   ├── scoring/             # Scoring logic
│   ├── outreach/            # Claude email generation
│   └── pipeline/            # Async orchestration
├── docs/
│   ├── architecture.md      # System design (updated each phase)
│   ├── scoring-logic.md     # Signal thresholds and rationale
│   ├── api-notes.md         # Per-API quirks and rate limits
│   └── rollout-plan.md      # Sales org rollout plan
└── tests/                   # Fully mocked unit + integration tests
```

---

## Architecture

See [`docs/architecture.md`](docs/architecture.md) for the full system design including data flow, component responsibilities, and key architectural decisions.

---

## Rollout Plan

See [`docs/rollout-plan.md`](docs/rollout-plan.md) for the project plan covering how to test, roll out, and measure this tool in a real sales organization — including stakeholders, timeline, and success metrics.
