# Security

## Implemented

Single-operator password authentication is configured through environment variables. Opaque server-side sessions use HttpOnly, SameSite cookies. POST actions require CSRF. CSP and security headers are applied. `.env` is ignored. OpenAI credentials are server-side `SecretStr` configuration; no template or client script receives them. Stage 3B generation groundwork delimits frozen Signals and Learnings as untrusted evidence/data; prompt injection is reduced by role separation and validation, not claimed to be solved. Approved Product Truth is immutable; consequential actions create audit events.

## Planned / deferred

No production secret rotation, multi-user authorization, rate limiting, encrypted prompt archives, or external monitoring has been added.
