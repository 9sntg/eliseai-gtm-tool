# Scoring Rules

## Weights and Thresholds

- All scoring weights are defined in `src/config.py` as named constants.
  Never reference a weight as an inline float in `scorer.py`.
  Good: `settings.WEIGHT_RENTER_UNITS`
  Bad: `score += 0.15 * renter_signal`

- All scoring thresholds (the boundary values that map raw data to a 0–1 signal)
  are also named constants at the top of `scorer.py`.
  Good: `RENTER_UNITS_MAX = 100_000`, `RENTER_UNITS_HIGH = 50_000`
  Bad: `if renter_units > 100000:`

- Weights must sum to 1.0. Validate this at startup in `config.py`.

## Signal Functions

- Each of the 13 signals has its own function: `score_renter_units(units: int | None) -> float`
- Signal functions return a float in [0.0, 1.0].
- Signal functions never read from config directly — thresholds are passed in as arguments
  or referenced from module-level constants in scorer.py.
- A signal function receiving `None` (missing data) returns `0.0` — always, without logging.
  The enrichment module already logged the warning when the data was missing.

## BuiltWith Redistribution

- When `CompanyData.tech_stack` is empty (BuiltWith absent or no data), the 8% weight
  for that signal must redistribute to Serper's portfolio_news signal — not silently
  disappear from the total.
- The redistribution logic is clearly commented in `scorer.py`.

## ScoreBreakdown

- `ScoreBreakdown` exposes both individual signal scores and the three category subtotals
  (`market_score`, `company_score`, `person_score`).
- Category subtotals are computed as the weighted sum of signals within that category,
  normalized to 0–100 (not 0–1).
- The overall `score` field is the sum of all weighted signal scores × 100.

## Tier Logic

- Tiers are computed from the final score, not from category scores.
- Tier boundaries (0–40 Low, 41–70 Medium, 71–100 High) are named constants.

## Testability

- `scorer.py` is a pure function module — no I/O, no API calls, no side effects.
- Every signal function is independently testable with direct inputs.
- `test_scorer.py` tests boundary values for every threshold (e.g., renter_units
  exactly at 50,000 and 100,000), and verifies weights sum to 1.0.
