"""Streamlit dashboard — Add Lead, Run Pipeline, View Results."""

from __future__ import annotations

import logging
from pathlib import Path

import streamlit as st

from gtm.dashboard.helpers import (
    append_lead_to_csv,
    list_output_folders,
    load_lead_data,
    load_leads_from_csv,
    render_category_metrics,
    render_company_section,
    render_email_section,
    render_market_section,
    render_person_section,
    render_score_header,
    render_signal_table,
    run_pipeline_sync,
)
from gtm.utils.slug import make_slug

DATA_DIR = Path("data")
LEADS_FILE = DATA_DIR / "leads_input.csv"
OUTPUTS_DIR = Path("outputs")

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s — %(message)s")

st.set_page_config(page_title="EliseAI GTM Tool", layout="wide")
st.title("EliseAI GTM Lead Enrichment")

tab_add, tab_run, tab_view = st.tabs(["➕ Add Lead", "▶️ Run Pipeline", "📊 View Results"])


# ── Tab 1: Add Lead ────────────────────────────────────────────────────────
with tab_add:
    st.subheader("Add a new lead")
    with st.form("add_lead"):
        c1, c2 = st.columns(2)
        name      = c1.text_input("Contact name *")
        email     = c2.text_input("Email *")
        company   = c1.text_input("Company *")
        prop_addr = c2.text_input("Property address")
        city      = c1.text_input("City *")
        state     = c2.text_input("State (2-letter) *", max_chars=2)
        submitted = st.form_submit_button("Add Lead", type="primary")

    if submitted:
        required = {"name": name, "email": email, "company": company, "city": city, "state": state}
        missing = [k for k, v in required.items() if not v.strip()]
        if missing:
            st.error(f"Required fields missing: {', '.join(missing)}")
        else:
            append_lead_to_csv(
                {"name": name, "email": email, "company": company,
                 "property_address": prop_addr, "city": city, "state": state.upper()},
                LEADS_FILE,
            )
            st.success(f"Added: {name} at {company} ({city}, {state.upper()})")


# ── Tab 2: Run Pipeline ────────────────────────────────────────────────────
with tab_run:
    st.subheader("Process pending leads")
    leads = load_leads_from_csv(LEADS_FILE)
    pending = [
        lead for lead in leads
        if not (OUTPUTS_DIR / make_slug(lead.company, lead.city, lead.state)).exists()
    ]
    done_count = len(leads) - len(pending)

    if not leads:
        st.info("No leads in `data/leads_input.csv`. Add some in the Add Lead tab.")
    else:
        m1, m2 = st.columns(2)
        m1.metric("Pending", len(pending))
        m2.metric("Already processed", done_count)

        if not pending:
            st.success("All leads are processed. Check the View Results tab.")
        else:
            st.dataframe(
                [{"Name": lead.name, "Company": lead.company, "City": lead.city, "State": lead.state}
                 for lead in pending],
                use_container_width=True,
                hide_index=True,
            )
            if st.button("▶️ Run Pipeline", type="primary"):
                with st.spinner(f"Enriching {len(pending)} lead(s) — ~20s per lead…"):
                    try:
                        results = run_pipeline_sync(pending, OUTPUTS_DIR)
                        st.success(f"Done — {len(results)} lead(s) enriched.")
                        st.dataframe(
                            [{"Company": r.raw.company, "City": r.raw.city,
                              "Score": f"{r.score:.0f}", "Tier": r.tier}
                             for r in results],
                            use_container_width=True,
                            hide_index=True,
                        )
                    except Exception as exc:
                        st.error(f"Pipeline error: {exc}")


# ── Tab 3: View Results ────────────────────────────────────────────────────
with tab_view:
    folders = list_output_folders(OUTPUTS_DIR)

    if not folders:
        st.info("No processed leads yet. Run the pipeline first.")
    else:
        options = {display: path for display, path in folders}
        selected = st.selectbox("Select a lead", list(options.keys()))

        if selected:
            enrichment, assessment, email_text = load_lead_data(options[selected])

            render_score_header(
                assessment["score"], assessment["tier"], assessment.get("insights", [])
            )
            st.divider()
            render_category_metrics(assessment["breakdown"])
            render_signal_table(assessment["breakdown"])
            st.divider()

            left, right = st.columns(2)
            with left:
                render_market_section(enrichment["market"])
                render_person_section(enrichment["person"])
            with right:
                render_company_section(enrichment["company"])
                render_email_section(email_text)
