> **Baseline — test companion for** `batch-1-signal-cleaning.md`, migrated from `docs/implementation/phase-2/phase-2-2-p1-signal-cleaning.md` and `phase-2-2-p2-rr-deviation-filter-remediation.md` **on** 2026-07-19.

## Test Scenarios

Derived from the test manifest (`tests/test-manifest/phase-2-2.yaml`) and actual test files.

### Unit — SignalCleaningService
**File:** `tests/unit/test_signal_cleaning_service.py`

**Pipeline ordering:**
- Given `clean(activity_id)`, steps execute in fixed order: resample → artifact removal → smoothing → derived metrics → rolling features
- No step can be skipped or reordered

**Resampling:**
- Given a FIT file with variable recording rate, pipeline resamples to uniform 1 Hz
- Given null gaps in input, nulls propagate (no forward-fill)

**Artifact removal — hard bounds:**
- Given HR values outside 30–220 bpm, those samples are nulled
- Given speed values > 25 m/s, those samples are nulled
- Given RR values outside 200–2500 ms, those samples are nulled

**Artifact removal — power:**
- Given power values > 3× rolling-30s median, those samples are nulled

**Artifact removal — RR ±20% deviation filter:**
- Given a synthetic uniform RR series (all 800 ms), every RR sample retained (no false positives — all within ±20% of rolling median)
- Given a candidate RR sample at 400 ms within hard bounds but deviating > ±20% from trailing rolling median (|400-800|=400 > 0.2×800=160), that sample is nulled
- Given an HR sample within 30–220 bpm but deviating > ±20% from its rolling median, the HR sample is RETAINED (deviation filter is RR-specific)
- The ±20% deviation filter does NOT fire on power, speed, or elevation — only RR
- Given a window with fewer than 2 non-null RR samples (first 2 samples, or everything nulled by hard bound), the candidate is left unchanged
- Given a null RR sample, it stays null — deviation filter only operates on non-null samples
- Given the stage ordering within `_remove_artifacts`: (a) hard bounds, (b) power 3× median, (c) RR ±20% deviation filter. RR deviation pass runs LAST so its median sees the post-hard-bound RR series.

**available_channels after deviation filter:**
- Given an RR channel where the deviation filter nulls > 80% of post-hard-bound samples, `available_channels.rr_intervals` is `false`

**Smoothing:**
- Given HR series, EMA (α=0.1) applied with null carry-forward
- Given power/pace series, Savitzky-Golay (window=7, poly=3) applied
- Nulls propagate through smoothing (not filled)

**Derived metrics:**
- Given GPS speed data, `gap_sec_per_km` computed via Gen-1 population GAP (a=0.033, b=0.00012)
- Given no GPS data, `available_channels.pace = false`

**Gates:**
- Given < 300s non-null HR after artifact removal, returns `CleaningResult(created=False, reason="short_stream")` — no `RawSensorStream` created
- Given >80% null per channel, that channel marked unavailable in `available_channels`
- Given missing activity, raises error
- Given `source = manual_entry`, returns no-op
- Given already cleaned (existing `RawSensorStream`), returns idempotent success
- Given `calibration_eligible = false` or `sport_type != running`, raises

**Constructor:**
- Given `grep self._session app/services/signal_cleaning_service.py`, returns zero matches
- Given the `signal_clean` worker task constructs `SignalCleaningService(session=session, ...)`, task still works

**Constants:**
- Given `PIPELINE_VERSION = "v1-signal-cleaning"`, `RR_ROLLING_WINDOW_S = 30`, `RR_DEVIATION_THRESHOLD = 0.20` are frozen module constants

### Unit — Object Storage
**File:** `tests/unit/test_signal_cleaning_object_storage.py`
- Given `build_cleaned_stream_key(athlete_id, activity_id)`, returns `"cleaned-streams/{athlete_id}/{activity_id}/stream.gz"`
- Given upload to existing key, raises `ObjectStorageConflictError`
- Given download of existing key, returns bytes

### Integration — SignalCleaningService End-to-End
**File:** `tests/integration/test_signal_cleaning_service_integration.py`
- Given eligible running activity with HR data, `RawSensorStream` row created with `available_channels.hr = true` and non-null `cleaning_pipeline_version`
- Given eligible running activity with power data, `available_channels.power = true`
- Given eligible running activity with RR intervals, `available_channels.rr_intervals = true` and cleaned RR series excludes values outside 200–2500 ms and > ±20% from rolling median
- Given activity with < 5 min non-null HR, no `RawSensorStream` created, `cleaning_pipeline_version` stays null
- Given ineligible activity (sport_type=cycling), raises and writes nothing
- Given `manual_entry` activity, returns no-op
- Given re-run against already-cleaned activity, returns `created=False, reason="already_cleaned"` — idempotent
- Given partial failure (upload succeeded but DB write failed on first attempt), retry succeeds: upload hits conflict → converted to success → inserts row + sets version
- Given HR dropout > 20% in `quality_flags`, cleaning NOT blocked — `RawSensorStream` still created

### Integration — Worker Task
**File:** `tests/integration/test_signal_cleaning_task_integration.py`
- Given `signal_clean` task called with valid activity_id, opens own session, calls service, commits once

### Behaviour — Full User Journey
**File:** `tests/behaviour/test_signal_cleaning_user_journey.py`
- Given HTTP register → upload FIT activity → ingestion pipeline → signal_clean task, `RawSensorStream` row exists with correct key and channels
- Given non-running activity, `signal_clean` NOT deferred
- Given manual entry, `signal_clean` NOT deferred
