# Benchmarks

## Stage 3A — AI execution

FEATURE: AI execution traceability
BENCHMARKED AGAINST: OpenAI Responses API; LangSmith
PROVEN PATTERN: Bounded state, request metadata, error visibility, idempotency.
WE ADOPTED: Persisted AIExecution lifecycle and idempotency key.
WE IMPROVED: Kept it in the existing monolith.
WE DID NOT COPY: Queues, provider routing, autonomous retries.
BUILD IMPACT: Stage 3A foundation only.
SOURCE / DATE: Official OpenAI and LangSmith documentation, 2026-09-07.

## Stage 3B — Batch ideation

FEATURE: Evidence-grounded creative generation
BENCHMARKED AGAINST: Notion AI; ChatGPT Projects; OpenAI Responses API; LangSmith
PROVEN PATTERN: Explicit generation with source context, editable artifacts, human review.
WE ADOPTED: Frozen inputs, visible batch state, structured artifacts, manual narrowing.
WE IMPROVED: Exact 12-card batch with evidence beside review.
WE DID NOT COPY: Chat, model choice, open web search, auto-ranking.
BUILD IMPACT: Confirms the frozen Stage 3B generation design.
SOURCE / DATE: Official product documentation, 2026-09-07.
