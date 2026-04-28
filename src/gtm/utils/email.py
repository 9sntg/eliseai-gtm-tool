"""Email domain utilities for corporate vs. free-provider detection.

Used by the PDL enrichment module to derive the ``is_corporate_email`` signal
without requiring a PDL API response.
"""

# Known free/consumer email providers — any domain not in this set is treated
# as a corporate address for scoring purposes.
FREE_DOMAINS: frozenset[str] = frozenset({
    "gmail.com", "yahoo.com", "hotmail.com", "outlook.com",
    "aol.com", "icloud.com", "mail.com", "protonmail.com",
    "live.com", "msn.com", "yahoo.co.uk", "googlemail.com",
})


def is_corporate_email(email: str) -> bool:
    """Return True if the email domain is not a known free provider."""
    if not email or "@" not in email:
        return False
    domain = email.split("@", 1)[1].lower().strip()
    return domain not in FREE_DOMAINS
