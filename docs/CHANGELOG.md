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

## [Stage 3C Slice 1 — Under review]

### Added
- Versioned five-gate challenge schema and initial blind `challenge_concept` service for one shortlisted concept.
- Canonical concept-snapshot SHA-256 provenance and a separate database challenge-slot invariant.
- Deterministic same-product Learning input, bounded evidence references and one structural repair attempt.

### Verified
- Deterministic service coverage and Stage 1–3B regression suite.
- Real PostgreSQL challenge persistence, duplicate/failed-retry/edited-snapshot semantics, state preservation and clean migration downgrade/re-upgrade.

### Not started
- Rendered AI challenge, revision/rechallenge UI and real-provider Stage 3C quality validation.
