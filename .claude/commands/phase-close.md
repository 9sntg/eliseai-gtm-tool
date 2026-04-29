# Phase Close Checklist

Run this command at the end of every implementation phase before committing. It gates the commit on docs, tests, lint, and code quality — in that order. A failure at any step must be resolved before moving on.

Usage: `/phase-close <N>` where N is the phase number being closed (e.g. `/phase-close 4`).


## Step 1 — Docs completeness

Read each doc file and verify it reflects the phase just completed. Flag any section that is still a stub or references future work that was actually implemented.

```
cat docs/architecture.md
cat docs/api-notes.md
cat docs/scoring-logic.md
cat docs/rollout-plan.md
cat CLAUDE.local.md
```

**Enforce these rules:**

| File | What to check |
|---|---|
| `docs/architecture.md` | Phase log shows ✅ Done for Phase N. Component descriptions exist for every new module. |
| `docs/api-notes.md` | Every API touched in Phase N has an entry. Endpoints, response shapes, and quirks match the actual implementation. |
| `docs/scoring-logic.md` | If Phase N added or changed scoring signals: all thresholds are documented with rationale. |
| `docs/rollout-plan.md` | If Phase N introduced user-facing behaviour (CLI, dashboard, email): at least a stub section exists. |
| `CLAUDE.local.md` | Any deferred decisions created during Phase N are recorded. No decisions were silently forgotten. |

Report each file as ✅ current or ⚠️ needs update. Update any flagged file before continuing.


## Step 2 — Phase log verification

Confirm the architecture.md phase log row for Phase N reads `✅ Done` and the description matches what was actually built (not the original plan).

```
grep -A 2 "Phase $N" docs/architecture.md
```

If the row still shows `—` or the description is out of date, update it now.


## Step 3 — Full test suite

Run the complete test suite. Do not proceed if any test fails.

```
.venv/bin/python -m pytest tests/ -v --tb=short
```

Report: total passed, total failed, any warnings. If there are failures, stop here and fix them. Do not bypass this gate.


## Step 4 — Line count audit

Check every source file in `src/` for the 200-line rule. Flag any file that exceeds it.

```
find src/ -name "*.py" | xargs wc -l | sort -rn | head -20
```

For each file over 200 lines: either split it now or explicitly justify why it's acceptable (e.g. a model file with many optional fields). Document the justification in a comment at the top of the file if keeping it as-is.


## Step 5 — Ruff lint gate

Run the linter. Fix all errors before committing. Warnings may be noted but do not block.

```
.venv/bin/python -m ruff check src/ tests/
```

If ruff is not installed in the venv:
```
.venv/bin/python -m pip install ruff --quiet
```

Do not use `--fix` automatically — review each suggestion and apply it intentionally.


## Step 6 — Orphaned stubs check

Search for unfinished implementation markers in `src/`. Any hit in a non-test file is a potential blocker.

```
grep -rn "TODO\|FIXME\|raise NotImplementedError\|^\s*pass$" src/ --include="*.py"
```

For each hit:
- If it is intentional scaffolding for a future phase: add a comment `# Phase N+1` so the intent is clear.
- If it is leftover from this phase: implement or remove it now.
- Bare `pass` in `__init__.py` files or empty exception bodies is acceptable — note these as false positives.


## Step 7 — CLAUDE.local.md deferred decisions review

Read the deferred decisions file and list every open item.

```
cat CLAUDE.local.md
```

For each open item, state one of:
- **Still deferred** — reason it doesn't need to be resolved now.
- **Ready to resolve** — propose the resolution and wait for user confirmation before changing anything.
- **No longer relevant** — the item was superseded; remove it from CLAUDE.local.md.

Do not silently skip this step. Even "all items still deferred, no action needed" is a valid outcome.


## Step 8 — Commit and push

Once all steps above are green (or explicitly accepted), stage and commit the changes.

**Commit message format:**

```
phase <N>: <one-line summary of what was built>

- <bullet: key module or feature added>
- <bullet: key module or feature added>
- <bullet: tests added / updated>
- <bullet: docs updated>

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
```

Show the proposed commit message to the user and wait for confirmation before running `git commit`.

After the user confirms, stage only relevant files (never `git add -A` blindly — check `git status` first), commit, and push:

```
git status
git add <specific files>
git commit -m "..."
git push
```

Confirm the push succeeded and report the final commit hash.


## Phase Close Summary

After completing all steps, output a summary table:

| Check | Status | Notes |
|---|---|---|
| Docs completeness | ✅ / ⚠️ | |
| Phase log | ✅ / ⚠️ | |
| Tests | ✅ N passed | |
| Line count | ✅ / ⚠️ files over 200 | |
| Ruff lint | ✅ / ⚠️ N issues | |
| Orphaned stubs | ✅ / ⚠️ N hits | |
| Deferred decisions | ✅ reviewed | |
| Committed & pushed | ✅ / — | commit hash |
