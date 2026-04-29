"""Streamlit dashboard — Add Lead, Run Pipeline, Overview, Lead Details."""

from __future__ import annotations

import logging
from pathlib import Path

import streamlit as st

from gtm.dashboard.helpers import (
    _lead_label,
    append_lead_to_csv,
    list_output_folders,
    load_lead_data,
    load_leads_from_csv,
    render_category_metrics,
    render_insights,
    render_outreach_section,
    render_overview_table,
    render_score_header,
    render_sidebar,
    render_signal_table,
    run_pipeline_sync,
)
from gtm.dashboard.render import (
    render_building_section,
    render_company_section,
    render_contact_section,
    render_market_section,
)
from gtm.utils.slug import make_slug

DATA_DIR = Path("data")
LEADS_FILE = DATA_DIR / "leads_input.csv"
OUTPUTS_DIR = Path("outputs")

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s — %(message)s")

st.set_page_config(page_title="EliseAI GTM Tool", layout="wide")

with st.sidebar:
    render_sidebar(OUTPUTS_DIR)

st.title("EliseAI GTM Lead Enrichment")

tab_add, tab_run, tab_overview, tab_details = st.tabs(
    ["Add Lead", "Run Pipeline", "Overview", "Lead Details"]
)


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
        if not (OUTPUTS_DIR / make_slug(
            lead.company, lead.city, lead.state, lead.property_address or ""
        )).exists()
    ]
    done_count = len(leads) - len(pending)

    if not leads:
        st.info("No leads in `data/leads_input.csv`. Add some in the Add Lead tab.")
    else:
        m1, m2 = st.columns(2)
        m1.metric("Pending", len(pending))
        m2.metric("Already processed", done_count)

        if not pending:
            st.success("All leads processed. Check the Overview or Lead Details tabs.")
        else:
            st.dataframe(
                [{"Name": lead.name, "Company": lead.company, "City": lead.city, "State": lead.state}
                 for lead in pending],
                use_container_width=True,
                hide_index=True,
            )
            if st.button("Run Pipeline", type="primary"):
                with st.spinner(f"Enriching {len(pending)} lead(s) — ~20s per lead..."):
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


# ── Tab 3: Overview ────────────────────────────────────────────────────────
with tab_overview:
    st.subheader("All Leads")
    render_overview_table(OUTPUTS_DIR)


# ── Tab 4: Lead Details ────────────────────────────────────────────────────
with tab_details:
    folders = list_output_folders(OUTPUTS_DIR)
    if not folders:
        st.info("No processed leads yet. Run the pipeline first.")
    else:
        labels = [_lead_label(p) for p in folders]
        folder_map = dict(zip(labels, folders, strict=True))

        default_idx = 0
        selected_slug = st.session_state.get("selected_lead")
        if selected_slug:
            slug_to_idx = {p.name: i for i, p in enumerate(folders)}
            default_idx = slug_to_idx.get(selected_slug, 0)

        selected_label = st.selectbox("Lead", labels, index=default_idx)
        selected_folder = folder_map[selected_label]
        enrichment, assessment, email_text = load_lead_data(selected_folder)

        contact  = enrichment.get("contact", {})
        market   = enrichment.get("market", {})
        company  = enrichment.get("company", {})
        building = enrichment.get("building", {})

        inner_enrich, inner_score, inner_outreach = st.tabs(
            ["Enrichment", "Scoring", "Outreach"]
        )

        with inner_enrich:
            col_l, col_r = st.columns(2)
            with col_l:
                render_contact_section(contact)
                render_market_section(market, contact)
            with col_r:
                render_company_section(company, contact)
                render_building_section(building, contact)

        with inner_score:
            render_score_header(assessment["lead_score"], assessment["tier"])
            render_insights(assessment.get("key_observations", []))
            st.markdown("")
            render_category_metrics(assessment)
            st.markdown("")
            render_signal_table(assessment)

        with inner_outreach:
            render_outreach_section(email_text)
