> **Baseline — test companion for** `batch-1-email-password-auth.md`, migrated from `docs/implementation/phase-1/phase-1-1-p1-email-password-auth.md` + `p2-security-invariants-patch.md` + `p3-single-primary-auth-enforcement.md` + `p4-jti-access-token.md` **on** 2026-07-19.

## Test Scenarios

Derived from the plan's Testing Requirements. Covers auth flows + security patches.

### Registration
- Given `POST /auth/register` with valid email/password/profile, creates exactly one `Athlete`, one `AthleteAuth` (provider=`email`, `is_primary=true`), one minimal `AthleteProfile`, and one `RefreshToken`
- Given response includes decodable JWT access token and raw refresh token
- Given `athlete.onboarding_complete` is `false`
- Given registering same email with different casing returns 409 (no partial state — no `Athlete`, no `AthleteAuth`, no `AthleteProfile`, no `RefreshToken`)
- Given email normalization: `"  User@Example.com  "` → stored as `"user@example.com"`
- Given `athlete_registered` event produced with `auth_provider='email'`, `has_password=true`, `profile_completed=true`

### Password Hashing
- Given password hashed with bcrypt cost ≥ 12
- Given `PasswordHasher.truncate_to_72_bytes` applied before hashing
- Given `PasswordHasher.verify()` uses constant-time comparison
- Given `hashed_password` never appears in API responses or logs

### Login
- Given `POST /auth/login` with correct email/password returns token pair (access + refresh) and 200
- Given `AthleteAuth.last_login_at` is updated on successful login
- Given `POST /auth/login` with wrong password returns 401 without revealing whether email exists
- Given `POST /auth/login` with non-existent email returns 401 without revealing whether password was correct
- Given `athlete_logged_in` event produced with `auth_provider='email'`, `token_type='access'`

### Refresh Token Rotation
- Given `POST /auth/refresh` with valid refresh token returns new token pair
- Given old refresh token then returns 401 (revoked)
- Given new refresh token can be used for another rotation
- Given rotation atomically sets `revoked_at` and `replaced_by_refresh_token_id` on old record and inserts new record
- Given new refresh token has 30-day expiry from rotation time
- Given two independently-issued refresh tokens for same athlete rotate independently (rotating one does not revoke the other)
- Given expired refresh token (>30 days) returns 401
- Given `athlete_logged_in` event produced with `token_type='refresh'`

### require_self
- Given valid token with matching `athlete_id` → request proceeds (200)
- Given valid token with mismatched `athlete_id` → 403 (never 404)
- Given expired access token → 401
- Given malformed JWT → 401
- Given missing Authorization header → 401

### Secret Exclusion
- Given no API response contains `hashed_password`, plaintext password, raw refresh token (after initial issuance), `token_hash`, `provider_tokens`, or `provider_user_id`
- Given no log output (via `logging_utils.ALLOWED_KEYS`) contains `token_hash` or raw `ip_address`
- Given `RefreshToken` model excluded from all Pydantic response schemas

### JWT jti Claim
- Given newly issued access token contains `jti` claim (valid UUID4)
- Given two access tokens issued for same athlete within same second have different `jti` values and different encoded JWT strings
- Given `POST /auth/refresh` returns access token with different `jti` from original
- Given verification ignores `jti` — tokens without `jti` (pre-patch) still validate
- Given `jti` is NOT exposed as a separate API response field (only inside JWT payload)

### IP Truncation
- Given `truncate_ip("192.168.1.100")` → `"192.168.1.0/24"`
- Given `truncate_ip("2001:db8:85a3::8a2e:370:7334")` → `"2001:0db8:85a3:0000::/64"`
- Given `truncate_ip(None)` → `None`
- Given `truncate_ip("invalid")` → `None`
- Given `athlete_logged_in` event payload contains truncated IP, not raw IP
- Given `RefreshToken.ip_address` in DB contains raw IP at creation time
- Given auth service `_log` calls pass truncated IP

### IP Discard After 7 Days
- Given `RefreshToken` with `ip_address = "1.2.3.4"` and `created_at = 8 days ago`, after `discard_old_ips()` runs, `ip_address` is NULL
- Given `RefreshToken` with `ip_address = "1.2.3.4"` and `created_at = 6 days ago`, after `discard_old_ips()`, `ip_address` is still `"1.2.3.4"`
- Given `discard_old_ips()` is idempotent — running twice produces same result
- Given cleanup task wired into project's task runner (procrastinate or cron)

### Single Primary Enforcement
- Given inserting second `AthleteAuth` with `is_primary=true` for same athlete raises `IntegrityError`
- Given inserting multiple `AthleteAuth` with `is_primary=false` for same athlete succeeds (non-primary multiplicity allowed)
- Given inserting first `AthleteAuth` with `is_primary=true` for new athlete succeeds
- Given partial unique index `ix_athlete_auths_single_primary` exists in database
- Given migration applies and rolls back cleanly

### DB-Level Constraints
- Given functional unique index on `lower(email)` in `athletes` — inserting same email with different case raises violation
- Given unique constraint on `(athlete_id, provider)` in `athlete_auths`
- Given unique constraint on `token_hash` in `athlete_refresh_tokens`
- Given unique constraint on `athlete_id` in `athlete_profiles`

### Transaction Atomicity
- Given registration failure at any step (e.g., profile insert fails), no `Athlete`, `AthleteAuth`, `AthleteProfile`, or `RefreshToken` rows exist
- Given login failure after password verification (e.g., refresh token insert fails), no new `RefreshToken` is created
- Given refresh rotation failure after old token revocation (e.g., new token insert fails), transaction rolls back and old token is not revoked

### Event Production
- Given `athlete_registered` event exists after successful registration with correct payload fields
- Given `athlete_logged_in` event exists after successful login with correct payload fields
- Given `athlete_logged_in` event exists after successful refresh rotation with `token_type='refresh'`
- Given events are produced inside the transaction via `EventPublisher` (outbox pattern) — `SystemEvent` + `SystemEventOutbox` rows exist
