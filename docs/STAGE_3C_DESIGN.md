# Stage 3C design gate — AI-assisted concept challenge

## Frozen decision

Stage 3C solves one operator problem: after shortlisting a promising LeaseDesk concept, the operator needs a fast, evidence-grounded independent challenge before deciding whether to retain, revise, or kill it.

It is deliberately a **challenge checkpoint**, not a general AI writing suite. The smallest coherent scope is an operator-triggered AI challenge for one shortlisted concept, followed by operator-led revision and explicit rechallenge. AI experiment drafting and AI learning drafting are later checkpoints.

## Scope

In scope:

- challenge one shortlisted concept per explicit operator action;
- return the existing five challenge gates with structured reasoning;
- show unsupported-claim concerns separately from deterministic Stage 3B warnings;
- preserve the exact challenge input and output through `AIExecution` provenance;
- permit the operator to edit the concept, then explicitly request a new challenge;
- preserve past AI challenge assessments as immutable execution records; and
- retain existing manual challenge, RETAIN, REVISE and KILL controls.

Out of scope:

- AI choosing, ranking or retaining a winner;
- autonomous concept revision or accepting an AI rewrite;
- batch challenge of all shortlisted concepts;
- experiment drafting, learning drafting, publishing, background jobs, provider routing, parallel-run redesign or semantic-safety claims.

## Benchmark findings

Sources were accessed and verified against current first-party documentation on 2026-09-08.

| Product / workflow | Type | Proven pattern | Avoid | Takaven Go adoption / deliberate non-adoption |
| --- | --- | --- | --- | --- |
| [Figma AI Design Feedback](https://www.figma.com/solutions/ai-design-feedback-agent/) | AI-assisted critique | Contextual critique, visible feedback and iteration history; AI is a starting point rather than a human-review replacement. | A separate feedback universe or automatic edits. | Put challenge beside the concept and retain its history; do not let AI mutate the concept. |
| [Notion AI edit workflow](https://www.notion.com/help/guides/notion-ai-for-docs) | AI-assisted revision | Targeted action on selected material with explicit accept, discard or retry control. | Broad agentic rewriting and hidden page mutation. | Target one concept and keep operator control; do not add AI rewriting in Stage 3C. |
| [GitHub Copilot code review](https://docs.github.com/en/copilot/how-tos/use-copilot-agents/request-a-code-review/use-code-review) | AI-assisted critique/re-review | AI feedback is advisory, suggestions require explicit application, and re-review is explicitly requested after changes. | Automatic remediation, repository-scale context gathering and AI approval authority. | Use explicit challenge/rechallenge and advisory findings; do not auto-apply repairs or treat AI review as approval. |
| [Optimizely hypothesis workflow](https://support.optimizely.com/hc/en-us/articles/16504831061773-Hypothesis-workflow) and [history](https://support.optimizely.com/hc/en-us/articles/25191016996749-Hypothesis-creation-walkthrough) | Non-AI workflow/provenance comparator | Structured workflow, required approval and durable hypothesis history. | Assignment, calendars, templates and workflow administration for one operator. | Preserve structured gates, approvals and history; do not import work-management machinery. |

## Operator flow

1. Operator opens a shortlisted concept in its frozen Creative Run.
2. Operator selects **Challenge with AI**. No call runs automatically.
3. The UI shows a pending/running execution state and blocks duplicate challenge requests for that exact concept fingerprint.
4. A structured assessment appears beside the concept. It is advice, not a decision.
5. Operator may save a manual challenge, RETAIN, REVISE or KILL. Existing hard promotion rules remain authoritative.
6. On REVISE, the operator edits the concept. The existing concept stays the operational object; each challenge execution preserves the exact concept snapshot it assessed.
7. Operator explicitly selects **Rechallenge**. The new assessment is a new provenance record and never overwrites the prior assessment.

## AI input contract

The challenge request must contain deterministic JSON evidence, kept separate from higher-priority instructions.

### Initial challenge

- the exact concept-field snapshot being assessed, including its deterministic claim warnings;
- the Creative Run's frozen Product Truth, whitespace and selected Signal snapshots;
- every approved same-product Learning existing at execution time, ordered by `approved_at` then `id` and copied into the input snapshot.

The initial challenge must exclude the current manual `Challenge`, operator gate verdicts, operator recommendation, and any RETAIN/REVISE/KILL intent. It is a blind independent assessment. The manual assessment remains separately visible to the operator.

### Rechallenge after operator revision

Rechallenge supplies the same frozen run evidence plus the previous concept snapshot, previous AI assessment, and revised current concept snapshot. Its explicit purpose is to determine whether the revision addressed earlier weaknesses while reassessing all five gates. It never receives manual gate verdicts or the operator's recommendation. It creates a new execution and never overwrites the previous assessment.

Signals, Learnings and any free text are untrusted data, not control instructions. The input must preserve confidence labels in Product Truth. No fresh data, web research, named distribution targets or inferred product capability may be introduced.

## Structured output contract

The schema remains bounded and maps directly to the existing manual challenge form:

- five named gates — Remarkable, Logo-Off, Product-Owned, Commercially Convertible, Buyable / Internally Defensible — each with `verdict: PASS | WEAK | FAIL`, concise `reasoning`, and an `evidence_refs` list containing one to five allowed input references;
- strongest reason it might work;
- strongest objection;
- unsupported-claim check, distinguishing a concern from a confirmed product claim;
- smallest viable repair; and
- recommendation: `GO`, `REVISE` or `KILL`.

Evidence references identify only supplied input locations, for example `concept.creative_mechanic`, `concept.product_proof`, `truth.magic_moment`, `truth.prohibited_claims`, `signal:<snapshot-id>`, or `learning:<id>`. Unsupported-claim concerns must identify the relevant concept field and Truth basis. This is lightweight decision provenance, not a citation engine or semantic-safety system.

There is no composite score, ranking, winner, experiment object, revision text or automatic status transition. Product-Owned `FAIL` and unresolved unsupported claims continue to block retention through the existing domain rule; AI output cannot bypass it.

## Human decision boundary

Only the operator can save a manual assessment and choose `RETAIN`, `REVISE` or `KILL`. AI may recommend, identify a risk and suggest the smallest repair; it cannot edit the concept, resolve a claim warning, promote a concept, create an experiment or change run state.

An AI challenge marked PASS does not create or satisfy the manual `Challenge` required by current domain logic. It does not authorize RETAIN. The operator must still complete and save the manual five-gate challenge before retention; current KILL and REVISE rules remain unchanged.

Deterministic Stage 3B warning detection remains a guardrail, not semantic safety proof. Human challenge remains responsible for deciding whether a claim is unsupported in context.

## Revision and rechallenge

`REVISE` means the operator changes the concept deliberately using the existing edit path. AI-generated repaired variants are out of scope because they would create a second ideation surface and require acceptance/version semantics not needed to prove independent challenge.

Rechallenge is explicit. It creates a new `AIExecution` with its own input snapshot, output and timestamps. This supplies audit reconstruction for each assessed concept state without overwriting the prior assessment. The accepted manual challenge remains independently editable and is never silently replaced by AI output.

## Snapshot identity and database invariant

Before creating an execution, canonical JSON is constructed from all eight Concept content fields plus the lexically sorted deterministic `claim_warnings`, with stable field names, sorted object keys, UTF-8 encoding and compact separators. `SHA-256(canonical_json)` is the challenge `input_fingerprint` persisted on nullable `AIExecution.input_fingerprint`.

Challenge executions use `origin_type = concept`, `origin_id = concept.id`, `task_type = challenge_concept`, and the fingerprint. Request-level unique idempotency keys remain separate. PostgreSQL and SQLite enforce a partial unique invariant over `origin_type + origin_id + task_type + input_fingerprint` where `task_type = challenge_concept` and status is `pending`, `running`, or `succeeded`.

Therefore an unchanged concept with a pending/running/succeeded challenge is blocked, a failed attempt releases the slot for explicit retry, and an operator content edit produces a new fingerprint that permits explicit rechallenge. The Stage 3B one-success-forever generation invariant is not reused for challenges.

## Failure and retry semantics

- One bounded structural repair is permitted for malformed structured output; a second malformed result is `FAILED`.
- Authentication, permission, billing, configuration and provider errors do not enter a structural-repair loop.
- Expected failures persist a failed `AIExecution`, preserve prior concept/challenge work and return an understandable retry action.
- One pending/running/succeeded challenge execution is allowed for the same concept fingerprint. A failed execution releases an explicit retry. A content revision produces a distinct fingerprint for explicit rechallenge.
- Unexpected programming errors remain visible rather than being relabelled as provider failures.

## UI states

For a shortlisted concept: no assessment → **Challenge with AI**; pending/running → visible state and no duplicate CTA; failed → visible error plus **Retry challenge**; succeeded → gate card, evidence link and **Rechallenge after revision** only when the concept changed. The manual challenge form remains available as the operator's independent override.

## Provenance and verification

Implementation must extend the existing `AIExecution` trace pattern rather than introduce agent infrastructure. PostgreSQL verification must prove structured challenge persistence, exact frozen input/output provenance, one-slot duplicate protection, failure preservation and clean migration downgrade/re-upgrade.

Automated and rendered UI coverage must prove all five gates render, AI cannot promote a concept, Product-Owned `FAIL` and unresolved claims still block retention, revision preserves previous assessment provenance, explicit rechallenge creates a new record, and Stage 1–3B regressions remain green.

## Real-provider acceptance gate

One controlled GitHub quality workflow using `gpt-5.6-sol` and the existing synthetic LeaseDesk fixture performs exactly two normal model actions: initial concept → AI Challenge #1 → deterministic synthetic operator revision → AI Rechallenge #2. The existing single structural-repair allowance applies independently only when an output is malformed; multiple models and repeated favourable-result runs are prohibited.

The sanitized artifact must contain both immutable executions and prove the concept snapshots differ, fingerprints differ, the first assessment remains preserved, and all five gates are reassessed. Independent review must confirm grounded reasoning, identification of a real weakness, whether the deterministic revision addressed it, useful objections/repairs, no invented capability, no automatic domain transition, and defensible claim treatment. API success alone is not acceptance.

## Implementation slices

1. **Challenge foundation:** schema/service/input-output contracts, execution provenance, provider failures and PostgreSQL migration smoke.
2. **Rendered challenge:** operator-triggered CTA, execution states, gate assessment display and manual-decision boundary.
3. **Revision/rechallenge:** explicit revised-state snapshot, prior assessment visibility, second execution and regression/real-provider gate.

Stage 3C stops after these slices. AI experiment drafting and AI learning drafting require separate design gates.
