> **Baseline — migrated from** `docs/implementation/phase-1/phase-1-1-p1-email-password-auth.md` + `p2-security-invariants-patch.md` + `p3-single-primary-auth-enforcement.md` + `p4-jti-access-token.md` **on** 2026-07-19.
> This plan documents what was built in Phase 1-1, including all three security patches, verified against the current codebase on 2026-07-19.

## Batch Objective

Implement the first authentication layer for Pheidipp: email/password registration, email/password login, JWT access-token issuance (with per-issuance `jti`), 30-day refresh-token issuance with rotation, the `require_self` authorization dependency, and security invariants for token_hash non-disclosure, IP address truncation, 7-day IP discard, and single-primary AthleteAuth enforcement at the DB level. This plan establishes the secure identity foundation that all later sub-phases depend on.

## Preconditions

- PostgreSQL is running (brand new project — no prior schema)
- Alembic is initialized
- Object storage is not required at this layer

## Scope

- `POST /auth/register` — email/password registration with atomic `Athlete` + `AthleteAuth` + `AthleteProfile` + `RefreshToken` creation
- `POST /auth/login` — email/password login with token-pair issuance
- `POST /auth/refresh` — refresh-token rotation (revoke old, insert new atomically)
- JWT access-token signing/verification with 15-minute expiry and per-issuance `jti` (UUID4)
- Refresh-token issuance with 30-day expiry, append-only revocation ledger, multi-device support
- Bcrypt password hashing (cost ≥ 12), 72-byte truncation
- `require_self` dependency: 401 on invalid/expired token, 403 on athlete_id mismatch
- Email normalization (lowercase + strip) with DB-level unique index on `lower(email)`
- Security invariants:
  - `token_hash` never in API responses or logs
  - `ip_address` truncated to /24 (IPv4) or /64 (IPv6) in logs/events
  - `ip_address` discarded from `RefreshToken` records after 7 days
  - Partial unique index on `athlete_auths(athlete_id) WHERE is_primary = true`
- Production of `athlete_registered` and `athlete_logged_in` events via transactional outbox

## Out Of Scope

- OAuth providers (Google, Strava)
- Account linking, primary-method switching, auth-method removal
- Email verification flow, password reset flow
- Rate limiting or brute-force throttling
- Onboarding, training goals, twin bootstrap, full profile schema

## Steps

### Core Auth Implementation

1. [OWNER: Coder] Create `Athlete` model: `email` (unique via `lower(email)` index), `onboarding_complete` (default false), `created_at`. Register in `app/models/__init__.py`.

2. [OWNER: Coder] Create `AthleteAuth` model: `athlete_id` (FK), `provider` (enum), `hashed_password` (nullable), `is_primary`, `last_login_at`. Unique on `(athlete_id, provider)`. Register.

3. [OWNER: Coder] Create minimal `AthleteProfile` model: `athlete_id` (unique FK), `date_of_birth`, `sex`, `height_cm` (nullable), `updated_at`. One per athlete. Register.

4. [OWNER: Coder] Create `RefreshToken` model: `athlete_id` (FK), `token_hash` (unique), `expires_at`, `revoked_at` (nullable), `replaced_by_refresh_token_id` (self-ref FK, nullable), `ip_address` (nullable), `user_agent` (nullable), `created_at`. Append-only revocation ledger. Register.

5. [OWNER: Coder] Implement `PasswordHasher` in `app/core/security/password_hasher.py`: bcrypt cost 12, `hash(password)` truncates to 72 bytes, `verify(password, hashed)`. Constant-time comparison.

6. [OWNER: Coder] Implement `TokenService` in `app/core/security/token_service.py`: HS256 JWT, 15-min access token TTL with `jti` (UUID4), `sub`, `iat`, `exp`, `iss`, `athlete_id`, `auth_provider` claims. 30-day refresh token TTL. Refresh tokens use `secrets.token_urlsafe(48)`, hashed with SHA-256. `verify_access_token()` decodes and verifies signature/expiry without DB lookup.

7. [OWNER: Coder] Create `AthleteRepository` (`get_by_normalized_email`, `add`, `email_exists`, `is_unique_violation`), `AthleteAuthRepository` (`get_by_athlete_and_provider`, `get_email_auth_by_normalized_email`, `add`, `touch_last_login`), `RefreshTokenRepository` (`get_by_token_hash`, `add`, `is_active`), `AthleteProfileRepository` (`get_by_athlete_id`, `add`). All with `AsyncSession`, flush but no commit. Register.

8. [OWNER: Coder] Create `AuthService` in `app/services/auth_service.py`:
   - `register(email, password, profile)` — validate, normalize email, hash password, create `Athlete` + `AthleteAuth` (provider=email, is_primary=true) + minimal `AthleteProfile` + first `RefreshToken` in one transaction, commit, produce `athlete_registered`. Return token pair. 409 on duplicate email.
   - `login(email, password)` — lookup normalized email, verify password (constant-time), update `last_login_at`, create new `RefreshToken`, commit, produce `athlete_logged_in`. Return token pair. 401 on mismatch.
   - `rotate_refresh_token(raw_token)` — hash, lookup, verify active, create new `RefreshToken`, revoke old (atomically: `revoked_at` + `replaced_by_refresh_token_id`), issue new access token, commit, produce `athlete_logged_in` (token_type=refresh). 401 on missing/revoked/expired.

9. [OWNER: Coder] Create auth domain errors in `app/services/auth_errors.py`: `AuthError`, `DuplicateEmailError` (409), `InvalidCredentialsError` (401), `InvalidRefreshTokenError` (401), `CrossAthleteAccessError` (403), `UnauthenticatedError` (401).

10. [OWNER: Coder] Create auth schemas in `app/schemas/auth.py`: `RegisterRequest`, `LoginRequest`, `RefreshRequest`, `AthleteResponse`, `TokenPairResponse`, `AuthResponse`, `RefreshResponse`. Register.

11. [OWNER: Coder] Create `auth_router` in `app/api/v1/auth.py`: `POST /auth/register`, `POST /auth/login`, `POST /auth/refresh`. Each delegates to `AuthService`, translates domain errors to `HTTPException`. Register in `app/api/v1/__init__.py`.

12. [OWNER: Coder] Implement `require_self` dependency in `app/api/deps.py`: decode JWT via `TokenService.verify_access_token`, return 401 for invalid/expired, return 403 for athlete_id mismatch, inject `athlete_id`. Create `build_auth_service` factory.

13. [OWNER: Coder] Generate Alembic migration for all 4 tables with constraints and indexes: `athletes` (lower-email unique index), `athlete_auths` (athlete+provider unique, partial unique on is_primary), `athlete_refresh_tokens` (token_hash unique, athlete+expires index), `athlete_profiles` (athlete_id unique). Register models in `__init__.py`.

### Security Patch: token_hash & IP

14. [OWNER: Coder] Verify `token_hash` is never in any Pydantic response schema or log call. Add code comments in `logging_utils.py` listing `token_hash` and raw `ip_address` as forbidden fields.

15. [OWNER: Coder] Create `app/utils/ip_utils.py` with `truncate_ip(ip: str | None) -> str | None`: IPv4 → /24 (last octet zeroed), IPv6 → /64 (last 64 bits zeroed). Uses `ipaddress` stdlib. Unit test.

16. [OWNER: Coder] Apply IP truncation to all event/log emission sites in `AuthService`: `athlete_logged_in` event payload uses truncated IP. Raw IP still stored in DB. Any `_log` call passing raw `ip_address` switches to truncated version.

17. [OWNER: Coder] Add `RefreshTokenRepository.discard_old_ips()` — sets `ip_address = NULL` where `created_at < now - 7 days`. Idempotent. Register as a procrastinate task or cron script running daily.

### Security Patch: Single Primary Enforcement

18. [OWNER: Coder] Add partial unique index on `athlete_auths(athlete_id) WHERE is_primary = true` via Alembic migration. Name: `ix_athlete_auths_single_primary`. Downgrade drops the index. Update `01-entities/athlete-auth.md` to document DB-level enforcement.

### JWT jti Claim

19. [OWNER: Coder] Update `TokenService.issue_access_token()` to include `jti` claim (UUID4) in every issued access token. Verification ignores `jti` — no replay detection, no DB lookup. Already-issued tokens without `jti` remain valid until expiry. Do not expose `jti` in API responses.

## Context Needed

- `01-entities/athlete.md` — Athlete model, onboarding gate, require_self semantics
- `01-entities/athlete-auth.md` — credential storage, login validation, refresh-token lifecycle, primary method invariant
- `01-entities/athlete-profile.md` — minimal registration profile schema
- `00-foundations/event-catalogue.md` — `athlete_registered`, `athlete_logged_in` event contracts
- `docs/vision/product/brand-philosophy.md` — plain, non-technical auth errors
- `docs/vision/product/constraints.md` — security constraints

## Batch Success Criteria

- Registering with valid email/password creates exactly one `Athlete`, one `AthleteAuth` (provider=email, is_primary=true), one minimal `AthleteProfile`, and one `RefreshToken` in a single transaction
- Registering same email with different casing returns 409, no partial state
- `POST /auth/login` with wrong password returns 401; correct password returns token pair and updates `last_login_at`
- API responses and logs never contain `hashed_password`, plaintext passwords, raw refresh tokens, `token_hash`, `provider_tokens`, or `provider_user_id`
- `require_self` returns 401 for invalid/expired token, 403 for athlete mismatch (never 404)
- `POST /auth/refresh` with valid refresh token returns new token pair; old refresh token then returns 401
- Refresh-token rotation atomically revokes old token and inserts new append-only record with 30-day expiry
- Two independently-issued refresh tokens for same athlete rotate independently
- `athlete_registered` and `athlete_logged_in` events contain required payload fields, produced after commit
- JWT access tokens contain `jti` claim (UUID4); two tokens issued within same second have different `jti` values
- `ip_address` in event payloads is truncated to /24 or /64 (security patch)
- `RefreshToken.ip_address` is NULL for records older than 7 days (security patch)
- Partial unique index `ix_athlete_auths_single_primary` prevents multiple primaries at DB level (security patch)
- Inserting second `is_primary=true` for same athlete raises `IntegrityError` (security patch)

## Files Expected To Change

- `app/models/athlete.py` — new model
- `app/models/athlete_auth.py` — new model
- `app/models/athlete_profile.py` — new minimal model
- `app/models/athlete_refresh_token.py` — new model
- `app/models/__init__.py` — register models
- `app/core/security/password_hasher.py` — new
- `app/core/security/token_service.py` — new
- `app/repositories/athlete_repository.py` — new
- `app/repositories/athlete_auth_repository.py` — new
- `app/repositories/refresh_token_repository.py` — new (+ `discard_old_ips` method)
- `app/repositories/athlete_profile_repository.py` — new
- `app/repositories/__init__.py` — register repos
- `app/services/auth_errors.py` — new error classes
- `app/services/auth_results.py` — new result dataclasses
- `app/services/auth_service.py` — new service (+ IP truncation in events/logs)
- `app/services/__init__.py` — register service + errors
- `app/schemas/auth.py` — new schemas
- `app/schemas/__init__.py` — register schemas
- `app/api/v1/auth.py` — new routes
- `app/api/v1/__init__.py` — register `auth_router`
- `app/api/deps.py` — `require_self`, `get_current_athlete_id`, `build_auth_service`
- `app/utils/email_utils.py` — `normalize_email` (may exist already from consistency pass)
- `app/utils/ip_utils.py` — `truncate_ip` (security patch)
- `migrations/versions/<rev>_phase_1_1_auth.py` — main migration
- `migrations/versions/<rev>_phase_1_1_p3_single_primary_auth.py` — partial index migration

## Coder Notes

- **Phase 1.1 is the foundation**. `AthleteProfile` must be minimal — only `date_of_birth`, `sex`, `height_cm`. Full profile schema is Phase 1-2a.
- **Email uniqueness is DB-level**: functional unique index on `lower(email)`. Email normalization (`lowercase + strip`) at service layer before any DB call.
- **Bcrypt cost ≥ 12**. `PasswordHasher` truncates input to 72 bytes. Never store or log plaintext passwords.
- **Refresh-token rotation is atomic**: revocation of old token and insertion of new token in same transaction. Multi-device: rotating one refresh token does NOT revoke others (separate records per device).
- **`require_self` must distinguish**: 401 for token validity issues, 403 for athlete mismatch (never 404).
- **`token_hash` never leaked**: Verify no Pydantic response schema includes `RefreshToken` or `token_hash`. Logging allowlist excludes both.
- **IP truncation**: Raw IP stored in `RefreshToken.ip_address` for up to 7 days. Truncated IP used in event payloads and logs. Cleanup task runs daily via `discard_old_ips()`.
- **Single-primary index**: Partial unique on `(athlete_id) WHERE is_primary = true`. Application layer already sets correctly during registration — this defends against future bugs. No service code changes needed.
- **`jti` is stateless**: UUID4 in JWT payload only. No DB persistence, no replay detection. Already-issued tokens without `jti` remain valid. Verification ignores `jti`. `jti` not exposed in API responses.
- **Events after commit**: `athlete_registered` and `athlete_logged_in` published via `EventPublisher.publish()` inside the transaction (before commit). Outbox pattern per ADR-004.
