# Testing Rules

## No Network in Tests

- No test ever touches the network. All external API calls are mocked.
- Mock at the `httpx.AsyncClient` level — patch `client.get` or `client.post`.
- If a test fails because a real API key is missing, the test is written wrong.

## Independence

- Every module must be independently testable with a single function call.
- No test requires the full pipeline to run. `enrich()` functions, `score()`,
  and `generate_email()` all run in isolation with only their declared inputs.

## Structure

- `tests/conftest.py` holds all shared fixtures: `raw_lead`, mock API response
  payloads per module, and a temp `outputs/` directory.
- Each enrichment module gets at least two tests in `test_enrichment.py`:
  - Happy path: mock returns valid data, assert model fields are populated
  - Degradation path: mock returns 404 or raises, assert empty model returned and no exception raised
- `test_scorer.py` tests:
  - Each signal function at boundary values (e.g. renter_units at 0, 10_000, 50_000, 100_000, 200_000)
  - That weights sum to 1.0
  - BuiltWith-absent redistribution: when tech_stack is empty, portfolio_news signal receives the redistributed weight
- `test_pipeline.py` tests:
  - Full `run_pipeline()` with all 7 enrichment mocks in place
  - Assert that 3 output files are written per lead
  - Assert that a lead with an existing output folder is skipped (incremental logic)

## Async Tests

- Use `pytest-asyncio` with `asyncio_mode = "auto"` (configured in pyproject.toml).
- Async test functions are declared `async def test_...()` — no extra decorator needed.

## Fixtures

- Mock API responses should reflect realistic (but fake) payloads. Don't use
  empty dicts as mock responses — the parsing logic won't exercise real code paths.
- Use `pytest_mock.MockerFixture` (`mocker` fixture) for patching, not `unittest.mock`
  directly.

## Coverage

- Target: every signal function in `scorer.py` is exercised by at least one test.
- Target: every enrichment module's degradation path (API failure → empty model) is tested.
- Don't chase 100% line coverage for its own sake — test behavior, not implementation.
