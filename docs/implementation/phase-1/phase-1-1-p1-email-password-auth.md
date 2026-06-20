# Implementation Plan: Phase-1.1 — Email/Password Authentication
## Plan ID: Phase-1.1-P1

## Sub-Phase Reference
Sub-Phase ID: Phase-1.1
Sub-Phase Title: Phase 1 — Email/Password Authentication

## Objective
Implement the first authentication layer for Pheidipp by creating email/password registration, email/password login, JWT access-token issuance, 30-day refresh-token issuance, refresh-token rotation, and the `require_self` authorization dependency used by athlete-scoped routes. This plan establishes the secure identity foundation that later sub-phases depend on without implementing OAuth, email verification, password reset, rate limiting, onboarding, or full profile personalisation.

## Scope
- `POST /auth/register` for email/password registration.
- Atomic creation of `Athlete`, `AthleteAuth` with provider `email`, and minimal `AthleteProfile` with only registration demographics.
- Secure bcrypt password hashing and password verification.
- JWT access-token signing and verification with 15-minute expiry.
- Refresh-token issuance with 30-day expiry and multi-device support through separate refresh-token records.
- `POST /auth/refresh` refresh-token rotation: revoke the old token and insert a new token atomically.
- `POST /auth/login` for email/password login and token-pair issuance.
- `require_self` route dependency for athlete-scoped endpoints.
- Safe API response serialization and logging that excludes secrets.
- Production of authentication audit/security events defined by the architecture.

## Out Of Scope
- OAuth providers Google and Strava.
- Account linking, primary-method switching, auth-method removal, or password-change endpoints.
- Email verification flow.
- Password reset flow.
- Rate limiting or brute-force throttling.
- Onboarding, training goals, twin bootstrap, or full `AthleteProfile` schema fields.
- Athlete-scoped endpoint business logic beyond the shared `require_self` dependency.

## Architecture Contracts
- `01-entities/athlete.md` — IMPLEMENTS `Athlete` creation, `onboarding_complete = false` at registration, and `require_self` authorization semantics.
- `01-entities/athlete-auth.md` — IMPLEMENTS email/password credential storage, login validation, refresh-token lifecycle, and auth event production.
- `01-entities/athlete-profile.md` — IMPLEMENTS minimal registration profile with only `date_of_birth`, `sex`, and `height_cm` demographics.
- `00-foundations/event-catalogue.md` → `athlete_registered` — PRODUCES after successful registration commit.
- `00-foundations/event-catalogue.md` → `athlete_logged_in` — PRODUCES after successful login or refresh-token rotation.
- `docs/vision/product/brand-philosophy.md` — DEPENDS ON plain, non-technical user-facing communication; auth errors must be clear without exposing internals.
- `docs/vision/product/constraints.md` — DEPENDS ON security constraints and the principle that sensitive processing stays behind the API boundary.

## Invariants
- `email` is unique across all athletes. Case-insensitive uniqueness enforced at DB level via unique index on `lower(email)`.
- `hashed_password` is never returned by any API endpoint or included in any log. Encrypted at rest.
- Refresh tokens are rotated on every use — old token is revoked atomically with new token creation.
- `RefreshToken` records are append-only revocation records; rotation revokes the old token and inserts a new token record.
- Refresh tokens expire 30 days after issuance (`expires_at = created_at + 30 days`). Expired tokens are rejected even if not revoked.
- One `AthleteProfile` per `Athlete`. Created at registration. Enforced by unique constraint on `(athlete_id)`.
- Exactly one `AthleteAuth` record per athlete must have `is_primary = true`. Primary cannot be removed without reassigning.
- `ip_address` in `RefreshToken` records is stored for audit only; if used for security analysis, it must be anonymized or hashed before logging.
- Authentication credentials are stored in `AthleteAuth`, not in `Athlete`. See `01-entities/athlete-auth.md`.
- The `require_self` FastAPI dependency validates that JWT `athlete_id` === path `athlete_id` and returns 403 on mismatch — never 404.
- Registration atomically creates `Athlete` + `AthleteAuth` + `AthleteProfile` in a single database transaction. If any part fails, all roll back.

## Implementation Steps
1. Add or update persistence models for `Athlete`, `AthleteAuth`, minimal `AthleteProfile`, and `RefreshToken` so model registration and migrations reflect the Phase-1.1 contracts only.
2. Enforce database uniqueness and lookup indexes for email normalization, `AthleteAuth`, and refresh-token lookup:
   - `Athlete.email` unique via `lower(email)`.
   - `AthleteAuth` unique per `(athlete_id, provider)`.
   - `RefreshToken.token_hash` unique.
   - `AthleteProfile.athlete_id` unique for the one-profile-per-athlete rule.
3. Introduce a password-hashing component that hashes email-provider passwords with bcrypt cost factor 12 or higher and verifies passwords without returning or logging plaintext credentials.
4. Introduce a token service that signs and verifies JWT access tokens with 15-minute expiry and creates opaque refresh tokens with 30-day expiry. JWT claims must include `athlete_id`; `auth_provider` may be included as informational only.
5. Implement `POST /auth/register` in the auth service:
   - Validate email format and password length.
   - Normalize email to lowercase before persistence.
   - Hash the password before persistence.
   - Create `Athlete`, `AthleteAuth` with provider `email`, `is_primary = true`, and minimal `AthleteProfile` in one transaction.
   - Create the first refresh-token audit record with a one-way token hash.
   - Commit before producing `athlete_registered`.
   - Return `AthleteResponse`, access token, and raw refresh token exactly once.
   - Return 409 for duplicate email with no partial state.
6. Implement `POST /auth/login` in the auth service:
   - Look up the email-provider `AthleteAuth` record using normalized email.
   - Verify the password with bcrypt and avoid credential/timing leakage.
   - Update `last_login_at` only on successful validation.
   - Issue a new access token and new refresh-token record.
   - Produce `athlete_logged_in` after successful validation and token issuance.
   - Return 401 for missing account, wrong password, or disabled credential without revealing which condition failed.
7. Implement `POST /auth/refresh`:
   - Hash the submitted refresh token and look up the matching `RefreshToken`.
   - Reject missing, revoked, or expired tokens with 401.
   - In one transaction, revoke the old token and insert a new token record with a new hash and new 30-day expiry.
   - Populate the old token's replacement link atomically.
   - Produce `athlete_logged_in` with `token_type = 'refresh'` after rotation succeeds.
   - Return a new access token and new raw refresh token.
8. Implement the `require_self` dependency used by athlete-scoped routes:
   - Decode and verify the access-token signature and expiry.
   - Return 401 for missing, malformed, or expired tokens.
   - Return 403 when JWT `athlete_id` does not match the path `athlete_id`.
   - Inject the authenticated `athlete_id` for downstream service calls.
9. Add response serializers and logging safeguards so responses and logs never include `hashed_password`, `provider_tokens`, `provider_user_id`, plaintext passwords, raw refresh tokens, or stored token hashes.
10. Register authentication metrics and safe audit logs for registration, login success/failure, refresh success/failure, and token rotation without logging credentials or email addresses.

## Event Contracts
- `athlete_registered` — PRODUCES
  - Payload fields required by this plan: `auth_provider = 'email'`, `has_password = true`, `profile_completed = true` when the required registration profile fields are present.
  - Ordering assumption: emitted only after the `Athlete`, `AthleteAuth`, minimal `AthleteProfile`, and first `RefreshToken` transaction commits.
- `athlete_logged_in` — PRODUCES
  - Payload fields required by this plan: `auth_provider = 'email'`, `token_type = 'access'` for login, `token_type = 'refresh'` for refresh rotation, `ip_address`, `user_agent`.
  - Ordering assumption: emitted only after password validation succeeds for login or after refresh-token rotation commits.
- `refresh_token_rotated` — NOT PRODUCED
  - Ordering assumption: token rotation is intentionally observable through the append-only `RefreshToken` ledger and metrics, not through a separate event.

## Pseudocode
```text
POST /auth/register
  validate email, password, required profile fields
  normalized_email = lowercase(email)
  password_hash = bcrypt_hash(password, cost >= 12)

  begin transaction
    create Athlete(email = normalized_email, onboarding_complete = false)
    create AthleteAuth(
      athlete_id,
      provider = 'email',
      hashed_password = password_hash,
      is_primary = true
    )
    create AthleteProfile(athlete_id, date_of_birth, sex, height_cm)
    create RefreshToken(
      athlete_id,
      token_hash = hash(raw_refresh_token),
      expires_at = now + 30 days
    )
  commit transaction

  emit athlete_registered(auth_provider='email', has_password=true, profile_completed=true)
  return athlete, access_token(expires_in=15min), raw_refresh_token

POST /auth/login
  normalized_email = lowercase(email)
  auth_record = find AthleteAuth(provider='email', email normalized)
  if auth_record missing or password verification fails:
    return 401 without credential-specific details

  begin transaction
    update auth_record.last_login_at
    create RefreshToken(athlete_id, token_hash = hash(raw_refresh_token), expires_at = now + 30 days)
  commit transaction

  emit athlete_logged_in(auth_provider='email', token_type='access')
  return athlete, access_token(expires_in=15min), raw_refresh_token

POST /auth/refresh
  submitted_hash = hash(raw_refresh_token)
  token_record = find RefreshToken(token_hash = submitted_hash)
  if token_record missing, revoked, or expired:
    return 401

  begin transaction
    create new RefreshToken(
      athlete_id = token_record.athlete_id,
      token_hash = hash(new_raw_refresh_token),
      expires_at = now + 30 days
    )
    set token_record.revoked_at = now
    set token_record.replaced_by_refresh_token_id = new_token.id
  commit transaction

  emit athlete_logged_in(auth_provider='email', token_type='refresh')
  return access_token(expires_in=15min), new_raw_refresh_token

require_self(path_athlete_id)
  decode JWT
  if token invalid or expired:
    return 401
  if jwt.athlete_id != path_athlete_id:
    return 403
  inject jwt.athlete_id
```

## Testing Requirements
- Registering with a valid email/password creates exactly one `Athlete`, one email-provider `AthleteAuth`, one minimal `AthleteProfile`, and one refresh-token record; response includes a decodable access token and raw refresh token.
- Registering the same email with different casing returns 409 and leaves no partial `Athlete`, `AthleteAuth`, `AthleteProfile`, or `RefreshToken` records.
- `POST /auth/login` with the wrong password returns 401; with the correct password returns a new token pair and updates `AthleteAuth.last_login_at`.
- API responses and logs do not contain `hashed_password`, plaintext passwords, raw refresh tokens, stored refresh-token hashes, `provider_tokens`, or `provider_user_id`.
- A request to an athlete-scoped route with an expired access token returns 401.
- A request to an athlete-scoped route with a valid JWT for a different athlete returns 403, not 404.
- `POST /auth/refresh` with a valid refresh token returns a new token pair; the old refresh token then returns 401, and the new refresh token can be used for another rotation.
- Refresh-token rotation leaves the old `RefreshToken` revoked with a replacement link and inserts a new append-only `RefreshToken` record with a 30-day expiry.
- Two independently issued refresh tokens for the same athlete can be rotated independently; rotating one does not revoke the other.
- `athlete_registered` and `athlete_logged_in` events contain the required payload fields and are produced only after their respective success conditions.

## Coder Handoff Notes
- No implementation ADR is required for this plan; the architecture already specifies the refresh-token rotation and append-only revocation-ledger behaviour.
- This is Phase 1.1, so `AthleteProfile` must be minimal. Do not add personalisation models, location, timezone, training window, structural risk, or objective-threshold columns here; those belong to Phase 1.2a.
- OAuth schema may exist in `AthleteAuth`, but Phase 1.1 implements only provider `email`. Do not implement Google, Strava, linking, unlinking, or primary-method switching.
- `Athlete` owns identity and onboarding status only. Passwords and refresh-token audit state belong to `AthleteAuth`/auth service ownership.
- Bcrypt cost must be 12 or higher. Never store or log plaintext passwords.
- Refresh-token rotation is the highest-risk operation in this plan: revocation of the old token and insertion of the new token must be atomic.
- `require_self` must distinguish invalid/expired tokens from cross-athlete authorization failures: 401 for token validity, 403 for athlete mismatch.
- If an existing event/outbox mechanism exists in the codebase, use it for `athlete_registered` and `athlete_logged_in`; otherwise implement the minimum event persistence required by the architecture and keep event emission after commit.
- Keep user-facing auth errors simple and non-technical, consistent with the brand philosophy of no AI-feel and no unnecessary jargon.
