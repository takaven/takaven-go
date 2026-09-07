# Security

## Implemented

Single-operator password authentication is configured through environment variables. Opaque server-side sessions use HttpOnly, SameSite cookies. POST actions require CSRF. CSP and security headers are applied. `.env` is ignored. OpenAI credentials are server-side `SecretStr` configuration; no template or client script receives them. Signal evidence is treated as untrusted input for future AI prompts. Approved Product Truth is immutable; consequential actions create audit events.

## Planned / deferred

No production secret rotation, multi-user authorization, rate limiting, encrypted prompt archives, or external monitoring has been added.
