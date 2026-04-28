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

## Rollout Strategy (Phase 9)

> Full rollout plan to be completed in Phase 9 (Part B of the assessment). Sections planned:
>
> - Pilot: 1 SDR, 20 leads, 2-week trial
> - Measurement: time-to-first-email, open rate, reply rate vs. manual baseline
> - Guardrails: SDR review gate before any email is sent
> - Gradual expansion: team-wide after pilot metrics confirmed
> - CRM integration path: push enriched records to HubSpot/Salesforce via API
