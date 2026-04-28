"""Shared utilities: file cache, geocoder, slug generation."""

from gtm.utils.cache import FileCache
from gtm.utils.geocoder import FipsResult, get_fips
from gtm.utils.slug import make_slug, unique_slug

__all__ = ["FileCache", "FipsResult", "get_fips", "make_slug", "unique_slug"]
