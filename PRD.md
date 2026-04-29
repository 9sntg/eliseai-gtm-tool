# EliseAI GTM Engineer — Inbound Lead Enrichment Tool
## Product Requirements Document (PRD)


## 1. Context and Purpose

EliseAI is an AI company automating leasing and resident operations for property management companies. When a new inbound lead comes in, it contains only basic information: contact name, email, company name, and a property address with city and state. An SDR then manually researches, prioritizes, and drafts outreach for each lead.

This tool automates that entire top-of-funnel process using public APIs. It takes a raw lead list, enriches each lead with market, company, building, and person intelligence, scores each lead on an additive point model (139 pts max across four categories), and generates a personalized draft outreach email so the SDR can act immediately instead of spending 20+ minutes researching each one.


## 2. What a Lead Is

A lead in this context is a **property management company** that has expressed interest in EliseAI or that EliseAI's sales team wants to reach out to. The lead record contains:

| Field | Example |
|---|---|
| Contact name | John Smith |
| Email | john@greystar.com |
| Company name | Greystar |
| Property address | 3333 Harry Hines Blvd |
| City | Dallas |
| State | TX |

The `property_address` field is a specific apartment building the company manages in that city. It is used to find the building on Yelp and extract building-level signals (tenant reviews, price tier, pain themes). The city and state serve as the geographic anchor for all market-level signals.

**Geographic scope:** This version of the tool is US-only. The data sources it depends on (U.S. Census ACS, Census Geocoder, SEC EDGAR, and Yelp Fusion's US-market depth) are either exclusively US-based or significantly more complete for US cities than for international markets. A future iteration could support Canada and the UK by substituting equivalent national statistics APIs (Statistics Canada, ONS) and adjusting the Yelp and Serper queries for local address formats.


## 3. Why This Matters for EliseAI

EliseAI's ideal customer is a **large property management company** operating in a **renter-dense, growing market**. The bigger the portfolio, the more leasing conversations EliseAI automates, and the more valuable the contract. A company running legacy software (Yardi, RealPage, Entrata) is a direct displacement opportunity. A company whose tenants are complaining on Yelp is already experiencing the pain that EliseAI's AI leasing agent solves.


## 4. Data Source Stack

### Market Level

**U.S. Census API** (free; optional key for higher rate limits)

Provides renter-occupied housing units, total housing units, renter rate, median gross rent, and population at the city level. Used to assess market size and density. See [`docs/api-notes.md`](docs/api-notes.md) for endpoint details.

**Census ACS Multi-Year** (same API, two consecutive years)

`datausa.py` queries the Census ACS5 API for two consecutive years (2022 and 2021) and computes year-over-year growth rates for population and median household income. Used to assess market momentum.

**Census Geocoder API** (free; no key required)

Converts `city + state` to `(state_fips, place_fips)` FIPS codes, which are required by all Census ACS queries. Results are cached per city to avoid redundant calls. Implemented in [`src/gtm/utils/geocoder.py`](src/gtm/utils/geocoder.py).

### Company Level

**Serper API** (`SERPER_API_KEY`, paid; 2,500 searches on free tier)

Two queries per lead: `"{company} property management"` and `site:linkedin.com/company {company}`. The first surfaces company description, portfolio news, Google rating (from knowledge graph), Yelp alias, and social media presence. The second surfaces LinkedIn snippet for employee count, founding year, and portfolio size extraction via Claude Haiku.

**SEC EDGAR EFTS** (free; no key required)

Detects whether the company is publicly traded by searching for 10-K filings. Used as an insight signal only (not scored), since most EliseAI targets are private companies. Surfaces as an insight bullet for SDR context.

**BuiltWith API** (`BUILTWITH_API_KEY`, paid plan required for named tech detection)

Detects property management software running on the company's website. A company on Yardi, RealPage, or Entrata is on legacy software and is a direct displacement opportunity. When the key is absent or no data is returned, the signal scores zero.

**Yelp Fusion v3 — Company** (`YELP_API_KEY`, free tier; 500 req/day)

`enrich_company` finds the company's Yelp page, fetches its rating, review count, and review highlights, and computes a market average rating from comparable property management businesses in the same city. See [`docs/api-notes.md`](docs/api-notes.md) for full endpoint details.

### Building Level

**Yelp Fusion v3 — Building** (`YELP_API_KEY`, same key as above)

`enrich_building` resolves the `property_address` to an apartment complex name via a Serper query, then fetches the building's own Yelp page for rating, review count, price tier, and resident pain themes. The building page is distinct from the company page — it reflects tenant experience at a specific property rather than the company's overall reputation.

### Person Level

**People Data Labs (PDL) API** (`PDL_API_KEY`, free tier: 100 req/month)

Email-only lookup returning job title, seniority level (c_suite, vp, director, manager, etc.), and department/function. Used to assess whether the contact is a decision maker with budget authority. When PDL returns a title but no seniority classification, Claude Haiku infers the level from the title.

### AI Extraction

**Anthropic Claude** (`ANTHROPIC_API_KEY`, pay-per-use)

Used for three distinct tasks: (1) Claude Haiku extracts structured JSON (`employee_count`, `founded_year`, `portfolio_size`) from LinkedIn and PM search snippets. (2) Claude Haiku extracts pain themes from Yelp review highlights and Serper organic snippets. (3) Claude Sonnet generates the personalized outreach email and three SDR insight bullets per lead. The email system prompt is cached with `cache_control: ephemeral` to reduce token costs across a batch.


## 5. Scoring Model

Scores use an **additive point model**. Each signal contributes 0 to N points when it fires and 0 when data is absent. Absent signals do not affect other signals.

**Total: 139 pts** across four categories.

**Tier thresholds:**
- **High (71+ pts):** Strong fit. Multiple signals align. Prioritize for immediate SDR outreach.
- **Medium (41–70 pts):** Qualified target. Enough signal to warrant outreach, not yet a priority.
- **Low (0–40 pts):** Weak fit. Limited enrichment data or market and company signals absent.

### Market Fit (38 pts)

| Signal | Source | Points |
|---|---|---|
| Renter-occupied units in city | Census ACS5 | 15 |
| Renter rate (%) | Census ACS5 | 8 |
| Median gross rent (portfolio value proxy) | Census ACS5 | 5 |
| Population growth rate (YoY) | Census ACS5 multi-year | 5 |
| Economic momentum (median income growth) | Census ACS5 multi-year | 5 |

### Company Fit (60 pts)

| Signal | Source | Points |
|---|---|---|
| Portfolio and company news (web presence) | Serper | 8 |
| Legacy tech stack (Yardi, RealPage, Entrata, MRI, AppFolio) | BuiltWith | 8 |
| Employee count | Serper / LinkedIn (Haiku-extracted) | 8 |
| Company age | LinkedIn (Haiku-extracted) or Yelp | 5 |
| Portfolio size (units under management) | Serper / LinkedIn (Haiku-extracted) | 6 |
| Social media presence | Serper (organic link scan) | 5 |
| Yelp company rating vs. market average | Yelp Fusion | 6 |
| Google company rating | Serper knowledge graph | 4 |
| Company pain themes (Yelp + Serper combined) | Yelp + Serper (Haiku-extracted) | 5 |
| Competitor rank on Yelp | Yelp Fusion (comparables search) | 5 |

### Person Fit (21 pts)

| Signal | Source | Points |
|---|---|---|
| Seniority level | PDL (Haiku fallback) | 10 |
| Function and department | PDL | 7 |
| Corporate email domain | Email parse (local) | 4 |

### Building Fit (20 pts)

These signals score 0 when Yelp building-level data is unavailable, consistent with all other signals in the additive model.

| Signal | Source | Points |
|---|---|---|
| Building rating (inverted — lower rating scores higher) | Yelp Fusion | 8 |
| Building review count (signal confidence) | Yelp Fusion | 4 |
| Building price tier ($ to $$$$) | Yelp Fusion | 4 |
| Building pain themes | Yelp (Haiku-extracted) | 4 |

Full threshold documentation: [`docs/scoring-logic.md`](docs/scoring-logic.md)


## 6. Outputs Per Lead

For each lead the tool generates:

1. **Enriched data record:** all raw API responses structured into typed Pydantic models
2. **Lead score** (0–139) with tier label (Low / Medium / High)
3. **Score breakdown:** per-signal scores plus Market / Company / Person / Building category subtotals
4. **SDR insight bullets:** 3 bullets generated by Claude Sonnet, grounded in actual signal findings
5. **Draft outreach email:** personalized using enriched data, written by Claude Sonnet

### Output Format

Each lead gets its own folder under `outputs/` at the project root:

```
outputs/{company}-{address-slug}-{city}-{state}/
  enrichment.json   ← structured API data (contact, market, company, building sections)
  assessment.json   ← lead_score, tier, key_observations, category subtotals, signals list
  email.txt         ← full personalized outreach draft
```

**Slug naming:** company name plus address slug plus city and state, lowercased and hyphenated (e.g., `greystar-3333-harry-hines-blvd-dallas-tx`). The address is included so that the same company can have multiple leads for different buildings without collision.

The pipeline is **incremental**: it checks whether a lead's output folder already exists before processing. Re-running is always safe.


## 7. Tool Behavior

### Input

A CSV file at `data/leads_input.csv` with columns:
`name, email, company, property_address, city, state`

### Trigger

Four ways to run the pipeline:

1. **CLI:** `python main.py` processes all leads in `leads_input.csv` that do not already have an output folder.
2. **Streamlit dashboard:** the "Run Pipeline" button in `app.py` runs the same logic with live progress in the UI.
3. **File-watch mode:** `python main.py --watch` keeps running and re-processes whenever `leads_input.csv` changes, using the `watchdog` library.
4. **Daily schedule:** `python main.py --schedule 09:00` runs the pipeline immediately on startup, then repeats every day at the specified time. Useful for unattended overnight or morning runs on a shared VM. `--schedule` and `--watch` are mutually exclusive.

### Graceful Degradation

If any API call fails or returns no data for a lead, that signal scores zero and the pipeline continues. Missing data is logged and the signal shows in the breakdown as 0 pts. The tool never crashes on a single bad API response.


## 8. Project Structure

```
eliseai-gtm-tool/
├── CLAUDE.md                        # Global project memory and architecture summary
├── PRD.md                           # This file
├── README.md                        # Human-facing overview
├── pyproject.toml                   # Dependencies (uv), ruff, pytest config
├── main.py                          # CLI entry point
├── app.py                           # Streamlit dashboard
├── .env                             # API keys (never committed)
├── .env.example                     # Template showing required keys
│
├── .claude/
│   └── rules/
│       ├── enrichment.md            # Wrap API calls in try/except. Cache. Respect rate limits.
│       ├── scoring.md               # No magic numbers. Document every weight.
│       ├── outreach.md              # Never hallucinate lead data. Only use enriched fields.
│       └── tests.md                 # Mock all external calls. No test touches the network.
│
├── docs/
│   ├── architecture.md              # Living system design doc — updated each phase
│   ├── scoring-logic.md             # Full scoring assumptions and threshold rationale
│   ├── api-notes.md                 # Per-API quirks, endpoints, rate limits
│   └── rollout-plan.md              # Project plan for rolling out to the sales org
│
├── src/
│   └── gtm/
│       ├── config.py                # Centralized settings; scoring point values as constants
│       ├── models/                  # Pydantic models: RawLead, MarketData, CompanyData,
│       │                            #   PersonData, BuildingData, EnrichedLead, ScoreBreakdown
│       ├── utils/
│       │   ├── geocoder.py          # city+state to FIPS codes (Census Geocoder API)
│       │   ├── slug.py              # Lead slug generation and collision handling
│       │   └── cache.py             # JSON file cache (24-hr TTL)
│       ├── enrichment/
│       │   ├── census.py            # U.S. Census ACS API
│       │   ├── datausa.py           # Census ACS multi-year (growth signals)
│       │   ├── serper.py            # Serper API (PM presence + LinkedIn queries)
│       │   ├── serper_helpers.py    # Serper extraction helpers (Haiku, regex, alias scan)
│       │   ├── edgar.py             # SEC EDGAR (public company detection)
│       │   ├── builtwith.py         # BuiltWith API (tech stack detection)
│       │   ├── pdl.py               # People Data Labs (person enrichment + Haiku fallback)
│       │   ├── yelp.py              # Yelp Fusion (company + building enrichment)
│       │   └── yelp_helpers.py      # Yelp extraction helpers (Haiku pain themes, rank)
│       ├── scoring/
│       │   ├── scorer.py            # Additive point model; tier mapping; insight generation
│       │   ├── scorer_signals.py    # 22 individual signal functions with threshold constants
│       │   └── reasons.py           # Signal reason sentences for dashboard and assessment.json
│       ├── outreach/
│       │   ├── email_generator.py   # Claude Sonnet email + insight generation
│       │   └── system_prompt.md     # Cached system prompt with EliseAI context
│       └── pipeline/
│           └── runner.py            # Async orchestration: enrichment -> scoring -> output
│
├── data/
│   └── leads_input.csv              # Input: raw lead list
│
├── outputs/                         # Per-lead output folders (one per processed lead)
│
└── tests/
    ├── conftest.py                  # Shared fixtures and mock API responses
    ├── test_enrichment.py           # Unit tests per enrichment module (mocked)
    ├── test_scorer.py               # Unit tests for scoring logic and signal boundaries
    ├── test_email_generator.py      # Unit tests for outreach generation
    ├── test_pipeline.py             # Integration test for full pipeline (mocked)
    └── test_config.py               # Validates point constants sum to correct baseline
```


## 9. API Keys Required

Add these to `.env`:

```
SERPER_API_KEY=
PDL_API_KEY=
ANTHROPIC_API_KEY=
YELP_API_KEY=
BUILTWITH_API_KEY=       # optional; paid plan required for tech stack detection
CENSUS_API_KEY=          # optional; rate limit is generous without one
```


## 10. Production Upgrade Path

This MVP uses free API tiers and public data. A production version would add:

- **Clearbit or ZoomInfo:** paid company-level enrichment with verified employee count and revenue
- **Bombora:** intent data showing whether a company has been searching for leasing automation tools
- **ProxyCurl:** full LinkedIn profile enrichment from email
- **Clay:** full waterfall enrichment orchestration replacing the manual API stack
- **Salesforce or HubSpot integration:** push scored leads directly into CRM instead of writing files


## 11. Done Criteria

- [x] Pipeline runs end to end on a 17-lead CSV without errors
- [x] All 8 enrichment modules return data for at least one lead
- [x] Scoring produces an additive point score with per-signal breakdown for each lead
- [x] Draft outreach email is personalized with enriched data points per lead
- [x] Tier thresholds are documented (Low 0–40, Medium 41–70, High 71+)
- [x] Trigger fires automatically when a new row is added to leads_input.csv (--watch flag)
- [x] All external API calls are mocked in tests; no test touches the network
- [x] README explains how to run the tool in under 5 minutes
- [x] Streamlit dashboard provides a no-code interface for the full pipeline
