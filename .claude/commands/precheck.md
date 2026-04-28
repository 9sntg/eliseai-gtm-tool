# Pre-Implementation Checklist

Before implementing any module, read the following files in order and confirm you have a clear picture of the project's purpose, constraints, and rules.

## Step 1 — Assessment instructions

Read the original take-home brief so implementation decisions stay aligned with what the evaluator expects:

```
cat instructions/eliseai-takehome-assessment-instructions.md
```

## Step 2 — Project overview

Read the README for the high-level description, how to run the tool, and the current project structure:

```
cat README.md
```

## Step 3 — Architecture and memory

Read CLAUDE.md for the full architecture summary, key design decisions, scoring model, output structure, and environment variables:

```
cat CLAUDE.md
```

## Step 4 — Coding rules

Read every rule file that governs the module you are about to implement:

```
cat .claude/rules/conventions.md
cat .claude/rules/enrichment.md
cat .claude/rules/scoring.md
cat .claude/rules/outreach.md
cat .claude/rules/tests.md
```

## Step 5 — Confirm before proceeding

After reading everything above, state:

1. **What you are about to build** — module name, file path, responsibility.
2. **Which rules apply** — list the rule files relevant to this module.
3. **Any open questions** — flag ambiguities before writing a single line of code.

Do not begin implementation until the user confirms your plan in Step 5.
