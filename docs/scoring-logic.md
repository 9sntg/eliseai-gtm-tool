# Scoring Logic

Threshold rationale for all 13 signals. Constants live in `src/gtm/scoring/scorer_signals.py`.

---

## Scoring Overview

Leads are scored 0–100 across three categories. The final score drives an SDR priority tier.

| Category | Weight | Rationale |
|---|---|---|
| Market Fit | 38% | Market size and rental demand determine how many units EliseAI could automate |
| Company Fit | 41% | Company signals indicate likelihood to buy, budget, and proximity to decision |
| Person Fit | 21% | Contact quality determines email deliverability and whether the pitch reaches a buyer |

**Tier thresholds:** 0–40 Low · 41–70 Medium · 71–100 High

---

## Market Fit Signals (38%)

### Renter-Occupied Units (15%)

The most important single signal. Larger renter markets mean more potential leases for EliseAI to automate. Uses Census ACS5 variable B25003_002E.

| Units | Score | Rationale |
|---|---|---|
| ≥ 200,000 | 1.0 | Large metro — tens of thousands of leads per management company |
| ≥ 100,000 | 0.75 | Major market — strong PM software demand |
| ≥ 50,000 | 0.5 | Mid-size city — viable but not top priority |
| ≥ 10,000 | 0.25 | Smaller market — still addressable |
| < 10,000 | 0.0 | Rural or micro market — outside EliseAI's sweet spot |
| None | 0.0 | Census data unavailable |

### Renter Rate (8%)

The share of housing that is renter-occupied. High renter rates indicate cities structurally oriented toward renting (coastal metros, college towns) rather than homeownership.

| Rate | Score |
|---|---|
| ≥ 55% | 1.0 |
| ≥ 45% | 0.75 |
| ≥ 35% | 0.5 |
| < 35% | 0.25 |
| None | 0.0 |

A floor of 0.25 (not 0.0) reflects that even low-renter-rate cities still have PM activity.

### Median Gross Rent (5%)

Higher rents correlate with larger per-unit revenue for property managers and higher willingness to pay for automation tools.

| Rent/month | Score | Rationale |
|---|---|---|
| ≥ $2,000 | 1.0 | High-cost metro — premium market |
| ≥ $1,500 | 0.75 | Above-average market |
| ≥ $1,000 | 0.4 | Average US market |
| < $1,000 | 0.1 | Below-average — price-sensitive buyers |
| None | 0.0 | |

### Population Growth YoY (5%)

Growing cities develop new housing, creating more leases and more automation demand. DataUSA provides two years of population data; growth = (latest − prior) / prior.

| Growth | Score | Rationale |
|---|---|---|
| > 2% | 1.0 | Fast-growing — rising PM demand |
| 0–2% | 0.5 | Stable — steady demand |
| < 0% | 0.1 | Shrinking — lower future opportunity |
| None | 0.0 | |

### Economic Momentum (5%)

YoY income growth (same formula, applied to median household income). Rising incomes signal an improving local economy and higher PM software budgets.

Uses identical thresholds to population growth (see above).

---

## Company Fit Signals (41%)

### Job Postings (12%)

Open leasing consultant / property manager roles signal that the company is actively growing. The count comes from Serper organic results for `"{company} leasing consultant jobs"`.

| Organic results | Score |
|---|---|
| ≥ 5 | 1.0 |
| ≥ 3 | 0.6 |
| ≥ 1 | 0.3 |
| 0 | 0.0 |

### Portfolio / Company News (8% → up to 16% with BuiltWith redistribution)

Measures company web presence: Google Knowledge Graph entry + organic result count for `"{company} property management"`. A KG entry indicates EliseAI-scale brand recognition.

| Condition | Score |
|---|---|
| KG present + ≥ 3 organic | 1.0 |
| KG present OR ≥ 3 organic | 0.75 |
| ≥ 1 organic | 0.5 |
| No results | 0.0 |

**BuiltWith redistribution:** When `tech_stack` is empty (BuiltWith key absent or returned no data), `WEIGHT_TECH_STACK` (8%) is added to this signal's effective weight, bringing it to 16%. This keeps the total to 100% and avoids silently dropping 8 points.

### Tech Stack (8%)

Uses BuiltWith to detect property management software. PM platforms (Yardi, RealPage, Entrata, MRI, AppFolio) indicate a company locked into legacy tools — the strongest replacement pitch. Detected by substring match on lowercased tech names.

| Stack | Score |
|---|---|
| Contains PM platform (Yardi, RealPage, Entrata, MRI, AppFolio) | 1.0 |
| Non-empty (other tech detected) | 0.5 |
| Empty or BuiltWith absent | 0.0 → redistributed |

### Employee Count (8%)

Larger companies have more leasing staff, more manual processes, and higher EliseAI ROI. Employee count is extracted from LinkedIn search snippets by Claude Haiku and stored as `linkedin_employee_count`.

| Employees | Score |
|---|---|
| ≥ 1,000 | 1.0 |
| ≥ 500 | 0.8 |
| ≥ 100 | 0.6 |
| ≥ 50 | 0.3 |
| < 50 | 0.1 |
| None | 0.0 |

### Company Age (5%)

Older companies have accumulated legacy processes and tech debt, making them more likely to need modernization. Derived from `founded_year` (integer), extracted from LinkedIn snippets by Claude Haiku.

| Age | Score | Rationale |
|---|---|---|
| > 10 years | 1.0 | Established operator — legacy tech likely |
| ≥ 5 years | 0.6 | Mid-stage — open to tools |
| < 5 years | 0.2 | Early stage — may lack budget or process maturity |
| None | 0.0 | LinkedIn snippet had no founding year data |

---

## Person Fit Signals (21%)

### Seniority (10%)

The single most important person signal. Decision-makers with budget authority (C-suite, VP) are the right targets for an EliseAI pitch.

| PDL level | Score |
|---|---|
| c_suite / owner / partner | 1.0 |
| vp | 0.85 |
| director | 0.70 |
| manager | 0.50 |
| senior | 0.30 |
| other / None | 0.1 |

A floor of 0.1 (not 0.0) for unknown seniority avoids penalising leads where PDL has no data — the person still exists, we just don't know their level.

### Department / Function (7%)

Operations and Property Management contacts are EliseAI's primary buyers. Finance and Accounting are adjacent (involved in ROI decisions). Marketing or unrelated departments score at the floor.

| PDL department | Score |
|---|---|
| operations / property_management | 1.0 |
| real_estate / leasing | 0.8 |
| finance / accounting | 0.5 |
| other / None | 0.1 |

### Corporate Email (4%)

A corporate domain (`@greystar.com`) confirms this is a professional contact at an established org, not a personal address. Derived locally by `utils/email.py` without requiring a PDL response.

| Email | Score |
|---|---|
| Corporate domain | 1.0 |
| Free provider (Gmail, Yahoo, …) | 0.0 |

---

## Open Questions / Calibration Notes

See `CLAUDE.local.md` for deferred decisions. Key items to revisit after end-to-end testing:

- Growth thresholds (2% high / 0% flat) should be validated against actual DataUSA output distributions.
- Renter unit tiers should be calibrated against EliseAI's current customer portfolio sizes.
- Seniority floor (0.1 vs 0.0 for None) — revisit if PDL coverage is low on real lead lists.
