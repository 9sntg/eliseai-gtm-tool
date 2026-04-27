# Enrichment Module Rules

## Interface

Every enrichment module exposes one public async function:

```python
async def enrich(lead: RawLead, client: httpx.AsyncClient) -> <DataModel>
```

- Takes a `RawLead` and a shared `httpx.AsyncClient`.
- Returns the appropriate Pydantic model (`MarketData`, `CompanyData`, `PersonData`).
- Never raises. Returns an empty/default model on any failure.

## Error Handling

- Wrap every API call in try/except. Never let an exception escape `enrich()`.
- Catch the narrowest exception type whose recovery you understand:
  - `httpx.TimeoutException` — request timed out
  - `httpx.HTTPStatusError` — non-2xx response
  - `(ValueError, KeyError, TypeError)` — parse errors on untrusted response data
- Only use `except Exception` when multiple distinct failure modes share the same
  recovery path — document why with a short inline comment.
- Never silently swallow. Always `logger.warning("context: %s", exc)` before returning default.

## HTTP Status Codes

Handle these consistently across all modules:

| Status | Behavior |
|---|---|
| 200–299 | Parse response normally |
| 401 / 403 | `logger.error(...)` + raise `ConfigurationError` — retrying won't help; missing/invalid API key |
| 404 | `logger.info(...)` + return empty model — resource not found is expected |
| 429 | Retry with exponential backoff (use `tenacity`); if exhausted, log WARNING + return empty |
| 5xx | Same as 429 — transient, retry then degrade |

HTTP retry logic lives inside the enrichment module, not the pipeline runner. Callers see either a result or an empty model — never raw HTTP details.

## Rate Limiting

- Every module that calls an external API must implement randomized delays between requests.
- Fixed delays create detectable patterns — randomize within a range.
- Delay lives in the module that makes the request, not the caller.
- Standard pattern: `await asyncio.sleep(random.uniform(DELAY_MIN, DELAY_MAX))`
- Constants at module top: `DELAY_MIN = 1.0`, `DELAY_MAX = 3.0`
- Log every real outbound request at INFO with context: `"Serper: querying '%s' (req 1/2)"`.

## Caching

- Use `FileCache` from `src/utils/cache.py` for all API responses.
- Cache key = a deterministic string from the inputs (e.g. `f"census:{state_fips}:{place_fips}"`).
- Log cache hits at DEBUG: `"cache hit: census:06:53000"`.
- Never cache error responses — only cache successful (2xx) responses.

## Async vs Sync

- Enrichment modules are async. Scoring and email generation are sync.
- Do not mix async and sync in the same file without a comment explaining why.
- Never call `asyncio.run()` inside an enrichment module — that responsibility belongs to
  `pipeline/runner.py`.

## Fallback Values

Good fallback values match the field's declared type:
- `None` for optional scalars
- `[]` for lists
- `0` for counters
- `False` for flags

Bad fallback values: `"N/A"`, `"unknown"`, `"[error]"`, `-1`, `0` for a field where 0 is meaningful.
Use `None` — downstream code reading `None` knows the data wasn't captured.
