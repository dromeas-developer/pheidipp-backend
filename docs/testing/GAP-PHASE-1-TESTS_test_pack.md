# Test Pack — GAP-PHASE-1-TESTS (Batch 1: Auth & Identity)

unit: done · integration: done · api: done · behaviour: skipped

## Overview

Plan: `GAP-PHASE-1-TESTS` / Batch 1 — Sub-Phase 1.1 (Email/Password Authentication)
Source: `docs/implementation/phase-1/gap-analysis-phase-1/batch-1-auth-identity-tests.md`
Generated: 2026-07-25

This test pack covers Phase 1's email/password authentication flow: registration,
login, refresh token rotation, IP truncation, token security, and the `require_self`
route dependency. 26 scenarios were defined; 23 are tested (3 skipped per
enforcement-layer rules: pure Pydantic `min_length`, `EmailStr`, and `Field(le=300)`
constraints — the framework enforces these, not our code).

## Unit Tests

| File | Scenarios | Tests |
|---|---|---|
| `tests/unit/test_auth_service.py` | 1, 8, 9, 10, 11, 13, 14, 15, 16, 17 | 10 |
| `tests/unit/test_auth_schemas.py` | 5, 12 | 3 |
| `tests/unit/test_ip_utils.py` | 18, 19, 20 | 7 |
| `tests/unit/test_token_security.py` | 21, 22 | 6 |

**Coverage:**
- AuthService.register (atomically creates 4 entities + event; rollback on failure)
- AuthService.login (happy path; wrong password 401; nonexistent email constant-time)
- AuthService.rotate_refresh_token (rotation; old token rejected; expired rejected; unknown rejected; atomicity rollback)
- RegisterRequest._validate_password_not_blank (whitespace rejected)
- AuthResponse / TokenPairResponse exclude token_hash and hashed_password
- truncate_ip (IPv4 /24 CIDR; IPv6 /64 CIDR; None/empty/invalid)
- safe_extra / log_event dual-filter (token_hash, hashed_password, ip_address blocked)
- RefreshTokenRepository.discard_old_ips (7-day cutoff; zero-row case)

## Integration Tests

| File | Scenarios | Tests |
|---|---|---|
| `tests/integration/test_auth_db.py` | 2, 3 | 2 |

**Coverage:**
- `ix_athletes_lower_email_unique` functional index (IntegrityError pgcode 23505)
- normalize_email case-insensitive matching before the unique index fires

## API Tests

| File | Scenarios | Tests |
|---|---|---|
| `tests/api/test_require_self.py` | 23, 24, 25, 26 | 4 |

**Coverage:**
- require_self: own JWT succeeds; different athlete JWT → 403
- get_current_athlete_id: expired JWT → 401; missing header → 401

## Behaviour Tests

None — no full user journeys in this batch. Auth is a narrow cross-cutting concern;
behaviour tests for onboarding and plan generation will arrive in batches 3 and 4.

## Skipped Scenarios

| # | Scenario | Reason |
|---|---|---|
| 4 | Password too short (5 chars) | Pydantic `min_length=8` — framework enforces |
| 6 | Invalid email format | Pydantic `EmailStr` — framework enforces |
| 7 | height_cm=400 rejected | Pydantic `Field(le=300)` — framework enforces |

One schema-level confirmation test ensuring `RegisterRequest` exists with the correct
field constraints could be added in a future batch, but per the enforcement-layer
consumption rules, type-system-only constraints are not tested individually.

## Coverage Summary

| Category | Total | Covered | Skipped | Coverage |
|---|---|---|---|---|
| Scenarios | 26 | 23 | 3 (legitimate) | 100% of testable |
| Events | 2 | 2 (athlete_registered, athlete_logged_in) | — | 100% |
| Invariants | 5 | 5 (I1, I26-I29) | — | 100% |

## Recurring Infrastructure Risk

None — first test pack; no DevOps reports to feed Step 2.
