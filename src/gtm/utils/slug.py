"""Output folder slug generation."""

import re
from pathlib import Path


def make_slug(company: str, city: str, state: str, address: str = "") -> str:
    """Return lowercased, hyphenated slug.

    With address: {company}-{address}-{city}-{state}
    Without:      {company}-{city}-{state}
    """

    def clean(s: str) -> str:
        return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")

    parts = [company, address, city, state] if address.strip() else [company, city, state]
    return "-".join(clean(p) for p in parts)


def unique_slug(base: str, outputs_dir: Path) -> str:
    """Return base if its folder doesn't exist, otherwise append -2, -3, …"""
    if not (outputs_dir / base).exists():
        return base
    n = 2
    while (outputs_dir / f"{base}-{n}").exists():
        n += 1
    return f"{base}-{n}"
