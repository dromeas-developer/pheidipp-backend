# Test Pack: Phase-2.2-P2 — RR Deviation Filter Remediation

## Status

**unit:** done (14 tests) · **integration:** done (4 tests — 1 strengthened, 3 added) · **api:** not-applicable · **behaviour:** not-applicable

## Summary

**14 unit tests** added to `tests/unit/test_signal_cleaning_service.py` for Phase-2.2-P2
(`docs/implementation/phase-2/phase-2-2-p2-rr-deviation-filter-remediation.md`).

This patch is a focused remediation of the **MAJOR** finding from
`reports/phase-2-2-p1-signal-cleaning_validation.md`: the RR artifact-removal
step in `SignalCleaningService._remove_artifacts` applied only the
200–2500 ms hard bounds and was missing the ±20% rolling-median deviation
filter required by the sub-phase Exit Gate and by
`02-computations/threshold-detection.md` Algorithm 2 step 1. The patch
also addresses the **MINOR** finding: the dead `self._session` field on
`SignalCleaningService.__init__` is removed (the constructor parameter
is retained; the injected repositories hold the session).

The Phase-2.2-P1 integration test pack included a single test
(`test_rr_above_20pct_rolling_median_is_nulled`) that loosely covered
the deviation filter at the integration layer. That test was
**strengthened** by this patch: the prior weak assertion
("some record in the spike window is null") was replaced with precise
per-index assertions on the persisted cleaned stream, and **3 new
integration tests** were added to the same class
(`TestCleanRrRollingMedianFilter`) to cover the persistence-boundary
contract for Phase-2.2-P2 testing requirements 3, 4, and 5 at the
integration layer:

* `test_rr_deviation_filter_pushed_rr_intervals_to_unavailable` —
  Phase-2.2-P2 Testing Requirement 5. The deviation filter's nulls
  are correctly counted in the `available_channels.rr_intervals`
  computation at the persistence boundary (the post-P2 null fraction
  crosses the strict 80% threshold).
* `test_rr_deviation_filter_skips_when_window_too_small` —
  Phase-2.2-P2 Testing Requirement 4. The `len(window_values) < 2`
  guard preserves the candidate at the persistence boundary
  (verified by re-reading the cleaned stream from object storage).
* `test_rr_deviation_filter_does_not_affect_hr_persistence` —
  Phase-2.2-P2 Testing Requirement 3. The RR-specific filter does
  not bleed into the HR channel at the persistence boundary
  (the HR spike inside the [30, 220] bpm hard bound is preserved
  even when co-located with an RR spike inside [200, 2500] ms).

The integration layer is the unique value here: it exercises the
transaction contract (the in-memory deviation filter logic → the
persisted cleaned stream in object storage → the
`available_channels` JSONB column on the `RawSensorStream` row).
The unit layer can prove the in-memory logic is correct; only the
integration layer can prove the persistence boundary is correct.

### Unit capability areas

| Capability | Test File | Tests |
|---|---|---|
| RR ±20% rolling-median deviation filter (behavioural) | `tests/unit/test_signal_cleaning_service.py` | 9 |
| RR deviation filter regression guards | `tests/unit/test_signal_cleaning_service.py` | 2 |
| `_session` dead field removed (MINOR fix) | `tests/unit/test_signal_cleaning_service.py` | 3 |

### Integration capability areas

| Capability | Test File | Tests |
|---|---|---|
| RR ±20% rolling-median deviation filter (persistence boundary) | `tests/integration/test_signal_cleaning_service_integration.py` | 4 |

## unit

### tests/unit/test_signal_cleaning_service.py — Phase-2.2-P2 additions (14 tests)

| Test | Scenario | Invariants Protected |
|---|---|---|
| `TestRrDeviationFilter::test_clean_uniform_rr_within_deviation_band_is_preserved` | Uniform 800 ms RR series for 600 s → no false-positive nulling; every record carries `rr_ms == 800.0` | Cleaned RR values that deviate more than ±20% from the rolling median are filtered out (no false positives on conformant data) |
| `TestRrDeviationFilter::test_clean_out_of_band_rr_inside_hard_bound_is_nulled` | 30 conformant 800 ms baselines followed by one 400 ms candidate → candidate nulled; baselines at indices 0, 29, 31 preserved | Cleaned RR values that deviate more than ±20% from the rolling median are filtered out (Exit Gate bullet) |
| `TestRrDeviationFilter::test_clean_rr_deviation_filter_does_not_apply_to_hr` | Uniform 150 bpm HR + 1 deviation-nulled RR → every HR sample is 150.0; the RR filter does not bleed into HR | Filter is RR-specific (HR hard bound 30–220 bpm applies; deviation does not) |
| `TestRrDeviationFilter::test_clean_rr_deviation_filter_does_not_apply_to_power` | Uniform 200 W power + 1 deviation-nulled RR → every power sample is 200.0; the RR filter does not bleed into power | Filter is RR-specific (power 3× rule applies separately) |
| `TestRrDeviationFilter::test_clean_rr_deviation_filter_does_not_apply_to_speed` | Uniform 3.0 m/s GPS + 1 deviation-nulled RR → `gap_sec_per_km` is finite for every record; speed channel unaffected | Filter is RR-specific (speed 25 m/s bound applies) |
| `TestRrDeviationFilter::test_clean_rr_deviation_filter_skips_when_window_too_small` | Sparse RR series (only indices 0, 1, 2 carry 800 ms; rest is None) → all 3 populated samples preserved (`< 2` non-null window guard) | Null-propagation: windows with < 2 non-null RR samples leave the candidate unchanged (matches power artifact's `if not window_values: continue` guard) |
| `TestRrDeviationFilter::test_clean_deviation_filter_window_excludes_candidate_sample` | 31 conformant baselines + one 400 ms candidate at index 31 → candidate nulled; threshold boundary at 0.20 × 800 = 160 ms honoured (the 400 ms outlier is nulled at 2.5× the threshold) | Window excludes the candidate (Coder Handoff Notes warning against "harmonising" with the power artifact's window that INCLUDES the candidate) |
| `TestRrDeviationFilter::test_clean_rr_deviation_filter_nulls_in_2to1_pattern` | 2:1 conformant (800 ms) : outlier (400 ms) pattern → outliers at t=10, 50, 100, 200, 400 (congruent to 2 mod 3) nulled; conformants preserved | Rolling 30-sample median locks to the conformant value; outliers in conformant-majority windows are nulled |
| `TestRrDeviationFilter::test_clean_available_channels_rr_intervals_reflects_post_deviation_state` | 480 hard-bound-null + 30 conformant baselines + 90 outliers → pre-P2 null fraction = 80% (rr_intervals = true at the strict->80% boundary); post-P2 deviation nulls enough to push past 80% → `rr_intervals = false` | available_channels reflects what survived artifact removal — the post-deviation null fraction is the determinant |
| `TestRrDeviationFilterRegression::test_hr_five_minute_gate_unaffected_when_rr_data_is_all_artifacted` | Uniform 150 bpm HR + RR entirely hard-bound-nulled (50 ms < 200 ms) → `created=True`, `available_channels.hr = true`, `available_channels.rr_intervals = false`; HR gate (≥ 300 non-null HR seconds) is unaffected by the RR change | If the pipeline produces a stream shorter than 5 minutes of non-null HR data, `RawSensorStream` is not created — and the 5-min HR gate is read from `artifact_free.hr` which the RR change does not touch |
| `TestRrDeviationFilterRegression::test_signal_clean_idempotency_short_circuits_before_deviation_filter` | `exists_for_activity=True` → `created=False, reason="already_cleaned"`; `_fit_parser.parse` is NOT called (proving the new deviation filter is never reached on retry) | Idempotency guard: the deviation filter is downstream of the `exists_for_activity` short-circuit and is therefore not reached on retry |
| `TestSessionDeadFieldRemoved::test_signal_cleaning_service_source_does_not_reference_self_session` | Source file contains no `self._session` *code* reference (docstring mentions allowed, as the docstring anchors historical context) | MINOR finding: `self._session` is dead weight; the injected repositories hold the session |
| `TestSessionDeadFieldRemoved::test_signal_cleaning_service_init_signature_retains_session_parameter` | `inspect.signature` shows `session` is a KEYWORD_ONLY parameter on `__init__` | MINOR regression guard: the worker constructs the service with `session=session`; the keyword-only signature is unchanged |
| `TestSessionDeadFieldRemoved::test_signal_cleaning_service_constructor_accepts_session_keyword_argument` | `service = SignalCleaningService(session=AsyncMock(), ...)` does not raise; `not hasattr(service, "_session")` is True; the other 4 dependencies are still stored under their declared names | MINOR regression guard: the worker wiring compiles and the service does not store a redundant session reference |

## Layer Contract Conformance

Per `tests/MOCKING_CONTRACT.md` Layer Boundaries:

### Unit layer

| Concern | Conformance |
|---|---|
| **Mocked** | Repository interfaces (`_activities`, `_raw_streams`), `ObjectStorageClient`, `FitParserService`, `AsyncSession` — all `AsyncMock` / `MagicMock` ✓ |
| **Real** | `SignalCleaningService` business logic, frozen module constants (`RR_DEVIATION_THRESHOLD`, `RR_ROLLING_WINDOW_S`, `RR_MIN_MS`, `RR_MAX_MS`), the `_median` helper, the `_ResampledChannel` / `CleanedStream` / `CleaningResult` dataclasses, `ParsedFitData` and `GpsRecord` — all imported as live types from `app.services.signal_cleaning_service` and `app.services.fit_parser_service` ✓ |
| **AsyncSession** | Never used directly — only the parameter is passed to the constructor; the service no longer stores it (per the MINOR fix) ✓ |
| **Anti-patterns avoided** | (1) No `session.execute()` mocking (the P1 root cause of `MissingGreenlet`); (2) no schema inspection via `sync_session.connection()`; (3) no boolean checks on SQLAlchemy column expressions; (4) no JWT access-token uniqueness assertions; (5) no `patch("openai.AsyncOpenAI")` (n/a — no LLM); (6) no `MagicMock(spec=Activity)` with unset `planned_session_id` (the mocks here use real `Activity` attributes: `id`, `athlete_id`, `sport_type`, `source`, `calibration_eligible`, `fit_file_key`, `cleaning_pipeline_version`) ✓ |
| **Canonical fixtures reused** | `_mock_activity`, `_parsed_fit_data_hr_only`, `_parsed_fit_data_full`, `_SUFFICIENT_DURATION`, `_run_clean_and_return_result` — all from the P1 test file, no new fixtures introduced ✓ |
| **File scope (per Step 3)** | `app/services/signal_cleaning_service.py` only — single-file remediation matches the plan's single-file Scope ✓ |

### Integration layer

| Concern | Conformance |
|---|---|
| **Mocked** | `FitParserService` only — stubbed at the constructor boundary to return engineered `ParsedFitData`. The integration layer's unique value (the persistence-boundary contract) requires the service, the repositories, and the object storage to all be real, so the parser is the only dependency substituted. ✓ |
| **Real** | Database (real test DB via `db_session: AsyncSession` fixture), `RawSensorStreamRepository`, `ActivityRepository`, `ObjectStorageClient` (real local-fallback at `./var/object-storage`), `SignalCleaningService` business logic, all the engineering around the transaction contract ✓ |
| **AsyncSession** | `db_session` fixture with auto-rollback + post-test truncation per `tests/README.md` ✓ |
| **Anti-patterns avoided** | (1) No `session.execute()` mocking; (2) no schema inspection via `sync_session.connection()` (the `tests/utils/schema_helpers.py` sync engine path is unused here); (3) no `scalar_one_or_none` mocking (real `raw_repo.get_by_activity_id()` returns a real row); (4) no boolean checks on SQLAlchemy column expressions; (5) no JWT uniqueness; (6) no `patch("openai.AsyncOpenAI")` (n/a); (7) no `MagicMock(spec=Activity)` (real `Activity` rows are created via the factory `await _create_running_activity(db_session, ...)`); (8) no `Activity` factory without `sport_type` (the P1 anti-pattern from the README — the factory here explicitly sets `sport_type=SportType.RUNNING`) ✓ |
| **Canonical fixtures reused** | `db_session`, `make_athlete`, `_create_running_activity`, `_build_real_object_storage`, `_upload_raw_fit`, `_build_service`, `_SUFFICIENT_DURATION` — all from the P1 integration test file, no new fixtures introduced ✓ |
| **Persistence-boundary assertions** | Each new integration test re-reads the persisted `RawSensorStream` row from the DB AND the cleaned stream from object storage to assert the in-memory logic → persisted state contract holds ✓ |
| **File scope (per Step 3)** | `app/services/signal_cleaning_service.py` only (same as the unit layer — the integration tests exercise the service's interface, the unit tests exercise its internals) ✓ |

## integration

### tests/integration/test_signal_cleaning_service_integration.py — Phase-2.2-P2 additions (4 tests: 1 strengthened, 3 added)

| Test | Scenario | Invariants Protected |
|---|---|---|
| `TestCleanRrRollingMedianFilter::test_rr_above_20pct_rolling_median_is_nulled` (strengthened) | Engineered RR series: 299 conformant 1000 ms baselines, one 1300 ms spike at index 299 (+30% deviation), then 300 conformant 1000 ms baselines. **Strengthened**: prior weak assertion "some record in the spike window is null" replaced with per-index assertions on the persisted cleaned stream — the spike at index 299 is nulled, the conformant samples at indices 298, 300, 0, and 599 are preserved, `available_channels.rr_intervals` stays `True` (1/600 null fraction is well below the 80% threshold). | Cleaned RR values that deviate more than ±20% from the rolling median are filtered out (Exit Gate bullet) — verified at the **persistence boundary** (re-read from object storage), not just in-memory |
| `TestCleanRrRollingMedianFilter::test_rr_deviation_filter_pushed_rr_intervals_to_unavailable` (new) | 480 hard-bound-null (100 ms < 200 ms) + 30 conformant baselines (800 ms) + 90 outliers (400 ms vs ~800 ms median). The hard-bound pass leaves 480/600 = 80% null. The deviation pass then nulls the 29 outliers in conformant-majority windows (indices 510–538), pushing the cumulative null fraction to 509/600 = 84.8%. The available_channels rule `non_null_fraction > 80%` fails, so `rr_intervals=False`. Direct proof at the persistence boundary: re-read the cleaned stream from object storage, confirm `null_count > 480` and `null_count / 600 > 0.80`. | `available_channels.rr_intervals` is computed AFTER the deviation filter — the deviation filter's nulls propagate to the persisted `available_channels` JSONB column. (Phase-2.2-P2 Testing Requirement 5.) |
| `TestCleanRrRollingMedianFilter::test_rr_deviation_filter_skips_when_window_too_small` (new) | 30 leading nulls + 5 conformant 800 ms cluster (indices 30–34) + 565 trailing nulls, with 600 samples of 150 bpm HR (passes the 5-min HR gate). The 5 conformant samples are preserved at the persistence boundary — the deviation filter's `len(window_values) < 2` guard fires for the leading samples and the equal-to-median cluster samples pass the deviation check. `rr_intervals=False` because the high null fraction (5/600 non-null ≈ 0.83%) is far below the 80% non-null threshold; this is correct — the channel IS effectively unavailable. | The deviation filter respects null-propagation: a window with fewer than 2 non-null RR samples leaves the candidate unchanged. (Phase-2.2-P2 Testing Requirement 4.) |
| `TestCleanRrRollingMedianFilter::test_rr_deviation_filter_does_not_affect_hr_persistence` (new) | Co-located HR spike (100 bpm, inside the [30, 220] bpm hard bound but 33% below the 150 bpm median) and RR spike (400 ms, inside [200, 2500] ms hard bound but -50% from 800 ms median) at index 31. The RR spike is nulled at the persistence boundary, the HR spike is preserved (the HR EMA smoothing step modifies the value but never nulls it; the RR-specific filter does not apply to HR), and the HR EMA smoothing is unaffected. | The RR deviation filter does NOT fire on HR, power, speed, or elevation — only RR. (Phase-2.2-P2 Testing Requirement 3.) |

## Cross-Phase Coverage Note

The sub-phase Exit Gate invariant
"Cleaned RR values that deviate more than ±20% from the rolling median
are filtered out" is now covered at three layers:

| Layer | Test | Scope |
|---|---|---|
| **Unit (this pack)** | `tests/unit/test_signal_cleaning_service.py::TestRrDeviationFilter` (9 tests), `TestRrDeviationFilterRegression` (2 tests) | Per-sample RR value assertions; filter-isolation guards; null-propagation; window exclusion; `available_channels` post-deviation; HR-gate and idempotency regression guards |
| **Integration (this pack)** | `tests/integration/test_signal_cleaning_service_integration.py::TestCleanRrRollingMedianFilter` (4 tests: 1 strengthened, 3 added) | End-to-end against real DB and real local-fallback `ObjectStorageClient`; persistence-boundary contract; `available_channels.rr_intervals` post-deviation state; filter-isolation at the persistence boundary; window-too-small guard at the persistence boundary |
| **Behaviour (P1 pack)** | `tests/behaviour/test_signal_cleaning_user_journey.py` (Journeys E, F) | Public HTTP surface; user-visible outcome via `GET /athletes/{id}/activities/{aid}` |

The integration layer is the unique value here: it exercises the
transaction contract (in-memory deviation-filter logic → persisted
cleaned stream in object storage → `available_channels` JSONB column
on the `RawSensorStream` row). The unit layer can prove the
in-memory logic is correct; only the integration layer can prove the
persistence boundary is correct. The P1 integration test for the
same capability (the original `test_rr_above_20pct_rolling_median_is_nulled`)
was strengthened by this patch because its original assertion
("some record in the spike window is null") was weak enough to pass
even if a totally different code path (smoothing) nulled the record
— the strengthened version asserts the specific record at the spike
position is null and the records immediately before/after are
preserved, proving the filter (not smoothing) did the work.

The promotion to `regression` and `release` execution groups will be
done by the Test Architect after a successful DevOps PASS for this
plan; the manifest's `validation.executable` and `validation.passed`
fields remain DevOps-owned per the Manifest Ownership Rules.

## DevOps Execution

Execution scope for Phase-2.2-P2 tests:

```bash
# Unit (14 new tests added by this pack; the file now has 31 tests
# total in tests/unit/test_signal_cleaning_service.py, of which 17
# were generated by Phase-2.2-P1).
bash scripts/pytest.sh tests/unit/test_signal_cleaning_service.py

# Integration (1 strengthened, 3 new tests in the
# TestCleanRrRollingMedianFilter class; the file's total integration
# test count for signal cleaning is now 11).
bash scripts/pytest.sh tests/integration/test_signal_cleaning_service_integration.py
```

Prerequisites: no migrations, no seed data, no external services for
the unit tests (pure-logic / mock-based). The integration tests
require a working test DB (the `db_session` fixture auto-rolls back
and truncates per `tests/README.md`); the local-fallback
`ObjectStorageClient` writes to `./var/object-storage` and does not
require S3 credentials (conftest clears S3 env vars at import time).

## Post-Generation Fix — 2026-07-09

**Issue**: DevOps reported 14 unit test failures in
`tests/unit/test_signal_cleaning_service.py`. All 14 failures were
caused by a single fixture helper `_parsed_fit_data_full` (line 111)
that constructed `GpsRecord(speed=..., altitude=...)` without the
required `timestamp: datetime` first field. The `GpsRecord` dataclass
(in `app/services/fit_parser_service.py`) requires `timestamp` as its
first field; the integration test file at
`tests/integration/test_signal_cleaning_service_integration.py` line
192 already showed the correct pattern (passing `timestamp=...`).
Collection did not catch this because pytest collection imports
modules and discovers test functions but does not execute test bodies
or fixture construction.

**Fix**: Added `timestamp` to the `GpsRecord` constructor in the
`_parsed_fit_data_full` helper. Each GPS record now receives
`timestamp=start_time + timedelta(seconds=i)` where `start_time` is
the FIT start time. Also added `timedelta` to the `datetime` import.

**Classification**: One-off fixture bug. Not a reusable failure class —
no README or MOCKING_CONTRACT update warranted. The schema widening
fixes DevOps applied (`String(16)` → `String(32)` on
`cleaning_pipeline_version` columns) are also one-offs and did not
require documentation updates.

**Self-check**: `bash scripts/pytest.sh --collect-only
tests/unit/test_signal_cleaning_service.py` now collects 31 items
without errors. `tests/integration/test_signal_cleaning_service_integration.py`
collects 14 items without errors. Awaiting DevOps re-execution to
confirm all 31 unit tests pass.
