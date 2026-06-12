# Phase 1 — Email/Password Authentication
## Sub-Phase ID: Phase-1.1

## Objective
Establish the authentication layer that all subsequent sub-phases build upon. This delivers a secure, token-based authentication system supporting email/password registration and login. OAuth providers (Google, Strava) are explicitly deferred to later phases — the schema in `AthleteAuth` is designed to accommodate them, but this sub-phase implements only the email/password provider.

## Challenge Notes
OAuth providers (Google, Strava) and account linking are deferred to a later phase to reduce initial complexity. The `AthleteAuth` entity schema already supports multiple providers, so adding OAuth later is an extension, not a rewrite.

Registration atomically creates `Athlete` + `AthleteAuth` + `AthleteProfile`. The `AthleteProfile` table is created with a **minimal schema** containing only the demographics fields needed at registration (`date_of_birth`, `sex`, `height_cm`). The full schema (personalisation models, location, training window, etc.) is extended in Phase-1.2a. The architect can deduce the minimal schema from the API contracts in `athlete-auth.md` and `athlete.md`.

## Capabilities Delivered
- Athlete can register with email + password (`POST /auth/register`)
- Athlete can log in with email + password (`POST /auth/login`)
- Access token (JWT, 15min expiry) and refresh token (30-day expiry, rotated on use) lifecycle
- `require_self` route dependency for athlete-scoped endpoints
- Secure password hashing (bcrypt)
- Multi-device session support (via refresh token table)

## Architectural Contracts Required
- `01-entities/athlete.md`
- `01-entities/athlete-auth.md`
- `01-entities/athlete-profile.md` (minimal schema — only demographics columns needed for registration; full schema completed in Phase-1.2a)

## Vision References Required
- `product/brand-philosophy.md` — "no AI-feel, no tech jargon"
- `product/constraints.md` — security constraints

## Upstream Dependencies
None. This is the first sub-phase.

## Downstream Enablement
- Phase-1.2a (Profile & Preferences) — registration creates the `Athlete` record
- Phase-1.3 (Onboarding) — requires authenticated user to complete onboarding
- All athlete-scoped endpoints require the auth layer

## Invariants To Preserve
- `email` is unique across all athletes (case-insensitive)
- `hashed_password` is never returned by any API endpoint or included in any log
- Refresh tokens are rotated on every use — old token is revoked atomically with new token creation
- Registration atomically creates `Athlete` and minimal `AthleteProfile`. If either fails, neither is committed.

## Non-Goals
- OAuth (Google, Strava) — deferred to a later phase
- Email verification flow
- Password reset flow
- Rate limiting (deferred to infrastructure hardening)

## Exit Gate
- `POST /auth/register` creates an `Athlete` and returns a valid token pair.
- `POST /auth/login` with wrong password returns 401; with correct password returns a new token pair.
- An authenticated request to an athlete-scoped route with a JWT belonging to a different athlete returns 403.
- A request with an expired access token returns 401.
- Refresh token rotation: after `POST /auth/refresh`, the old refresh token is invalid and a new one is usable.

## Risks
- **Password compromise**: bcrypt with appropriate work factor (12+) mitigates this.
- **Token theft**: Short-lived access tokens + refresh token rotation limit window of exposure.

