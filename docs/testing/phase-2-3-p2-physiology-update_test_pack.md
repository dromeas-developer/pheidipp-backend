# Test Pack — Phase-2.3-P2 (Physiology Update Service)

**Plan ID:** phase-2-3-p2-physiology-update
**Plan file:** docs/implementation/phase-2/phase-2-3-p2-physiology-update.md
**Sub-phase:** Phase-2.3 — Threshold Detection & Physiology Update
**Manifest:** tests/test-manifest/phase-2-3p2.yaml

**Status by Test Mode:**
- unit: done (triage pass 2026-07-14 — 1 batch-transition test fix: accept `("low", "high")` instead of `("medium", "high")`) · integration: done (triage pass 2026-07-14 pass 1 — 4 `_state()` default date fixes + 1 rollback fixture isolation fix; pass 2 — 6 multi-day accumulation fixes + 1 loop-pattern fix + 1 post-rollback column-level SELECT fix; pass 3 — 1 post-rollback PK access fix: capture `athlete_id` before rollback; 2 impl bugs routed to p-coder 2026-07-13) · api: done (no-op — no endpoints) · behaviour: done (triage pass 2026-07-14 — 6 tests fixed: pre-populate `AthletePhysiology` for shift assertions + same-date activities for multi-activity threshold assertions)

**Sub-phase status:** **PROMOTED** (2026-07-15 — DevOps report PASS, 193/193 tests, all 32 features advanced to `status: promoted`, all 10 test files added to `selection.regression` and `selection.release`, `physiology_updated` added to `coverage.events.covered`).

---

## Promotion Summary (2026-07-15)

**DevOps report:** `reports/phase-2-3-p2_devops.md` — Result: **PASS** (193 passed / 0 failed / 0 skipped, 25.70s). No infrastructure changes were made by DevOps. All 3 prior root causes (RC1 source_value enum `.value`, RC2 intra-call state accumulation, RC3 post-rollback PK access) were already resolved across the 2026-07-13/14 triage passes.

**Test Architect promotion actions:**

1. **Status promotion** — all 32 features in `tests/test-manifest/phase-2-3p2.yaml` advanced from `status: generated` to `status: promoted`. All were already at `validation.implemented = true`, `validation.executable = true`, `validation.passed = true` per the DevOps report.

2. **`index.yaml` `selection.regression`** — added all 10 test file paths:
   - `tests/unit/test_physiology_update_service_bayesian.py`
   - `tests/unit/test_physiology_update_service_pure_helpers.py`
   - `tests/unit/test_physiology_update_service_orchestration.py`
   - `tests/unit/test_athlete_physiology_repository_update_in_place.py`
   - `tests/integration/test_physiology_update_service_integration.py`
   - `tests/integration/test_physiology_update_service_idempotency_integration.py`
   - `tests/integration/test_physiology_update_service_confidence_transitions_integration.py`
   - `tests/integration/test_physiology_update_service_first_observation_integration.py`
   - `tests/integration/test_athlete_physiology_repository_update_in_place_integration.py`
   - `tests/behaviour/test_physiology_update_user_journey.py`

3. **`index.yaml` `selection.release`** — same 10 test file paths added (all 32 features are `status: promoted`, so all 10 test files are eligible for the `release` group).

4. **`index.yaml` `coverage.events.covered`** — added `physiology_updated` (produced by `PhysiologyUpdateService.apply_observations()` when posterior shifts > 1 bpm).

5. **`index.yaml` `coverage.invariants.covered`** — 3 new invariants added in prior triage sessions and confirmed present:
   - `physiology_updated event atomicity — SystemEvent + SystemEventOutbox land in the SAME transaction as the AthletePhysiology update (ADR-004)`
   - `One AthletePhysiology row per athlete — the row id is preserved across update_in_place (no second row created)`
   - `Confidence is monotonic (only increases, never decreases) — the prior_weight decays over time, but the per-metric level (LOW/MEDIUM/HIGH) ratchets up only`

6. **Manifest timestamps** — `last_reviewed_at` bumped to `2026-07-15T00:00:00Z` in both `index.yaml` and `phase-2-3p2.yaml`. New `history` entry appended to `phase-2-3p2.yaml` with `result: PROMOTED`.

**No new tests generated** — the suite was already complete from prior sessions. The 2026-07-15 session is a promotion-only session: the DevOps report triggered a full PASS, and the Test Architect's role was to advance the manifest to the promoted state.

**No new infrastructure fixes to ingest** — the DevOps report's `## Infrastructure Fixes` section explicitly states: "No infrastructure changes were made in this session." The 3 prior root causes were resolved across the 2026-07-13/14 triage passes, and their lessons are already recorded in `tests/README.md` and `tests/MOCKING_CONTRACT.md`.

---

## Overview

Phase-2.3-P2 introduces the `PhysiologyUpdateService` — the Bayesian
update engine that consumes threshold observations from
`ThresholdDetectionService` (Plan P1), applies the posterior update
formula to `AthletePhysiology` in place, writes append-only
`PhysiologyMeasurement` records, and fires the `physiology_updated`
event when the posterior shifts by > 1 bpm. This plan also implements
confidence transition detection (LOW → MEDIUM at evidence weight ≥ 4.0,
MEDIUM → HIGH at ≥ 8.0).

The unit-mode session generated four test files covering every
unit-tagged capability in the inventory. Integration, API, and
behaviour tests are deferred to later sessions.

---

## Triage — DevOps Report 2026-07-13

**Reference:** `reports/phase-2-3-p2_devops.md` (Result: FAIL, 143/194 passed, 51 failed)

The DevOps report's 51 test failures split into **5 test-pack issues (fixed by Test Architect)** and **2 implementation bugs (routed to p-coder)**. No infrastructure changes were required; the `MOCKING_CONTRACT.md` Known Anti-Patterns were not the source of any failure.

### Test-pack fixes applied (5 issues)

1. **Bayesian fixture date mismatch (4 tests)** — the `_state()` default `last_observation_date="2026-05-01"` and `_observation()` default `obs_date=date(2026, 6, 15)` create a 45-day gap that decays the prior weight via the 42-day time constant. Four tests (`test_posterior_mean_exact_when_weights_equal`, `test_new_total_weight_is_decayed_plus_observation`, `test_uncertainty_above_floor_when_evidence_moderate`, `test_prior_dominates_when_weights_equal`) expected no-decay math. Fixed by pinning `last_observation_date='2026-06-15'` in those four `_state()` calls.
2. **Integration test FK violation (`activity_id=uuid.uuid4()`)** — the `_observation()` helper defaulted `activity_id` to a fresh UUID with no matching `Activity` row, violating the `physiology_measurements.activity_id` FK. Fixed by changing the default to `None` in all 4 integration test files and adding a `make_activity` factory in `tests/utils/factories.py` for tests that need a real `Activity` reference (idempotency dedup tests).
3. **Behaviour test missing `AthletePhysiology` row** — `http_register` only creates `Athlete + AthleteAuth + AthleteProfile`; the `AthletePhysiology` row is bootstrapped by the onboarding service (separate sub-phase, out of P2 scope). Fixed by adding an `_ensure_physiology_row` helper in `test_physiology_update_user_journey.py` and calling it after every `http_register` (7 test bodies touched).
4. **`test_updated_at_changes_even_with_no_column_mutations` removed** — the test asserted `updated_at` advances on a `flush()` with no column mutations, but SQLAlchemy's `onupdate=` hook only fires when an actual `UPDATE` statement is issued (i.e. when at least one column is mutated). Replaced with a NOTE comment explaining the removal; the correct semantics are pinned by `test_updated_at_changes_after_update`.
5. **No new infrastructure fixtures** — the existing `db_session`, `client`, `make_athlete`, and `http_register` helpers were sufficient after the test-pack fixes. Only one new factory was added (`make_activity` in `tests/utils/factories.py`).

### Implementation bugs (routed to p-coder)

**Two production bugs were identified during triage.** They are not test-pack issues and the Test Architect does not have authority to fix them. Both are reproduced below with their root cause, the failing tests, and a suggested fix.

#### Bug 1 — `_source_value()` returns the wrong string format for `MeasurementSource` enum members

**Severity:** HIGH — affects every observation whose source is a `MeasurementSource` enum member. Every `dominant_source` JSONB value written by `bayesian_update` and every `dominant_sources` field in a `physiology_updated` event payload is wrong.

**Location:** `app/services/physiology_update_service.py`, function `_source_value` (line 326-336).

**Current code:**
```python
def _source_value(source: Any) -> str:
    """Return the ``MeasurementSource.value`` string for ``source``.

    Accepts either a ``MeasurementSource`` enum member (preferred
    — produced by threshold detection) or a pre-stringified value
    (defensive — JSONB round-trips can hand back plain strings).
    """
    # ``MeasurementSource`` is a ``str``-valued enum, so ``str(source)``
    # yields the canonical value string in both cases.
    return str(source)
```

**Bug:** `MeasurementSource` is declared `class MeasurementSource(str, Enum)` in `app/models/enums.py`. For `class Foo(str, Enum)`, `str(enum_member)` returns `'ClassName.MEMBER_NAME'` (e.g. `'MeasurementSource.TRAINING_RR_INFLECTION'`), not the `.value` string (`'training_rr_inflection'`). The `str` mixin only enables string comparison and JSON serialisation, not `str()` semantics. Verified in `.venv/bin/python`:

```python
>>> from app.models.enums import MeasurementSource
>>> str(MeasurementSource.TRAINING_RR_INFLECTION)
'MeasurementSource.TRAINING_RR_INFLECTION'
>>> MeasurementSource.TRAINING_RR_INFLECTION.value
'training_rr_inflection'
```

**Failing tests (8 unit + several integration + several behaviour):**
- `tests/unit/test_physiology_update_service_pure_helpers.py::TestSourceValue::test_enum_member_returns_value_string`
- `tests/unit/test_physiology_update_service_bayesian.py::TestBayesianUpdateDominantSource::test_observation_dominates_when_weight_exceeds_decayed_prior`
- `tests/unit/test_physiology_update_service_bayesian.py::TestBayesianUpdateDominantSource::test_dominant_source_stored_as_value_string`
- `tests/unit/test_physiology_update_service_bayesian.py::TestInitNullParameterState::test_bootstrap_uses_observation_source`
- `tests/unit/test_physiology_update_service_orchestration.py::TestApplyObservationsFirstObservationForNullParameter::test_first_cp_observation_bootstraps_state` (asserts `dominant_source == "training_power_hr_ratio"`)
- And every integration / behaviour test that asserts the `dominant_source` JSONB column or the `dominant_sources` dict in the `physiology_updated` event payload.

**Suggested fix (one line in production code):**
```python
def _source_value(source: Any) -> str:
    """Return the ``MeasurementSource.value`` string for ``source``."""
    if isinstance(source, MeasurementSource):
        return source.value
    # Defensive — JSONB round-trips can hand back a plain string.
    return str(source)
```

**Impact assessment:**
- JSONB `dominant_source` field on `AthletePhysiology.lt1/l2/cp/max_hr` — every posterior update writes the wrong string.
- `dominant_sources` dict in `physiology_updated` event payload — every event payload has the wrong string. P3's `TwinRecalibrationService` consumers will read wrong values.
- `init_null_parameter_state` and `bayesian_update` both call `_source_value` — both write the wrong string for every observation where the source is a `MeasurementSource` enum member.

**No downstream dependency on the wrong format** — no other service reads `dominant_source` yet (this is a P2 contract that P3 will consume), so the fix is contained to this plan's implementation and the downstream test pack.

---

#### Bug 2 — `apply_observations` loop does not accumulate state across same-parameter observations in a single call

**Severity:** HIGH — breaks the confidence transition contract. 4 observations of weight 1.0 should reach `prior_weight=4.0` (LOW→MEDIUM), but the post-loop prior_weight is 1.0. 8 observations should reach 8.0 (MEDIUM→HIGH), but post-loop is 1.0. The contract `low→medium at prior_weight ≥ 4.0` and `medium→high at prior_weight ≥ 8.0` is unverifiable at the integration and behaviour layers.

**Location:** `app/services/physiology_update_service.py`, function `PhysiologyUpdateService.apply_observations` (lines 510-705), specifically the observation loop at lines 555-602.

**Current code (abbreviated):**
```python
for obs in observations:
    if await self._is_duplicate(...):
        ...
        continue

    # Resolve the current state — null for previously unobserved parameters.
    current_state = self._get_parameter_state(physiology, obs.parameter)
    # ← BUG: always reads from `physiology`, which is NOT updated
    # until AFTER the loop. The 2nd, 3rd, 4th observations see
    # the SAME current_state as the 1st.

    if current_state is None:
        new_state = init_null_parameter_state(observation_payload)
    else:
        new_state = bayesian_update(current_state, observation_payload)

    working_state[obs.parameter] = new_state
    # ← The dict overwrite means only the last iteration's
    # result survives. The accumulated state across iterations
    # is lost.
```

**Bug analysis:** The implementation reads `current_state` from the in-memory `physiology` ORM entity on every iteration. But `physiology` is only mutated AFTER the loop completes (in `_apply_updated_states(physiology, working_state)` and `athlete_physiology.update_in_place(...)`). So for 4 observations of the same parameter in a single `apply_observations` call:
- All 4 iterations see the original `prior_weight=0.0` (or `0.5` depending on the test fixture).
- Each iteration's `working_state[obs.parameter] = new_state` overwrites the previous one.
- The final `working_state[obs.parameter]["prior_weight"]` reflects exactly ONE observation's contribution, not 4.

This violates the standard Bayesian sequential-update pattern: `posterior_n = bayesian_update(posterior_{n-1}, observation_n)`, not `posterior_n = bayesian_update(prior, observation_n)` for n > 1.

**Failing tests (3 unit + 4 integration + 2 behaviour):**
- `tests/unit/test_physiology_update_service_orchestration.py::TestApplyObservationsConfidenceTransitions::test_four_observations_reach_medium`
- `tests/unit/test_physiology_update_service_orchestration.py::TestApplyObservationsConfidenceTransitions::test_eight_observations_reach_high`
- `tests/unit/test_physiology_update_service_orchestration.py::TestApplyObservationsConfidenceTransitions::test_rr_observations_reach_medium_faster`
- `tests/integration/test_physiology_update_service_confidence_transitions_integration.py::TestLowToMediumTransition::test_four_observations_reach_prior_weight_4_point_5` (asserts `prior_weight=4.5` after 4 observations)
- `tests/integration/test_physiology_update_service_confidence_transitions_integration.py::TestLowToMediumTransition::test_four_observations_trigger_low_to_medium_transition`
- `tests/integration/test_physiology_update_service_confidence_transitions_integration.py::TestMediumToHighTransition::test_eight_observations_reach_prior_weight_8_point_5`
- `tests/integration/test_physiology_update_service_confidence_transitions_integration.py::TestMediumToHighTransition::test_eighth_observation_triggers_medium_to_high_transition`
- `tests/integration/test_physiology_update_service_confidence_transitions_integration.py::TestHighWeightSourceCrossesThresholdFaster::test_two_rr_observations_reach_medium_confidence`
- `tests/integration/test_physiology_update_service_confidence_transitions_integration.py::TestHighWeightSourceCrossesThresholdFaster::test_four_rr_observations_reach_high_confidence`
- `tests/integration/test_physiology_update_service_confidence_transitions_integration.py::TestSubsequentCallsAccumulateAgainstPersistedState::test_three_calls_each_with_one_observation`
- `tests/behaviour/test_physiology_update_user_journey.py::TestPhysiologyUpdateConfidenceTransitionsJourney::test_journey_four_observations_reach_medium_confidence` (asserts `lt2_hr_state["prior_weight"] >= 4.0`)
- `tests/behaviour/test_physiology_update_user_journey.py::TestPhysiologyUpdateConfidenceTransitionsJourney::test_journey_eight_observations_reach_high_confidence`

**Suggested fix (one block in production code, inside the observation loop):**
```python
for obs in observations:
    if await self._is_duplicate(...):
        ...
        continue

    # CRITICAL: if this parameter was already updated in a prior
    # iteration of THIS batch, use the in-loop `working_state`
    # entry as the next iteration's prior. Otherwise, read from
    # the in-memory `physiology` row (which reflects the
    # persisted state at call entry).
    current_state = working_state.get(obs.parameter)
    if current_state is None:
        current_state = self._get_parameter_state(physiology, obs.parameter)

    if current_state is None:
        new_state = init_null_parameter_state(observation_payload)
    else:
        new_state = bayesian_update(current_state, observation_payload)

    working_state[obs.parameter] = new_state
    ...
```

**Verification:** A trace through 4 observations of weight 1.0 against initial `prior_weight=0.0`:
- Iteration 1: `working_state` is empty → read from physiology (0.0) → new `prior_weight = 0.0 + 1.0 = 1.0` → `working_state[param] = {..., prior_weight: 1.0}`
- Iteration 2: `working_state.get(param)` returns `{..., prior_weight: 1.0}` → use as prior → new `prior_weight = 1.0 * 1.0 (no decay) + 1.0 = 2.0` → `working_state[param] = {..., prior_weight: 2.0}`
- Iteration 3: `working_state.get(param)` returns `{..., prior_weight: 2.0}` → new `prior_weight = 3.0`
- Iteration 4: `working_state.get(param)` returns `{..., prior_weight: 3.0}` → new `prior_weight = 4.0` → LOW→MEDIUM transition fires correctly.

**Impact assessment:**
- Plan P3's `TwinRecalibrationService` consumes the `confidence_transitions` dict from `PhysiologyUpdateResult`. With the bug, the transitions are wrong (no transition fires even after 4+ observations) — P3's `twin_confidence_upgraded` event will never fire from the P2 service.
- The `metric_confidence` dict returned to P3 will always be `"low"` (since prior_weight stays at 1.0, not 4.0+). P3's monotonicity ratchet will then hold the level at LOW, so the system never advances the athlete's confidence past the initial bootstrap. The downstream coaching message pipeline that depends on `twin_confidence_upgraded` would be permanently dormant.
- Cross-call accumulation still works correctly (each `apply_observations` call reads from the persisted `physiology` row, which was correctly updated by the previous call's `update_in_place`). The bug is intra-call only.

**Testability of the fix:** The failing tests above directly exercise the fix — once the production code is corrected, the existing tests will pass without modification (the test fixtures already set up the multi-observation batches).

---

### Routing

| Finding | Route To |
|---------|----------|
| 5 test-pack fixes | Applied by Test Architect (this file's "Triage" section; see `tests/test-manifest/phase-2-3p2.yaml` history entry for 2026-07-13) |
| Bug 1 (`_source_value` wrong format) | p-coder — one-line fix in `app/services/physiology_update_service.py` |
| Bug 2 (`apply_observations` loop doesn't accumulate) | p-coder — block-level fix in the observation loop in `app/services/physiology_update_service.py::apply_observations` |

The next DevOps run will re-execute the test suite. With both production bugs fixed, the test count is expected to be 194 passed, 0 failed (modulo any pre-existing failures from other plans).



---

## Unit Tests (this session)

### Files generated

| File | Tests | Capabilities covered |
|------|-------|----------------------|
| `tests/unit/test_physiology_update_service_bayesian.py` | 39 | `bayesian_update_posterior_mean`, `bayesian_update_uncertainty_floor`, `bayesian_update_dominant_source`, `bayesian_update_prior_decay`, `bayesian_update_date_parsing`, `init_null_parameter_state_bootstrap`, `physiology_update_result_dataclass`, architecture constants |
| `tests/unit/test_physiology_update_service_pure_helpers.py` | 41 | `compute_metric_confidence_pure`, `detect_confidence_transitions_pure`, `_confidence_level`, `_state_prior_weight`, `_parse_iso_date`, `_coerce_observation_date`, `_source_value` |
| `tests/unit/test_physiology_update_service_orchestration.py` | 32 | `service_construct_with_dependencies`, `service_apply_observations_raises_missing_physiology_error`, `service_apply_observations_writes_measurement_for_each_observation`, `service_apply_observations_shifts_posterior_and_fires_event_when_gt_1_unit`, `service_apply_observations_does_not_fire_event_when_shift_le_1_unit`, `service_apply_observations_idempotent_duplicate`, `service_apply_observations_first_observation_for_null_cp`, `service_apply_observations_confidence_transitions`, `service_get_parameter_state_for_lt1_hr`, `service_get_parameter_state_unsupported_raises`, `service_apply_updated_states_writes_back_with_flag_modified`, `service_registration_in_services_init` |
| `tests/unit/test_athlete_physiology_repository_update_in_place.py` | 27 | `athlete_physiology_repo_update_in_place` (per-parameter semantics, UNSET_SENTINEL identity, flush-not-commit, RuntimeError on missing row) |

**Total: 139 tests across 4 files.**

### Self-check

`bash scripts/pytest.sh --collect-only` collected all 139 tests
cleanly — no import errors, no fixture-not-found errors, no syntax
errors. The collection-only check passed in 0.15s.

### Coverage classification

| Capability | Status |
|------------|--------|
| `bayesian_update_posterior_mean` | Covered |
| `bayesian_update_uncertainty_floor` | Covered |
| `bayesian_update_dominant_source` | Covered |
| `bayesian_update_prior_decay` | Covered |
| `bayesian_update_date_parsing` | Covered |
| `init_null_parameter_state_bootstrap` | Covered |
| `physiology_update_result_dataclass` | Covered |
| `compute_metric_confidence_pure` | Covered |
| `detect_confidence_transitions_pure` | Covered |
| `athlete_physiology_repo_update_in_place` | Covered |
| `service_get_parameter_state_for_lt1_hr` | Covered |
| `service_get_parameter_state_unsupported_raises` | Covered |
| `service_apply_updated_states_writes_back_with_flag_modified` | Covered |
| `service_construct_with_dependencies` | Covered |
| `service_apply_observations_raises_missing_physiology_error` | Covered |
| `service_apply_observations_writes_measurement_for_each_observation` | Covered |
| `service_apply_observations_shifts_posterior_and_fires_event_when_gt_1_unit` | Covered |
| `service_apply_observations_does_not_fire_event_when_shift_le_1_unit` | Covered |
| `service_apply_observations_idempotent_duplicate` | Covered |
| `service_apply_observations_first_observation_for_null_cp` | Covered |
| `service_apply_observations_confidence_transitions` | Covered |
| `service_registration_in_services_init` | Covered |

**22/22 unit-tagged capabilities covered. 0 partial. 0 missing.**

### Mocking boundary

All unit tests conform to `tests/MOCKING_CONTRACT.md`:

* **Layer:** `tests/unit/` — repository interfaces and event publisher
  are mocked; pure function logic is real.
* **Mocks:** `AsyncMock(spec=AthletePhysiologyRepository)`,
  `AsyncMock(spec=PhysiologyMeasurementRepository)`,
  `AsyncMock(spec=EventPublisher)`. The `AthletePhysiology` ORM model
  is constructed in-memory (not persisted) so `_compute_metric_confidence`
  can read its JSONB attributes.
* **No real DB connections.** No real event publishing.
* **No `session.execute()` mocking** for the service tests — the
  service's repository dependencies are mocked directly, per the
  "Repository mocking requires scalar_one_or_none() not first()"
  anti-pattern in `tests/MOCKING_CONTRACT.md`.
* **Repository tests** (`test_athlete_physiology_repository_update_in_place.py`)
  mock `session.execute()` because the repository IS the unit under
  test — this is the documented exception.

### Key design decisions

1. **Real `ThresholdObservation` dataclass instances** are built in
   the orchestration tests (not `MagicMock(spec=ThresholdObservation)`)
   because the dataclass is `frozen=True` and the service reads its
   attributes directly. A `MagicMock` would auto-create truthy
   `MagicMock()` values for unset fields, which would corrupt the
   observation payload.

2. **Real `AthletePhysiology` ORM model instances** are built in-memory
   (not `MagicMock(spec=AthletePhysiology)`) because the service reads
   `physiology.lt1`, `physiology.lt2`, `physiology.cp`, `physiology.max_hr`
   directly via `_get_parameter_state` and `_compute_metric_confidence`.
   A `MagicMock` would auto-create `MagicMock()` values for unset
   attributes, which would break the JSONB path navigation.

3. **Constructor uses keyword-only parameters** —
   `PhysiologyUpdateService(session, *, athlete_physiology_repository=...,
   physiology_measurement_repository=..., events=...)`. The brief from
   `p-code-explorer` flagged this as a critical correction; tests use
   the keyword form throughout.

4. **`UNSET_SENTINEL` identity check** — the repository's
   `update_in_place` uses `cp is not _UNSET` (identity, not equality).
   Tests pass `UNSET_SENTINEL` (imported from
   `app.repositories.athlete_physiology_repository`) for the
   "do not touch" branch, and a separate `object()` instance to verify
   the identity check rejects non-sentinel objects.

5. **`flag_modified` patching** — the orchestration tests patch
   `app.services.physiology_update_service.flag_modified` (the import
   location, not the source location) so the patch intercepts the
   call from inside the service module.

---

## Integration Tests (this session)

### Files generated

| File | Tests | Capabilities covered |
|------|-------|----------------------|
| `tests/integration/test_physiology_update_service_integration.py` | 14 | `integration_physiology_update_service_end_to_end` — service construction, JSONB persistence, `PhysiologyMeasurement` audit rows, `physiology_updated` event with `SystemEvent` + `SystemEventOutbox` PENDING, no-event when shift ≤ 1 unit, multi-parameter event payload, ADR-004 transactional outbox atomicity (rollback test) |
| `tests/integration/test_physiology_update_service_idempotency_integration.py` | 6 | `integration_physiology_update_idempotency_db` — same-call duplicate, cross-call duplicate, non-duplicates (different value / activity / source) |
| `tests/integration/test_physiology_update_service_confidence_transitions_integration.py` | 8 | `integration_physiology_update_confidence_transitions_db` — LOW→MEDIUM at 4.0, MEDIUM→HIGH at 8.0, higher-weight source crosses faster, subsequent calls accumulate against persisted state |
| `tests/integration/test_physiology_update_service_first_observation_integration.py` | 6 | `integration_physiology_update_first_observation_cp_db` — cp null→bootstrapped state, second observation grows prior_weight, max_hr bootstrap |
| `tests/integration/test_athlete_physiology_repository_update_in_place_integration.py` | 14 | `integration_physiology_update_repo_persistence` — lt1/lt2 mapping persists, cp/max_hr null transitions and UNSET_SENTINEL semantics, updated_at hook, RuntimeError on missing row, row id preserved |

**Total: 48 tests across 5 files.**

### Self-check

`bash scripts/pytest.sh --collect-only` collected all 48 tests
cleanly — no import errors, no fixture-not-found errors, no syntax
errors. The collection-only check passed in 0.03s.

### Coverage classification

| Capability | Status |
|------------|--------|
| `integration_physiology_update_service_end_to_end` | Covered |
| `integration_physiology_update_idempotency_db` | Covered |
| `integration_physiology_update_confidence_transitions_db` | Covered |
| `integration_physiology_update_first_observation_cp_db` | Covered |
| `integration_physiology_update_repo_persistence` | Covered |

**5/5 integration-tagged capabilities covered. 0 partial. 0 missing.**

### Mocking boundary

All integration tests conform to `tests/MOCKING_CONTRACT.md`:

* **Layer:** `tests/integration/` — external services are not used
  (there are none for this plan); the database is real (test DB);
  the `EventPublisher` writes real `SystemEvent` + `SystemEventOutbox`
  rows in the same transaction as the physiology update.
* **No mocking of `AsyncSession` methods.** All DB interactions use
  the real test database via the `db_session` fixture.
* **No mocking of repositories.** The service uses the real
  `AthletePhysiologyRepository` and `PhysiologyMeasurementRepository`
  built from the session.
* **The `EventPublisher` is the default one** — built from
  `SystemEventRepository(session)` and
  `SystemEventOutboxRepository(session)`. This is the production
  code path; the integration test verifies the real transactional
  outbox contract, not a mock.

### Key design decisions

1. **Full `PhysiologyParameterState` dicts in test fixtures** — the
   conftest `_default_athlete_physiology_fields` before_insert
   listener fills `lt1`/`lt2` with
   `{"hr": 150, "source": "population_default"}` when null at insert
   time. This is NOT a valid `PhysiologyParameterState` — the
   Bayesian update would fail when it tries to read `uncertainty` or
   `prior_weight`. All test fixtures use the `_state()` helper
   which returns a full PhysiologyParameterState shape.

2. **Deterministic `activity_id` per observation** — the `_observation()`
   helper generates a fresh UUID per call, so successive
   observations are NOT deduped against each other. Tests that
   exercise the dedup key (same activity, same tuple) pass an
   explicit `activity_id`.

3. **`MeasurementSource.TRAINING_POWER_HR_RATIO` for CP** — the plan
   identifies this as the source for the first qualifying CP
   observation. The integration test uses this source for the
   first-observation bootstrap path.

4. **Rollback test for ADR-004 atomicity** — the end-to-end test
   includes a test that calls `apply_observations`, then rolls back
   the transaction, and asserts that NONE of the artefacts (event
   row, outbox row, measurement row, physiology JSONB mutation)
   persisted. This pins the ADR-004 rule "Event Persistence
   Atomicity" at the real-DB layer.

5. **`updated_at` hook test sleeps 1.1 seconds** — the DB stores
   `updated_at` at second-precision. A 1.1s sleep guarantees the
   timestamp difference is observable.

6. **No new fixtures added to `tests/conftest.py`** — the existing
   `db_session`, `make_athlete`, and `_SafeAsyncSession` are
   sufficient. The `_default_athlete_physiology_fields` listener
   is the only conftest-level behaviour that affects these tests,
   and it's handled by the `_state()` helper returning full
   `PhysiologyParameterState` dicts.

7. **EventPublicationStatus imported from `app.models.system_event`**
   (not `app.models.enums`) — the enum is defined in
   `system_event.py` alongside the `SystemEvent` and
   `SystemEventOutbox` models. The unit-mode session didn't need
   this import; the integration session does because it asserts
   on the outbox row status.

## API Tests (this session)

### Outcome: no tests generated — plan introduces no API endpoints

Phase-2.3-P2 does not introduce any HTTP routes. The plan's Scope
section explicitly defers API endpoints:

> "API endpoints for `GET/POST /physiology/measurements` (deferred —
> sub-phase focuses on training-derived pipeline)"

The `PhysiologyUpdateService` is invoked by the worker task in
Phase-2.3-P3, not by an HTTP route. The plan's Out Of Scope section
also lists "Worker task and pipeline wiring (Plan P3)" — the worker
that calls `apply_observations()` is a separate plan.

### Verification performed

* `grep_files` for `physiology|Physiology` across `app/api/**/*.py`
  returned **no matches** — no router, route handler, or schema
  references the physiology update service.
* `grep_files` for `PhysiologyUpdateService` across `app/**/*.py`
  returned matches only in:
  - `app/services/physiology_update_service.py` (the service itself)
  - `app/services/__init__.py` (registration)
  - `app/services/threshold_detection_service.py` (docstring
    references — Plan P1's data contract)
  - `app/repositories/athlete_physiology_repository.py` (docstring
    references — the `update_in_place` method's caller)
  - `app/models/athlete_physiology.py` and
    `app/models/physiology_measurement.py` (docstring references)
  No `app/api/` matches.
* `grep_files` for `physiology|Physiology` across `tests/api/**/*.py`
  returned **no matches** — no existing API test references the
  physiology update service.
* `tests/test-manifest/phase-2-3p2.yaml` contains **zero
  `test_type: api` capabilities** — the inventory has no API
  capabilities to generate against.

### Capability inventory (api mode)

Empty. The plan introduces no API routes, no request/response
schemas, and no router-level behaviour to test. The capability
inventory for this plan is:

| Test type | Capabilities |
|-----------|--------------|
| unit | 22 (all generated in unit-mode session) |
| integration | 5 (all generated in integration-mode session) |
| api | 0 |
| behaviour | 0 (the user-journey capability is owned by Phase-2.3-P3, which wires the worker task that invokes `apply_observations()`) |

### Mocking boundary

N/A — no tests generated. The `tests/api/` directory was not
modified.

### Key design decisions

1. **No `tests/api/test_physiology_update_endpoints.py` created.**
   Creating an empty test file would be misleading — it would
   suggest coverage where none exists. The test pack records the
   no-op outcome instead.

2. **No manifest entries added.** The manifest's `features` block
   has no `test_type: api` entries to promote. The `selection`
   groups in `index.yaml` are unchanged.

3. **No `index.yaml` update required.** The `feature` selection
   group already lists the unit and integration test paths from
   prior sessions; no new paths to add.

4. **Behaviour tests remain pending.** The user-journey capability
   (`physiology_update_user_journey_threshold_to_event`) is owned
   by Phase-2.3-P3, not Phase-2.3-P2. The behaviour-mode session
   for this plan will be a no-op for the same reason as this
   api-mode session — the worker wiring that triggers the
   end-to-end flow is in P3.

## Behaviour Tests (this session)

### Files generated

| File | Tests | Capabilities covered |
|------|-------|----------------------|
| `tests/behaviour/test_physiology_update_user_journey.py` | 7 | `behaviour_physiology_update_user_journey_threshold_to_event` (2 tests), `behaviour_physiology_update_user_journey_idempotency` (1 test), `behaviour_physiology_update_user_journey_confidence_transitions` (2 tests), `behaviour_physiology_update_user_journey_first_observation_cp` (1 test), `behaviour_physiology_update_user_journey_no_event_when_shift_le_1_unit` (1 test) |

**Total: 7 tests across 1 file.**

### Self-check

`bash scripts/pytest.sh --collect-only tests/behaviour/test_physiology_update_user_journey.py` collected all 7 tests cleanly — no import errors, no fixture-not-found errors, no syntax errors. The collection-only check passed in 0.10s.

### Coverage classification

| Capability | Status |
|------------|--------|
| `behaviour_physiology_update_user_journey_threshold_to_event` | Covered |
| `behaviour_physiology_update_user_journey_idempotency` | Covered |
| `behaviour_physiology_update_user_journey_confidence_transitions` | Covered |
| `behaviour_physiology_update_user_journey_first_observation_cp` | Covered |
| `behaviour_physiology_update_user_journey_no_event_when_shift_le_1_unit` | Covered |

**5/5 behaviour-tagged capabilities covered. 0 partial. 0 missing.**

### Mocking boundary

All behaviour tests conform to `tests/MOCKING_CONTRACT.md`:

* **Layer:** `tests/behaviour/` — no mocking of internal services or
  repositories. The full user journey is exercised end-to-end:
  HTTP register → activity creation → signal-cleaned stream upload
  → ThresholdDetectionService.detect() → PhysiologyUpdateService
  .apply_observations() → physiology_updated event in the
  transactional outbox.
* **Real DB connections** via the `db_session` fixture.
* **Real `EventPublisher`** — the default constructor path builds
  the publisher from `SystemEventRepository(session)` and
  `SystemEventOutboxRepository(session)`, writing real
  `SystemEvent` + `SystemEventOutbox` rows in the same transaction
  as the physiology update.
* **Real `ObjectStorageClient`** — uses the local filesystem
  fallback (S3 env vars are cleared in conftest).
* **No mocking of `AsyncSession` methods.** All DB interactions use
  the real test database.

### Key design decisions

1. **Service invocation pattern mirrors the sibling threshold
   detection behaviour file** — `tests/behaviour/test_threshold_detection_user_journey.py`
   establishes the pattern of invoking the service directly after
   the cleaned stream is in object storage, simulating what the P3
   worker task will do. This file follows the same pattern for
   `PhysiologyUpdateService.apply_observations()`.

2. **Module-level helpers** — `_create_running_activity`,
   `_upload_cleaned_stream_and_create_raw`,
   `_build_threshold_detection_service`, and
   `_build_physiology_update_service` are defined per-module (not
   in conftest) because they are specific to this test file's
   journey. The `_build_physiology_update_service` helper accepts
   an optional `events` parameter for tests that want to inject a
   fake publisher (though the current tests use the default real
   publisher to verify the transactional outbox contract).

3. **`FakeEventPublisher` test double** — defined but not used in
   the current tests. The default real publisher is used to verify
   the transactional outbox contract at the full user-journey
   boundary. The fake is available for future tests that need to
   assert on event payloads without touching the outbox.

4. **Idempotency test uses the same session for both calls** —
   the `_is_duplicate` check uses `get_recent_for_parameter()` on
   the same session, so it sees rows flushed by the same session.
   No commit between calls is needed because the first call's
   measurement row is already flushed in the session.

5. **Confidence transitions test uses separate activities** —
   each observation comes from a separate activity with a
   different date, so the decay factor applies between
   observations. This mirrors the production pattern where
   observations accumulate across multiple training sessions.

6. **First CP observation test builds a `ThresholdObservation`
   directly** — the HR deflection stream doesn't produce CP
   observations, so the test constructs a CP observation with
   `TRAINING_POWER_HR_RATIO` source and weight 1.5 directly,
   rather than going through `detect()`.

7. **No-event-when-shift-le-1-unit test uses a probabilistic
   assertion** — the HR deflection stream produces observations
   at the same intensity steps, so the second call's posterior
   should be close to the first call's. The test handles both
   cases (shift > 1 unit → event fires; shift ≤ 1 unit → no
   event) with a conditional assertion. If the shift happens to
   exceed 1 unit (unlikely but possible), the assertion will
   fail and the test should be redesigned.

8. **No new fixtures added to `tests/conftest.py`** — the
   existing `db_session`, `client`, `make_athlete`, and
   `http_register` helpers are sufficient. The
   `_default_athlete_physiology_fields` listener fills `lt1`/`lt2`
   with default values when null at insert time, which is
   handled by the service's `_get_parameter_state` returning
   the existing state.

---

## Recurring Infrastructure Risk

### Post-commit JSONB reads — `scalar_one()` returns identity-mapped instance with stale attributes

During a follow-up fix pass on the integration tests, all 25
post-commit `scalar_one()` calls across the 5 integration test files
were replaced with `.scalars().all()[0]`. Without this fix, the
tests would have asserted `fresh.cp is None` (or other stale JSONB
values) immediately after `repo.update_in_place(athlete.id, cp=new_cp)`
persisted a non-null value, because SQLAlchemy's identity map returns
the same ORM instance that was loaded before the commit and does
not refresh JSONB attributes on a same-table SELECT.

**Status:** This is a reusable failure class. The first
occurrence was in this session (Phase-2.3-P2 integration tests).
A dated lesson was added to `tests/README.md` ("Post-commit JSONB
reads must use `.scalars().all()[0]`, not `.scalar_one()`",
2026-07-13) and a row was added to `tests/MOCKING_CONTRACT.md`
"Known Anti-Patterns". **If a second integration test
author encounters this pattern, the fix should move into a
shared conftest helper** — e.g. a `fresh_row(session, model, id)`
fixture that does the `.scalars().all()[0]` internally and returns
the fresh instance, so the next author cannot reach for
`scalar_one()` and reintroduce the failure.

Any future integration test that does a post-commit read of a
JSONB-mutated row (e.g. `AthletePhysiology`, `TwinState`,
`WorkoutTarget`) is at risk.

### `str(enum_member)` for `class Foo(str, Enum)` — every JSONB write of the enum-derived value is wrong

**Status:** First occurrence was in this session (Phase-2.3-P2
triage). Dated lessons added to `tests/README.md`:
- "`str(enum_member)` is NOT the `.value` for `class Foo(str, Enum)`" (2026-07-13)
- "`_observation()` helper default `activity_id=uuid.uuid4()` violates the FK chain" (2026-07-13)
- "`http_register` does not create `AthletePhysiology` — behaviour tests must insert it explicitly" (2026-07-13)
- "Test fixtures with default `last_observation_date` cause 45-day decay when assertions assume same-day" (2026-07-13)
- "`onupdate=` hook fires only when a column is mutated — not on a no-op flush" (2026-07-13)
- "Multi-observation apply loop must use in-loop `working_state` as the next iteration's prior" (2026-07-13 — covered in the impl-bug analysis above, recorded for the next time a similar sequential-update pattern is implemented)

The str-enum rule and the FK-chain rule are both generalisable
beyond this plan. The str-enum rule applies to any enum that inherits
from `str` (`MeasurementSource`, `PhysiologyParameter`, `SportType`,
`TwinConfidenceLevel`, `GoalType`, `MeasurementSource`, etc. — most
enums in this codebase). The FK-chain rule applies to any test helper
that builds a model with a non-nullable FK column. **If a third
integration test author encounters either pattern, the fix should
move into a shared helper:**
- For str-enum: a `to_value(enum_or_string)` utility in
  `tests/utils/` (or a custom `__str__` on the enums themselves —
  but that would change the production data contract and is out of
  scope for the test pack).
- For FK-chain: the `make_activity` factory in
  `tests/utils/factories.py` is the right model — any future
  test helper that needs a real parent row should use the
  factory, not generate a fresh UUID.

The intra-call state-accumulation rule (Bug 2) is a Bayesian
sequential-update pattern that applies to any service that processes
a batch of observations for the same parameter in one call. The
`working_state.get(obs.parameter)` pattern is the canonical fix;
the same fix should be applied if/when a similar pattern emerges
in P3's `TwinRecalibrationService` or any future Bayesian service.

Any future service that processes a batch of observations with
sequential updates is at risk.

---

## Manifest

* `tests/test-manifest/phase-2-3p2.yaml` — created with full
  capability inventory (every test type tagged, not just unit).
* `tests/test-manifest/index.yaml` — `feature` selection group
  updated with the four new test paths; `last_reviewed_at` bumped
  to 2026-07-12T10:00:00Z.

---

## Files Saved

### Unit-mode session (previous)

* `tests/unit/test_physiology_update_service_bayesian.py` (new)
* `tests/unit/test_physiology_update_service_pure_helpers.py` (new)
* `tests/unit/test_physiology_update_service_orchestration.py` (new)
* `tests/unit/test_athlete_physiology_repository_update_in_place.py` (new)
* `tests/test-manifest/phase-2-3p2.yaml` (new)
* `tests/test-manifest/index.yaml` (updated — feature group + timestamp)
* `docs/testing/phase-2-3-p2-physiology-update_test_pack.md` (this file)

### Integration-mode session (previous)

* `tests/integration/test_physiology_update_service_integration.py` (new)
* `tests/integration/test_physiology_update_service_idempotency_integration.py` (new)
* `tests/integration/test_physiology_update_service_confidence_transitions_integration.py` (new)
* `tests/integration/test_physiology_update_service_first_observation_integration.py` (new)
* `tests/integration/test_athlete_physiology_repository_update_in_place_integration.py` (new)
* `tests/test-manifest/phase-2-3p2.yaml` (updated — 5 integration capabilities added, all promoted to `generated`; new execution group `physiology_update_integration`; new history entry; coverage updated)
* `tests/test-manifest/index.yaml` (updated — 5 new test paths in `feature` group; 3 new invariants in cross-phase coverage; `last_reviewed_at` bumped to 2026-07-12T11:00:00Z; pre-existing YAML formatting issue at line 156 fixed)
* `docs/testing/phase-2-3-p2-physiology-update_test_pack.md` (this file — integration section added, status line updated)

### Integration fix pass (2026-07-13, previous)

* Replaced 25 `.scalar_one()` post-commit reads with
  `.scalars().all()[0]` across all 5 integration test files. The
  original `scalar_one()` calls would have returned identity-mapped
  instances with stale JSONB attributes after the `await
  db_session.commit()` boundary. See "Recurring Infrastructure Risk"
  below and `tests/README.md` dated lesson 2026-07-13 for the full
  pattern analysis.
* `tests/README.md` (updated — new dated lesson "Post-commit JSONB
  reads must use `.scalars().all()[0]`, not `.scalar_one()`" appended
  under "Dated Lessons (2026-07-13)").
* `tests/MOCKING_CONTRACT.md` (updated — new row in "Known
  Anti-Patterns" table cross-referencing the new README lesson).
* `docs/testing/phase-2-3-p2-physiology-update_test_pack.md` (this
  file — "Recurring Infrastructure Risk" section now documents the
  fix; status line remains `integration: done`).

### API-mode session (previous)

* No test files generated — plan introduces no API endpoints.
* No manifest changes — `tests/test-manifest/phase-2-3p2.yaml` has
  zero `test_type: api` capabilities; `tests/test-manifest/index.yaml`
  unchanged.
* `docs/testing/phase-2-3-p2-physiology-update_test_pack.md` (this
  file — API section added with no-op outcome, status line updated
  to `api: done (no-op — no endpoints)`)

### Behaviour-mode session (previous)

* `tests/behaviour/test_physiology_update_user_journey.py` (new)
* `tests/test-manifest/phase-2-3p2.yaml` (updated — 5 behaviour capabilities added, all promoted from `pending` to `generated`; new execution group `physiology_update_behaviour`; new history entry)
* `tests/test-manifest/index.yaml` (updated — 1 new test path in `feature` group; `last_reviewed_at` bumped to 2026-07-13T10:00:00Z)
* `docs/testing/phase-2-3-p2-physiology-update_test_pack.md` (this file — behaviour section added, status line updated to `behaviour: done`)

### Triage pass (2026-07-13, this session)

Test-pack fixes applied (5 issues, 1 test removed, 1 factory added, ~20 tests touched):

* `tests/unit/test_physiology_update_service_bayesian.py` (modified — 4 tests
  pinned `last_observation_date='2026-06-15'` to match the observation date
  for the same-day no-decay math).
* `tests/utils/factories.py` (modified — added `make_activity` factory for
  tests that need a real `Activity` row to satisfy the
  `physiology_measurements.activity_id` FK).
* `tests/integration/test_physiology_update_service_integration.py`
  (modified — `_observation()` helper default `activity_id` to `None`;
  added `make_activity` calls where tests assert `row.activity_id`).
* `tests/integration/test_physiology_update_service_idempotency_integration.py`
  (modified — `_observation()` helper default `activity_id` to `None`;
  added `make_activity` calls in 4 tests that exercise the dedup key
  which includes `activity_id`).
* `tests/integration/test_physiology_update_service_confidence_transitions_integration.py`
  (modified — `_observation()` helper default `activity_id` to `None`).
* `tests/integration/test_physiology_update_service_first_observation_integration.py`
  (modified — `_observation()` helper default `activity_id` to `None`).
* `tests/integration/test_athlete_physiology_repository_update_in_place_integration.py`
  (modified — removed `test_updated_at_changes_even_with_no_column_mutations`,
  replaced with NOTE comment explaining the SQLAlchemy `onupdate=` semantics).
* `tests/behaviour/test_physiology_update_user_journey.py` (modified — added
  `_ensure_physiology_row` helper and called it after every `http_register`
  in 7 tests; the helper inserts an `AthletePhysiology` row for the
  athlete, matching the production data topology where `http_register` only
  creates `Athlete + AthleteAuth + AthleteProfile`).
* `tests/test-manifest/phase-2-3p2.yaml` (updated — new TRIAGE history
  entry documenting the 5 test-pack fixes and 2 implementation bugs;
  `last_reviewed_at` bumped to 2026-07-13T12:00:00Z).
* `tests/test-manifest/index.yaml` (updated — `last_reviewed_at` bumped to
  2026-07-13T12:00:00Z).
* `tests/README.md` (updated — 6 new dated lessons under "Dated Lessons
  (2026-07-13, Phase-2.3-P2 triage)" — str-enum `.value` rule, FK-chain
  default rule, `http_register` topology rule, date-default fixture
  rule, `onupdate=` no-op rule, and multi-observation apply-loop rule).
* `tests/MOCKING_CONTRACT.md` (updated — 5 new rows in "Known Anti-Patterns"
  table cross-referencing the new README lessons; new change-log entry).
* `docs/testing/phase-2-3-p2-physiology-update_test_pack.md` (this file —
  new "Triage" section at the top with detailed analysis of the 2
  implementation bugs, suggested fixes, and routing to p-coder;
  "Recurring Infrastructure Risk" section updated with the new
  failure classes; status line updated with the triage-pass summary;
  "Files Saved" section appended).

**Collection check:** `bash scripts/pytest.sh --collect-only` on all 9
modified test files (3 unit, 5 integration, 1 behaviour) collected 172
tests cleanly in 0.13s. No import errors, no fixture-not-found errors,
no syntax errors.

**Expected outcome of the next DevOps run:** With both production bugs
fixed by p-coder, the test count is expected to be 194 passed, 0
failed (modulo any pre-existing failures from other plans). The
TRIAGE history entry's "test-pack fixes" applied here are the minimum
set needed for the existing tests to pass against a corrected
implementation.

---

## Triage — DevOps Report 2026-07-14 (test pack re-run)

**Reference:** `reports/phase-2-3-p2_devops_testpack_1.md` (Result: FAIL, 170/193 passed, 23 failed)

The DevOps report's 23 test failures split into **4 test-pack issues (fixed by Test Architect)** and **0 implementation bugs (all already resolved by p-coder in the 2026-07-13 triage pass)**. No infrastructure changes were required; the `MOCKING_CONTRACT.md` Known Anti-Patterns were not the source of any failure.

### Root causes (4 test-pack issues, 23 tests touched)

#### Issue 1 — Integration `_state()` helper default `last_observation_date="2026-05-01"` is 45 days behind the sibling `_observation()` helper's default `measurement_date=date(2026, 6, 15)` (16 tests)

The 2026-07-13 triage pass fixed 4 unit tests by pinning `last_observation_date='2026-06-15'` on the per-test `_state()` calls. The integration test files' `_state()` helper was not touched — its default was still `"2026-05-01"`, producing a 45-day gap in every integration test that relied on the default. The integration tests' expected values were computed for same-day math (e.g. `(160 * 0.5 + 170 * 1.0) / 1.5 = 166.67`), not the decayed math (e.g. `(160 * 0.171 + 170 * 1.0) / 1.171 = 168.54`).

**Affected tests (16):**
- `tests/integration/test_physiology_update_service_integration.py::TestApplyObservationsPersistsPosterior::test_lt2_hr_posterior_persists_after_commit` (got 168.54, expected 166.67)
- `tests/integration/test_physiology_update_service_integration.py::TestApplyObservationsPersistsPosterior::test_existing_lt2_hr_value_persists_when_only_lt1_updated` (got 154.27, expected 153.33)
- `tests/integration/test_physiology_update_service_integration.py::TestPhysiologyUpdatedEvent::test_event_persisted_when_shift_exceeds_one_unit` (got 1.17, expected 1.5)
- `tests/integration/test_physiology_update_service_idempotency_integration.py::TestDuplicateObservationInSameCall::test_second_observation_writes_measurement_but_does_not_mutate` (got 1.17, expected 1.5)
- `tests/integration/test_physiology_update_service_idempotency_integration.py::TestNonDuplicatesAreNotDeduped::test_different_observed_value_is_not_a_duplicate` (got 2.17, expected 2.5)
- `tests/integration/test_physiology_update_service_idempotency_integration.py::TestNonDuplicatesAreNotDeduped::test_different_activity_id_is_not_a_duplicate` (got 2.17, expected 2.5)
- `tests/integration/test_physiology_update_service_idempotency_integration.py::TestNonDuplicatesAreNotDeduped::test_different_source_is_not_a_duplicate` (got 2.17, expected 2.5)
- `tests/integration/test_physiology_update_service_confidence_transitions_integration.py::TestLowToMediumTransition::test_four_observations_reach_prior_weight_4_point_5` (got 4.02, expected 4.5)
- `tests/integration/test_physiology_update_service_confidence_transitions_integration.py::TestLowToMediumTransition::test_four_observations_trigger_low_to_medium_transition` (got "low", expected "medium")
- `tests/integration/test_physiology_update_service_confidence_transitions_integration.py::TestMediumToHighTransition::test_eight_observations_reach_prior_weight_8_point_5` (got 7.52, expected 8.5)
- `tests/integration/test_physiology_update_service_confidence_transitions_integration.py::TestMediumToHighTransition::test_eighth_observation_triggers_medium_to_high_transition` (got "medium", expected "high")
- `tests/integration/test_physiology_update_service_confidence_transitions_integration.py::TestHighWeightSourceCrossesThresholdFaster::test_four_rr_observations_reach_high_confidence` (got "medium", expected "high" from "low")
- `tests/integration/test_physiology_update_service_confidence_transitions_integration.py::TestSubsequentCallsAccumulateAgainstPersistedState::test_three_calls_each_with_one_observation` (got 1.17, expected 1.5)
- `tests/integration/test_physiology_update_service_first_observation_integration.py::TestSecondCpObservation::test_second_observation_grows_prior_weight` (got 1.98, expected 2.0)
- `tests/integration/test_physiology_update_service_first_observation_integration.py::TestSecondCpObservation::test_second_observation_fires_event_when_shift_exceeds_one` (got 1.98, expected 2.0)
- `tests/integration/test_physiology_update_service_integration.py::TestPhysiologyUpdatedEvent::test_event_atomicity_rolls_back_when_later_step_fails` (IndexError, see Issue 2)

**Fix applied:** Aligned the `_state()` default to `"2026-06-15"` in all 4 integration test files (matching the sibling `_observation()` helper's `measurement_date=date(2026, 6, 15)`). This is the canonical fix: when two helper functions in the same test file have default date values that interact, the two defaults must agree. Tests that need a different gap (e.g. an explicit 7-day decay exercise) pass the date explicitly. The 2026-07-13 unit-test date-default lesson was correct but only fixed the 4 unit tests that explicitly passed `last_observation_date`; the integration tests relied on the helper's default, so the default's drift from the observation's date was the single point of failure for 16 of 23 failures.

#### Issue 2 — `test_event_atomicity_rolls_back_when_later_step_fails`: `IndexError: list index out of range` from `flush()`-only fixture being rolled back (1 test)

The test creates an `AthletePhysiology` row via `_create_physiology_row()` (flush-only, no commit), then calls `apply_observations`, then `db_session.rollback()`. The accumulation fix (the production fix for RC2 in the 2026-07-13 triage) made `apply_observations` actually mutate the row in place via `update_in_place` + `flag_modified`, which now flushes real SQL updates through the same session. When the test then called `rollback()`, the rollback unwound BOTH the fixture row's INSERT (only flushed, not committed) AND the observation batch's UPDATE — leaving no `AthletePhysiology` row at all. The post-rollback SELECT returned `[]`, and `.scalars().all()[0]` raised `IndexError`.

The test was previously passing because the broken accumulation did not flush any modifications — the rollback only undid the row creation, but `apply_observations` did not change anything that triggered the rollback to matter. The accumulation fix exposed this latent fixture design issue.

**Fix applied:** Committed the fixture row in its own transaction (`await db_session.commit()` after `_create_physiology_row()`) so it survives the subsequent rollback. The `apply_observations` call opens a new transaction; its rollback unwinds the observation batch but NOT the fixture row. The post-rollback SELECT now finds the row and can assert that the JSONB columns are unchanged (the rollback undid the mutation).

#### Issue 3 — `test_eight_observations_reach_high` (orchestration): batch transition is `("low", "high")`, not `("medium", "high")` (1 test)

The test author assumed the service reports per-observation transitions — that observation 4 (which crosses prior_weight=4.0 → MEDIUM) would be reported as a transition, then observation 8 (which crosses prior_weight=8.0 → HIGH) would be reported as a second transition. The actual architecture reports a single `confidence_transitions` dict per `apply_observations` call, with the entry being `(pre_call_level, post_call_level)` — a batch transition between the call's input and output. A single batch that starts at LOW (prior_weight=0.0) and ends at HIGH (prior_weight=8.0) reports a direct `LOW→HIGH` transition. The MEDIUM level is reached internally at observation 4 but is not a snapshot the service reports.

**Fix applied:** Updated the expected value to `("low", "high")` and added a doc comment explaining the batch-transition contract. The plan's Step 8 explicitly states: "the service computes the raw confidence level from current `prior_weight`" — a single computation per call, not per-observation.

#### Issue 4 — Behaviour tests: pre-populate `AthletePhysiology` for shift assertions + same-date activities for multi-activity threshold assertions (6 tests)

The 2026-07-13 triage pass fixed `MissingAthletePhysiologyError` by adding `_ensure_physiology_row` after every `http_register`. The 2026-07-14 re-run surfaced a related but distinct issue: behaviour tests that insert an empty `AthletePhysiology` row (no `lt1`/`lt2` kwargs) and then call `apply_observations` with a single activity's observations get an empty `shifted_parameters` list. The first observation for each parameter bootstraps the state from null (via `init_null_parameter_state`), and the shift detection's `current_state is None` guard suppresses shift detection on the bootstrap. The architecture is correct — the "> 1 unit shift gate only applies when an existing estimate exists" (plan Step 5) — but the behaviour tests were designed assuming the first observation would produce a shift.

For the multi-activity tests, the activities were spread over multiple weeks (7-day gaps), so the 42-day decay reduced `prior_weight` to ~3.17 after 4 observations and ~4.79 after 8 observations — both below the 4.0 and 8.0 MEDIUM/HIGH thresholds.

**Affected tests (6):**
- `tests/behaviour/test_physiology_update_user_journey.py::TestPhysiologyUpdateThresholdToEventJourney::test_journey_threshold_detection_to_physiology_updated_event`
- `tests/behaviour/test_physiology_update_user_journey.py::TestPhysiologyUpdateThresholdToEventJourney::test_journey_event_payload_matches_shifted_parameters`
- `tests/behaviour/test_physiology_update_user_journey.py::TestPhysiologyUpdateIdempotencyJourney::test_journey_duplicate_observation_writes_measurement_not_event`
- `tests/behaviour/test_physiology_update_user_journey.py::TestPhysiologyUpdateConfidenceTransitionsJourney::test_journey_four_observations_reach_medium_confidence`
- `tests/behaviour/test_physiology_update_user_journey.py::TestPhysiologyUpdateConfidenceTransitionsJourney::test_journey_eight_observations_reach_high_confidence`
- `tests/behaviour/test_physiology_update_user_journey.py::TestPhysiologyUpdateNoEventWhenShiftLeOneJourney::test_journey_small_shift_writes_measurement_not_event`

**Fix applied:**
- Added a `_state()` helper to `tests/behaviour/test_physiology_update_user_journey.py` (mirroring the integration test helpers).
- For the 3 single-activity shift tests: pre-populated `lt1.hr` and `lt2.hr` with state that differs from the cleaned-stream observations by more than 1 bpm so the first observation produces a posterior shift.
- For the 2 multi-activity threshold tests: pre-populated `lt2.hr` with `prior_weight=0.5` and used same-date activities (distinct `activity_id` UUIDs, no decay). After 4 same-date observations: prior_weight = 0.5 + 4×1.0 = 4.5 → MEDIUM. After 8 same-date observations: prior_weight = 0.5 + 8×1.0 = 8.5 → HIGH.
- For the small-shift test: pre-populated `lt2.hr` with a baseline posterior that differs from the cleaned-stream observation by > 1 bpm so the first call's `assert len(result1.shifted_parameters) >= 1` passes.

The behaviour tests are designed to exercise the end-to-end user journey, not the decay math (the integration layer pins the decay math). The same-date activities keep the journey test deterministic — the dedup key includes `activity_id`, so multiple activities on the same date with distinct `activity_id` UUIDs are NOT duplicates.

### Test-pack fixes applied (4 issues, 23 tests touched, 1 helper added, 0 tests removed)

1. **Integration `_state()` default date (16 tests)** — aligned the default to `"2026-06-15"` in all 4 integration test files (matching the sibling `_observation()` helper's `measurement_date=date(2026, 6, 15)`). Tests that need a different gap (e.g. an explicit 7-day decay exercise) pass the date explicitly.
2. **Rollback fixture isolation (1 test)** — `test_event_atomicity_rolls_back_when_later_step_fails` now commits the fixture row in its own transaction before the service call, so the post-rollback SELECT finds the row and can assert that the JSONB columns are unchanged.
3. **Unit batch transition (1 test)** — `test_eight_observations_reach_high` now accepts `("low", "high")` as the correct batch-transition result. The MEDIUM level is a transient state inside the batch; the service contract is pre/post, not per-observation.
4. **Behaviour pre-population + same-date activities (6 tests)** — added a `_state()` helper to the behaviour test file and pre-populated `AthletePhysiology` state in 6 tests asserting on a posterior shift. Multi-activity confidence-transition tests now use same-date activities (distinct `activity_id` UUIDs, no decay) to keep the threshold-crossing assertion deterministic.

### Implementation bugs (routed to p-coder in 2026-07-13 triage — all resolved)

Both production bugs identified in the 2026-07-13 triage pass were resolved by p-coder before the 2026-07-14 re-run:

1. **`_source_value()` returns the wrong string format** — fixed at line 334-335 of `physiology_update_service.py` to use `source.value` for `MeasurementSource` enum members. All 7 unit/integration/behaviour tests that previously failed on this bug now pass.
2. **`apply_observations` loop does not accumulate state across same-parameter observations** — fixed at lines 584-586 of `physiology_update_service.py` to use `working_state.get(obs.parameter, self._get_parameter_state(...))` as the next iteration's prior. The cross-call accumulation (each call reads from the persisted `AthletePhysiology` row) was always correct; the fix is intra-call only.

Both fixes were verified by p-coder and the 2026-07-14 DevOps report confirmed them as resolved (RC1, fully fixed). The 23 remaining failures are all test-pack issues, not implementation bugs.

### Routing

| Finding | Route To |
|---------|----------|
| 4 test-pack fixes (23 tests) | Applied by Test Architect (this file's "Triage — DevOps Report 2026-07-14" section; see `tests/test-manifest/phase-2-3p2.yaml` history entry for 2026-07-14) |
| No new implementation bugs | RC1 and RC2 production bugs both resolved by p-coder in the 2026-07-13 triage pass |

The next DevOps run will re-execute the test suite. With both production bugs already fixed and the 23 test-pack issues corrected, the test count is expected to be 193 passed, 0 failed (modulo any pre-existing failures from other plans).

### Test-pack fixes applied (4 issues, 23 tests touched, 1 helper added, 0 tests removed)

1. **Integration `_state()` default date (16 tests)** — aligned the default to `"2026-06-15"` in all 4 integration test files (matching the sibling `_observation()` helper's `measurement_date=date(2026, 6, 15)`). Tests that need a different gap (e.g. an explicit 7-day decay exercise) pass the date explicitly.
2. **Rollback fixture isolation (1 test)** — `test_event_atomicity_rolls_back_when_later_step_fails` now commits the fixture row in its own transaction before the service call, so the post-rollback SELECT finds the row and can assert that the JSONB columns are unchanged.
3. **Unit batch transition (1 test)** — `test_eight_observations_reach_high` now accepts `("low", "high")` as the correct batch-transition result. The MEDIUM level is a transient state inside the batch; the service contract is pre/post, not per-observation.
4. **Behaviour pre-population + same-date activities (6 tests)** — added a `_state()` helper to the behaviour test file and pre-populated `AthletePhysiology` state in 6 tests asserting on a posterior shift. Multi-activity confidence-transition tests now use same-date activities (distinct `activity_id` UUIDs, no decay) to keep the threshold-crossing assertion deterministic.

### Reusable failure classes recorded

Four new dated lessons were added to `tests/README.md` (under "Dated Lessons (2026-07-14, Phase-2.3-P2 test pack re-run)"):

1. **Integration `_state()` helper default date causes 23 failures when assertions assume same-day math** — extends the 2026-07-13 unit-test date-default lesson to the integration and behaviour layers. The two helpers' default dates must agree; a drift silently introduces a date gap in every test that uses both defaults.
2. **`apply_observations` batch transition is `(pre_call_level, post_call_level)`, not per-observation transitions** — a test asserting on a sequence of intermediate state transitions is asserting a property the service does not implement.
3. **Rollback tests must commit fixture rows in their own transaction — `flush()` does not survive `rollback()`** — a test that mixes `flush()`-only fixtures with a `rollback()` is asserting a property the fixture cannot satisfy. The split-commit pattern (commit the fixture, then open a new transaction for the service call) is the canonical rollback-test fixture contract.
4. **Behaviour tests must pre-populate `AthletePhysiology` when asserting on a posterior shift — bootstrap suppresses shift detection** — an empty `lt1`/`lt2` row leaves the first observation as a bootstrap, and the `current_state is None` guard correctly suppresses shift detection. For multi-activity threshold assertions, use same-date activities (distinct `activity_id` UUIDs) to avoid 7-day decay reducing `prior_weight` below the threshold.

All 4 lessons are now first-class in `tests/MOCKING_CONTRACT.md` "Known Anti-Patterns" (rows added 2026-07-14).

### Collection check

`bash scripts/pytest.sh --collect-only` on all 7 modified test files (1 unit, 4 integration, 1 behaviour, plus the orchestrator's helper file) collected 77 tests cleanly in 0.15s. No import errors, no fixture-not-found errors, no syntax errors.

### Files saved

- `tests/integration/test_physiology_update_service_integration.py` (modified — `_state()` default aligned to `"2026-06-15"`; `test_event_atomicity_rolls_back_when_later_step_fails` commits the fixture row)
- `tests/integration/test_physiology_update_service_idempotency_integration.py` (modified — `_state()` default aligned to `"2026-06-15"`)
- `tests/integration/test_physiology_update_service_confidence_transitions_integration.py` (modified — `_state()` default aligned to `"2026-06-15"`)
- `tests/integration/test_physiology_update_service_first_observation_integration.py` (modified — `_state()` default aligned to `"2026-06-15"`)
- `tests/unit/test_physiology_update_service_orchestration.py` (modified — `test_eight_observations_reach_high` accepts `("low", "high")` batch transition)
- `tests/behaviour/test_physiology_update_user_journey.py` (modified — added `_state()` helper; pre-populated `AthletePhysiology` state in 6 tests; used same-date activities in 2 multi-activity tests)
- `tests/README.md` (updated — 4 new dated lessons under "Dated Lessons (2026-07-14, Phase-2.3-P2 test pack re-run)")
- `tests/MOCKING_CONTRACT.md` (updated — 4 new rows in "Known Anti-Patterns" table; new change-log entry for 2026-07-14)
- `docs/testing/phase-2-3-p2-physiology-update_test_pack.md` (this file — new "Triage — DevOps Report 2026-07-14" section with detailed analysis of the 4 test-pack issues, suggested fixes, and routing; status line updated with the test pack re-run summary)

---

## Triage — DevOps Report 2026-07-14 (test pack re-run, pass 2)

**Reference:** `reports/phase-2-3-p2_devops_testpack_2.md` (Result: FAIL, 185/193 passed, 8 failed)

The DevOps report's 8 test failures split into **3 test-pack issues (fixed by Test Architect)** and **0 implementation bugs (the implementation's decay behaviour is architecturally correct and is already pinned by `TestBayesianUpdatePriorDecay` in the unit tests)**. No infrastructure changes were required; the `MOCKING_CONTRACT.md` Known Anti-Patterns were partially the source (the `expire_all()` + lazy load rule partially described RC3's MissingGreenlet, but the post-rollback trigger is a distinct failure class).

### Root causes (3 test-pack issues, 8 tests touched)

#### Issue 1 — Integration multi-day `measurement_date` causes 1-day inter-observation decay that breaks linear-accumulation assertions (6 tests)

The pass-1 fix (aligning the integration `_state()` default to `"2026-06-15"`) resolved 16 of 23 tests that relied on the helper's default. But 7 tests explicitly construct observations at `measurement_date=date(2026, 6, 15 + i)` for `i in range(N)`, introducing 1-day gaps that the 42-day time constant decays by `exp(-1/42) ≈ 0.9765` per gap. The tests assert linear accumulation (e.g. `0.5 + 4 × 1.0 = 4.5`) but the actual values are `4.3265`, `7.7945`, `1.9765`, `2.4647` etc. Six of the 7 tests were fixed by pinning all observations to the same `measurement_date=date(2026, 6, 15)` (same-day) with distinct `observed_value` to avoid dedup, restoring the expected linear accumulation. The 7th test (Issue 2) required a structural change.

**Affected tests (6):**
- `tests/integration/test_physiology_update_service_confidence_transitions_integration.py::TestLowToMediumTransition::test_four_observations_reach_prior_weight_4_point_5` (got 4.3265, expected 4.5)
- `tests/integration/test_physiology_update_service_confidence_transitions_integration.py::TestMediumToHighTransition::test_eight_observations_reach_prior_weight_8_point_5` (got 7.7945, expected 8.5)
- `tests/integration/test_physiology_update_service_confidence_transitions_integration.py::TestMediumToHighTransition::test_eighth_observation_triggers_medium_to_high_transition` (got 'medium', expected 'high' — prior_weight 7.79 < 8.0 threshold)
- `tests/integration/test_physiology_update_service_confidence_transitions_integration.py::TestSubsequentCallsAccumulateAgainstPersistedState::test_three_calls_each_with_one_observation` (got 2.4647 at i=1, expected 2.5; 3.4068 at i=2, expected 3.5)
- `tests/integration/test_physiology_update_service_first_observation_integration.py::TestSecondCpObservation::test_second_observation_grows_prior_weight` (got 1.9765, expected 2.0)
- `tests/integration/test_physiology_update_service_first_observation_integration.py::TestSecondCpObservation::test_second_observation_fires_event_when_shift_exceeds_one` (got 1.9765 in event payload, expected 2.0)

**Fix applied:** Change `measurement_date=date(2026, 6, 15 + i)` to `measurement_date=date(2026, 6, 15)` in all 6 tests. Observations are distinguished by `observed_value` (e.g. `170.0, 170.1, 170.2, 170.3` for the 4-obs test; `250.0` vs `260.0` for the 2-obs test), so the dedup key `(parameter, source, measurement_date, observed_value)` does not catch them. The decay-between-observations behaviour remains pinned by `TestBayesianUpdatePriorDecay` in the unit tests — the integration layer's job is to verify accumulation and confidence transitions, not decay.

#### Issue 2 — Loop pattern cannot observe `from_level == "low"` on the Nth call when the (N-1)th call already crossed MEDIUM/HIGH (1 test)

`test_four_rr_observations_reach_high_confidence` used a 4-call loop asserting `from_level == "low"` on the 4th call. This is structurally impossible: the 3rd call already crosses MEDIUM (with 1-day gaps: `0.5 + 3*2.5*0.9765^2 ≈ 7.80`, MEDIUM) or HIGH (with same-day dates: `0.5 + 3*2.5 = 8.0`, HIGH), so the 4th call's pre-call level is never LOW. With any date pattern, the 4th call's pre-call level is MEDIUM (multi-day) or HIGH (same-day), and the test's `from_level == "low"` assertion is wrong.

**Affected test (1):**
- `tests/integration/test_physiology_update_service_confidence_transitions_integration.py::TestHighWeightSourceCrossesThresholdFaster::test_four_rr_observations_reach_high_confidence` (got 'medium', expected 'low' on `from_level`)

**Fix applied:** Restructured the test from a 4-call loop to a single `apply_observations` call with all 4 observations in one batch. The service reports a single `(pre_call_level, post_call_level)` transition reflecting the full batch, making the `("low", "high")` transition observable (pre-call state was LOW with `prior_weight=0.5`; post-call state is HIGH with `prior_weight=10.5`). The test name "four_rr_observations" describes the input group, which the batch call processes atomically. The loop pattern remains correct for tests that assert cross-call state persistence (e.g. `test_three_calls_each_with_one_observation`) or per-call confidence levels (e.g. `test_four_observations_trigger_low_to_medium_transition`).

#### Issue 3 — Post-rollback ORM attribute access triggers `MissingGreenlet` (1 test)

`test_event_atomicity_rolls_back_when_later_step_fails` passed the pass-1 fix (committing the fixture row in its own transaction before `apply_observations` + `rollback`) but the post-rollback assertion `fresh.lt2["hr"]["value"]` triggered a `MissingGreenlet`. The pass-1 fix's column-level SELECT (option 1 in the DevOps report) was recommended but not applied — the test was left with the ORM-attribute-access pattern that triggers the lazy load. After `rollback()`, accessing `fresh.lt2` on a freshly-loaded `AthletePhysiology` instance attempts async IO outside the greenlet context, raising `MissingGreenlet`. The `lt2` column is a standard non-deferred JSONB column, so the lazy load is triggered by SQLAlchemy's internal attribute-expiration mechanism after `rollback()`, not by any deferred-column configuration.

**Affected test (1):**
- `tests/integration/test_physiology_update_service_integration.py::TestPhysiologyUpdatedEvent::test_event_atomicity_rolls_back_when_later_step_fails` (MissingGreenlet on `fresh.lt2["hr"]["value"]`)

**Fix applied:** Replaced the post-rollback ORM attribute access with a column-level SELECT:

```python
# Before (post-rollback ORM access — MissingGreenlet):
fresh = (await db_session.execute(
    select(AthletePhysiology).where(AthletePhysiology.athlete_id == athlete.id)
)).scalars().all()[0]
assert fresh.lt2["hr"]["value"] == pytest.approx(160.0)

# After (column-level SELECT — bypasses ORM attribute layer):
fresh_lt2 = (await db_session.execute(
    select(AthletePhysiology.lt2).where(AthletePhysiology.athlete_id == athlete.id)
)).scalar_one()
assert fresh_lt2["hr"]["value"] == pytest.approx(160.0)
```

This is a different anti-pattern from the 2026-07-11 `expire_all()` + lazy load rule — `rollback()` puts the session in a distinct state where the connection lifecycle cannot service subsequent lazy loads, and column-level SELECT is the only safe pattern for reading JSONB values after a rollback. The two fixes have different root causes (`expire_all` evicts attribute state; `rollback` evicts transaction state) and different patterns (`expire_all` → use `.execution_options(populate_existing=True)`; `rollback` → use column-level SELECT).

### Reusable failure classes recorded

3 new dated lessons added to `tests/README.md` under "Dated Lessons (2026-07-14, Phase-2.3-P2 test pack re-run, pass 2)" and 3 new rows added to `tests/MOCKING_CONTRACT.md` "Known Anti-Patterns" table with cross-references to the README:

1. **Integration multi-day accumulation rule** — extends the 2026-07-13 and 2026-07-14 pass-1 date-default rules. Integration tests asserting linear accumulation of `prior_weight` across multiple `apply_observations` calls MUST pin all observations to the same `measurement_date` with distinct `observed_value` to avoid dedup. The decay-between-observations behaviour is already pinned by the unit tests.
2. **Loop `from_level` rule** — a new failure class specific to tests that assert `from_level` on the Nth call of a loop. When the (N-1)th call already crosses MEDIUM/HIGH, the Nth call's pre-call level is never LOW. Fix: use a single batch call or rewrite the assertion to match the actual pre-call level.
3. **Post-rollback column-level SELECT rule** — a new failure class that complements (but does not replace) the 2026-07-11 `expire_all()` + `populate_existing=True` rule. When a test needs to read JSONB values after a `rollback()`, column-level SELECT is the only safe pattern.

### No implementation bugs (routed to p-coder)

The implementation's decay behaviour is architecturally correct and is already pinned by `TestBayesianUpdatePriorDecay` in the unit tests. The 7 RC2 failures were all test-pack issues (multi-day dates, structurally-impossible loop assertion), not implementation bugs. The RC3 failure was a test-pack issue (ORM attribute access after rollback), not an implementation bug — the service correctly rolls back the batch; the test's post-rollback verification path was the defect.

### Collection check

`bash scripts/pytest.sh --collect-only` on the 3 modified test files collected 27 tests cleanly in 0.09s. No import errors, no fixture-not-found errors, no syntax errors. The full plan total of 193 tests is unchanged (no tests added or removed). The next DevOps run is expected to show 193 passed, 0 failed (modulo any pre-existing failures from other plans).

### Files saved (this pass)

- `tests/integration/test_physiology_update_service_integration.py` (modified — `test_event_atomicity_rolls_back_when_later_step_fails` now uses column-level SELECT for post-rollback JSONB read)
- `tests/integration/test_physiology_update_service_confidence_transitions_integration.py` (modified — 5 tests pinned to same-day `measurement_date=date(2026, 6, 15)`; `test_four_rr_observations_reach_high_confidence` restructured to single batch call)
- `tests/integration/test_physiology_update_service_first_observation_integration.py` (modified — 2 tests pinned to same-day `measurement_date=date(2026, 6, 15)` with distinct `observed_value`)
- `tests/README.md` (updated — 3 new dated lessons under "Dated Lessons (2026-07-14, Phase-2.3-P2 test pack re-run, pass 2)")
- `tests/MOCKING_CONTRACT.md` (updated — 3 new rows in "Known Anti-Patterns" table; new change-log entry for 2026-07-14 pass 2)
- `tests/test-manifest/phase-2-3p2.yaml` (updated — new history entry for 2026-07-14 pass 2; `last_reviewed_at` bumped to 2026-07-14T18:00:00Z)
- `docs/testing/phase-2-3-p2-physiology-update_test_pack.md` (this file — new "Triage — DevOps Report 2026-07-14 (test pack re-run, pass 2)" section; status line updated with pass-2 summary)

---

## Triage — DevOps Report 2026-07-14 (test pack re-run, pass 3)

**Reference:** `reports/phase-2-3-p2_devops_testpack_3.md` (Result: FAIL, 192/193 passed, 1 failed)

The DevOps report's 1 test failure is **1 test-pack issue (fixed by Test Architect)** and **0 implementation bugs**. The pass-2 fix resolved 7 of 8 RC2 failures (decay expectations / accumulation); the 1 remaining failure (RC3) is a refinement of the pass-2 post-rollback ORM access pattern — the column-level SELECT for the `fresh_lt2` JSONB read was applied, but the same hazard was present in the WHERE-clause references (`SystemEvent.athlete_id == athlete.id`, `PhysiologyMeasurement.athlete_id == athlete.id`, `AthletePhysiology.athlete_id == athlete.id`), all of which access `athlete.id` AFTER `db_session.rollback()`. No infrastructure changes were made; the `expire_on_rollback=False` conftest fix was attempted by DevOps and reverted because SQLAlchemy 2.x does not support that parameter. The fix is a per-test content change.

### Root cause (1 test-pack issue, 1 test touched)

#### Issue 1 — Post-rollback `athlete.id` access in WHERE clauses triggers `MissingGreenlet` (1 test)

`test_event_atomicity_rolls_back_when_later_step_fails` passed the pass-2 column-level SELECT fix for the `fresh_lt2` JSONB read but failed on the next assertion: `select(SystemEvent).where(SystemEvent.athlete_id == athlete.id)` at line 878 triggered `sqlalchemy.exc.MissingGreenlet: greenlet_spawn has not been called; can't call await_only() here.`

**Root cause:** `db_session.rollback()` expires ALL ORM instances tracked by the session, including the `athlete` object loaded at the start of the test (line 835). Accessing `athlete.id` (or any other mapped attribute — even a PK) on an expired instance triggers an async lazy load to re-fetch the row. Under async SQLAlchemy + NullPool, the lazy load fires outside the greenlet context, raising `MissingGreenlet`. The pass-2 fix addressed the freshly-loaded instance's JSONB attribute access (a different `AthletePhysiology` instance loaded by the post-rollback `SELECT`), but the same hazard exists for the in-memory `athlete` instance loaded BEFORE the rollback. The two instance types are independent — the pass-2 fix bypassed the ORM attribute layer for the fresh instance via column-level SELECT, but the in-memory `athlete` is used in 3 post-rollback WHERE clauses (`SystemEvent`, `PhysiologyMeasurement`, `AthletePhysiology.lt2` column-level SELECT) and cannot be replaced by column-level SELECT because its PK is the WHERE-clause value.

The DevOps report's RC3 root-cause analysis identifies this precisely:

> The test accesses `athlete.id` (an ORM-mapped attribute) after `db_session.rollback()` has expired all loaded instances. This triggers async lazy-load outside the greenlet context.

**Affected test (1):**
- `tests/integration/test_physiology_update_service_integration.py::TestPhysiologyUpdatedEvent::test_event_atomicity_rolls_back_when_later_step_fails` (MissingGreenlet on `athlete.id` access in `SystemEvent` WHERE clause at line 878)

**Fix applied:** Captured `athlete_id = athlete.id` as a plain Python UUID BEFORE the `rollback()` call, then replaced `athlete.id` with `athlete_id` in all 3 post-rollback WHERE clauses:

```python
await service.apply_observations(
    athlete_id=athlete.id, observations=[_observation()],
)
# Capture the athlete PK as a plain Python value BEFORE the rollback.
# `db_session.rollback()` expires ALL ORM instances tracked by the
# session — accessing `athlete.id` on the expired instance triggers
# an async lazy load outside the greenlet context.
athlete_id = athlete.id
await db_session.rollback()

# No event row.
events = (
    await db_session.execute(
        select(SystemEvent).where(
            SystemEvent.event_type == "physiology_updated",
            SystemEvent.athlete_id == athlete_id,  # ← captured scalar
        )
    )
).scalars().all()
assert len(events) == 0
# ... (measurements and fresh_lt2 also use athlete_id)
```

The captured `athlete_id` is a plain Python UUID, immune to the session-expiration hazard. The column-level SELECT for `fresh_lt2` (applied in pass 2) remains correct — its WHERE clause now uses the captured `athlete_id` scalar as well, so the post-rollback read of `AthletePhysiology.lt2` is fully safe.

### Reusable failure classes recorded

1 new dated lesson added to `tests/README.md` under "Dated Lessons (2026-07-14, Phase-2.3-P2 test pack re-run, pass 2)" — the same section as the pass-2 fix because the new lesson is a direct refinement of the pass-2 post-rollback ORM access pattern:

1. **Post-rollback PK access in WHERE clauses triggers `MissingGreenlet` — capture the PK before `rollback()`** — a strict superset of the 2026-07-11 `expire_all()` + lazy-load-on-captured-scalar rule. `rollback()` is a different state-setter than `expire_all()` (rollback evicts transaction state; expire_all evicts attribute state), but both leave the instance in a state where lazy loads are unservicable, and the capture-first pattern works for both. The `expire_on_rollback=False` parameter on `async_sessionmaker` is NOT supported in SQLAlchemy 2.x — the only viable fix is the per-test content change.

1 new row added to `tests/MOCKING_CONTRACT.md` "Known Anti-Patterns" table cross-referencing the new README lesson, and a new change-log entry for 2026-07-14 pass 3 documenting the SQLAlchemy 2.x `expire_on_rollback` non-support finding.

### Recurring Infrastructure Risk

**The "session-state-change → async lazy load hazard" failure class has now occurred 3 times across this plan** (2026-07-11 expire_all pattern, 2026-07-14 pass 2 post-rollback JSONB pattern, 2026-07-14 pass 3 post-rollback PK pattern), with at least 4 dated entries in `tests/README.md` covering the broad failure class:

- "Use `expire()` then access lazy attributes" (top-level anti-pattern section in `Common Pitfalls`)
- "Don't: Use `expire()` then access lazy attributes" (top-level anti-pattern)
- "`expire_all()` + async lazy load on captured scalar — capture scalars BEFORE `expire_all()`" (2026-07-11)
- "`expire_all()` + identity-map return — add `.execution_options(populate_existing=True)` to the post-cascade SELECT" (2026-07-11)
- "Post-rollback ORM attribute access triggers `MissingGreenlet` — use column-level SELECT for JSONB reads" (2026-07-14, pass 2)
- "Post-rollback PK access in WHERE clauses triggers `MissingGreenlet` — capture the PK before `rollback()`" (2026-07-14, pass 3)

The pattern is stable: a test calls `db_session.rollback()` or `db_session.expire_all()` and then accesses an ORM attribute on an in-memory instance. The first time the author of `test_event_atomicity_rolls_back_when_later_step_fails` encountered this hazard, the pass-2 fix (column-level SELECT for JSONB) addressed the freshly-loaded instance. The second time, the same author (or the next test author) hit the in-memory instance's PK access. A third integration test author writing a different rollback or expire_all test will almost certainly hit the same hazard.

**Should the fix move into a shared `conftest.py` fixture?** Two options, with tradeoffs:

1. **Add a `captured_pk(instance)` helper in `tests/utils/`** — a trivial one-liner that returns `instance.pk_attribute`. The advantage: forces test authors to think about the hazard by giving the pattern a name. The disadvantage: it's a wrapper around `pk = instance.pk` that adds a layer of indirection without actually preventing the bug. The bug is not "the author forgot the helper" — it's "the author didn't realise the in-memory instance is expired after rollback". A helper does not teach the lesson; a README entry does.

2. **Add a session-state-change fixture wrapper** — e.g. `@pytest.fixture def after_rollback(): ...` that yields a state in which the test is committed-not-rolled-back, or a `safe_rollback(session)` context manager that automatically captures all PKs from tracked instances before rolling back. The advantage: makes the safe pattern the easy pattern. The disadvantage: requires introspecting the session's tracked instances (an SQLAlchemy private API), and only helps tests that use the wrapper — a test that calls `db_session.rollback()` directly still hits the hazard.

**Recommendation:** Keep the per-test capture pattern. The fix is `pk = instance.pk` (one line, clearly named, immediately visible to a reviewer). The hazard is well-documented in the contract and the README. A future conftest fixture could codify the pattern if a 4th occurrence emerges, but at 3 occurrences with 2 already addressed by per-test fixes, the marginal value of a fixture is small. The README + MOCKING_CONTRACT entries are the structural protection — they make the failure class visible at test-writing time, before the bug can be reintroduced.

### No implementation bugs (routed to p-coder)

The implementation's behaviour in the RC3 scenario is correct: `apply_observations` correctly mutates the row, `db_session.rollback()` correctly unwinds the mutation, and no event/measurement/outbox/JSONB mutation persists. The test's post-rollback verification path was the defect — `athlete.id` access on an expired instance triggers an async lazy load that fires outside the greenlet context. The production code is not at fault.

### Collection check

`bash scripts/pytest.sh --collect-only tests/integration/test_physiology_update_service_integration.py` collected 14 tests cleanly in 0.08s. No import errors, no fixture-not-found errors, no syntax errors. The full plan total of 193 tests is unchanged (no tests added or removed). The next DevOps run is expected to show 193 passed, 0 failed (modulo any pre-existing failures from other plans).

### Files saved (this pass)

- `tests/integration/test_physiology_update_service_integration.py` (modified — `test_event_atomicity_rolls_back_when_later_step_fails` now captures `athlete_id = athlete.id` before `rollback()` and uses the captured scalar in all 3 post-rollback WHERE clauses)
- `tests/README.md` (updated — 1 new dated lesson "Post-rollback PK access in WHERE clauses triggers `MissingGreenlet` — capture the PK before `rollback()`" appended under "Dated Lessons (2026-07-14, Phase-2.3-P2 test pack re-run, pass 2)")
- `tests/MOCKING_CONTRACT.md` (updated — 1 new row in "Known Anti-Patterns" table; new change-log entry for 2026-07-14 pass 3 documenting the SQLAlchemy 2.x `expire_on_rollback` non-support finding)
- `tests/test-manifest/phase-2-3p2.yaml` (updated — new history entry for 2026-07-14 pass 3; `last_reviewed_at` bumped to 2026-07-14T20:00:00Z)
- `docs/testing/phase-2-3-p2-physiology-update_test_pack.md` (this file — new "Triage — DevOps Report 2026-07-14 (test pack re-run, pass 3)" section with root-cause analysis, recurring infrastructure risk evaluation, and recommendation against moving to a shared conftest fixture; status line updated with pass-3 summary)
