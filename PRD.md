# EliseAI GTM Engineer — Inbound Lead Enrichment Tool
## Product Requirements Document (PRD)

---

## 1. Context and Purpose

EliseAI is an AI company automating leasing and resident operations for property management companies. When a new inbound lead comes in, it contains only basic information: contact name, email, company name, and a property address with city and state. An SDR then manually researches, prioritizes, and drafts outreach for each lead.

This tool automates that entire top-of-funnel process using public APIs. It takes a raw lead list, enriches each lead with market and company intelligence, scores each lead 0–100, and generates a personalized draft outreach email — so the SDR can act immediately instead of spending 20+ minutes researching each one.

---

## 2. What a Lead Is

A lead in this context is a **property management company** that has expressed interest in EliseAI or that EliseAI's sales team wants to reach out to. The lead record contains:

| Field | Example |
|---|---|
| Contact name | John Smith |
| Email | john@greystar.com |
| Company name | Greystar |
| Property address | 1234 Main St |
| City | Austin |
| State | TX |

The tool does **not** look up the company directly via the address. Instead, it uses the city and state as a geographic anchor to assess the market the company operates in, then uses the company domain and name to assess the company and contact directly.

---

## 3. Why This Matters for EliseAI

EliseAI's ideal customer is a **large property management company** operating in a **renter-dense, growing market**. The bigger the portfolio, the more leasing conversations EliseAI automates, and the more valuable the contract. A company running legacy software (Yardi, RealPage, Entrata) is a direct displacement opportunity. A company actively hiring leasing consultants is paying people to do exactly what EliseAI replaces.

---

## 4. Data Source Stack

### Market Level

**U.S. Census API** (free, no key required for basic queries)
- Renter-occupied housing units in the city
- Total housing units
- Renter rate (%)
- Median gross rent
- Population
- Used to assess: market size and density

**DataUSA API** (free, no key required)
- Population growth rate (YoY)
- Median household income
- Real estate sector employment
- Median property value
- Used to assess: market momentum and economic health

### Company Level

**Serper API** (`SERPER_API_KEY`)
- Two queries per lead:
  1. `"[company name] property management"` — surfaces company description, portfolio size, news, recent acquisitions
  2. `"[company name] leasing consultant jobs"` — surfaces active hiring signals
- Used to assess: company scale, growth signals, timing signals (new leadership, portfolio expansion, job postings)

**OpenCorporates API** (free tier)
- Legal company name
- Incorporation date
- Jurisdiction
- Status (active/inactive)
- Number of filings
- Used to assess: company legitimacy and age

**Hunter.io API** (`HUNTER_API_KEY`, free tier: 25 req/month)
- Company name from domain
- Industry
- Employee count estimate
- Used to assess: company size from email domain

**BuiltWith API** (`BUILTWITH_API_KEY`, paid plan required for tech stack detection)
- Technology stack running on company website
- Key signal: if they run Yardi, RealPage, or Entrata → large operator on legacy software → displacement opportunity
- Used to assess: operational scale and technology maturity
- **Note:** BuiltWith's free tier returns technology group counts only, not named technologies. Detecting Yardi/RealPage/Entrata requires a paid plan. When no key is present or the API returns no data, the 8% weight for this signal redistributes proportionally to the Serper portfolio signal, which can surface tech stack mentions in search snippets as a weaker proxy.

**Census Geocoder API** (free, no key required)
- Prerequisite for Census and DataUSA queries
- Converts `city + state` → `(state_fips, place_fips)` FIPS codes
- Census ACS API requires numeric FIPS codes, not city names
- Results are cached per city to avoid redundant calls
- Implemented in `src/utils/geocoder.py`

### Person Level

**People Data Labs (PDL) API** (`PDL_API_KEY`, free tier: 100 req/month)
- Job title
- Seniority level (c_suite, vp, director, manager, individual)
- Department / function
- Years of experience
- Used to assess: whether the contact is a decision maker with budget authority

---

## 5. Scoring Model

Scores range from **0 to 100**. Three tiers:
- **0–40**: Low — deprioritize, nurture only
- **41–70**: Medium — worth outreach, not urgent
- **71–100**: High — prioritize immediately, SDR action required

Signals are grouped into three categories that map to the three questions a sales rep asks: _Is this market worth targeting? Is this company a real opportunity? Is this contact a decision maker?_

### Market Fit — 38%

| Signal | Source | Weight |
|---|---|---|
| Renter-occupied units in city | Census | 15% |
| Renter rate % | Census | 8% |
| Median gross rent (portfolio value proxy) | Census | 5% |
| Population growth rate (YoY) | DataUSA | 5% |
| Economic momentum (median income growth) | DataUSA | 5% |

### Company Fit — 41%

| Signal | Source | Weight |
|---|---|---|
| Active leasing job postings | Serper | 12% |
| Leadership changes / portfolio news | Serper | 8% |
| Legacy tech stack (Yardi / RealPage / Entrata) | BuiltWith (optional) | 8% |
| Employee count estimate | Hunter.io | 8% |
| Company age and legitimacy | OpenCorporates | 5% |

### Person Fit — 21%

| Signal | Source | Weight |
|---|---|---|
| Seniority level | PDL | 10% |
| Function / department (ops, tech, leasing) | PDL | 7% |
| Corporate email domain (vs. Gmail / Hotmail) | Email parse | 4% |

### Scoring Logic Notes (documented assumptions)

- **Renter units**: >100,000 = max score; 50,000–100,000 = high; 10,000–50,000 = medium; <10,000 = low
- **Renter rate**: >50% = max; 40–50% = high; 30–40% = medium; <30% = low
- **Tech stack**: Running Yardi/RealPage/Entrata = max (displacement opportunity); no recognized PM software = medium (greenfield); modern alternatives = low
- **Seniority**: C-suite/VP = max; Director = high; Manager = medium; Individual contributor = low
- **Function**: Operations/Technology/Leasing/Property Management = max; Finance/HR = low; unknown = medium
- **Email domain**: Corporate domain = max; Gmail/Hotmail/Yahoo = zero
- **Job postings**: 5+ leasing consultant postings found = max; 1–4 = medium; none = zero
- **Company age**: >10 years = established operator = high; 5–10 = medium; <5 = low
- **Employee count**: >500 = large operator = max; 100–500 = high; <100 = low

---

## 6. Outputs Per Lead

For each lead the tool generates:

1. **Enriched data record** — all raw API responses structured into typed Pydantic models
2. **Lead score** (0–100) with tier label (Low / Medium / High)
3. **Score breakdown** — per-signal scores + Market / Company / Person category subtotals
4. **Sales insights summary** — 3–5 bullet points an SDR needs to know before reaching out
5. **Draft outreach email** — personalized using enriched data, Claude API

### Output Format

Each lead gets its own folder under `outputs/` at the project root:

```
outputs/{company}-{city}-{state}/
  enrichment.json   ← structured API data (MarketData, CompanyData, PersonData)
  assessment.json   ← score, tier, ScoreBreakdown, insights
  email.txt         ← full personalized outreach draft
```

**Slug naming:** company name + city + state, lowercased and hyphenated (e.g., `greystar-austin-tx`, `lincoln-property-company-charlotte-nc`).

The pipeline is **incremental**: it checks whether a lead's output folder already exists before processing. Re-running is always safe — only new leads are enriched.

---

## 7. Tool Behavior

### Input

A CSV file at `data/leads_input.csv` with columns:
`name, email, company, property_address, city, state`

### Trigger

Three ways to run the pipeline:
1. **CLI**: `python main.py` — processes all leads in `leads_input.csv` that don't already have an output folder
2. **Streamlit dashboard**: "Run Pipeline" button in the `app.py` dashboard — same behavior, with live progress in the UI
3. **File-watch mode**: `python main.py --watch` — keeps running and re-processes whenever `leads_input.csv` changes (uses `watchdog`)

### Graceful degradation

If any API call fails or returns no data for a lead, that signal scores zero and the pipeline continues. Missing data is logged and flagged in the output. The tool never crashes on a single bad API response.

---

## 8. Project Structure

```
eliseai-gtm-tool/
│
├── CLAUDE.md                        # Global project memory and architecture summary
├── PRD.md                           # This file
├── README.md                        # Human-facing overview
├── pyproject.toml                   # Dependencies (uv), ruff, pytest config
├── main.py                          # CLI entry point
├── app.py                           # Streamlit dashboard
├── .env                             # API keys — never committed
├── .env.example                     # Template showing required keys
├── .gitignore
│
├── .claude/
│   ├── settings.json                # Permissions, model — commit this
│   ├── settings.local.json          # Personal overrides — gitignore this
│   │
│   ├── rules/
│   │   ├── enrichment.md            # Wrap API calls in try/except. Cache. Respect rate limits.
│   │   ├── scoring.md               # No magic numbers. Document every weight. Scores 0–100.
│   │   ├── outreach.md              # Never hallucinate lead data. Only use enriched fields.
│   │   └── tests.md                 # Mock all external calls. No test touches the network.
│   │
│   └── commands/
│       ├── enrich.md                # /enrich — runs pipeline on leads_input.csv
│       ├── score.md                 # /score — reruns scoring on already-enriched data
│       └── test-lead.md             # /test-lead — runs a single lead end to end
│
├── docs/
│   ├── architecture.md              # Living system design doc — updated each phase
│   ├── scoring-logic.md             # Full scoring assumptions and weight rationale
│   ├── api-notes.md                 # Per-API quirks, endpoints, rate limits
│   └── rollout-plan.md              # Project plan for rolling out to the sales org
│
├── src/
│   ├── config.py                    # Centralized settings via pydantic-settings; scoring weights as constants
│   ├── models.py                    # Pydantic models: RawLead, MarketData, CompanyData, PersonData, EnrichedLead, ScoreBreakdown
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── geocoder.py              # city+state → FIPS codes (Census Geocoder API)
│   │   ├── slug.py                  # Lead slug generation and collision handling
│   │   └── cache.py                 # JSON file cache (24hr TTL)
│   ├── enrichment/
│   │   ├── __init__.py
│   │   ├── census.py                # U.S. Census ACS API
│   │   ├── datausa.py               # DataUSA API
│   │   ├── serper.py                # Serper API (company + hiring queries)
│   │   ├── opencorporates.py        # OpenCorporates API
│   │   ├── hunter.py                # Hunter.io API
│   │   ├── builtwith.py             # BuiltWith API (optional)
│   │   └── pdl.py                   # People Data Labs API
│   ├── scoring/
│   │   ├── __init__.py
│   │   └── scorer.py                # Scoring logic — 3-category model
│   ├── outreach/
│   │   ├── __init__.py
│   │   └── email_generator.py       # Claude API with prompt caching
│   └── pipeline/
│       ├── __init__.py
│       └── runner.py                # Async orchestration: enrichment → scoring → output
│
├── data/
│   └── leads_input.csv              # Input: raw lead list (output goes to outputs/)
│
├── outputs/                         # Per-lead output folders
│   └── {company}-{city}-{state}/
│       ├── enrichment.json
│       ├── assessment.json
│       └── email.txt
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py                  # Shared fixtures and mock API responses
│   ├── test_enrichment.py           # Unit tests per enrichment module (mocked)
│   ├── test_scorer.py               # Unit tests for scoring logic
│   └── test_pipeline.py             # Integration test for full pipeline (mocked)
│
└── main.py                          # CLI entry point
```

---

## 9. API Keys Required

Add these to `.env`:

```
SERPER_API_KEY=
HUNTER_API_KEY=
BUILTWITH_API_KEY=
PDL_API_KEY=
ANTHROPIC_API_KEY=
CENSUS_API_KEY=       # optional, rate limit is generous without one
```

---

## 10. Production Upgrade Path

This MVP uses free API tiers and public data only. A production version would add:

- **Clearbit or ZoomInfo** — paid company-level enrichment with verified employee count and revenue
- **Bombora** — intent data showing if a company has been searching for leasing automation tools
- **ProxyCurl** — full LinkedIn profile enrichment from email
- **Playwright** — headless browser for JS-heavy company websites
- **Clay** — full waterfall enrichment orchestration replacing the manual API stack
- **Salesforce / HubSpot integration** — push scored leads directly into CRM

---

## 11. Done Criteria

- [ ] Pipeline runs end to end on a sample CSV of 5 leads without errors
- [ ] All 7 APIs return data for at least one sample lead
- [ ] Scoring produces a 0–100 score with per-signal breakdown for each lead
- [ ] Draft outreach email is personalized with at least 2 enriched data points per lead
- [ ] Output CSV is clean and readable by a non-technical SDR
- [ ] Trigger fires automatically when a new row is added to leads_input.csv
- [ ] All external API calls are mocked in tests — no test touches the network
- [ ] README explains how to run the tool in under 5 minutes