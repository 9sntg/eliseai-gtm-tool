# Outreach / Email Generation Rules

## No Hallucination

- The email prompt must only inject data that is present in the `EnrichedLead` object.
- Never construct sentences like "You manage over X properties" unless `employee_count`
  or a portfolio size figure was actually returned by an API.
- If a field is None, omit that signal from the prompt entirely — do not use a placeholder
  or generic substitute.
- The system prompt must include an explicit instruction: "Only use data provided in the
  lead context. Do not invent statistics, company claims, or market figures."

## Prompt Caching

- The system prompt (EliseAI context, tone guidelines, no-hallucination rules) must be
  sent with `cache_control: {"type": "ephemeral"}`.
- This ensures one cache hit covers all leads processed in a single batch run.
- Never move product context into the user message — it belongs in the cached system prompt.

## Model

- Always use `claude-sonnet-4-6` (latest Sonnet). Do not use Haiku for email generation —
  output quality matters here.
- Temperature: 0.7 (some variation per lead, but not random).
- Max tokens: 400 (sufficient for a 150–200 word email).

## Output

- Return plain text only. No markdown formatting, no subject line unless explicitly added.
- Email should be 150–200 words. Enforce in the prompt: "Write a 150–200 word email."
- If the Claude API call fails, return `None` — do not return a generic template.
  The pipeline writes an empty `email.txt` and logs a WARNING. Never fake the email.

## Logging

- Log at INFO when the email is generated successfully: `"email drafted for {company} ({len(draft)} chars)"`
- Log at WARNING if the API call fails: `"email generation failed for {company}: {exc}"`
- Never log the email body itself — it may contain PII (contact names).
