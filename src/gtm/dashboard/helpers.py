"""Streamlit rendering helpers and sync pipeline runner for the dashboard."""

from __future__ import annotations

import asyncio
import contextlib
import csv
import json
import threading
from pathlib import Path

import streamlit as st

from gtm.models.lead import RawLead
from gtm.pipeline.runner import run_pipeline

SIGNAL_META: list[tuple[str, str, str]] = [
    ("renter_units",       "Renter-Occupied Units",    "Market"),
    ("renter_rate",        "Renter Rate",               "Market"),
    ("median_rent",        "Median Gross Rent",         "Market"),
    ("population_growth",  "Population Growth YoY",    "Market"),
    ("economic_momentum",  "Economic Momentum",         "Market"),
    ("job_postings",       "Job Postings",              "Company"),
    ("portfolio_news",     "Portfolio / Web Presence",  "Company"),
    ("tech_stack",         "Tech Stack",                "Company"),
    ("employee_count",     "Employee Count",            "Company"),
    ("company_age",        "Company Age",               "Company"),
    ("portfolio_size",      "Portfolio Size",            "Company"),
    ("social_presence",     "Social Media Presence",    "Company"),
    ("yelp_company_rating", "Yelp Rating vs. Market",   "Company"),
    ("seniority",           "Contact Seniority",        "Person"),
    ("department_function", "Department / Function",    "Person"),
    ("corporate_email",     "Corporate Email",          "Person"),
    ("building_rating",     "Building Yelp Rating",     "Building"),
    ("building_reviews",    "Building Review Volume",   "Building"),
]

TIER_COLOR: dict[str, str] = {"High": "🟢", "Medium": "🟡", "Low": "🔴"}


def load_leads_from_csv(path: Path) -> list[RawLead]:
    """Read RawLead objects from CSV; silently skip malformed rows."""
    if not path.exists():
        return []
    leads: list[RawLead] = []
    with path.open(newline="") as f:
        for row in csv.DictReader(f):
            with contextlib.suppress(Exception):
                leads.append(RawLead(**{k: v for k, v in row.items() if k in RawLead.model_fields}))
    return leads


def append_lead_to_csv(data: dict, path: Path) -> None:
    """Append one lead row to CSV, writing header if the file is new."""
    path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not path.exists() or path.stat().st_size == 0
    with path.open("a", newline="") as f:
        writer = csv.DictWriter(
            f, fieldnames=["name", "email", "company", "property_address", "city", "state"]
        )
        if write_header:
            writer.writeheader()
        writer.writerow(data)


def list_output_folders(outputs_dir: Path) -> list[tuple[str, Path]]:
    """Return (display_name, path) for every complete lead output folder."""
    if not outputs_dir.exists():
        return []
    return [
        (p.name.replace("-", " ").title(), p)
        for p in sorted(outputs_dir.iterdir())
        if p.is_dir() and (p / "assessment.json").exists()
    ]


def load_lead_data(folder: Path) -> tuple[dict, dict, str]:
    """Load enrichment.json, assessment.json, and email.txt from a lead folder."""
    enrichment = json.loads((folder / "enrichment.json").read_text())
    assessment = json.loads((folder / "assessment.json").read_text())
    email_text = (folder / "email.txt").read_text() if (folder / "email.txt").exists() else ""
    return enrichment, assessment, email_text


def run_pipeline_sync(leads: list[RawLead], outputs_dir: Path) -> list:
    """Run the async pipeline in a dedicated thread to avoid Streamlit event-loop conflicts."""
    results: list = []
    exc_holder: list = []

    def _worker() -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            results.extend(loop.run_until_complete(run_pipeline(leads, outputs_dir)))
        except Exception as exc:
            exc_holder.append(exc)
        finally:
            loop.close()

    t = threading.Thread(target=_worker)
    t.start()
    t.join()
    if exc_holder:
        raise exc_holder[0]
    return results


def render_score_header(score: float, tier: str, insights: list[str]) -> None:
    """Render the lead score, tier badge, and insight bullets."""
    icon = TIER_COLOR.get(tier, "⚪")
    col1, col2 = st.columns([1, 3])
    col1.metric("Lead Score", f"{score:.0f} / 100")
    with col2:
        st.markdown(f"### {icon} {tier} Priority")
        for bullet in insights:
            st.markdown(f"- {bullet}")


def render_category_metrics(breakdown: dict) -> None:
    """Render Market / Company / Person / Building subtotals as metric tiles."""
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Market Fit",   f"{breakdown.get('market_score',   0):.1f} / 100")
    c2.metric("Company Fit",  f"{breakdown.get('company_score',  0):.1f} / 100")
    c3.metric("Person Fit",   f"{breakdown.get('person_score',   0):.1f} / 100")
    c4.metric("Building Fit", f"{breakdown.get('building_score', 0):.1f} / 100")


def render_signal_table(breakdown: dict) -> None:
    """Render all 13 scoring signals as a colour-coded markdown table."""
    with st.expander("Signal Breakdown", expanded=False):
        rows = ["| Signal | Category | Score |", "|---|---|---|"]
        for key, label, category in SIGNAL_META:
            val = breakdown.get(key, 0.0)
            dot = "🟢" if val >= 0.75 else "🟡" if val >= 0.40 else "🔴"
            rows.append(f"| {label} | {category} | {dot} {val:.0%} |")
        st.markdown("\n".join(rows))


def render_market_section(market: dict) -> None:
    """Render market enrichment fields in a labelled expander."""
    with st.expander("📍 Market Data", expanded=True):
        _field(market, "renter_occupied_units", "Renter-occupied units",  lambda v: f"{v:,}")
        _field(market, "total_housing_units",   "Total housing units",    lambda v: f"{v:,}")
        _field(market, "renter_rate",           "Renter rate",            lambda v: f"{v:.1%}")
        _field(market, "median_gross_rent",     "Median gross rent",      lambda v: f"${v:,}/mo")
        _field(market, "total_population",      "Total population",       lambda v: f"{v:,}")
        _field(market, "population_growth_yoy", "Population growth YoY",  lambda v: f"{v:+.2%}")
        _field(market, "median_household_income","Median household income",lambda v: f"${v:,}")
        _field(market, "median_income_growth_yoy","Income growth YoY",    lambda v: f"{v:+.2%}")


def render_company_section(company: dict) -> None:
    """Render company enrichment fields in a labelled expander."""
    with st.expander("🏢 Company Data", expanded=True):
        _field(company, "linkedin_employee_count", "Employees",      lambda v: f"{v:,}+")
        _field(company, "founded_year",            "Founded",        lambda v: str(v))
        if company.get("is_publicly_traded"):
            st.write("**Publicly traded:** Yes")
        if company.get("tech_stack"):
            st.write(f"**Tech stack:** {', '.join(company['tech_stack'])}")
        job_count = len(company.get("serper_jobs", {}).get("organic", []))
        if job_count:
            st.write(f"**Open leasing roles:** {job_count}")
        kg = company.get("serper_property_management", {}).get("knowledge_graph_title")
        if kg:
            st.write(f"**Google Knowledge Graph:** {kg}")


def render_person_section(person: dict) -> None:
    """Render person enrichment fields in a labelled expander."""
    with st.expander("👤 Person Data", expanded=True):
        _field(person, "job_title",   "Title",      lambda v: v)
        _field(person, "seniority",   "Seniority",  lambda v: v.replace("_", " ").title())
        _field(person, "department",  "Department", lambda v: v.replace("_", " ").title())
        st.write(f"**Corporate email:** {'Yes' if person.get('is_corporate_email') else 'No'}")
        _field(person, "pdl_likelihood", "PDL match confidence", lambda v: f"{v}/10")


def render_building_section(building: dict) -> None:
    """Render building enrichment fields in a labelled expander."""
    with st.expander("🏢 Building Data", expanded=True):
        _field(building, "address",           "Address",        lambda v: v)
        _field(building, "yelp_rating",       "Yelp rating",    lambda v: f"{v}/5")
        _field(building, "yelp_review_count", "Yelp reviews",   lambda v: f"{v:,}")
        _field(building, "google_rating",     "Google rating",  lambda v: f"{v}/5")
        if building.get("pain_themes"):
            st.write(f"**Resident pain themes:** {', '.join(building['pain_themes'])}")


def render_email_section(email_text: str) -> None:
    """Render the email draft in a copyable text area."""
    with st.expander("✉️ Email Draft", expanded=True):
        if email_text.strip():
            st.text_area("", value=email_text, height=220, label_visibility="collapsed")
        else:
            st.info("No email draft — ANTHROPIC_API_KEY not configured.")


def _field(data: dict, key: str, label: str, fmt) -> None:
    """Write a single labelled field if value is not None."""
    val = data.get(key)
    if val is not None:
        st.write(f"**{label}:** {fmt(val)}")
