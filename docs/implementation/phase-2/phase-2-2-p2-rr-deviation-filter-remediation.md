# Implementation Plan: Phase-2.2 — Signal Cleaning Remediation (RR Deviation Filter + Dead Field Cleanup)
## Plan ID: Phase-2.2-P2

## Sub-Phase Reference
Sub-Phase ID: Phase-2.2
Sub-Phase Title: Signal Cleaning & Raw Sensor Stream

This is a remediation plan for Phase-2.2-P1. It addresses the single MAJOR
finding and the single MINOR finding from the Phase-2.2-P1 validation report
(`reports/phase-2-2-p1-signal-cleaning_validation.md`):

- **MAJOR** — the RR artifact-removal step in `SignalCleaningService._remove_artifacts`
  applies only the 200–2500 ms hard bounds. The ±20% rolling-median deviation
  check required by the sub-phase Exit Gate ("Cleaned streams pass artifact
  validation thresholds (RR values within ±20% of rolling median retained)")
  and the Phase-2.2-P1 Testing Requirements is absent. RR samples that pass
  the hard bound but deviate > ±20% from their local rolling median are
  retained, contradicting both the plan and the Exit Gate.
- **MINOR** — `SignalCleaningService.__init__` stores `self._session = session`
  but the field is never read; the injected `AsyncSession` is used implicitly
  through the injected repositories. The stored reference is dead weight.

The original Phase-2.2-P1 plan's contract blocks (Architecture Contracts,
Invariants, Pseudocode) already established the RR deviation filter as a
required behaviour. The signal-cleaning architecture Step 1 spec was
incomplete — it showed only the hard-bound check. The architecture doc has
been updated (see Architecture Contracts → ARCH CLARIFICATION) to make the
two-stage RR artifact removal — hard bound then ±20% rolling-median deviation
filter — explicit in Step 1. This plan implements that clarification in
`SignalCleaningService` and removes the dead field. No new entities, events,
migrations, or storage keys are introduced.

## Objective
Deliver the RR ±20% rolling-median deviation filter that the sub-phase Exit
Gate requires, by extending the existing `SignalCleaningService._remove_artifacts`
method with a follow-on RR deviation pass that runs after the 200–2500 ms hard
bound. Remove the dead `self._session` field from
`SignalCleaningService.__init__` that the validation report flagged as unused.
Both fixes land in a single focused file — `app/services/signal_cleaning_service.py`
— with no schema, migration, repository, or worker changes. This is the only
plan for this remediation; it is a corrective follow-on to Phase-2.2-P1 and
shares the same sub-phase Exit Gate.

## Scope
- Extend `SignalCleaningService._remove_artifacts` with a follow-on RR
  rolling-median deviation pass that nulls RR samples deviating more than
  ±20% from their trailing rolling median, using the same rolling-window
  pattern already established for the power artifact check
- Add the `RR_DEVIATION_THRESHOLD: float = 0.20` and
  `RR_ROLLING_WINDOW_S: int = 30` frozen module constants alongside the
  existing RR hard-bound constants
- Remove the dead `self._session = session` assignment from
  `SignalCleaningService.__init__` (the constructor param is retained; the
  session flows through the injected repositories and is not held as a
  service field)
- Update the `_remove_artifacts` docstring to document the two-stage RR
  artifact removal (hard bound then deviation filter)
- Update the module-level docstring's pipeline invariant list if it
  references the RR artifact-removal contract (it currently does not
  mention the deviation check explicitly — the contract lived only in
  the plan's Testing Requirements)

## Out Of Scope
- No change to the signal-cleaning pipeline step order or any other
  pipeline step (steps 1–4 unchanged except the RR follow-on inside step 1;
  steps 2–4 / derived metrics / rolling features untouched)
- No change to HR, power, speed, or elevation artifact removal — only the
  RR channel gains the follow-on deviation filter
- No new entity, migration, repository, or worker task
- No change to the `signal_clean` procrastinate task, the enqueue hook in
  `ActivityIngestionService`, or the `ObjectStorageClient` cleaned-stream
  methods — all validated as conformant by the Phase-2.2-P1 validation
  report
- No change to `RawSensorStreamRepository`, `ActivityRepository`, or the
  `RawSensorStream` model — none touch RR artifact logic
- No reprocessing of historical activities cleaned under the prior
  (deviation-filter-less) pipeline — that is a future-phase reprocessing
  concern (Principle #14); this plan fixes the pipeline for
  newly-ingested activities going forward. Activities already cleaned
  carry `PIPELINE_VERSION = "v1-signal-cleaning"`; a future algorithm
  change would increment the version and produce a new row per ADR-009.
- No change to `available_channels` evaluation — `rr_intervals` availability
  still derives from the post-artifact null fraction (the > 80% null rule),
  which is now evaluated after BOTH the hard bound AND the deviation filter
- The ±20% threshold value is fixed (not configurable per athlete or per
  device) — it is the population-level RR artifact-rejection threshold from
  the signal-cleaning corpus; per-athlete RR variability thresholds are a
  downstream `ThresholdDetectionService` concern and out of scope here

## Architecture Contracts
- `02-computations/signal-cleaning.md` — IMPLEMENTS (Step 1 — Artifact Removal;
  the two-stage RR artifact removal is now documented explicitly in the Step 1
  spec, including the rolling- median deviation filter and the downstream
  `ThresholdDetectionService` HRV-inflection consumer contract it serves)
- `02-computations/threshold-detection.md` → Algorithm 2: HRV Inflection —
  DEPENDS ON (step 1 of that algorithm: "values outside ±20% of rolling median
  removed"; this plan implements the cleaning that produces the cleaned RR
  series that contract consumes; the threshold-detection algorithm itself is
  Phase-2.3 and out of scope)
- `01-entities/raw-sensor-stream.md` — DEPENDS ON (the `available_channels.rr_intervals`
  flag reflects what survived artifact removal — now including the deviation
  filter; the row is created by `SignalCleaningService.clean` which this plan
  does not change)
- `docs/architecture/02-computations/signal-cleaning.md` Step 1 — ARCH
  CLARIFICATION (the RR deviation check was a minor gap in the Step 1 spec;
  the doc has been updated to make the two-stage RR artifact removal —
  hard bound then ±20% rolling-median deviation filter — explicit. Read
  the updated Step 1 section before implementing. The clarification does
  not change ownership, invariants, event contracts, or behavioural
  semantics — it adds the missing detail that the sub-phase Exit Gate,
  the threshold-detection consumer contract, and the original plan's
  Testing Requirements already required)

## Invariants
Copied verbatim from the architecture corpus. This plan MUST preserve each
one. No new invariants are introduced; these are the same invariants that
Phase-2.2-P1 preserved and that this remediation must not regress.

- "Steps run in fixed order 1→7. No step may be skipped or reordered." (`02-computations/signal-cleaning.md`)
- "Null propagation: artifact-removed nulls propagate through smoothing. A channel with > 80% null values after artifact removal is marked unavailable in `AvailableChannels`." (`02-computations/signal-cleaning.md`)
- "One `RawSensorStream` per `Activity`. Created atomically with the cleaned stream upload." (`01-entities/raw-sensor-stream.md`)
- "If cleaning fails (stream too short, all HR artifacts), no `RawSensorStream` is created. The Activity exists with null `cleaning_pipeline_version`. Segmentation is skipped for this activity." (`01-entities/raw-sensor-stream.md`)
- "`available_channels` reflects what survived artifact removal — an activity that had HR but all values were flagged as artifacts will have `hr: false`." (`01-entities/raw-sensor-stream.md`)
- "If the pipeline produces a stream shorter than 5 minutes of non-null HR data, `RawSensorStream` is not created and segmentation is skipped." (`02-computations/signal-cleaning.md`)
- Cleaned RR values that deviate more than ±20% from the rolling median are filtered out — the cleaned RR series excludes them. (Sub-phase Exit Gate verbatim: "Cleaned streams pass artifact validation thresholds (RR values within ±20% of rolling median retained)")

## Implementation Steps

1. [OWNER: Coder] Add two frozen module constants alongside the existing RR
   hard-bound constants (`RR_MIN_MS`, `RR_MAX_MS`) in
   `app/services/signal_cleaning_service.py`:
   - `RR_ROLLING_WINDOW_S: int = 30` — the trailing window size in seconds
     (matches the power artifact rolling window of 30 s; at the 1 Hz
     resampled rate this is 30 samples)
   - `RR_DEVIATION_THRESHOLD: float = 0.20` — the ±20% deviation fraction
     (a sample is nulled if `abs(sample - rolling_median) > 0.20 * rolling_median`)
   Document the source: `02-computations/signal-cleaning.md` Step 1 (the
   updated two-stage RR artifact removal section) and the
   `threshold-detection.md` Algorithm 2 consumer contract ("values outside
   ±20% of rolling median removed"). The docstrings on these constants
   are the future extraction anchor if the threshold is ever promoted to
   a per-athlete value in `ThresholdDetectionService`.

2. [OWNER: Coder] Extend `SignalCleaningService._remove_artifacts` with a
   follow-on RR deviation pass that runs AFTER the existing 200–2500 ms hard
   bound and AFTER the power artifact pass. The deviation pass must:
   - Operate on the `artifact_free.rr` array (which has already had the hard
     bound applied — so only samples inside [200, 2500] ms remain; nulls
     from the hard bound stay null).
   - For each index `t` with a non-null RR sample, compute the rolling
     median over the trailing window
     `artifact_free.rr[max(0, t - RR_ROLLING_WINDOW_S + 1) : t + 1]` excluding
     the candidate sample itself (the candidate is being tested against the
     median, so it must not contribute to the median — otherwise a single
     extreme sample would pull the median toward itself and pass the check).
     Use the existing `_median` helper at the bottom of the module. If the
     window contains fewer than 2 non-null RR samples (excluding the
     candidate), skip the deviation check for that sample (not enough
     context to judge — keep the sample, consistent with the power
     artifact's `if not window_values: continue` guard).
   - Null the sample if `abs(sample - median) > RR_DEVIATION_THRESHOLD * median`.
   - Preserve null-propagation: a null RR sample stays null; the deviation
     filter only operates on non-null samples.
   - Do NOT apply the deviation check to HR, power, speed, or elevation —
     only RR. Power has its own 3×-rolling-median rule (already implemented
     and validated); HR has only the 30–220 bpm hard bound; speed has only
     the 25 m/s hard bound. The ±20% rolling-median rule is RR-specific
     per the threshold-detection contract.
   - Order within `_remove_artifacts`: (a) hard-bound pass (existing, HR +
     speed + RR) → (b) power 3×-rolling-median pass (existing) → (c) RR
     ±20% rolling-median deviation pass (new). The new pass runs last so
     its median computation sees the post-hard-bound RR series — samples
     removed by the hard bound are already null and excluded from the
     window, so they do not poison the deviation median.

3. [OWNER: Coder] Update the `_remove_artifacts` docstring to document the
   two-stage RR artifact removal — hard bound then deviation filter — and
   reference the updated `02-computations/signal-cleaning.md` Step 1
   section and the `threshold-detection.md` Algorithm 2 consumer contract.
   The docstring must list all four artifact rules (HR, power, speed, RR)
   and for RR explicitly state: "RR: hard bound 200–2500 ms, then ±20%
   rolling-median deviation filter (window=30 s, threshold=0.20); samples
   surviving the hard bound but deviating > ±20% from their trailing
   rolling median are nulled. This two-stage removal produces the cleaned
   RR series consumed by `ThresholdDetectionService` HRV-inflection step 1."

4. [OWNER: Coder] Remove the `self._session = session` assignment from
   `SignalCleaningService.__init__` (line ~311: `self._session = session`).
   The constructor's `session` parameter is RETAINED — it is passed through
   to the injected repositories which hold it — but the service itself does
   not store a reference. Confirm no other method on the service reads
   `self._session` (grep the file for `self._session` — the validation
   report confirms zero read sites beyond the assignment). The class
   docstring ("the service holds an `AsyncSession`...") is still accurate:
   the repositories hold the session; the service holds the repositories.
   No docstring change is required.

5. [OWNER: Test Architect] Update `tests/test-manifest/phase-2-2.yaml` (which
   is being produced by the Phase-2.2-P1 Step 10 handoff to the Test
   Architect) to add a test entry for the RR deviation filter — the
   capability "Cleaned RR series excludes samples deviating > ±20% from
   rolling median". If `phase-2-2.yaml` does not yet exist when this plan's
   coder work is complete, the Test Architect creates it with this entry
   plus the entries from Phase-2.2-P1's Step 10. Update the
   `protects` field to reference the Exit Gate bullet "RR values within
   ±20% of rolling median retained". Mirror the `phase-2-1.yaml` structure.

## Event Contracts
None. This plan produces no events and consumes no events. It is a
behavioural fix inside `SignalCleaningService` and does not touch the
event catalogue or the `cleaning_pipeline_version` readiness signal
(which is already implemented and validated by Phase-2.2-P1).

## Pseudocode
The RR deviation filter added inside `_remove_artifacts`, after the
existing hard-bound and power passes:

```
# (existing) hard-bound pass: HR, speed, RR (200-2500 ms) → null outside bounds
# (existing) power pass: power > 3× rolling-30s median → null

# (new) RR deviation pass — after hard bound, on artifact_free.rr
for t in range(n):
    candidate = artifact_free.rr[t]
    if candidate is None:
        continue   # null-propagation: already-nulled samples stay null
    # trailing window EXCLUDING the candidate (t-1 .. t-W)
    window_start = max(0, t - RR_ROLLING_WINDOW_S)
    window_values = [
        v for i, v in enumerate(artifact_free.rr[window_start:t])
        if v is not None
    ]
    if len(window_values) < 2:
        continue   # not enough context — keep the sample
    median = _median(window_values)
    if abs(candidate - median) > RR_DEVIATION_THRESHOLD * median:
        artifact_free.rr[t] = None
# (existing) return artifact_free → continues to _smooth → ...

# (minor) constructor: drop self._session = session
#   session still injected into repositories at construction;
#   service no longer holds a direct reference.
```

## Testing Requirements
Each requirement maps to a sub-phase Exit Gate bullet or to the validation
report's MAJOR / MINOR findings; all are independently verifiable at this
plan's completion — none depend on Phase-2.3+.

- A cleaned RR series where every sample inside [200, 2500] ms is within
  ±20% of its trailing 30-sample rolling median is retained entirely (no
  false positives). Construct a synthetic uniform RR series (e.g., all
  800 ms) and assert `_remove_artifacts` leaves every RR sample non-null.
  Maps to MAJOR finding (regression guard).
- A cleaned RR series containing one sample of, e.g., 400 ms inside the
  [200, 2500] hard bound but deviating > ±20% from its trailing rolling
  median (where the median is ~800 ms, so `|400 - 800| = 400 > 0.2 × 800 = 160`)
  has that sample nulled by the deviation filter. Assert the cleaned RR
  series at that index is `None`. Maps to the Exit Gate bullet "RR values
  within ±20% of rolling median retained" and to MAJOR finding.
- The RR deviation filter does NOT fire on HR, power, speed, or elevation
  — only RR. Construct a series where an HR sample is within 30–220 bpm
  but deviates > ±20% from its rolling median; assert the HR sample is
  retained (not nulled by the RR-specific deviation check). The HR hard
  bound (30–220) still applies; the deviation filter does not.
- The RR deviation filter respects null-propagation: a window with fewer
  than 2 non-null RR samples (e.g., the first 2 samples of the series, or
  a window where the hard bound already nulled everything) leaves the
  candidate sample unchanged. This matches the power artifact's
  `if not window_values: continue` guard.
- `available_channels.rr_intervals` is computed AFTER the deviation filter
  (not after the hard bound alone) — an RR channel where the hard bound
  left > 80% non-null but the deviation filter removed enough to push the
  null fraction past 80% results in `rr_intervals: false`. Construct a
  synthetic series where the deviation filter nulls > 80% of the
  post-hard-bound RR samples and assert `available_channels.rr_intervals`
  is `False`. This protects the invariant "available_channels reflects
  what survived artifact removal" and the > 80% null rule.
- The 5-minute non-null HR gate is unaffected by the RR deviation change
  — an eligible running activity with ≥ 300 s of non-null HR still
  produces a `RawSensorStream` row after the remediation. (Regression
  guard: the HR gate count reads from `artifact_free.hr`, which the RR
  change does not touch.)
- Re-running `signal_clean` against an activity that already has a
  `RawSensorStream` is still idempotent — the `exists_for_activity` guard
  returns `created=False, reason="already_cleaned"` before the pipeline
  runs. (Regression guard: the deviation filter is downstream of the
  idempotency guard and is therefore not reached on retry.)
- `self._session` is not referenced anywhere in
  `app/services/signal_cleaning_service.py` after the constructor —
  grep the file for `self._session` and assert zero matches. Maps to
  MINOR finding.
- The `signal_clean` worker task still constructs
  `SignalCleaningService(session=session, ...)` with the `session`
  positional/keyword argument (the constructor signature is unchanged;
  only the field storage was removed). The task still commits once after
  `service.clean(activity_id)`. (Regression guard: no constructor or
  wiring change leaks into the worker.)

## Notes

**Architecture Clarifications** — this is the only category with content for
this plan. The signal-cleaning.md Step 1 spec previously showed only the
200–2500 ms hard bound for RR artifact removal. The sub-phase Exit Gate
("Cleaned streams pass artifact validation thresholds (RR values within ±20%
of rolling median retained)") AND the `threshold-detection.md` Algorithm 2
step 1 ("artifact detection; values outside ±20% of rolling median removed")
both required the deviation filter, but the Step 1 spec did not show it. This
was a Minor Gap in the architecture doc: the threshold was implied by the
surrounding contracts but not stated in the step that implements it. The doc
has been updated (see Architecture Contracts → ARCH CLARIFICATION) to make
the two-stage RR artifact removal explicit. The implementation now matches
the clarified contract. Event firing order relative to other events is not
affected — this plan produces no events.

The ±20% deviation removal lives in signal-cleaning Step 1, NOT in
threshold-detection Algorithm 2, because the cleaned RR series persisted in
the `RawSensorStream` object-storage blob is the shared input that
`ThresholdDetectionService` consumes offline. If the deviation filter lived
only in threshold detection, the persisted cleaned stream would carry
unfiltered RR samples and every downstream consumer would re-implement the
filter. The architecture's intent (now made explicit) is that the filter
runs once at cleaning time and the persisted stream is the artefact of
record. Threshold detection's step 1 wording ("Clean RR series...") refers
to the cleaning that has ALREADY happened upstream — it is the consumer's
statement that the input it expects is already clean, not a second cleaning
pass.

## Coder Handoff Notes

The single highest-risk thing the coder can get wrong: computing the rolling
median over a window that INCLUDES the candidate sample. If the candidate
is in the window, a single extreme RR sample pulls the median toward itself
and the deviation check becomes a no-op for exactly the samples it is meant
to catch. The pseudocode and Step 2 both specify the window is
`[max(0, t - WINDOW), t)` — i.e., the trailing samples BEFORE index `t`,
explicitly excluding the candidate at `t`. Read Step 2's window slice
description carefully: `artifact_free.rr[window_start:t]` is a half-open
slice that runs up to but NOT including index `t`. The existing power
artifact check uses a window that INCLUDES the candidate
(`resampled.power[window_start : t + 1]`) because power's rule is a 3×
threshold — including the candidate in the median is safe there because a
3× outlier does not move the median enough to pass. The RR rule is a ±20%
threshold — a 20% outlier can move the median enough to pass if the candidate
is in the window. The two checks MUST use different window conventions.
Do not "harmonise" them by making the RR window include the candidate.

The second risk: running the deviation filter BEFORE the hard bound. The
hard bound must run first so the deviation filter's median computation sees
only physiologically plausible samples (200–2500 ms). If the deviation filter
runs first, a 5000 ms artefact would be included in the median and shift it
upward, potentially passing other out-of-bound samples. The Step 2 ordering —
hard-bound pass → power pass → RR deviation pass — is load-bearing. Do not
reorder.

The MINOR fix (removing `self._session`) is safe because the validation
report confirms zero read sites. If `grep -n "self._session" app/services/signal_cleaning_service.py`
returns any match other than the assignment line being removed, STOP — that
match is a read site the validation report missed, and removing the field
would break it. Do not remove the constructor `session` parameter — only
the `self._session = session` assignment. The service still receives the
session; it just does not hold a redundant reference to it.

### Coder Scope
Execute:  Steps 1, 2, 3, 4  [OWNER: Coder] — all changes are in
          `app/services/signal_cleaning_service.py`
Skip:     Step 5 (Test Architect — test manifest update)

### Coder Batches
Batch 1: Steps 1, 2, 3, 4 — all four steps touch a single file
         (`app/services/signal_cleaning_service.py`). The constants (Step 1)
         are referenced by the deviation filter (Step 2); the docstring update
         (Step 3) documents the behaviour added in Step 2; the dead-field
         removal (Step 4) is independent of the deviation logic but trivial
         and belongs in the same single-file batch. There is no reason to
         split a single-file remediation across batches — the coder edits
         one file in one focused session.

### Batch Success Criteria
Batch 1 complete when:
- `app/services/signal_cleaning_service.py` defines `RR_ROLLING_WINDOW_S`
  and `RR_DEVIATION_THRESHOLD` as frozen module constants with docstrings
  pointing to `02-computations/signal-cleaning.md` Step 1 and
  `threshold-detection.md` Algorithm 2.
- `SignalCleaningService._remove_artifacts` runs a third pass (RR ±20%
  rolling-median deviation) AFTER the existing hard-bound and power passes.
  The deviation pass uses a trailing window EXCLUDING the candidate sample,
  skips windows with < 2 non-null RR samples, and nulls samples where
  `abs(candidate - median) > 0.20 * median`.
- The `_remove_artifacts` docstring documents the two-stage RR artifact
  removal (hard bound then deviation filter) and references both the
  signal-cleaning Step 1 spec and the threshold-detection consumer contract.
- `self._session = session` is removed from `SignalCleaningService.__init__`.
  The constructor `session` parameter is retained. `grep -n "self._session"
  app/services/signal_cleaning_service.py` returns zero matches.
- No other file in the repo is modified. The `signal_clean` task, the
  `ActivityIngestionService` enqueue hook, `RawSensorStreamRepository`,
  `ActivityRepository`, `ObjectStorageClient`, and the `RawSensorStream`
  model are untouched. (`implemented-state.md`'s transaction boundaries and
  wiring diagram remain valid.)

### Context Needed
Steps 1–4 (single file):
  Primary:    `app/services/signal_cleaning_service.py` (the full file — the
              constants block at the top, the `_remove_artifacts` method
              ~lines 580–630, the constructor ~lines 310–311, the existing
              `_median` helper at the bottom, and the power artifact pass
              which is the pattern to mirror for the RR pass with the
              critical window-exclusion difference noted in Coder Handoff
              Notes)
  Secondary:  `docs/architecture/02-computations/signal-cleaning.md` (read
              the UPDATED Step 1 section — the RR deviation check
              clarification; this is the contract being implemented);
              `docs/architecture/02-computations/threshold-detection.md`
              → Algorithm 2 step 1 (the downstream consumer contract that
              the deviation filter serves — "values outside ±20% of rolling
              median removed")
  Forbidden:  `app/services/signal_cleaning_service.py` itself — do NOT
              compute the RR rolling median over a window that includes
              the candidate sample (the existing power artifact pass does
              include its candidate; that convention does not transfer to
              the RR pass — see Coder Handoff Notes). Do NOT apply the
              ±20% deviation filter to HR, power, speed, or elevation —
              only RR. Do NOT remove the constructor `session` parameter
              — only the `self._session = session` assignment inside the
              constructor body. Do NOT modify `app/worker/app.py`
              (`signal_clean` task), `app/services/activity_ingestion_service.py`
              (enqueue hook), or `app/models/raw_sensor_stream.py` —
              none of these touch RR artifact logic.
  This is everything relevant to this plan.
