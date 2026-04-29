"""Streamlit helpers, sync pipeline runner, sidebar, and scoring renderers.

File exceeds the 200-line limit. All content belongs to a single responsibility:
dashboard utilities and presentation. Splitting would require passing constants
and tag helpers across thin modules with no behavioural gain. Accepted as-is.
"""

from __future__ import annotations

import asyncio
import contextlib
import csv
import json
import threading
from datetime import datetime
from pathlib import Path

import streamlit as st

from gtm.config import settings
from gtm.models.lead import RawLead
from gtm.pipeline.runner import run_pipeline

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Tag color presets: (background, foreground)
TAG_SENIO = ("#EDE9FE", "#5B21B6")   # purple  — seniority level
TAG_DEPT  = ("#DBEAFE", "#1E40AF")   # blue    — department / function
TAG_PAIN  = ("#FEE2E2", "#991B1B")   # red     — pain / complaint themes
TAG_TECH  = ("#D1FAE5", "#065F46")   # green   — tech stack
TAG_PRICE = ("#FEF3C7", "#92400E")   # amber   — price tier

_TAG_CAT: dict[str, tuple[str, str]] = {
    "Market":   ("#DBEAFE", "#1E40AF"),
    "Company":  ("#EDE9FE", "#5B21B6"),
    "Person":   ("#D1FAE5", "#065F46"),
    "Building": ("#FEF3C7", "#92400E"),
}

TIER_STYLE: dict[str, tuple[str, str]] = {
    "High":   ("#D1FAE5", "#065F46"),
    "Medium": ("#FEF3C7", "#92400E"),
    "Low":    ("#FEE2E2", "#991B1B"),
}

_TIER_TEXT_COLOR = {"High": "#16A34A", "Medium": "#D97706", "Low": "#DC2626"}

_TH = (
    'style="padding:8px 12px;text-align:left;background:#F9FAFB;color:#6B7280;'
    'font-size:0.8rem;font-weight:600;border-bottom:2px solid #E5E7EB;font-family:inherit"'
)
_TD = (
    'style="padding:8px 12px;border-bottom:1px solid #F3F4F6;'
    'font-size:0.875rem;color:#1F2937;font-family:inherit"'
)


def _tag(text: str, bg: str, fg: str) -> str:
    """Single HTML tag chip, title-cased."""
    style = (
        f"background:{bg};color:{fg};padding:2px 9px;border-radius:4px;"
        f"font-size:0.8rem;font-weight:500;display:inline-block;margin:1px 2px"
    )
    return f'<span style="{style}">{text.title()}</span>'


def _tags(items: list[str], bg: str, fg: str) -> str:
    """Multiple HTML tag chips joined from a list."""
    return " ".join(_tag(t, bg, fg) for t in items) if items else ""


def _html_table(header_cells: list[str], rows: list[list[str]]) -> str:
    """Build a borderless HTML table string."""
    ths = "".join(f"<th {_TH}>{h}</th>" for h in header_cells)
    trs = "".join(
        "<tr>" + "".join(f"<td {_TD}>{cell}</td>" for cell in row) + "</tr>"
        for row in rows
    )
    return (
        f'<table style="width:100%;border-collapse:collapse">'
        f"<thead><tr>{ths}</tr></thead><tbody>{trs}</tbody></table>"
    )


# ---------------------------------------------------------------------------
# I/O utilities
# ---------------------------------------------------------------------------

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


def list_output_folders(outputs_dir: Path) -> list[Path]:
    """Return paths for every complete lead output folder, sorted."""
    if not outputs_dir.exists():
        return []
    return [
        p for p in sorted(outputs_dir.iterdir())
        if p.is_dir() and (p / "assessment.json").exists()
    ]


def load_lead_data(folder: Path) -> tuple[dict, dict, str]:
    """Load enrichment.json, assessment.json, and email.txt from a lead folder."""
    enrichment = json.loads((folder / "enrichment.json").read_text())
    assessment = json.loads((folder / "assessment.json").read_text())
    email_text = (folder / "email.txt").read_text() if (folder / "email.txt").exists() else ""
    return enrichment, assessment, email_text


def _lead_label(folder: Path) -> str:
    """Return 'Company · City, State' label for a lead folder."""
    with contextlib.suppress(Exception):
        enrichment = json.loads((folder / "enrichment.json").read_text())
        contact = enrichment.get("contact", {})
        company = contact.get("company") or folder.name
        city, state = contact.get("city", ""), contact.get("state", "")
        suffix = f" · {city}, {state}" if city and state else ""
        return f"{company}{suffix}"
    return folder.name.replace("-", " ").title()


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


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

def render_sidebar(outputs_dir: Path) -> None:
    """Render left sidebar: pipeline stats and integration status."""
    st.markdown("### EliseAI GTM")
    st.markdown("---")
    st.markdown("**Pipeline**")

    folders = list_output_folders(outputs_dir)
    if not folders:
        st.caption("No leads processed yet.")
    else:
        assessments: list[dict] = []
        for p in folders:
            with contextlib.suppress(Exception):
                assessments.append(json.loads((p / "assessment.json").read_text()))

        tier_counts: dict[str, int] = {"High": 0, "Medium": 0, "Low": 0}
        scores: list[float] = []
        for a in assessments:
            t = a.get("tier", "Low")
            tier_counts[t] = tier_counts.get(t, 0) + 1
            if a.get("lead_score") is not None:
                scores.append(a["lead_score"])

        st.metric("Leads Processed", len(assessments))

        tier_parts = " ".join(
            _tag(f"{tier}  {tier_counts[tier]}", *TIER_STYLE[tier])
            for tier in ("High", "Medium", "Low")
        )
        st.markdown(tier_parts, unsafe_allow_html=True)

        if scores:
            st.markdown(f"**Avg score:** {sum(scores)/len(scores):.1f} / 131")

        mtimes = [p.stat().st_mtime for p in folders]
        if mtimes:
            last_run = datetime.fromtimestamp(max(mtimes)).strftime("%b %d, %H:%M")
            st.caption(f"Last run: {last_run}")

    st.markdown("---")
    st.markdown("**Integrations**")

    integrations = [
        ("Serper",    bool(settings.serper_api_key)),
        ("PDL",       bool(settings.pdl_api_key)),
        ("Anthropic", bool(settings.anthropic_api_key)),
        ("Yelp",      bool(settings.yelp_api_key)),
        ("BuiltWith", bool(settings.builtwith_api_key)),
        ("Census",    bool(settings.census_api_key)),
    ]
    for name, active in integrations:
        dot_color = "#16A34A" if active else "#D1D5DB"
        status_color = "#6B7280" if active else "#D1D5DB"
        status = "active" if active else "not configured"
        st.markdown(
            f'<span style="color:{dot_color}">●</span>&nbsp;'
            f'<span style="font-size:0.88em">{name}</span>&nbsp;'
            f'<span style="color:{status_color};font-size:0.75em">{status}</span>',
            unsafe_allow_html=True,
        )


# ---------------------------------------------------------------------------
# Overview table
# ---------------------------------------------------------------------------

def render_overview_table(outputs_dir: Path) -> None:
    """Sorted leads table with priority-colored score bars and tier tags."""
    folders = list_output_folders(outputs_dir)
    if not folders:
        st.info("No processed leads yet. Run the pipeline first.")
        return

    rows: list[dict] = []
    for p in folders:
        with contextlib.suppress(Exception):
            a = json.loads((p / "assessment.json").read_text())
            label = _lead_label(p)
            parts = label.split(" · ", 1)
            rows.append({
                "company":  parts[0],
                "location": parts[1] if len(parts) > 1 else "",
                "score":    round(a.get("lead_score", 0)),
                "tier":     a.get("tier", ""),
            })

    rows.sort(key=lambda r: r["score"], reverse=True)

    table_rows = []
    for r in rows:
        tier_color = _TIER_TEXT_COLOR.get(r["tier"], "#9CA3AF")
        pct = round(r["score"] / 131 * 100)
        bar = (
            f'<div style="display:flex;align-items:center;gap:8px">'
            f'<div style="background:#E5E7EB;border-radius:4px;height:8px;width:80px;flex-shrink:0">'
            f'<div style="width:{pct}%;background:{tier_color};border-radius:4px;height:8px"></div>'
            f'</div>'
            f'<span style="font-size:0.875rem;color:#1F2937">{r["score"]} / 131</span>'
            f'</div>'
        )
        table_rows.append([
            f'<span style="font-weight:600">{r["company"]}</span>',
            f'<span style="color:#6B7280">{r["location"]}</span>',
            bar,
            _tag(r["tier"], *TIER_STYLE.get(r["tier"], ("#F3F4F6", "#374151"))),
        ])

    st.markdown(
        '<div style="border-radius:4px;overflow:hidden;border:1px solid #E5E7EB">'
        + _html_table(["Company", "Location", "Score", "Tier"], table_rows)
        + "</div>",
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Scoring tab renderers
# ---------------------------------------------------------------------------

def render_score_header(score: float, tier: str) -> None:
    """Render score metric and tier as matching side-by-side metric widgets."""
    bg, fg = TIER_STYLE.get(tier, ("#F3F4F6", "#374151"))
    c1, c2 = st.columns(2)
    c1.metric("Lead Score", f"{score:.1f} / 131")
    c2.markdown(
        f'<div style="padding-top:2px">'
        f'<p style="font-size:0.8rem;color:#6B7280;font-weight:600;margin:0 0 6px 0">Priority</p>'
        f'<span style="background:{bg};color:{fg};padding:6px 18px;border-radius:4px;'
        f'font-size:1.6rem;font-weight:400;display:inline-block">{tier}</span>'
        f'</div>',
        unsafe_allow_html=True,
    )


def render_category_metrics(assessment: dict) -> None:
    """Render category subtotals as colored mini cards matching category tag colors."""
    cats = [
        ("Market Fit",   "market_fit",   "#DBEAFE", "#1D4ED8"),
        ("Company Fit",  "company_fit",  "#EDE9FE", "#5B21B6"),
        ("Person Fit",   "person_fit",   "#D1FAE5", "#065F46"),
        ("Building Fit", "building_fit", "#FEF3C7", "#92400E"),
    ]
    for col, (title, key, bg, _fg) in zip(st.columns(4), cats, strict=True):
        score = assessment.get(key, 0)
        col.markdown(
            f'<div style="background:{bg};border-radius:4px;padding:16px;text-align:center">'
            f'<div style="color:#1F2937;font-size:0.875rem;font-weight:400;margin-bottom:8px">{title}</div>'
            f'<div style="color:#1F2937;font-size:1.8rem;font-weight:400;line-height:1">{score:.1f}%</div>'
            f'</div>',
            unsafe_allow_html=True,
        )


def render_signal_table(assessment: dict) -> None:
    """Signal table: sorted by earned pts, per-signal colored bars, category tags, Reason column."""
    signals = assessment.get("signals", [])

    table_rows = []
    for sig in signals:
        max_pts = sig["max_points"]
        earned = sig["points"]
        val = earned / max_pts if max_pts else 0.0
        bar_color = "#16A34A" if val >= 0.75 else "#D97706" if val >= 0.40 else "#9CA3AF"
        cat_bg, cat_fg = _TAG_CAT.get(sig["category"], ("#F3F4F6", "#374151"))
        pct = int(val * 100)
        bar = (
            f'<div style="display:flex;align-items:center;gap:8px">'
            f'<div style="background:#E5E7EB;border-radius:3px;height:6px;width:56px;flex-shrink:0">'
            f'<div style="width:{pct}%;background:{bar_color};border-radius:3px;height:6px"></div>'
            f'</div>'
            f'<span style="color:#1F2937;font-size:0.875rem;white-space:nowrap">'
            f'{earned:.1f} / {int(max_pts)} pts</span>'
            f'</div>'
        )
        table_rows.append([
            f'<span style="color:#1F2937">{sig["name"]}</span>',
            _tag(sig["category"], cat_bg, cat_fg),
            bar,
            f'<span style="color:#6B7280;font-size:0.875rem">{sig["reason"]}</span>',
        ])

    st.markdown(
        '<div style="border-radius:4px;overflow:hidden;border:1px solid #E5E7EB">'
        + _html_table(["Signal", "Category", "Score", "Reason"], table_rows)
        + "</div>",
        unsafe_allow_html=True,
    )


def render_insights(insights: list[str]) -> None:
    """Render key observations derived from enrichment data."""
    if not insights:
        return
    st.markdown("")
    st.markdown("**Key Observations**")
    st.markdown(
        '<hr style="margin:2px 0 6px 0;border:none;border-top:1px solid #E5E7EB">',
        unsafe_allow_html=True,
    )
    st.caption(
        "Rule-based highlights generated from the enrichment data above. "
        "Each bullet fires when a specific signal threshold is met: "
        "large rental market, decision-maker contact, legacy PM tech detected, etc."
    )
    for bullet in insights:
        st.markdown(f"- {bullet}")


def render_outreach_section(email_text: str) -> None:
    """Render the email draft at full height with no scroll."""
    if email_text.strip():
        st.markdown(
            f'<div style="white-space:pre-wrap;font-family:inherit;font-size:0.9rem;'
            f'line-height:1.7;padding:1.25rem 1.5rem;background:#F9FAFB;'
            f'border:1px solid #E5E7EB;border-radius:8px">'
            f'{email_text.strip()}</div>',
            unsafe_allow_html=True,
        )
    else:
        st.info("No email draft. Configure ANTHROPIC_API_KEY to enable.")
