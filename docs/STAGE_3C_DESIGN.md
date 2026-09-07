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

| Product / workflow | Proven pattern | Avoid | Takaven Go adoption |
| --- | --- | --- | --- |
| [Figma AI Design Feedback](https://www.figma.com/solutions/ai-design-feedback-agent/) | Contextual critique, visible feedback and iteration history; AI is a starting point rather than human review replacement. | A separate feedback universe or automatic edits. | Place challenge beside the concept, retain the assessment and make the operator act explicitly. |
| [Notion AI edit workflow](https://www.notion.com/help/guides/notion-ai-for-docs) | Targeted action on existing material, with accept, discard or retry control. | Broad agentic rewriting and hidden page mutation. | Challenge one named concept; operator can revise manually or discard the assessment. |
| [Optimizely hypothesis workflow](https://support.optimizely.com/hc/en-us/articles/16504831061773-Hypothesis-workflow) | Structured workflow and required approval before consequential completion. | Assignment, calendars, templates and workflow administration for a single operator. | Use structured gates and preserve the human approval boundary before Experiment promotion. |
| [Optimizely hypothesis history](https://support.optimizely.com/hc/en-us/articles/25191016996749-Hypothesis-creation-walkthrough) | Experiment evidence and decisions linked to a durable history. | A full experimentation work-management layer. | Link assessments to the concept/run and freeze the exact evidence used by every challenge. |

## Operator flow

1. Operator opens a shortlisted concept in its frozen Creative Run.
2. Operator selects **Challenge with AI**. No call runs automatically.
3. The UI shows a pending/running execution state and blocks duplicate challenge requests for that concept state.
4. A structured assessment appears beside the concept. It is advice, not a decision.
5. Operator may save a manual challenge, RETAIN, REVISE or KILL. Existing hard promotion rules remain authoritative.
6. On REVISE, the operator edits the concept. The existing concept stays the operational object; each challenge execution preserves the exact concept snapshot it assessed.
7. Operator explicitly selects **Rechallenge**. The new assessment is a new provenance record and never overwrites the prior assessment.

## AI input contract

The challenge request must contain deterministic JSON evidence, kept separate from higher-priority instructions:

- the exact concept-field snapshot being assessed, including its deterministic claim warnings;
- the Creative Run's frozen Product Truth, whitespace and selected Signal snapshots;
- same-product approved Learning snapshots frozen at execution time, only when useful to the challenge;
- the current manual challenge, if any, labelled as operator context rather than instruction; and
- on rechallenge, the prior assessment and the operator's revised concept snapshot, labelled as evidence.

Signals, Learnings and any free text are untrusted data, not control instructions. The input must preserve confidence labels in Product Truth. No fresh data, web research, named distribution targets or inferred product capability may be introduced.

## Structured output contract

The schema remains bounded and maps directly to the existing manual challenge form:

- five named gates — Remarkable, Logo-Off, Product-Owned, Commercially Convertible, Buyable / Internally Defensible — each with `PASS`, `WEAK` or `FAIL` and concise reasoning;
- strongest reason it might work;
- strongest objection;
- unsupported-claim check, distinguishing a concern from a confirmed product claim;
- smallest viable repair; and
- recommendation: `GO`, `REVISE` or `KILL`.

There is no composite score, ranking, winner, experiment object, revision text or automatic status transition. Product-Owned `FAIL` and unresolved unsupported claims continue to block retention through the existing domain rule; AI output cannot bypass it.

## Human decision boundary

Only the operator can save a manual assessment and choose `RETAIN`, `REVISE` or `KILL`. AI may recommend, identify a risk and suggest the smallest repair; it cannot edit the concept, resolve a claim warning, promote a concept, create an experiment or change run state.

Deterministic Stage 3B warning detection remains a guardrail, not semantic safety proof. Human challenge remains responsible for deciding whether a claim is unsupported in context.

## Revision and rechallenge

`REVISE` means the operator changes the concept deliberately using the existing edit path. AI-generated repaired variants are out of scope because they would create a second ideation surface and require acceptance/version semantics not needed to prove independent challenge.

Rechallenge is explicit. It creates a new `AIExecution` with its own input snapshot, output and timestamps. This supplies audit reconstruction for each assessed concept state without overwriting the prior assessment. The accepted manual challenge remains independently editable and is never silently replaced by AI output.

## Failure and retry semantics

- One bounded structural repair is permitted for malformed structured output; a second malformed result is `FAILED`.
- Authentication, permission, billing, configuration and provider errors do not enter a structural-repair loop.
- Expected failures persist a failed `AIExecution`, preserve prior concept/challenge work and return an understandable retry action.
- One pending/running/succeeded challenge execution is allowed for the same concept snapshot. A failed execution releases an explicit retry. A revision creates a distinct input state for an explicit rechallenge.
- Unexpected programming errors remain visible rather than being relabelled as provider failures.

## UI states

For a shortlisted concept: no assessment → **Challenge with AI**; pending/running → visible state and no duplicate CTA; failed → visible error plus **Retry challenge**; succeeded → gate card, evidence link and **Rechallenge after revision** only when the concept changed. The manual challenge form remains available as the operator's independent override.

## Provenance and verification

Implementation must extend the existing `AIExecution` trace pattern rather than introduce agent infrastructure. PostgreSQL verification must prove structured challenge persistence, exact frozen input/output provenance, one-slot duplicate protection, failure preservation and clean migration downgrade/re-upgrade.

Automated and rendered UI coverage must prove all five gates render, AI cannot promote a concept, Product-Owned `FAIL` and unresolved claims still block retention, revision preserves previous assessment provenance, explicit rechallenge creates a new record, and Stage 1–3B regressions remain green.

## Real-provider acceptance gate

One controlled `gpt-5.6-sol` run against the existing synthetic LeaseDesk fixture must produce a sanitized artifact with model, prompt/schema versions, frozen input, request ID, structured assessment and validation metadata. Independent review must confirm: grounded gate reasoning, useful objections and repairs, no invented capability, no autonomous decision, correct claim treatment and a credible distinction between concept proof and creative mechanic. API success alone is not acceptance.

## Implementation slices

1. **Challenge foundation:** schema/service/input-output contracts, execution provenance, provider failures and PostgreSQL migration smoke.
2. **Rendered challenge:** operator-triggered CTA, execution states, gate assessment display and manual-decision boundary.
3. **Revision/rechallenge:** explicit revised-state snapshot, prior assessment visibility, second execution and regression/real-provider gate.

Stage 3C stops after these slices. AI experiment drafting and AI learning drafting require separate design gates.
