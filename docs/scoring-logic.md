# Scoring Logic

Threshold rationale for all signals. Constants live in `src/gtm/scoring/scorer_signals.py`.

---

## Scoring Overview

The pipeline uses an **additive point model**. Each of the 13 baseline signals contributes 0–N points when it fires and 0 when data is absent — absent signals do not affect other signals. Two bonus signals can push the final score above the 100-pt baseline.

| Category | Points | Rationale |
|---|---|---|
| Market Fit | 38 pts | Market size and rental demand determine how many units EliseAI could automate |
| Company Fit | 41 pts | Company signals indicate likelihood to buy, budget, and proximity to decision |
| Person Fit | 21 pts | Contact quality determines email deliverability and whether the pitch reaches a buyer |
| **Bonus** | up to +11 pts | Extra signals fired when data is available; absence never penalises a lead |

**Tier thresholds (applied to final score):** 0–40 Low · 41–70 Medium · 71–100 High · > 100 still "High"

---

## Market Fit Signals (38 pts baseline)

### Renter-Occupied Units (15 pts)

The most important single signal. Larger renter markets mean more potential leases for EliseAI to automate. Uses Census ACS5 variable B25003_002E.

| Units | Signal | Rationale |
|---|---|---|
| ≥ 200,000 | 1.0 | Large metro — tens of thousands of leads per management company |
| ≥ 100,000 | 0.75 | Major market — strong PM software demand |
| ≥ 50,000 | 0.5 | Mid-size city — viable but not top priority |
| ≥ 10,000 | 0.25 | Smaller market — still addressable |
| < 10,000 | 0.0 | Rural or micro market — outside EliseAI's sweet spot |
| None | 0.0 | Census data unavailable |

### Renter Rate (8 pts)

The share of housing that is renter-occupied. High renter rates indicate cities structurally oriented toward renting (coastal metros, college towns) rather than homeownership.

| Rate | Signal |
|---|---|
| ≥ 55% | 1.0 |
| ≥ 45% | 0.75 |
| ≥ 35% | 0.5 |
| < 35% | 0.25 |
| None | 0.0 |

A floor of 0.25 (not 0.0) reflects that even low-renter-rate cities still have PM activity.

### Median Gross Rent (5 pts)

Higher rents correlate with larger per-unit revenue for property managers and higher willingness to pay for automation tools.

| Rent/month | Signal | Rationale |
|---|---|---|
| ≥ $2,000 | 1.0 | High-cost metro — premium market |
| ≥ $1,500 | 0.75 | Above-average market |
| ≥ $1,000 | 0.4 | Average US market |
| < $1,000 | 0.1 | Below-average — price-sensitive buyers |
| None | 0.0 | |

### Population Growth YoY (5 pts)

Growing cities develop new housing, creating more leases and more automation demand. `datausa.py` fetches two consecutive Census years and computes `(cur - prior) / prior`.

| Growth | Signal | Rationale |
|---|---|---|
| > 2% | 1.0 | Fast-growing — rising PM demand |
| 0–2% | 0.5 | Stable — steady demand |
| < 0% | 0.1 | Shrinking — lower future opportunity |
| None | 0.0 | |

### Economic Momentum (5 pts)

YoY income growth (same formula, applied to median household income). Rising incomes signal an improving local economy and higher PM software budgets. Uses identical thresholds to population growth.

---

## Company Fit Signals (41 pts baseline)

### Job Postings (12 pts)

Open leasing consultant / property manager roles signal that the company is actively growing. The count is extracted via regex from Indeed/ZipRecruiter snippets in the jobs Serper query — not the organic result count, which is always ~7–10.

Regex: `(\d[\d,]*)\s+(?:\w+\s+){0,3}jobs?` — captures the largest real job count found.

| Job count | Signal |
|---|---|
| ≥ 5 | 1.0 |
| ≥ 3 | 0.6 |
| ≥ 1 | 0.3 |
| 0 | 0.0 |

### Portfolio / Company News (8 pts)

Measures company web presence: Google Knowledge Graph entry + organic result count for `"{company} property management"`. A KG entry indicates EliseAI-scale brand recognition.

| Condition | Signal |
|---|---|
| KG present + ≥ 3 organic | 1.0 |
| KG present OR ≥ 3 organic | 0.75 |
| ≥ 1 organic | 0.5 |
| No results | 0.0 |

### Tech Stack (8 pts)

Uses BuiltWith to detect property management software. PM platforms (Yardi, RealPage, Entrata, MRI, AppFolio) indicate a company locked into legacy tools — the strongest replacement pitch. When BuiltWith is absent, this signal contributes 0 pts; other signals are unaffected (additive model — no redistribution).

| Stack | Signal |
|---|---|
| Contains PM platform (Yardi, RealPage, Entrata, MRI, AppFolio) | 1.0 |
| Non-empty (other tech detected) | 0.5 |
| Empty or BuiltWith absent | 0.0 |

### Employee Count (8 pts)

EliseAI's ICP is **mid-market to enterprise** property management companies (Greystar, Summit PM, Landmark Properties — 1,000+ units). Solo operators below ~20 employees rarely have the scale or budget. Signal is binary: past solo-operator scale = full marks.

| Employees | Signal | Rationale |
|---|---|---|
| ≥ 20 | 1.0 | Past solo-operator scale — viable EliseAI target |
| < 20 | 0.3 | Micro operator — ROI marginal |
| None | 0.0 | LinkedIn snippet had no employee data |

### Company Age (5 pts)

Older companies have accumulated legacy processes and tech debt, making them more likely to need modernization. Derived from `founded_year`, extracted from LinkedIn snippets by Claude Haiku.

| Age | Signal | Rationale |
|---|---|---|
| > 10 years | 1.0 | Established operator — legacy tech likely |
| ≥ 5 years | 0.6 | Mid-stage — open to tools |
| < 5 years | 0.2 | Early stage — may lack budget or process maturity |
| None | 0.0 | LinkedIn snippet had no founding year data |

---

## Person Fit Signals (21 pts baseline)

### Seniority (10 pts)

The single most important person signal. Decision-makers with budget authority (C-suite, VP) are the right targets for an EliseAI pitch.

| PDL level | Signal |
|---|---|
| c_suite / owner / partner | 1.0 |
| vp | 0.85 |
| director | 0.70 |
| manager | 0.50 |
| senior | 0.30 |
| other / None | 0.1 |

A floor of 0.1 (not 0.0) for unknown seniority avoids penalising leads where PDL has no data — the person still exists, we just don't know their level.

### Department / Function (7 pts)

Operations and Property Management contacts are EliseAI's primary buyers. Finance and Accounting are adjacent (involved in ROI decisions). Marketing or unrelated departments score at the floor.

| PDL department | Signal |
|---|---|
| operations / property_management | 1.0 |
| real_estate / leasing | 0.8 |
| finance / accounting | 0.5 |
| other / None | 0.1 |

### Corporate Email (4 pts)

A corporate domain (`@greystar.com`) confirms this is a professional contact at an established org, not a personal address. Derived locally by `utils/email.py` without requiring a PDL response.

| Email | Signal |
|---|---|
| Corporate domain | 1.0 |
| Free provider (Gmail, Yahoo, …) | 0.0 |

---

## Bonus Signals (up to +11 pts)

Bonus signals fire when data is available and contribute 0 when absent. Their absence never penalises a lead, so they sit outside the 100-pt baseline. Point values are provisional — calibrate after more real lead runs.

### Portfolio Size (up to +6 pts)

Total units/communities under management, extracted from LinkedIn + PM search snippets by Claude Haiku. Larger portfolios mean more leasing automation opportunity.

| Units | Signal | Rationale |
|---|---|---|
| ≥ 10,000 | 1.0 | Enterprise scale — clear EliseAI ROI |
| ≥ 1,000 | 0.75 | Mid-market — strong prospect |
| ≥ 100 | 0.5 | Small PM company — viable |
| < 100 | 0.2 | Very small — lower priority |
| None | 0.0 | Not extractable from snippets |

### Social Media Presence (up to +5 pts)

Distinct non-LinkedIn social platforms (Facebook, Instagram, YouTube, Twitter/X, TikTok) detected in Serper PM-query organic links. Companies with active social presence tend to be more marketing-savvy and open to new tools.

| Platforms | Signal |
|---|---|
| ≥ 2 | 1.0 |
| 1 | 0.5 |
| 0 | 0.0 |

---

## Signals kept as enrichment-only (not scored)

| Signal | Reason not scored |
|---|---|
| `is_publicly_traded` (EDGAR) | Biased toward large-cap public REITs — most EliseAI targets are private. Present as insight bullet only. |
| `yelp_alias` | Used for email personalization context (review themes, response rate); not a scoring signal. Coverage is strongest for mid-market, weaker for enterprise. |

---

## Calibration Notes

See `CLAUDE.local.md` for open calibration items. Key items to revisit after end-to-end testing:

- Growth thresholds (2% high / 0% flat) should be validated against actual Census output distributions.
- Bonus signal point values (6.0 and 5.0) are provisional — adjust after more lead runs.
- Renter unit tiers should be calibrated against EliseAI's current customer portfolio sizes.
