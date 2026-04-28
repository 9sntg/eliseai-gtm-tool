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

## Rollout Strategy (Phase 9)

> Full rollout plan to be completed in Phase 9 (Part B of the assessment). Sections planned:
>
> - Pilot: 1 SDR, 20 leads, 2-week trial
> - Measurement: time-to-first-email, open rate, reply rate vs. manual baseline
> - Guardrails: SDR review gate before any email is sent
> - Gradual expansion: team-wide after pilot metrics confirmed
> - CRM integration path: push enriched records to HubSpot/Salesforce via API
