# Validation Report — Phase-2.2-P1
Date: 2026-07-08
Plan: docs/implementation/phase-2/phase-2-2-p1-signal-cleaning.md

## Result: FAIL WITH DEVIATIONS

A single MAJOR finding blocks Exit-Gate conformance: the cleaned RR series
is not subjected to the ±20% rolling-median deviation check that the
Plan's Testing Requirements AND the sub-phase Exit Gate explicitly
require. Everything else conformance-relevant passes.

Note on validation scope: the Plan labels Steps 9 (DevOps migration
review/application) and 10 (Test Architect manifest) as OWNER ≠ Coder,
and the Coder Handoff Notes mark both as Skip for the coder. The
migration file IS staged (the coder produced it per Step 2) but is NOT
applied to the test DB (`implemented-state.md` records `Current DB
Revision: 2340974caeca` — i.e. the Phase-2.1 head, NOT this plan's
`297ea8ac7f69`). That is the expected pre-DevOps state, not a finding
against the coder. The Test-Architect manifest
(`tests/test-manifest/phase-2-2.yaml`, `index.yaml` update) is absent —
also expected per the plan's Coder Scope/Skip split.

---

## Layer 1: Plan Conformance

| Step | Description | Severity | Finding |
|------|-------------|----------|---------|
| 1 | RawSensorStream ORM model | ✅ | `app/models/raw_sensor_stream.py` has `id` (UUID PK), `activity_id` (UUID FK → activities.id, ON DELETE CASCADE), `fit_file_key`, `sampling_rate_hz` (server_default 1.0), `available_channels` (JSONB), `cleaning_pipeline_version` (non-null String(16)), `created_at` (server_default now). UNIQUE `uq_raw_sensor_streams_activity` on activity_id + index `ix_raw_sensor_streams_activity`. No `updated_at`/`cleaned_at` mutation column. Registered in `app/models/__init__.py`. |
| 2 | Alembic revision | ✅ | `alembic/versions/297ea8ac7f69_phase_2_2_p1_batch_1_raw_sensor_streams.py` has `down_revision = '2340974caeca'` (the current head at plan start, confirmed by `implemented-state.md`). upgrade() creates the table with UNIQUE constraint + FK index; downgrade() drops both in correct order. `db-upgrade.sh` was not run. |
| 3 | RawSensorStreamRepository | ✅ | `app/repositories/raw_sensor_stream_repository.py` exposes exactly `insert` (flush+refresh), `get_by_activity_id`, `exists_for_activity`. No UPDATE/DELETE. AsyncSession injected at construction. Registered in `app/repositories/__init__.py`. |
| 4 | ObjectStorageClient extension | ✅ | `build_cleaned_stream_key(athlete_id, activity_id)` returns literal `cleaned-streams/{athlete_id}/{activity_id}/stream.gz`, deterministic from activity_id (not a fresh UUID). `upload_cleaned_stream(*, athlete_id, activity_id, payload_bytes, content_type="application/gzip")` → `StoredCleanedStream` (frozen dataclass mirroring `StoredFitObject`). `download_cleaned_stream(key)` reuses `download_fit`. `upload_cleaned_stream` reuses the existing `_upload_local` fallback which raises `ObjectStorageConflictError` on existing key — that is the retry idempotency gate. No new error class introduced; key derivation lives on the client (single source of truth). |
| 5 | SignalCleaningService | MAJOR | Pipeline step order (`_resample_to_1hz → _remove_artifacts → _smooth → _compute_derived_metrics → _compute_rolling_features`) is fixed by call sequence with no dispatcher (✅). Guards ordered: missing → NotFound; manual_entry → no-op; already-cleaned → idempotent success; not-eligible/not-running → raise (✅). 5-minute/300s non-null HR gate returns `CleaningResult(created=False, reason="short_stream")` without writing (✅). available_channels uses >80% null rule (✅). Atomic persist: upload → insert RawSensorStream → `update_cleaning_version` in same transaction (✅). `ObjectStorageConflictError` is caught and treated as success (✅). `PIPELINE_VERSION = "v1-signal-cleaning"` is a frozen module constant (✅). GAP coefficients hardcoded as `GAP_COEFFICIENT_A=0.033`, `GAP_COEFFICIENT_B=0.00012` with docstring anchor (✅). **BUT** the RR artifact-removal step applies ONLY the 200–2500 ms hard bounds; the ±20% rolling-median deviation check required by the Plan's Testing Requirements and by the sub-phase Exit Gate ("Cleaned streams pass artifact validation thresholds (RR values within ±20% of rolling median retained)") is absent. See Layer 2 for the contract finding. |
| 6 | `ActivityRepository.update_cleaning_version` | ✅ | `app/repositories/activity_repository.py` adds `update_cleaning_version(*, activity_id, version)` mirroring `update_load_scores` / `update_calibration_eligibility`: look-up → set field → flush → refresh → return. Docstring documents the only permitted transition as `null → non-null`. |
| 7 | `signal_clean` procrastinate task | ✅ | `app/worker/app.py` defines `@app.task() async def signal_clean(*, activity_id: str) -> dict[str, Any]` registered on the shared `app` instance. Body opens its own `AsyncSessionLocal`, constructs `SignalCleaningService(session=..., object_storage=ObjectStorageClient(), raw_stream_repository=..., activity_repository=..., fit_parser=FitParserService())`, calls `await service.clean(uuid.UUID(activity_id))`, then `await session.commit()` exactly once. Imports of the service/repo/live ObjectStorageClient are inside the body (importable without a DB). Returns `{"activity_id": str, "raw_sensor_stream_id": str | None, "created": bool}`. No retry/timeout decorator added. |
| 8 | Enqueue hook in `_run_ingestion_pipeline` | ✅ | After the `activity_calibration_eligible` publish AND after `self.twin_recalibration.recalibrate(...)` returns (the await is resolved before the defer), the gate `eligible and activity.sport_type == SportType.RUNNING and activity.source != ActivitySource.MANUAL_ENTRY` defers the task via `await self._defer_signal_clean(activity_id=activity.id)`. The dispatch is NOT awaited for its result — the helper calls `await dispatcher(activity_id=str(activity_id))` where `dispatcher` resolves to `procrastinate_app.tasks["signal_clean"].defer_async` (or the injected test fake). A defer failure is swallowed and logged under `activity.signal_clean.enqueue.failure` so the ingestion commit still proceeds. Constructor accepts `task_dispatcher: Optional[Any] = None` mirroring the existing optional-injection pattern. Ordering constraint from `async-pipeline.md` ("twin recalibration BEFORE signal_clean defer") is preserved exactly. |

---

## Layer 2: Contract Conformance

| Contract | Check | Severity | Finding |
|----------|-------|----------|---------|
| Invariant: One RawSensorStream per Activity, created atomically with the cleaned-stream upload | ✅ | UNIQUE constraint on activity_id; `clean()` performs `upload_cleaned_stream` → `raw_streams.insert(...)` → `update_cleaning_version(...)` within the caller's single-commit transaction. Worker commits once. |
| Invariant: cleaning failure leaves no RawSensorStream; Activity keeps null cleaning_pipeline_version; segmentation skipped | ✅ | The short-stream gate returns `created=False` BEFORE any DB write; any exception in the worker leaves the session uncommitted. Atomicity preserved. |
| Invariant: `fit_file_key` on RawSensorStream is the cleaned-stream key (different from the raw FIT key on Activity) | ✅ | `RawSensorStream.fit_file_key` is set to `build_cleaned_stream_key(activity.athlete_id, activity.id)` → `cleaned-streams/{...}/stream.gz`. Activity's `fit_file_key` is the raw `fit-files/{...}/{uuid}.fit` set by ingestion. Two distinct keys under the same field name. |
| Invariant: available_channels reflects what survived artifact removal | ✅ | `_available_channels(artifact_free)` reads null fractions AFTER `_remove_artifacts`. Per-channel >80% null → False. `cadence=False` per the documented deferral. |
| Invariant: fixed step order 1→7, no skipping/reordering | ✅ | Five private methods called in order by `clean()`. Steps 5–7 are out-of-scope (deferred) and NOT replaced by no-ops — they are simply absent. The plan's "no-ops-by-omission" wording is satisfied. |
| Invariant: null propagation through smoothing; >80% null after artifact removal → channel unavailable | ✅ | `_smooth` carries forward null-either-stays-null (HR EMA) or restores null post-filter (power/GAP Savitzky-Golay); `_available_channels` enforces the 80% gate. |
| Invariant: resample to uniform 1 Hz before step 1, no HR forward-fill | ✅ | `_resample_to_1hz` materialises a 0…duration-1 index, all channels start as None, and only source-aligned samples fill in — no forward-fill for HR. |
| Invariant: stream < 5 min non-null HR → no RawSensorStream, segmentation skipped | ✅ | `non_null_hr_count < MIN_NON_NULL_HR_SECONDS` (300) returns `CleaningResult(created=False, reason="short_stream")` before any write. |
| Invariant: cleaned data in object storage is immutable/append-only | ✅ | `upload_cleaned_stream` reuses `_upload_local` which raises `ObjectStorageConflictError` on existing key; the service treats that conflict as idempotent success without re-uploading. |
| Invariant: manual_entry activities never get a RawSensorStream | ✅ | The service returns `created=False, reason="manual_entry"` AND the Step 8 enqueue gate excludes `source == MANUAL_ENTRY` (defence-in-depth). |
| Invariant: signal cleaning failure does not block Activity creation | ✅ | The task runs in its own procrastinate transaction; the ingestion transaction has already committed. ADR-009 compliance verified. |
| Invariant: HR dropout >20% flags `quality_flags.hr_dropout_pct` but does not block cleaning | ✅ | The cleaning service makes the post-artifact null fraction the determinant of `available_channels.hr`; the `hr_dropout_pct` flag is not read or used to gate anything. |
| Invariant: sport_type != 'running' → no calibration-eligibility/cleaning | ✅ | Both Step 8 enqueue gate AND Step 5 service guard exclude non-`RUNNING`. |
| Exit Gate / Testing Req: RR values within ±20% of rolling median retained | MAJOR | `_remove_artifacts` (signal_cleaning_service.py:586-619) applies exclusively the 200–2500 ms hard bounds to the RR channel. There is NO follow-on rolling-median deviation check. The Plan's Testing Requirements state explicitly: "the cleaning service's artifact-removal step 1 applies the 200/2500 ms bounds, and a follow-on deviation check enforces the ±20% rolling-median criterion for RR specifically." The sub-phase Exit Gate repeats the same criterion verbatim ("Cleaned streams pass artifact validation thresholds (RR values within ±20% of rolling median retained)"). A grep for `0.2`, `rolling.median`, `deviation` across the service returned only docstring mentions and unrelated code; the RR-specific deviation filter is absent. Result: an RR value of, e.g., 400 ms sitting inside [200,2500] but deviating >20% from its local rolling median will be retained by the cleaner, contradicting the Exit Gate. |

---

## Layer 3: Deviations

| Item | What Was Added | Classification | Action |
|------|---------------|----------------|--------|
| `variability_index` computed from `gap_sec_per_km` rather than pace | The Plan's step-4 spec says "coefficient of variation of pace/power over 30 s". The implementation computes CV of `gap_sec_per_km` (the GAP-adjusted pace). Since GAP-pace is the pace signal actually carried and consumed downstream, this is a reasonable interpretation within the coder's authority. | Acceptable | None — within coder authority. |
| Savitzky-Golay "pace" smoothing applied to `gap_sec_per_km` not raw pace | The Plan step-3 spec says "Power and pace: Savitzky-Golay (window=7, polynomial=3)." The implementation smooths `gap_sec_per_km` (the only pace-derivative present at step 3) rather than a raw `pace_sec_per_km` channel that never exists. Raw pace `1000/speed` is computed in-line and immediately turned into GAP; smoothing GAP achieves the spec's intent. | Acceptable | None — within coder authority. |
| `available_channels.pace` derived from `speed_m_s` null fraction | The Plan defines pace from GPS speed; the implementation computes `available_channels.pace` from the null fraction of the resampled `speed_m_s` channel. Because raw pace is `1000/speed`, pace availability IS speed availability, so the mapping is correct up to the conversion edge cases that already produce null (speed=0, speed=null). Documented in `_compute_derived_metrics`. | Acceptable | None — within coder authority. |
| `_defer_signal_clean` helper extracted between `_run_ingestion_pipeline` and `app.worker.app` | The Plan Step 8 describes the defer call inline. The implementation extracts it into a small `_defer_signal_clean(*, activity_id)` private method that handles dispatcher resolution + error swallowing. The visibility of the helper does not change ordering, ownership, or error semantics. | Acceptable | None — within coder authority. |

No new entities, no new events, no compensating EventLog/`SystemEvent` rows, no new router registrations, no API surface additions, no new error class on the storage client (the existing hierarchy is reused), no second repository, no schema export beyond what the plan enumerates. The dependency addition `scipy>=1.10.0` to `requirements.txt` is explicitly foreseen by the Plan's Implementation Clarifications and is the only file-level deviation. It is a multi-megabyte native wheel — flagged for the DevOps review step per the plan.

---

## Stack-Truth

### CRITICAL
None.

### MAJOR
- RR ±20% rolling-median deviation filter missing — `app/services/signal_cleaning_service.py` (`_remove_artifacts`, ~lines 586–619) — Exit-Gate contract required a follow-on rolling-median deviation check for RR; only the 200–2500 ms hard bounds are enforced. RR samples deviating more than ±20% of their rolling median are retained, contradicting the saved-RR series contract.

### MINOR
- `_session` field stored on `SignalCleaningService` but never referenced directly — `app/services/signal_cleaning_service.py:313` — the AsyncSession is used implicitly through the injected repositories; the cached `self._session = session` reference is dead weight. Not a violation; the plan says the service "holds an AsyncSession" and this satisfies the wording. No action required.

Runtime Rules (AsyncSession, atomic transactions, events-after-commit, no api↔repo shortcut, no business logic in api):
- All DB access in `signal_clean`, `SignalCleaningService`, `RawSensorStreamRepository`, `ActivityRepository.update_cleaning_version` uses `AsyncSession` / `AsyncSessionLocal` ✅
- Atomic transaction shared by upload + insert + activity version update in `signal_clean` ✅
- No events produced (plan specifies none); n/a for the after-commit rule ✅
- No API layer touched; the enqueue happens in the service layer ✅

Framework Rules:
- No `parse_obj()`/`.dict()` usage in any added file ✅
- No PATCH handler added; n/a for `exclude_unset` ✅
- No cross-model relationship imports added ✅
- No SQLAlchemy Enum column added ✅
- New model `RawSensorStream` exported in `app/models/__init__.py` ✅
- No new schema added to `app/schemas/__init__.py`; n/a ✅
- No new route file under `app/api/v1/`; n/a ✅

Architecture Rules:
- No layer skipping or reversal (api → repository directly): none observed; the worker constructs the service which constructs the repositories ✅
- No business logic outside the service layer: cleaning logic is in `SignalCleaningService`, enqueue gate is in `ActivityIngestionService` ✅
- No wrong ownership boundary: signal cleaning owns steps 1–4; ingestion service owns the gate; repositories own persistence ✅
- No LLM involvement in this plan; LLM-routing rule n/a ✅

---

## Validation Confidence

**Level: HIGH**

| Dimension | Status |
|-----------|--------|
| Contracts embedded in plan | yes — all invariants copied verbatim; RR ±20% criterion present in both Testing Requirements and Exit Gate |
| Implementation files retrieved | 13 of 13 listed in scope (8 coder-owned scope files + 5 dependency/context files needed for cross-checks) |
| Release alignment checked | yes — plan ID Phase-2.2-P1 sits under sub-phase phase-2-2-signal-cleaning within Phase 2; no future-phase (2.3 segmentation / threshold detection, 2.5 objective updates, 2.6 power profile) code is present |
| Deviation scan complete | yes — grep across the whole repo for `signal_clean`/`RawSensorStream`/`cleaning_pipeline_version`; no entity registrations, API routes, or event types beyond the plan's scope were introduced |
| Dynamic context available | yes — `docs/implementation/implemented-state.md` loaded and treated as the primary source for current DB revision (`2340974caeca`), already-implemented entities/services, and migration chain |

Confidence is HIGH because all invariants are embedded in the plan, all scope files were retrieved, the implemented-state snapshot corroborates the migration chain, and the deviation scan returned no out-of-plan architectural surface. The MAJOR finding rests on an unambiguous contract clause ("a follow-on deviation check enforces the ±20% rolling-median criterion for RR specifically") that the plan states verbatim.

---

## Routing

| Finding | Route To |
|---------|----------|
| MAJOR: RR ±20% rolling-median deviation filter absent (Testing Requirement + Exit Gate) | p-architect + this report — coder fix is mechanical (a per-window rolling-median check on the RR channel in `_remove_artifacts`), but the contract wording in the Plan AND the sub-phase Exit Gate both carried the requirement, so the architect should confirm the scope and adjust the Plan/Exit-Gate text in lockstep with the fix |
| DevOps migration not applied (Step 9) | p-devops + this report — `297ea8ac7f69` is staged but `Current DB Revision` is still `2340974caeca`; review and apply per the release process |
| Test Architect manifest not produced (Step 10) | p-test-architect + this report — `tests/test-manifest/phase-2-2.yaml` and `index.yaml` update still pending |
| `scipy>=1.10.0` dependency added to `requirements.txt` | p-devops + this report — multi-megabyte native-wheel dependency the Plan flagged for DevOps review; no coder action needed beyond the addition already made |
