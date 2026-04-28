"""JSON file cache with 24-hour TTL for API responses."""

import hashlib
import json
import logging
import time
from pathlib import Path

logger = logging.getLogger(__name__)

TTL_SECONDS: int = 86_400
DEFAULT_CACHE_DIR = Path(".cache")


class FileCache:
    """Persist API responses as JSON files keyed by SHA-256 hash of the cache key."""

    def __init__(self, cache_dir: Path = DEFAULT_CACHE_DIR) -> None:
        self._dir = cache_dir
        self._dir.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        digest = hashlib.sha256(key.encode()).hexdigest()
        return self._dir / f"{digest}.json"

    def get(self, key: str) -> dict | None:
        """Return cached payload for key, or None if missing or expired."""
        path = self._path(key)
        if not path.exists():
            return None
        try:
            envelope = json.loads(path.read_text())
            if time.time() - envelope["cached_at"] > TTL_SECONDS:
                path.unlink(missing_ok=True)
                return None
            logger.debug("cache hit: %s", key)
            return envelope["payload"]
        except (KeyError, json.JSONDecodeError, OSError):
            return None

    def set(self, key: str, payload: dict) -> None:
        """Write payload to cache under key. Silently skips on write failure."""
        path = self._path(key)
        try:
            path.write_text(json.dumps({"cached_at": time.time(), "payload": payload}))
        except (OSError, TypeError) as exc:
            logger.warning("cache write failed for %s: %s", key, exc)
