"""Project-wide exception types."""


class ConfigurationError(Exception):
    """Raised when an API key is missing or invalid (HTTP 401/403).

    Retrying will not help — the operator must fix the key in .env.
    """
