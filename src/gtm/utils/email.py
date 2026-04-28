"""Email domain utilities."""

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
