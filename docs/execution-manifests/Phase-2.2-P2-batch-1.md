# Execution Manifest — Phase-2.2-P2 — Batch 1

## Manifest Metadata
Source Plan:       docs/implementation/phase-2/phase-2-2-p2-rr-deviation-filter-remediation.md
Batch:             1 of 1
Manifest Version:  v1
Generated At:      2026-07-08T00:00:00Z
Source Plan Lines: 430
Manifest Lines:    193

This section is for telemetry and debugging only — it does not affect how
the coder should read or act on anything below it. If a bug is later
traced to a specific batch's implementation, this is what identifies
exactly which manifest, generated from exactly which state of the master
plan, produced it. `Manifest Version` is the schema version of this
template, not a content version — bump it only if the section structure
above changes, not per regeneration.

## Objective
Implement the RR ±20% rolling-median deviation filter per the sub-phase Exit Gate requirement, alongside removing the dead `self._session` field.

## Preconditions
No preconditions — this is the first batch.

## Steps
### Step 1 — Add RR deviation filter constants
[OWNER: Coder] Add two frozen module constants alongside the existing RR
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

### Step 2 — Extend _remove_artifacts with RR deviation pass
[OWNER: Coder] Extend `SignalCleaningService._remove_artifacts` with a
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

### Step 3 — Update _remove_artifacts docstring
[OWNER: Coder] Update the `_remove_artifacts` docstring to document the
two-stage RR artifact removal — hard bound then deviation filter — and
reference the updated `02-computations/signal-cleaning.md` Step 1
section and the `threshold-detection.md` Algorithm 2 consumer contract.
The docstring must list all four artifact rules (HR, power, speed, RR)
and for RR explicitly state: "RR: hard bound 200–2500 ms, then ±20%
rolling-median deviation filter (window=30 s, threshold=0.20); samples
surviving the hard bound but deviating > ±20% from their trailing
rolling median are nulled. This two-stage removal produces the cleaned
RR series consumed by `ThresholdDetectionService` HRV-inflection step 1."

### Step 4 — Remove dead self._session field
[OWNER: Coder] Remove the `self._session = session` assignment from
`SignalCleaningService.__init__` (line ~311: `self._session = session`).
The constructor's `session` parameter is RETAINED — it is passed through
to the injected repositories which hold it — but the service itself does
not store a reference. Confirm no other method on the service reads
`self._session` (grep the file for `self._session` — the validation
report confirms zero read sites beyond the assignment). The class
docstring ("the service holds an `AsyncSession`...") is still accurate:
the repositories hold the session; the service holds the repositories.
No docstring change is required.

## Context Needed
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

## Relevant Architecture Contracts
- `docs/architecture/02-computations/signal-cleaning.md` Step 1 — ARCH CLARIFICATION (the RR deviation check was a minor gap in the Step 1 spec; the doc has been updated to make the two-stage RR artifact removal — hard bound then ±20% rolling-median deviation filter — explicit. Read the updated Step 1 section before implementing. The clarification does not change ownership, invariants, event contracts, or behavioural semantics — it adds the missing detail that the sub-phase Exit Gate, the threshold-detection consumer contract, and the original plan's Testing Requirements already required)

## Relevant Invariants
- "Cleaned RR values that deviate more than ±20% from the rolling median are filtered out — the cleaned RR series excludes them. (Sub-phase Exit Gate verbatim: "Cleaned streams pass artifact validation thresholds (RR values within ±20% of rolling median retained)")"

## Relevant Event Contracts
None. This plan produces no events and consumes no events. It is a
behavioural fix inside `SignalCleaningService` and does not touch the
event catalogue or the `cleaning_pipeline_version` readiness signal
(which is already implemented and validated by Phase-2.2-P1).

## Relevant Notes
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

## Files Expected To Change
- [EXISTING] app/services/signal_cleaning_service.py

## Batch Success Criteria
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