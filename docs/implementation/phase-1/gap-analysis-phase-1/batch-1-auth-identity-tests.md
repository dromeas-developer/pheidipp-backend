# Test Scenarios — Phase 1 Gap Analysis — Batch 1: Auth & Identity

## Source: docs/implementation/phase-1/gap-analysis-phase-1/overview.md
## Sub-Phases Covered: 1.1 (Email/Password Authentication)

---

## Step 1 — Registration (POST /auth/register)

| # | Scenario | Input | Expected | Enforcement | Mock Boundary |
|---|---|---|---|---|---|
| 1 | Successful registration creates Athlete + AthleteAuth + AthleteProfile + RefreshToken atomically | `email="athlete@example.com"`, `password="validpass123"`, `date_of_birth=1990-01-15`, `sex=Sex.MALE`, `height_cm=180` | `AuthResult` with `athlete_id` (UUID), `onboarding_complete=False`, valid `IssuedTokens` (access + refresh); 4 rows committed: Athlete, AthleteAuth, AthleteProfile, RefreshToken; `athlete_registered` event in outbox with `auth_provider="email"`, `has_password=true`, `profile_completed=true` | application-logic | db-session |
| 2 | Duplicate email rejected with 409 | First registration with `email="dup@example.com"` succeeds; second registration with same email | `DuplicateEmailError("email already in use")`; no second Athlete row; IntegrityError from `lower(email)` unique index caught and mapped | database | db-session |
| 3 | Case-insensitive email uniqueness | First registration `email="User@Example.com"`; second `email="user@example.com"` | `DuplicateEmailError` — `normalize_email` lowercases both before the unique index fires | database + application-logic | db-session |
| 4 | Password too short rejected at schema | `password="short"` (5 chars) | Pydantic `ValidationError` (min_length=8) — request never reaches service | type-system | none |
| 5 | Password blank/whitespace rejected | `password="        "` (8 spaces) | `@field_validator("_validate_password_not_blank")` raises `ValueError("password must not be blank or whitespace-only")` | type-system | none |
| 6 | Invalid email format rejected | `email="not-an-email"` | Pydantic `ValidationError` (`EmailStr` constraint) | type-system | none |
| 7 | height_cm out of range rejected | `height_cm=400` | Pydantic `ValidationError` (`Field(le=300)`) | type-system | none |
| 8 | Registration atomicity — mid-transaction failure rolls back all | Inject a failure after AthleteAuth insert but before RefreshToken persist | No Athlete, AthleteAuth, AthleteProfile, or RefreshToken row committed; `onboarding_complete` remains False; no outbox event | application-logic | db-session |

## Step 2 — Login (POST /auth/login)

| # | Scenario | Input | Expected | Enforcement | Mock Boundary |
|---|---|---|---|---|---|
| 9 | Successful login returns token pair | Registered athlete, `email="athlete@example.com"`, `password="validpass123"` | `AuthResult` with new `IssuedTokens`; `athlete_logged_in` event in outbox with `token_type="access"`, `auth_provider="email"`, `ip_address` truncated, `user_agent`; `AthleteAuth.last_login_at` updated | application-logic | db-session |
| 10 | Wrong password returns 401 | Registered athlete, `password="wrongpassword"` | `InvalidCredentialsError("invalid credentials")`; no token issued; no event published | application-logic | db-session |
| 11 | Non-existent email returns 401 (constant-time) | `email="nosuchuser@example.com"`, `password="anypassword"` | `InvalidCredentialsError`; response time approximately equal to wrong-password case (dummy bcrypt verify runs) | application-logic | db-session |
| 12 | token_hash never in response | Any successful login | `AuthResponse` / `TokenPairResponse` schema has no `token_hash` or `hashed_password` field; response JSON does not contain these keys | application-logic | none |

## Step 3 — Refresh Token Rotation (POST /auth/refresh)

| # | Scenario | Input | Expected | Enforcement | Mock Boundary |
|---|---|---|---|---|---|
| 13 | Valid refresh token rotates atomically | Valid `raw_refresh_token` from prior login | `IssuedTokens` with new access + refresh; old `RefreshToken.revoked_at` set; old `replaced_by_refresh_token_id` = new token's id; new token `is_active=true`; `athlete_logged_in` event with `token_type="refresh"` | application-logic | db-session |
| 14 | Old refresh token invalid after rotation | Use the old raw token after rotation | `InvalidRefreshTokenError("invalid refresh token")` — `RefreshTokenRepository.is_active` returns False (revoked_at is set) | application-logic | db-session |
| 15 | Expired refresh token rejected | Token with `expires_at < now` | `InvalidRefreshTokenError` | application-logic | db-session |
| 16 | Unknown refresh token rejected | `raw_refresh_token="nonexistent-hash"` | `InvalidRefreshTokenError` — `get_by_token_hash` returns None | application-logic | db-session |
| 17 | Rotation atomicity — old revoked + new inserted in one transaction | Inject failure after new token insert but before old token revoke | Neither the new token nor the revocation is committed — transaction rolls back | application-logic | db-session |

## Step 4 — IP & Token Security (ADR-005)

| # | Scenario | Input | Expected | Enforcement | Mock Boundary |
|---|---|---|---|---|---|
| 18 | IPv4 truncated to /24 before logging | `ip_address="192.168.1.100"` | `truncate_ip("192.168.1.100")` returns `"192.168.1.0"`; event payload `ip_address` field contains truncated value | application-logic | none |
| 19 | IPv6 truncated to /64 before logging | `ip_address="2001:db8:abcd:12ef::1"` | `truncate_ip` returns `"2001:db8:abcd:12ef::"` (first /64 prefix) | application-logic | none |
| 20 | None IP handled gracefully | `ip_address=None` | `truncate_ip(None)` returns `None`; no crash | application-logic | none |
| 21 | token_hash never logged | Any auth operation | Log events (`log_event` calls) do not include `token_hash` or `hashed_password` in fields dict | application-logic | none |
| 22 | IP discarded after 7 days | `RefreshToken` with `created_at` 8 days ago, `ip_address` set | `discard_old_ips` task sets `ip_address=None`; token record persists (30-day retention) | application-logic | db-session |

## Step 5 — require_self Route Dependency

| # | Scenario | Input | Expected | Enforcement | Mock Boundary |
|---|---|---|---|---|---|
| 23 | Authenticated request with own JWT succeeds | JWT for `athlete_id=A`, request to `/athletes/A/...` | Request proceeds to handler | application-logic | none |
| 24 | Authenticated request with different athlete's JWT returns 403 | JWT for `athlete_id=A`, request to `/athletes/B/...` | 403 Forbidden | application-logic | none |
| 25 | Expired access token returns 401 | JWT with `exp < now` | 401 Unauthorized | application-logic | none |
| 26 | Missing Authorization header returns 401 | No Authorization header | 401 Unauthorized | application-logic | none |