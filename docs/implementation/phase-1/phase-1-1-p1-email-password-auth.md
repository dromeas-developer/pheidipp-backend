# Implementation Plan: Phase-1.1 — Email/Password Authentication
## Plan ID: Phase-1.1-P1

## Sub-Phase Reference
Sub-Phase ID: Phase-1.1
Sub-Phase Title: Phase 1 — Email/Password Authentication

## Objective
Implement the foundational email/password authentication layer for Pheidipp so every later athlete-scoped endpoint can rely on a secure, token-based identity boundary. This plan creates the minimal identity/auth/profile storage, registration and login flows, JWT lifecycle, refresh-token rotation, and self-scope authorization dependency required by all downstream Phase 1 sub-phases.

## Scope
- Implement `POST /auth/register` for email/password registration.
- Implement `POST /auth/login` for email/password login.
- Implement `POST /auth/refresh` with 30-day refresh-token expiry and rotation on every use.
- Issue access tokens with 15-minute expiry and refresh tokens with 30-day expiry.
- Create minimal Phase 1.1 schema for `Athlete`, `AthleteAuth`, `AthleteProfile`, and `RefreshToken`.
- Implement `require_self` route dependency for athlete-scoped endpoints.
- Hash passwords with bcrypt and never store or return plaintext credentials.
- Support multi-device sessions through a refresh-token table.
- Produce auth events after successful registration and successful login/refresh token issuance.
- Preserve `athlete.onboarding_complete = false` after registration; onboarding remains a later sub-phase.

## Out Of Scope
- OAuth providers (`google`, `strava`) and account linking.
- Email verification flow.
- Password reset flow.
- Rate limiting or brute-force hardening beyond bcrypt verification.
- Full `AthleteProfile` schema beyond `date_of_birth`, `sex`, and `height_cm`.
- `AthletePreferences`, `TrainingGoal`, onboarding, plan, coaching, workout, or activity endpoints.
- OAuth provider token refresh or provider credential management.

## Architecture Contracts
- `01-entities/athlete.md` — IMPLEMENTS `Athlete` creation and `AthleteResponse`; depends on `onboarding_complete = false` state after registration.
- `01-entities/athlete-auth.md` — IMPLEMENTS email/password credential storage, token issuance, refresh-token rotation, and auth event production.
- `01-entities/athlete-profile.md` — IMPLEMENTS minimal `AthleteProfile` creation at registration with only demographics fields needed for Phase 1.1.
- `00-foundations/event-catalogue.md` → `athlete_registered` — PRODUCES after registration commits.
- `00-foundations/event-catalogue.md` → `athlete_logged_in` — PRODUCES after login or refresh token issuance.
- `docs/vision/product/brand-philosophy.md` — DEPENDS ON for plain, non-technical user-facing behavior and backend computation boundary.
- `docs/vision/product/constraints.md` — DEPENDS ON for security and no-raw-data product constraints.

## Invariants
- `email` is unique across all athletes. Case-insensitive uniqueness enforced at DB level via unique index on `lower(email)`.
- Authentication credentials are stored in `AthleteAuth`, not in `Athlete`. See `01-entities/athlete-auth.md`.
- One `AthleteAuth` record per `(athlete_id, provider)`. An athlete cannot link the same provider twice.
- `hashed_password` is never returned by any API endpoint or included in any log. Encrypted at rest.
- `provider_tokens` is never returned by any API endpoint or included in any log. Encrypted at rest.
- `provider_user_id` is never returned in API responses. Used for OAuth account matching only.
- Exactly one `AthleteAuth` record per athlete must have `is_primary = true`. Primary cannot be removed without reassigning.
- Refresh tokens are rotated on every use — old token is revoked atomically with new token creation.
- `RefreshToken` records are append-only revocation records; rotation revokes the old token and inserts a new token record.
- Email provider requires `hashed_password` (bcrypt). Google provider requires `provider_tokens`. Strava provider requires both `provider_tokens` and `provider_user_id`.
- One `AthleteProfile` per `Athlete`. Created at registration. Enforced by unique constraint on `(athlete_id)`.
- All events are scoped to a single `athlete_id`
- `event_id` is a UUID, generated at the point of production
- All events are append-only — events are never updated or deleted
- Failed event processing is retried; events are not consumed destructively
- `email` is unique across all athletes (case-insensitive)
- `hashed_password` is never returned by any API endpoint or included in any log
- Refresh tokens are rotated on every use — old token is revoked atomically with new token creation
- Registration atomically creates `Athlete` and minimal `AthleteProfile`. If either fails, neither is committed.

## Implementation Steps
1. Create Phase 1.1 migrations for:
   - `athletes` with `email` stored normalized to lowercase and `onboarding_complete = false`.
   - `athlete_auths` with `provider = 'email'`, `hashed_password`, `is_primary = true`, and `last_login_at`.
   - `athlete_profiles` with only `date_of_birth`, `sex`, and `height_cm` populated at registration.
   - `athlete_refresh_tokens` as an append-only revocation ledger with hashed token lookup, expiry, revocation, and replacement fields.
2. Add database constraints and indexes:
   - Unique index on `lower(athletes.email)`.
   - Unique constraint on `athlete_profiles.athlete_id`.
   - Unique constraint on `(athlete_auths.athlete_id, athlete_auths.provider)`.
   - Unique index on `athlete_refresh_tokens.token_hash`.
   - Index on `(athlete_refresh_tokens.athlete_id, athlete_refresh_tokens.expires_at)`.
3. Implement registration orchestration:
   - Normalize and validate email.
   - Validate password length and reject invalid requests before any write.
   - Hash password with bcrypt cost factor 12 or higher.
   - In one database transaction, insert `Athlete`, `AthleteAuth(provider='email')`, minimal `AthleteProfile`, and the first `RefreshToken`.
   - Issue an access token and refresh token only after the transaction commits.
   - Produce `athlete_registered` after commit.
4. Implement login orchestration:
   - Normalize email and locate the matching `AthleteAuth(provider='email')` through `Athlete`.
   - Verify password with constant-time bcrypt comparison.
   - On failure, return 401 without revealing whether email or password was wrong.
   - On success, update `last_login_at`, issue a new token pair, insert a new `RefreshToken`, and produce `athlete_logged_in`.
5. Implement refresh-token rotation:
   - Hash the incoming refresh token and find an unexpired, unrevoked row.
   - In one transaction, insert the replacement `RefreshToken`, set `revoked_at` and `replaced_by_refresh_token_id` on the old row, issue a new access token and refresh token, and produce `athlete_logged_in` with `token_type = 'refresh'`.
   - If the old token is expired or revoked, return 401 and do not issue a replacement.
6. Implement `require_self`:
   - Decode and validate the access token.
   - Return 401 for missing, malformed, expired, or unverifiable tokens.
   - Return 403 when the JWT `athlete_id` does not match the path `athlete_id`.
   - Never return 404 for authorization mismatches on athlete-scoped routes.
7. Implement response and logging guards:
   - Exclude `hashed_password`, `provider_tokens`, `provider_user_id`, raw refresh tokens, and token hashes from every API response.
   - Log only non-sensitive identifiers such as `athlete_id`, provider, success/failure, and token type.
   - Ensure duplicate registration cannot leave partial `Athlete`, `AthleteAuth`, `AthleteProfile`, or `RefreshToken` rows.
8. Add auth observability:
   - Count registrations, successful logins, failed logins, refresh successes, refresh failures, and expired-token attempts.
   - Emit structured auth events without email, password, refresh token, or token hash values.

## Event Contracts
- `athlete_registered` — PRODUCES
  - Required payload fields: `auth_provider: 'email'`, `has_password: true`, `profile_completed: boolean`.
  - Envelope requirement: `athlete_id` must identify the newly registered athlete.
  - Ordering assumption: Fires only after `Athlete`, `AthleteAuth`, minimal `AthleteProfile`, and initial `RefreshToken` have committed.
- `athlete_logged_in` — PRODUCES
  - Required payload fields: `auth_provider: 'email'`, `token_type: 'access' | 'refresh'`, `ip_address: string | null`, `user_agent: string | null`.
  - Envelope requirement: `athlete_id` must identify the authenticated athlete.
  - Ordering assumption: Fires after password validation succeeds for login, or after a valid refresh token is rotated during refresh.

## Pseudocode
```text
register(email, password, profile):
  normalize email
  validate password
  hash password with bcrypt

  transaction:
    insert Athlete(email=lower(email), onboarding_complete=false)
    insert AthleteAuth(athlete_id, provider='email', hashed_password, is_primary=true)
    insert AthleteProfile(athlete_id, date_of_birth, sex, height_cm)
    insert RefreshToken(athlete_id, token_hash, expires_at=now+30d)

  issue access_token(expiry=15m, athlete_id, auth_provider='email')
  issue refresh_token_secret
  produce athlete_registered(auth_provider='email', has_password=true, profile_completed=profile_provided)
  return athlete, access_token, refresh_token_secret
```

```text
login(email, password):
  normalize email
  load AthleteAuth(provider='email') by normalized email

  if no record or bcrypt verification fails:
    return 401

  transaction:
    update AthleteAuth.last_login_at = now
    insert RefreshToken(athlete_id, token_hash, expires_at=now+30d)

  issue access_token(expiry=15m, athlete_id, auth_provider='email')
  issue refresh_token_secret
  produce athlete_logged_in(auth_provider='email', token_type='access', ip_address, user_agent)
  return athlete, access_token, refresh_token_secret
```

```text
refresh(refresh_token_secret):
  token_hash = hash(refresh_token_secret)
  load RefreshToken by token_hash

  if missing, expired, or revoked:
    return 401

  transaction:
    insert RefreshToken(athlete_id, token_hash=new_hash, expires_at=now+30d)
    set old RefreshToken.revoked_at = now
    set old RefreshToken.replaced_by_refresh_token_id = new.id

  issue access_token(expiry=15m, athlete_id, auth_provider='email')
  issue refresh_token_secret
  produce athlete_logged_in(auth_provider='email', token_type='refresh', ip_address, user_agent)
  return access_token, refresh_token_secret
```

```text
require_self(jwt, path_athlete_id):
  if jwt missing, malformed, expired, or unverifiable:
    return 401

  if jwt.athlete_id != path_athlete_id:
    return 403

  allow request
```

## Testing Requirements
- `POST /auth/register` with a valid email/password creates exactly one `Athlete`, one `AthleteAuth(provider='email')`, one minimal `AthleteProfile`, and one `RefreshToken`; it returns a valid access token and refresh token.
- `POST /auth/register` with an existing email using different casing returns 409 and leaves no partial `Athlete`, `AthleteAuth`, `AthleteProfile`, or `RefreshToken` rows.
- `POST /auth/register` response contains no `hashed_password`, raw password, refresh token hash, or provider credential fields.
- `POST /auth/login` with the wrong password returns 401 and does not issue tokens or create a new `RefreshToken`.
- `POST /auth/login` with the correct password returns 200, updates `last_login_at`, creates a new `RefreshToken`, and produces `athlete_logged_in` with `token_type = 'access'`.
- `POST /auth/refresh` with a valid refresh token returns a new token pair; the old refresh token returns 401 afterward; the new refresh token succeeds once.
- Two independently issued refresh tokens for the same athlete can each be used until that specific token is rotated or expires.
- An expired refresh token returns 401 and does not create a replacement token.
- An expired access token on an athlete-scoped route returns 401.
- An access token for athlete A used on `/athletes/{athlete_b_id}/...` returns 403, not 404.
- Structured auth logs contain no email, password, refresh token, token hash, or credential value.

## Coder Handoff Notes
- No implementation ADR is required; the refresh-token table approach is already fixed by the sub-phase and has been added to `01-entities/athlete-auth.md`.
- Do not implement OAuth even though `AuthProvider` includes `google` and `strava` for future schema compatibility.
- Do not implement email verification, password reset, rate limiting, account linking, or password-change endpoints.
- Keep `athlete.onboarding_complete = false` after registration. The onboarding sub-phase sets it to `true`.
- The Phase 1.1 `athlete_profiles` table must remain minimal. Phase 1.2a extends it; do not add personalisation, location, timezone, training window, or structural-risk fields here.
- Refresh-token rotation must be atomic: insert replacement, revoke old row, and issue the new token in the same transaction.
- Never update or delete existing `RefreshToken` rows to rotate a token. Mark the old row revoked and insert the replacement.
- Never put credentials in `Athlete`; credentials belong only in `AthleteAuth` and hashed refresh tokens belong only in `RefreshToken`.
