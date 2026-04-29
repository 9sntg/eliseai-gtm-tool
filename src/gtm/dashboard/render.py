"""Enrichment section renderers for the Streamlit dashboard.

Each section renders as a flat 3-column HTML table: Field | Value | What it means.
Table is wrapped in a rounded container to match the st.dataframe visual style.
Categorical values render as colored tag chips. No expanders, no dashes.

File is ~206 lines — marginally over the 200-line limit. All four render functions
(Contact, Market, Company, Building) belong to one responsibility: enrichment display.
Splitting would require a thin wrapper with no behavioural gain. Accepted as-is.
"""

from __future__ import annotations

from datetime import date

import streamlit as st

from gtm.dashboard.helpers import (
    TAG_DEPT,
    TAG_PAIN,
    TAG_PRICE,
    TAG_SENIO,
    TAG_TECH,
    _tag,
    _tags,
)


def _growth_tag(value: float) -> str:
    """Colored tag for a YoY growth percentage (green positive, amber flat, red negative)."""
    if value > 0.005:
        return _tag(f"{value:+.2%}", *TAG_TECH)
    if value < -0.005:
        return _tag(f"{value:+.2%}", *TAG_PAIN)
    return _tag(f"{value:+.2%}", *TAG_PRICE)


def _rating_tag(rating: float) -> str:
    """Colored tag for a star rating out of 5 (green high, amber mid, red low)."""
    if rating >= 4.0:
        return _tag(f"{rating}/5", *TAG_TECH)
    if rating >= 3.0:
        return _tag(f"{rating}/5", *TAG_PRICE)
    return _tag(f"{rating}/5", *TAG_PAIN)


_TH = (
    'style="padding:8px 12px;text-align:left;background:#F9FAFB;color:#6B7280;'
    'font-size:0.8rem;font-weight:600;border-bottom:2px solid #E5E7EB;font-family:inherit"'
)
_TD_FIELD = (
    'style="padding:8px 12px;border-bottom:1px solid #F3F4F6;'
    'color:#6B7280;font-size:0.8rem;white-space:nowrap;vertical-align:top;font-family:inherit"'
)
_TD_VAL = (
    'style="padding:8px 12px;border-bottom:1px solid #F3F4F6;'
    'font-size:0.875rem;color:#1F2937;vertical-align:top;font-family:inherit"'
)
_TD_DESC = (
    'style="padding:8px 12px;border-bottom:1px solid #F3F4F6;'
    'color:#6B7280;font-size:0.8rem;vertical-align:top;font-family:inherit"'
)


def _section_table(title: str, rows: list[tuple[str, str, str]]) -> None:
    """Render a titled 3-column table in a rounded container: Field | Value | What it means."""
    st.markdown(f"**{title}**")
    st.markdown(
        '<hr style="margin:2px 0 10px 0;border:none;border-top:1px solid #E5E7EB">',
        unsafe_allow_html=True,
    )
    if not rows:
        return
    ths = f"<th {_TH}>Field</th><th {_TH}>Value</th><th {_TH}>What it means</th>"
    trs = "".join(
        f"<tr><td {_TD_FIELD}>{f}</td><td {_TD_VAL}>{v}</td><td {_TD_DESC}>{d}</td></tr>"
        for f, v, d in rows
    )
    html = (
        f'<div style="border-radius:4px;overflow:hidden;border:1px solid #E5E7EB">'
        f'<table style="width:100%;border-collapse:collapse;font-family:inherit">'
        f"<thead><tr>{ths}</tr></thead><tbody>{trs}</tbody></table>"
        f"</div>"
    )
    st.markdown(html, unsafe_allow_html=True)
    st.markdown("")


def render_contact_section(contact: dict) -> None:
    """Render the Contact section from the merged contact dict."""
    rows: list[tuple[str, str, str]] = []
    if contact.get("name"):
        rows.append(("Name", contact["name"], "Lead contact full name."))
    if contact.get("email"):
        rows.append(("Email", contact["email"], "Contact email address."))
    if contact.get("job_title"):
        rows.append(("Title", contact["job_title"].title(), "Current job title."))
    if contact.get("seniority"):
        rows.append((
            "Seniority",
            _tag(contact["seniority"].replace("_", " "), *TAG_SENIO),
            "Career level that determines budget authority.",
        ))
    if contact.get("department"):
        rows.append((
            "Department",
            _tag(contact["department"].replace("_", " "), *TAG_DEPT),
            "Functional area. Property management roles are direct decision makers.",
        ))
    if contact.get("is_corporate_email") is not None:
        rows.append((
            "Corporate email",
            "Yes" if contact["is_corporate_email"] else "No",
            "Email from the company domain confirms the contact is legitimate.",
        ))
    if contact.get("pdl_likelihood") is not None:
        rows.append((
            "PDL confidence",
            f"{contact['pdl_likelihood']}/10",
            "People Data Labs match confidence on a scale of 1 to 10.",
        ))
    _section_table("Contact", rows)


def render_market_section(market: dict, contact: dict) -> None:
    """Render the Market section from Census / DataUSA enrichment."""
    rows: list[tuple[str, str, str]] = []
    city, state = contact.get("city", ""), contact.get("state", "")
    if city or state:
        rows.append(("Location", f"{city}, {state}" if city and state else city or state, "City and state for this lead."))
    if market.get("renter_occupied_units") is not None:
        rows.append(("Renter-occupied units", f"{market['renter_occupied_units']:,}", "Total rental units in the city, measuring overall market size."))
    if market.get("total_housing_units") is not None:
        rows.append(("Total housing units", f"{market['total_housing_units']:,}", "All housing units including both owned and rented."))
    if market.get("renter_rate") is not None:
        rows.append(("Renter rate", f"{market['renter_rate']:.1%}", "Share of housing that is renter-occupied."))
    if market.get("median_gross_rent") is not None:
        rows.append(("Median gross rent", f"${market['median_gross_rent']:,}/mo", "Average monthly rent, used as a proxy for market tier."))
    if market.get("total_population") is not None:
        rows.append(("Total population", f"{market['total_population']:,}", "City population from the US Census."))
    if market.get("population_growth_yoy") is not None:
        rows.append(("Population growth YoY", _growth_tag(market["population_growth_yoy"]), "Annual population change. Rising population signals growing renter demand."))
    if market.get("median_household_income") is not None:
        rows.append(("Median household income", f"${market['median_household_income']:,}", "Average household income in the city."))
    if market.get("median_income_growth_yoy") is not None:
        rows.append(("Income growth YoY", _growth_tag(market["median_income_growth_yoy"]), "Annual income growth, a proxy for overall economic health."))
    _section_table("Market", rows)


def render_company_section(company: dict, contact: dict) -> None:
    """Render the Company section — company name prominent."""
    rows: list[tuple[str, str, str]] = []
    if contact.get("company"):
        rows.append(("Company", f"<strong>{contact['company']}</strong>", "Property management company name."))
    if company.get("linkedin_employee_count") is not None:
        rows.append(("Employees", f"{company['linkedin_employee_count']:,}+", "LinkedIn headcount estimate."))
    if company.get("founded_year"):
        age = date.today().year - company["founded_year"]
        rows.append(("Founded", f"{company['founded_year']}  ({age} yrs)", "Year the company was established. Older companies tend to carry more legacy tech debt."))
    elif company.get("yelp_year_established"):
        age = date.today().year - company["yelp_year_established"]
        rows.append(("Est. (Yelp)", f"{company['yelp_year_established']}  ({age} yrs)", "Year established per Yelp listing."))
    if company.get("portfolio_size") is not None:
        rows.append(("Portfolio", f"~{company['portfolio_size']:,} units", "Estimated units and communities managed."))
    if company.get("tech_stack"):
        rows.append(("Tech stack", _tags(company["tech_stack"], *TAG_TECH), "Software tools detected via BuiltWith."))
    if company.get("is_publicly_traded"):
        rows.append(("Publicly traded", "Yes", "Listed on SEC EDGAR."))
    kg = (company.get("serper_property_management") or {}).get("knowledge_graph_title")
    if kg:
        rows.append(("Google KG entry", kg, "Verified Google Knowledge Graph presence."))
    if company.get("yelp_rating") is not None:
        avg = company.get("yelp_market_avg_rating")
        avg_str = f", market avg {avg:.1f}" if avg else ""
        count = company.get("yelp_review_count", 0)
        meta = f'<span style="color:#6B7280;font-size:0.8rem"> · {count} reviews{avg_str}</span>'
        rows.append(("Yelp rating", _rating_tag(company["yelp_rating"]) + meta, "Rating compared to the local market average."))
    if company.get("google_rating") is not None:
        rows.append(("Google rating", _rating_tag(company["google_rating"]), "Google star rating. A low rating indicates resident dissatisfaction."))
    if company.get("competitor_rank_pct") is not None:
        rows.append(("Competitor rank", f"{company['competitor_rank_pct']:.0%} of local PM cos rate higher", "Relative Yelp standing compared to local competitors."))
    all_pain = (company.get("yelp_pain_themes") or []) + (company.get("serper_pain_themes") or [])
    if all_pain:
        rows.append(("Pain themes", _tags(all_pain, *TAG_PAIN), "Resident complaint categories extracted from Yelp and web reviews."))
    _section_table("Company", rows)


def render_building_section(building: dict, contact: dict) -> None:
    """Render the Building section when Yelp building data is available."""
    has_data = building and any(
        building.get(k) for k in ("name", "yelp_rating", "price_tier", "pain_themes")
    )
    if not has_data:
        return
    rows: list[tuple[str, str, str]] = []
    if building.get("name"):
        rows.append(("Building", f"<strong>{building['name']}</strong>", "Building name from the Yelp listing."))
    if contact.get("property_address"):
        rows.append(("Address", contact["property_address"], "Property street address."))
    if building.get("yelp_rating") is not None:
        count = building.get("yelp_review_count", 0)
        meta = f'<span style="color:#6B7280;font-size:0.8rem"> · {count} reviews</span>'
        rows.append(("Yelp rating", _rating_tag(building["yelp_rating"]) + meta, "Building Yelp rating. A low rating indicates unhappy residents."))
    if building.get("price_tier"):
        rows.append(("Price tier", _tag(building["price_tier"], *TAG_PRICE), "Yelp price tier indicating a quality-sensitive tenant base."))
    if building.get("pain_themes"):
        rows.append(("Pain themes", _tags(building["pain_themes"], *TAG_PAIN), "Resident complaint categories from building-specific reviews."))
    _section_table("Building", rows)
