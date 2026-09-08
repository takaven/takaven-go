# Changelog

## [Stage 1]

### Added
- LeaseDesk Product Truth, versioning, authentication and audit foundation.
### Verified
- Real PostgreSQL migrations and immutable Truth behavior.

## [Stage 2]

### Added
- Manual signals, creative runs, challenge, experiments, results and learning.
### Verified
- Full manual operator loop.

## [Checkpoint 3A]

### Added
- OpenAI configuration boundary, AIExecution entity, structured schema foundation and idempotency.
### Verified
- Real PostgreSQL, application/UI regression and configuration failure handling.
### Deferred
- All AI-generated workflow actions.

## [Checkpoint 3B — Accepted]

### Added
- Generate-12 UI, frozen-input provenance, bounded structural repair and one-batch database protection.
- Real PostgreSQL Generate-12 persistence smoke and rendered twelve-card/shortlist-cap workflow verification.
### Verified
- Real run 1: gpt-5.6-sol / 3b-v1 passed structural and grounding verification but failed independent output-quality review for demo-centric repetition and false-positive warnings.
- Real run 2: gpt-5.6-sol / 3b-v2 succeeded with exactly 12 concepts, one attempt/no repair and zero claim warnings; independent output-quality review passed and Stage 3B was accepted.

## [Stage 3C Slice 1 — Accepted]

### Added
- Versioned five-gate challenge schema and initial blind `challenge_concept` service for one shortlisted concept.
- Canonical concept-snapshot SHA-256 provenance and a separate database challenge-slot invariant.
- Deterministic same-product Learning input, bounded evidence references and one structural repair attempt.

### Verified
- Deterministic service coverage and Stage 1–3B regression suite.
- Real PostgreSQL challenge persistence, duplicate/failed-retry/edited-snapshot semantics, state preservation and clean migration downgrade/re-upgrade.

### Verified
- Independent acceptance, 42 automated tests at the accepted head, real PostgreSQL challenge persistence and clean migration downgrade/re-upgrade.

## [Stage 3C Slice 2 — Under review]

### Added
- Explicit authenticated and CSRF-protected AI challenge action in the existing manual Challenge workspace.
- Current-fingerprint pending, running, failed/retry and succeeded states plus read-only historical assessment handling.
- Structured five-gate assessment, supplied-evidence references, advisory summary and compact execution trace.
- Clear visual boundary preserving the operator-authored manual challenge as the only consequential decision input.

### Verified
- Deterministic rendered route and end-to-end HTTP workflow coverage, including safe provider failure, explicit retry, stale-result handling and zero AI-created domain transitions.

### Not started
- Slice 3 operator revision/rechallenge and the Stage 3C real-provider initial/rechallenge quality gate.
