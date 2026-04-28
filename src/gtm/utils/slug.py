"""Output folder slug generation."""

import re
from pathlib import Path


def make_slug(company: str, city: str, state: str) -> str:
    """Return lowercased, hyphenated slug: {company}-{city}-{state}."""

    def clean(s: str) -> str:
        return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")

    return "-".join(clean(p) for p in (company, city, state))


def unique_slug(base: str, outputs_dir: Path) -> str:
    """Return base if its folder doesn't exist, otherwise append -2, -3, …"""
    if not (outputs_dir / base).exists():
        return base
    n = 2
    while (outputs_dir / f"{base}-{n}").exists():
        n += 1
    return f"{base}-{n}"
