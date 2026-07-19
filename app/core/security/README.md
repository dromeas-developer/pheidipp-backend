# app/core/security/

## Purpose
Self-contained sub-package owning credential hashing and token issuance/verification. Password hashing uses bcrypt at cost factor 12. Token primitives are split into short-lived HS256 JWT access tokens (stateless, signed) and opaque single-use refresh tokens (SHA-256 hash persisted, raw value returned once). This package does not own athlete identity — that lives in the model layer.

## Contents
| File | Responsibility |
|---|---|
| `password_hasher.py` | `PasswordHasher` — bcrypt hashing and constant-time verification with 72-byte input cap |
| `token_service.py` | `TokenService` — JWT access token signing/verification and opaque refresh token generation/hashing/expiry |

## Architecture Notes
- `PasswordHasher` applies a deliberate 72-byte truncation before hashing to match bcrypt's input cap, preventing silent truncation asymmetry between `hash()` and `verify()`.
- `TokenService.issue_access_token` embeds a fresh random `jti` (UUID4) per issuance so two tokens for the same athlete within the same second produce distinct JWT strings.
- Refresh tokens use `secrets.token_urlsafe(48)` for raw generation and SHA-256 hex digest for persistence; the raw value is never stored.
- `TokenService.refresh_expiry` enforces a 30-day TTL from issuance; `RefreshTokenRepository.is_active` forms an independent second expiry mechanism on the same row, per ADR-005.

## Cross-References
- [ADR-005: IP Address and Token Hash Security](../../../docs/adr/005-ip-address-and-token-hash-security.md) — governs refresh token expiry invariants and the field denylist in the parent `logging_utils.py`
