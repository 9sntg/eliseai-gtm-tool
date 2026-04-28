# Rollout Plan

> How to test, roll out, and measure this tool in a real sales org. Part B of the assessment.

---

## Running the Tool (CLI)

```bash
# Install dependencies
uv sync

# Copy and populate API keys
cp .env.example .env   # then fill in keys

# Process all new leads in data/leads_input.csv
python main.py

# Watch for new CSV rows and re-run automatically
python main.py --watch
```

Output folders appear under `outputs/` — one per lead. Each contains `enrichment.json`, `assessment.json`, and `email.txt`. Re-running is safe: existing folders are skipped.

---

## Streamlit Dashboard

The dashboard (`app.py`) provides a no-code interface for the full pipeline. Launch with:

```bash
streamlit run app.py
```

Three tabs:
- **Add Lead** — fill in contact name, email, company, city, state; appends a row to `data/leads_input.csv`
- **Run Pipeline** — shows pending vs. processed lead counts; click "Run Pipeline" to enrich all new leads with a progress spinner
- **View Results** — select any processed lead from a dropdown; displays score, tier, Market/Company/Person subtotals, per-signal breakdown, enrichment data (market stats, company data, contact info), and the draft outreach email

The dashboard is designed for SDR use: no terminal access required after initial setup.

---

## Rollout Strategy

### The problem this solves

An EliseAI SDR today manually researches a lead before writing an outreach email: checking LinkedIn for company size and tenure, Googling for job postings, looking up local market stats, and drafting a personalized message from scratch. This takes 15–25 minutes per lead. With a typical SDR working 30–40 leads per week, that's 8–17 hours of research time — the majority of an SDR's working week.

This tool collapses that to under 3 minutes (pipeline runtime) + 2 minutes (SDR review). The SDR reads a pre-scored lead card and a ready-to-send draft, tweaks the draft if needed, and sends. The time savings pay for the API costs within the first 2–3 leads processed.

---

### Phase 1 — Controlled pilot (weeks 1–2)

**Who:** 1 SDR volunteer. 20 leads from the existing pipeline, drawn from a single city to keep enrichment comparable.

**What they do:**
1. Add lead rows to `leads_input.csv` via the Streamlit dashboard.
2. Click "Run Pipeline" at the start of each day.
3. Review the scored lead card in the "View Results" tab.
4. For High/Medium leads: read the draft email, edit 1–2 lines if needed, copy-paste into their email client, send.
5. Log each send in a shared sheet: lead name, score tier, time spent, whether they edited the draft.

**What the SDR does NOT change:** their existing outreach cadence, follow-up timing, or CRM logging. We are measuring pre-send time only in week 1–2.

**Success criteria for advancing to Phase 2:**
- Average time-to-send < 5 min (vs. ~20 min baseline)
- SDR reports draft quality ≥ 3/5 on a quick daily survey ("would you send this without editing?")
- Zero "bad emails" — the AI never fabricates a stat the SDR has to walk back

---

### Phase 2 — Measurement and calibration (weeks 3–6)

**Expand to:** 2–3 SDRs, 50–100 leads per week total.

**Track these metrics vs. manual baseline:**

| Metric | Baseline (manual) | Target | How to measure |
|---|---|---|---|
| Time-to-first-email | 18 min / lead | < 5 min / lead | SDR self-report log |
| Email open rate | ~25% (industry) | ≥ 30% | Email client tracking |
| Reply rate | ~8% | ≥ 12% | CRM tag |
| Demo booked rate | ~3% | ≥ 5% | CRM stage |
| Draft accepted without edit | — | ≥ 60% | SDR log |

Scoring model calibration: collect SDR feedback on leads they marked as "poor fit despite high score" (false positives) and "good fit despite low score" (false negatives). Use these to adjust threshold constants in `scorer_signals.py` after ~100 leads.

---

### Phase 3 — Team-wide deployment (week 7+)

**Trigger:** Phase 2 metrics at or above target for two consecutive weeks.

**Operational changes:**
- `leads_input.csv` is replaced by a shared Airtable base (or HubSpot list) that all SDRs can append to.
- The pipeline runs on a scheduled cron job (or `python main.py --watch`) on a shared VM — no manual "Run Pipeline" click needed.
- The dashboard moves to a shared internal URL (Streamlit Community Cloud or internal Heroku app).

**Guardrail retained permanently:** No email is ever sent directly by the tool. The SDR reviews every draft before sending. The tool is a research accelerator, not an auto-sender.

---

### Scoring model calibration process

After 200+ processed leads, revisit these thresholds with the SDR team:

1. **Job count thresholds** (3/5 boundaries) — calibrate against what "active hiring" looks like in the PM space.
2. **Portfolio size bonus thresholds** — the 100/1,000/10,000 tiers were set without real data. Adjust based on actual portfolio sizes appearing in extraction.
3. **Social presence bonus** — confirm whether social media activity is a meaningful signal for PM companies at the ICPs size range.
4. **Employee count binary cutoff** (currently 20) — may need to shift up if micro-operators are appearing as false positives.

---

### CRM integration path (future)

The current file-based output is appropriate for a pilot. When the team scales past ~100 leads/week, push enriched records directly to HubSpot or Salesforce via API:

- `assessment.json` → custom property fields on the Contact record (score, tier, signal breakdown)
- `email.txt` → pre-populated email template in the CRM sequence, flagged for SDR review
- `enrichment.json` → notes field or hidden enrichment properties for SDR context

The pipeline already produces clean JSON with `.model_dump(mode="json")`, so the CRM write is a straightforward API call appended to `runner.py`'s `_write_outputs`.

---

### API cost estimate at scale

| API | Cost basis | Per-lead estimate | 100 leads/week |
|---|---|---|---|
| Serper | ~$0.001/query × 3 | ~$0.003 | ~$0.30 |
| PDL | ~$0.10/enrichment | ~$0.10 | ~$10 |
| Anthropic (Haiku) | ~$0.0003/1K tokens | ~$0.001 | ~$0.10 |
| Anthropic (Sonnet email) | ~$0.003/1K tokens | ~$0.01 | ~$1.00 |
| BuiltWith | flat plan | ~$0 marginal | ~$0 marginal |
| Census / EDGAR | free | $0 | $0 |
| **Total** | | **~$0.11–$0.12** | **~$11–$12/week** |

At $11–12/week for 100 leads, API costs are negligible relative to SDR time savings (~8 hrs/week × SDR hourly rate).
