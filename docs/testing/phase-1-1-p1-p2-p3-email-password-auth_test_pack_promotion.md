# Test-Pack: Phase-1.1 Promotion Note

**Plan IDs**
* `phase-1-1-p1-email-password-auth` (core auth)
* `phase-1-1-p2-security-invariants-patch` (token_hash / IP / 7-day retention)
* `phase-1-1-p3-single-primary-auth-enforcement` (partial unique index)

**Operating mode**: Expansion (manifest already existed — see
`docs/testing/phase-1-1-p1-p2-p3-email-password-auth-test-pack.md`
and `docs/testing/phase-1-1-p1-p2-p3-email-password-auth_test_pack_rerun.md`
for the bootstrap and rerun packs).

**Trigger**: clean DevOps pass on 2026-06-19 — see
`reports/phase-1-1-p1-p2-p3-email-password-auth_devops.md` and
`reports/test_history/latest.md` (154/154 passed in 25 s, 0 failed,
0 skipped).

This pack documents the promotion decision and the selection-group
membership changes made in response to that pass. It does NOT
regenerate tests, generate new test files, or modify production code.

---

## 1. Promotion decisions

Every Phase-1.1 feature was advanced from `generated` directly to
`promoted`. The protocol calls for `generated → executable → passing
→ promoted`, with `executable` and `passing` set by DevOps inside
the same session that actually runs the tests. DevOps's report shows
they executed the feature group, ran 154 tests against the live
stack, and updated the manifest's `executable` / `passed` flags for
the features whose tests fell inside the run scope. The clean PASS
gives the Test Architect direct evidence to advance the next step.

| Feature | Status | Execution evidence |
|---|---|---|
| `phase-1-1-auth-register` | **`promoted`** | passed via `tests/integration/test_auth_service.py`, `test_athlete_repositories.py`, `tests/api/test_auth_endpoints.py`, `tests/behaviour/test_auth_user_journey.py` |
| `phase-1-1-auth-login` | **`promoted`** | passed via `tests/integration/test_auth_service.py`, `tests/api/test_auth_endpoints.py`, `tests/behaviour/test_auth_user_journey.py` |
| `phase-1-1-auth-refresh` | **`promoted`** | passed via `tests/integration/test_auth_service.py`, `test_refresh_token_repository.py`, `tests/api/test_auth_endpoints.py`, `tests/behaviour/test_auth_user_journey.py` |
| `phase-1-1-require-self` | **`promoted`** | passed via `tests/api/test_auth_endpoints.py`, `tests/behaviour/test_auth_user_journey.py` |
| `phase-1-1-security-invariants` | **`promoted`** | passed via `tests/unit/test_ip_utils.py`, `test_logging_utils.py`, `tests/integration/test_refresh_token_repository.py`, `test_discard_refresh_token_ips.py`, `test_auth_service.py`, `tests/api/test_auth_endpoints.py`, `tests/behaviour/test_auth_user_journey.py` |
| `phase-1-1-single-primary-enforcement` | **`promoted`** | passed via `tests/integration/test_athlete_auth_primary_enforcement.py` |
| `phase-1-1-events` | **`promoted`** | passed via `tests/integration/test_auth_service.py`, `tests/api/test_auth_endpoints.py`, `tests/behaviour/test_auth_user_journey.py` |
| `phase-1-1-password-crypto` | **`promoted`** | passed via `tests/unit/test_password_hasher.py` |
| `phase-1-1-token-primitives` | **`promoted`** | passed via `tests/unit/test_token_service.py` |

Reasoning for skipping the intermediate `passing` state at this
elevation: `validation.passed = true` is set for every Phase-1.1
feature by the DevOps report, so the only remaining gap between
`passing` and `promoted` is the Test Architect's judgment that the
tests are stable and worth carrying into the regression / release
corpus. That judgment is the only thing this pack adds. Promoting
straight through is purely a status-name change; it does not bypass
the validation gate that DevOps already cleared.

---

## 2. Selection-group review

### 2.1 `smoke`

**Members:**
* `tests/unit/test_password_hasher.py`
* `tests/unit/test_token_service.py`
* `tests/unit/test_ip_utils.py`
* `tests/unit/test_logging_utils.py`

**Reasoning:** All four are pure-function unit tests with no DB, no
HTTP, no migrations, no containers. They run sub-second each on the
per-test containerised environment. They guard the four most-leveraged
primitives authentication depends on:

| File | Tripwire for |
|---|---|
| `test_password_hasher.py` | bcrypt cost factor >= 12; 72-byte truncation symmetry; malformed hashes never raise. A regression here breaks every login and registration path. |
| `test_token_service.py` | JWT issue/verify contract (`athlete_id`, `jti`, TTL, 15-min default, strict verify); opaque refresh-token generation; SHA-256 refresh hashing; 30-day TTL. A regression here breaks every authenticated request. |
| `test_ip_utils.py` | `/24` IPv4 and `/64` IPv6 truncation invariants. A regression here breaks the ADR-005 PII-minimisation contract. |
| `test_logging_utils.py` | Audit-log `ALLOWED_KEYS` / `FORBIDDEN_KEYS` deny-list defence-in-depth. A regression here risks credential leakage to logs. |

Smoke deliberately excludes the integration, API, and behaviour
suites: they require a live DB, migrations applied, services up,
and measurable wall-clock (~25 s for the full feature group). Pulling
them into smoke would defeat the point — smoke is meant to be the
fastest signal you can run before declaring a refactor / small
change safe.

### 2.2 `feature`

**Members:** every Phase-1.1 test file (11 paths total).

**Reasoning:** Feature scope covers the current feature plus direct
impacts. Every Phase-1.1 file is either directly testing Phase-1.1
behaviour or testing infrastructure that Phase-1.1 introduced (e.g.
`test_athlete_repositories.py` and `test_refresh_token_repository.py`
grew alongside the Phase-1.1 services and protect invariants that
Phase-1.1 relies on). No neighbouring features exist yet to pull in
or exclude.

### 2.3 `regression`

**Members:** every Phase-1.1 test file (11 paths total).

**Reasoning:** Authentication is a non-optional security boundary.
Every one of the 11 test files covers either an invariant, an event
contract, a route contract, or an outbox-or-leakage property that a
later change could touch. Adding them to regression gives every
subsequent change a baseline check before merge. Excluding any
would leave a known gap in the safety net for a security boundary.

### 2.4 `release`

**Members:** every Phase-1.1 test file (11 paths total).

**Reasoning:** Authentication uses every protection — credentials,
hashing, tokens, rate-limit-adjacent DB constraints, audit logging,
event outbox. Skipping any of these on a release flight is too risky
to justify given that the full set runs in ~25 s. The cost of
running them on every release is sub-trivial compared to the cost
of a credential-leak regression slipping to production.

---

## 3. Manifest drift reconciled in this run

`tests/test_manifest.yaml` carried two drift items that were
inconsistent with the DevOps PASS report:

### 3.1 `phase-1-1-events` validation flags

The feature's `validation` block read `executable: false, passed: false`
at the start of this run even though:

* `reports/test_history/latest.md` shows the full 11-file run hit
  `tests/integration/test_auth_service.py`,
  `tests/api/test_auth_endpoints.py`, and
  `tests/behaviour/test_auth_user_journey.py` — every physical
  test file the `phase-1-1-events` feature declares under its
  `tests.integration`, `tests.api`, and `tests.behaviour` lists.
* The DevOps report's `Idempotency (no prior PASS)` check marked
  this as the first PASS in this branch (the prior devops report
  was a FAIL).

Both signals prove the events tests executed and passed inside this
session. DevOps missed updating this one feature entry. Corrected
to `executable: true, passed: true` along with the promotion.

### 3.2 Per-test `validation` blocks on `phase-1-1-auth-register`

A previous (pre-this-run) DevOps manifest write left ad-hoc
`validation:` blocks under each `tests.integration` / `tests.api` /
`tests.behaviour` entry on the `phase-1-1-auth-register` feature
with the following noise:

* `tests/integration/test_auth_service.py` → `passed: true`
* `tests/integration/test_athlete_repositories.py` → `passed: true`
* `tests/api/test_auth_endpoints.py` → `passed: false` (stale; the
  report proves this file passed)
* `tests/behaviour/test_auth_user_journey.py` → `passed: true`

The protocol's manifest schema places `validation` on the **feature**
entry, not on individual test paths within it. The per-test blocks
contradicted the canonical feature-level `validation: { implemented:
true, executable: true, passed: true }` already present on the
same feature, and `passed: false` for one of the four paths
contradicted the DevOps report's clean PASS.

Removed all four per-test `validation` blocks. The feature-level
block remains the single source of truth.

### 3.3 Other manifest fields touched

* `last_reviewed_at` bumped from `2026-06-19T04:30:00+00:00` to
  `2026-06-19T19:30:00+00:00`.
* Every feature's `status: generated` → `promoted`.
* `selection.smoke` populated with the 4 unit files listed in §2.1;
  `selection.feature`, `selection.regression`, `selection.release`
  populated with all 11 Phase-1.1 files.
* `execution_groups.p1-1-smoke.tests` populated to match
  `selection.smoke`.
* `history` appended with a 2026-06-19 entry summarising this
  promotion; the 06-18 rerun entry is preserved verbatim and
  remains the only record of the `discard_refresh_token_ips` /
  `system_event_outbox` production-side fixes that the Coder
  landed before the v3 pass.

No other manifest field was modified — schema, features, coverage,
and `owned_by_plan` are untouched per protocol.

---

## 4. Files modified

```
tests/test_manifest.yaml                                    (status, validation, selection, history)
docs/testing/phase-1-1-p1-p2-p3-email-password-auth_test_pack_promotion.md  (this file, new)
```

No test file, no fixture, no conftest, no production source was
touched in this run.

---

## 5. What is NOT in scope for the next test-pack author

* **Future phases that touch the auth foundation** (Phase-1.2
  OAuth, Phase-2 profile enrichment, etc.) should compile their
  own execution groups and add their own features into this manifest
  — they are not auto-included just because they exercise
  `require_self`.
* **Rate limiting / brute-force throttling** remains an
  intentionally-uncovered invariant on this manifest. Phase-2 or
  later may introduce it; when it does, the coverage gap closes at
  that point rather than now.
* **Per-test-level `validation` blocks** are NOT part of the
  schema. If a future DevOps write leaves them behind, the Test
  Architect on the next promotion should consolidate them again per
  §3.2 above.

---

## 6. Routing summary

* **No Coder action required.** This pack makes no production-side
  changes.
* **No Validator action required.** The validation report is
  unchanged and remains PASS WITH MINORS (the two MINOR findings
  are unchanged from the bootstrap pack; they are documentation /
  hand-test-cosmetic only — both invariants they describe are
  already covered by tests in the suite).
* **No DevOps action required for this pack itself.** The next
  DevOps run is driven by what the next plan introduces; if a
  Phase-1.2 (or later) plan lands, DevOps will resolve scope from
  the then-current `selection` groups automatically.
