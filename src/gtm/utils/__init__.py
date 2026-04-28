"""Shared utilities: file cache, geocoder, slug generation, email helpers."""

from gtm.utils.cache import FileCache
from gtm.utils.email import is_corporate_email
from gtm.utils.geocoder import FipsResult, get_fips
from gtm.utils.slug import make_slug, unique_slug

__all__ = ["FileCache", "FipsResult", "get_fips", "is_corporate_email", "make_slug", "unique_slug"]
