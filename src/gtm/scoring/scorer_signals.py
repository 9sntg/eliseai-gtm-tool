"""Signal evaluation functions and threshold constants for the lead scorer.

Each function maps a single enrichment field to a 0.0–1.0 value.
A None input always returns 0.0 — missing data scores zero; the enrichment
module already logged the warning when the field was unavailable.
"""

from __future__ import annotations

from datetime import date

# --- Threshold constants — all boundary values live here, never inline in logic ---

# Market signals
RENTER_UNITS_LOW: int = 10_000
RENTER_UNITS_MID: int = 50_000
RENTER_UNITS_HIGH: int = 100_000
RENTER_UNITS_MAX: int = 200_000

RENTER_RATE_LOW: float = 0.35
RENTER_RATE_MID: float = 0.45
RENTER_RATE_HIGH: float = 0.55

MEDIAN_RENT_LOW: int = 1_000
MEDIAN_RENT_MID: int = 1_500
MEDIAN_RENT_HIGH: int = 2_000

GROWTH_FLAT: float = 0.0
GROWTH_HIGH: float = 0.02

# Company signals
JOB_POSTINGS_MID: int = 3
JOB_POSTINGS_HIGH: int = 5

EMPLOYEE_FLOOR: int = 50
EMPLOYEE_MID: int = 100
EMPLOYEE_HIGH: int = 500
EMPLOYEE_MAX: int = 1_000

COMPANY_AGE_YOUNG: int = 5
COMPANY_AGE_MATURE: int = 10

# PM platforms are replacement targets; any match scores full marks.
PM_TECH: frozenset[str] = frozenset({"yardi", "realpage", "entrata", "mri", "appfolio"})

# Person signals — scored by lookup; anything not in the map scores 0.1
SENIORITY_SCORE: dict[str, float] = {
    "c_suite": 1.0, "owner": 1.0, "partner": 1.0,
    "vp": 0.85, "director": 0.70,
    "manager": 0.50, "senior": 0.30,
}
DEPARTMENT_SCORE: dict[str, float] = {
    "operations": 1.0, "property_management": 1.0,
    "real_estate": 0.80, "leasing": 0.80,
    "finance": 0.50, "accounting": 0.50,
}

# --- Market signal functions ---

def score_renter_units(units: int | None) -> float:
    """Score renter-occupied housing units (market size signal)."""
    if units is None:
        return 0.0
    if units >= RENTER_UNITS_MAX:
        return 1.0
    if units >= RENTER_UNITS_HIGH:
        return 0.75
    if units >= RENTER_UNITS_MID:
        return 0.5
    if units >= RENTER_UNITS_LOW:
        return 0.25
    return 0.0


def score_renter_rate(rate: float | None) -> float:
    """Score renter-occupancy rate (share of housing that is renter-occupied)."""
    if rate is None:
        return 0.0
    if rate >= RENTER_RATE_HIGH:
        return 1.0
    if rate >= RENTER_RATE_MID:
        return 0.75
    if rate >= RENTER_RATE_LOW:
        return 0.5
    return 0.25


def score_median_rent(rent: int | None) -> float:
    """Score median gross rent (higher rent = higher-value market for EliseAI)."""
    if rent is None:
        return 0.0
    if rent >= MEDIAN_RENT_HIGH:
        return 1.0
    if rent >= MEDIAN_RENT_MID:
        return 0.75
    if rent >= MEDIAN_RENT_LOW:
        return 0.4
    return 0.1


def score_population_growth(growth: float | None) -> float:
    """Score YoY population growth fraction (positive growth = rising renter demand)."""
    if growth is None:
        return 0.0
    if growth > GROWTH_HIGH:
        return 1.0
    if growth >= GROWTH_FLAT:
        return 0.5
    return 0.1


def score_economic_momentum(growth: float | None) -> float:
    """Score YoY income growth (proxy for improving economic conditions)."""
    return score_population_growth(growth)


# --- Company signal functions ---

def score_job_postings(organic_count: int) -> float:
    """Score leasing job posting count (active hiring = growth mode = likely buyer)."""
    if organic_count >= JOB_POSTINGS_HIGH:
        return 1.0
    if organic_count >= JOB_POSTINGS_MID:
        return 0.6
    if organic_count >= 1:
        return 0.3
    return 0.0


def score_portfolio_news(organic_count: int, has_knowledge_graph: bool) -> float:
    """Score company web presence from Serper (knowledge graph + organic results)."""
    if has_knowledge_graph and organic_count >= 3:
        return 1.0
    if has_knowledge_graph or organic_count >= 3:
        return 0.75
    if organic_count >= 1:
        return 0.5
    return 0.0


def score_tech_stack(tech_stack: list[str]) -> float:
    """Score tech stack: PM-specific tools = replacement pitch; any tech = established."""
    if not tech_stack:
        return 0.0
    lower_stack = [t.lower() for t in tech_stack]
    if any(pm in name for pm in PM_TECH for name in lower_stack):
        return 1.0
    return 0.5


def score_employee_count(count: int | None) -> float:
    """Score employee headcount (larger orgs have higher EliseAI ROI potential)."""
    if count is None:
        return 0.0
    if count >= EMPLOYEE_MAX:
        return 1.0
    if count >= EMPLOYEE_HIGH:
        return 0.8
    if count >= EMPLOYEE_MID:
        return 0.6
    if count >= EMPLOYEE_FLOOR:
        return 0.3
    return 0.1


def score_company_age(founded_year: int | None) -> float:
    """Score company age by founding year; older = more legacy tech debt = stronger pitch."""
    if founded_year is None:
        return 0.0
    age_years = date.today().year - founded_year
    if age_years > COMPANY_AGE_MATURE:
        return 1.0
    if age_years >= COMPANY_AGE_YOUNG:
        return 0.6
    return 0.2


# --- Person signal functions ---

def score_seniority(seniority: str | None) -> float:
    """Score PDL seniority level (c_suite/vp/director have budget authority)."""
    if seniority is None:
        return 0.1
    return SENIORITY_SCORE.get(seniority.lower(), 0.1)


def score_department_function(department: str | None) -> float:
    """Score PDL department/function (operations and PM are the primary EliseAI buyers)."""
    if department is None:
        return 0.1
    return DEPARTMENT_SCORE.get(department.lower(), 0.1)


def score_corporate_email(is_corporate: bool) -> float:
    """Score email domain type (corporate = professional contact at established org)."""
    return 1.0 if is_corporate else 0.0
