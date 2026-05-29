# 1b — Authentication & Security
*JWT lifecycle, password hashing, route protection*

## Objective

Establish the authentication layer before any user-facing endpoints are built.
All subsequent sub-phases build routes on top of this foundation. Getting auth
right before building functionality is cheaper than retrofitting it later.

## Scope

JWT access and refresh token lifecycle. Password hashing. Registration and login
endpoints. Route dependency for authenticated access. Athlete-identity guard for
athlete-scoped routes.

## Non-Goals

- OAuth or third-party auth (Garmin, intervals.icu use token-based API auth, not OAuth
  SSO — those are integration credentials, not user auth)
- Email verification flow
- Password reset flow
- Rate limiting (deferred to infrastructure hardening)

## Architecture References

- Async worker pattern: `architecture/principles.md` → Processing Is Async
- `Athlete` model fields: `architecture/data-models.md` → Planning Layer

## Dependencies

Requires 1a (Athlete model must exist).

## Models Introduced

**`RefreshToken`** — stored refresh token supporting multi-device sessions.
Fields: `id`, `athlete_id` FK (cascade delete), `token_hash` (SHA-256 hex digest,
unique index), `expires_at`, `revoked_at` (nullable — null means active),
`device_hint` (nullable), `last_used_at` (nullable), `created_at`.
No partial unique constraint on athlete — multi-device model.

**`Athlete` modified:** No new fields. `hashed_password` already present from 1a.

## Services & Tasks Introduced

**`AuthService`** (sync) — registration, login, token refresh, logout.
- `register(email, password, profile_data) → TokenResponse`
- `login(email, password, device_hint) → TokenResponse`
- `refresh(refresh_token) → TokenResponse`
- `logout(refresh_token) → None` (revokes the token)
- All password ops use bcrypt via `passlib`.

**`TokenService`** (sync) — JWT creation and validation.
- `create_access_token(athlete_id) → str`
- `create_refresh_token(athlete_id, device_hint) → (raw_token, RefreshToken)`
- `decode_access_token(token) → athlete_id` (raises on invalid/expired)

## Endpoints Introduced

- `POST /auth/register` — create Athlete + AthleteProfile (minimal), issue tokens
- `POST /auth/login` — validate credentials, issue tokens
- `POST /auth/refresh` — exchange refresh token for new token pair (rotation)
- `POST /auth/logout` — revoke refresh token

## Route Dependencies Introduced

**`get_current_athlete`** — FastAPI dependency. Validates Bearer JWT in Authorization
header. Returns `athlete_id: UUID`. Used on all authenticated routes.

**`require_self`** — FastAPI dependency extending `get_current_athlete`. Verifies
`athlete_id` from JWT matches `{athlete_id}` in the route path. Used on all
athlete-scoped routes. Returns 403 if mismatch — never 404.

## Key Constraints

- Refresh tokens are rotated on every use — old token is revoked atomically with
  new token creation. If rotation fails, the athlete must log in again.
- Access tokens are short-lived (15 minutes default, configurable).
- Refresh tokens are long-lived (30 days default, configurable).
- `token_hash` is stored, never the raw token.
- Registration atomically creates `Athlete` and minimal `AthleteProfile`. If either
  fails, neither is committed.

## Done Criteria

- `POST /auth/register` creates an Athlete and returns a valid token pair.
- `POST /auth/login` with wrong password returns 401; with correct password
  returns a new token pair without exposing the previous refresh token.
- An authenticated request to any athlete-scoped route with a JWT belonging to a
  different athlete returns 403.
- A request with an expired access token returns 401.
- Refresh token rotation: after `POST /auth/refresh`, the old refresh token is
  invalid and a new one is usable.
