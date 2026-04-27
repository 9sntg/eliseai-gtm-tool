# General Coding Conventions

## File Size and Responsibility

- Max 200 lines per file. If a module exceeds this, split it.
- One responsibility per file. A file should not do two distinct things.
- If an enrichment module exceeds 200 lines, split by responsibility into a
  thin orchestrator + helpers (e.g. `serper.py` + `serper_helpers.py`).

## Functions

- Max ~30 lines per function. If longer, extract helpers.
- One thing per function.
- Type hints on all function signatures, including return types.
- Docstrings on all public functions (one-line is fine if the intent is obvious).

## Imports

- Standard library first, then third-party, then local — separated by blank lines.
- No wildcard imports (`from module import *`).

## Logging

- Use `logging` everywhere inside `src/`. Never use `print()` there.
- `print()` is reserved for `main.py` (CLI output via Rich) and `app.py` (Streamlit).
- Top of every module: `logger = logging.getLogger(__name__)`
- Log levels:
  - INFO — major stage completions: `"census enrichment done: Austin TX"`, `"scored lead: 74/100 High"`
  - DEBUG — field-level details, cache hits, intermediate values
  - WARNING — recoverable failures where a signal returns a default: `"PDL returned no match for email, seniority signal = 0"`
  - ERROR — only when a lead-level operation fails fatally
- Never log API keys, tokens, or PII. If logging an HTTP response body, truncate to ~200 chars.

## Constants

- No magic numbers inline in logic. Named constants at the top of the file.
- Examples: `MAX_RETRIES = 3`, `TIMEOUT_SECONDS = 15`, `SIMILARITY_THRESHOLD = 0.6`,
  `DELAY_MIN = 1.0`, `DELAY_MAX = 3.0`
- Scoring thresholds belong in `src/config.py` as named constants, not in `scorer.py`.
- Scoring weights are always referenced by name (`settings.WEIGHT_RENTER_UNITS`), never as inline floats.

## Data Contracts (Pydantic adaptation)

This project uses Pydantic models (not plain dicts) for type safety within the pipeline.
The contract rules still apply:

- All optional fields must have a typed default (None, [], {}, 0, False) — never absent.
  Downstream code should never need `if hasattr(model, "x")` or `if model.x is not None`
  for fields that are always present (just sometimes empty).
- When writing to disk (enrichment.json, assessment.json), always call `.model_dump()`
  to ensure JSON serializability. No datetime objects, sets, or Exceptions in output.
- Datetimes → ISO strings before writing. Use `model.model_dump(mode="json")`.

## Reproducibility

- No hardcoded absolute paths. Use `Path(__file__).parent` or paths relative to project root.
- All directories the pipeline writes to must be created at runtime:
  `path.mkdir(parents=True, exist_ok=True)` — never assume they exist.
- API keys come exclusively from `.env` via `src/config.py`. Never hardcode them.
- The pipeline must run on a clean clone + `uv sync` + `.env` populated. Nothing else.
