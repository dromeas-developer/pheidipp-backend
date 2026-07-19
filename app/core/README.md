# app/core/

## Purpose
Cross-cutting platform primitives — security (password hashing, JWT access tokens, opaque refresh tokens), safe audit logging for authentication events, and a versioned prompt template registry. Modules here are platform concerns, not domain concerns.

## Contents
| File | Responsibility |
|---|---|
| `logging_utils.py` | Field-filtered auth logging with credential denylist and in-process metric counters |
| `prompt_registry.py` | Filesystem-backed, versioned prompt template loader with in-memory caching |

## Architecture Notes
- `security/` is a self-contained sub-package owning credential hashing (`PasswordHasher`) and token issuance/verification (`TokenService`). It is re-exported via `app/core/security/__init__.py`.
- `logging_utils.py` applies a dual filter (allow-list + denylist) on structured log payloads to prevent credential, secret, and PII leakage — the denylist is defence-in-depth on top of the allow-list.
- `prompt_registry.py` caches prompt templates in memory for the process lifetime; hot-reload is intentionally unsupported.

## Cross-References
- [ADR-005: IP Address and Token Hash Security](../docs/adr/005-ip-address-and-token-hash-security.md) — governs the field denylist in `logging_utils.py` and refresh token expiry invariants in `security/token_service.py`
