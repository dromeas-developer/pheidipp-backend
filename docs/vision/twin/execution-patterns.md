# Execution Patterns — Layer 5
*What the athlete actually does reveals truths self-reported data never will*

## Philosophy

Execution patterns are the most behavioural layer of the twin. They reveal what the athlete actually does when they train — their tendencies, habits, and responses under fatigue and pressure — in ways that no physiological metric or self-reported data captures. The gap between prescription and reality is the most honest signal of all.

## Macro Consistency — The Foundation

Before any within-workout analysis, the twin monitors training regularity at the weekly level: whether the athlete consistently completes the planned session count, whether they train on consistent days, and whether sessions happen at similar times of day.

Macro consistency matters for two reasons. First, it enables genuine like-for-like comparison — a Thursday threshold session after two easy days means something different to the same session done randomly in the week. Second, consistency itself is a performance predictor. A previously consistent athlete becoming irregular is a signal worth acknowledging regardless of what their physiological metrics show.

## Aerobic Session Patterns

The primary execution signal for aerobic sessions is drift resistance — the ability to hold pace and HR stable and decoupled throughout the session.

The twin monitors: cardiac drift (HR rising progressively while pace holds), pace drift in either direction, zone encroachment (drifting into tempo or threshold territory even briefly — an easy run with repeated tempo surges is not physiologically an easy run), and decoupling ratio (the HR-to-pace relationship over the session duration, a key aerobic fitness indicator that improves as aerobic base develops).

## Threshold and Interval Patterns

Interval sessions require a different analysis framework. The twin examines each rep individually and the shape of execution across the full session.

For each rep: did the athlete hit the target zone without overshooting, was effort consistent within the rep or did they surge and back off, what was the cross-rep trend — consistent execution, progressive fade, or a W-shaped pattern of blowing up and recovering.

**Recovery intervals are a commonly mishandled signal.** During a threshold or tempo workout, the cardiovascular system has not had time to return to recovery HR by the time the next rep begins — analysing recovery quality by HR zone is almost always misleading.

The correct signals for recovery quality: power drop to recovery target (when power data is available), grade-adjusted pace pullback to recovery pace, or HR trajectory showing a consistent downward trend even if it has not reached recovery HR. The rate of HR decline during recovery is itself a fitness signal — better conditioned athletes recover faster between efforts. The twin uses the best available signal and explicitly avoids misclassifying incomplete HR recovery as poor execution.

## VO2max Session Patterns

VO2max and hard interval sessions invert the aerobic session principles. The twin is looking for evidence the athlete pushed hard enough, sustained it, and showed controlled fade at the end.

A well-executed VO2max session has a specific shape: consistent hard effort across reps with slight degradation — roughly 2-3% — in the final one or two reps. That controlled fade signals the athlete found the right level.

Two failure modes the twin flags:

**Sandbagging** — athlete finishes every rep feeling strong, HR well below maximum, no execution degradation across reps. Targets likely need revising upward.

**Positive splitting** — athlete goes too hard early and falls apart after rep three or four. Pacing discipline becomes an explicit coaching objective.

## Session Shape Classification

Beyond rep-by-rep averages, the twin characterises the overall shape of structured sessions: even execution, progressive fade, positive split, W-shape blowup, strong finish. These shapes carry diagnostic information about pacing discipline, fatigue management, and whether targets are appropriate — information that averages alone cannot reveal.

## Behavioural Profile Over Time

Across many sessions, the twin builds a stable behavioural profile per athlete: their characteristic tendencies under fatigue, their zone discipline, their pacing instincts, their recovery patterns. Patterns that recur across multiple sessions become coaching objectives. The coach's tone in post-workout messages reflects what it knows about this athlete's tendencies — it does not treat every session as if it were the first.

## Architecture Cross-Reference

Each concept above maps to specific fields in `ExecutionObservation.coaching_observations`. See `01-entities/execution-observation.md` → **Vision Cross-Reference** for the authoritative mapping table.

| Pattern | Architecture Field |
|---|---|
| Cardiac drift | `cardiac_drift_score` |
| Decoupling ratio | `decoupling_ratio` |
| Zone encroachment | `flags[]` → `'zone_encroachment'` |
| Cross-rep trend | `cross_rep_trend` |
| Recovery quality | `recovery_quality` + `RecoveryAnalysis.hr_decline_rate_bpm_per_min` |
| Sandbagging | `sandbagging_flag` |
| Positive splitting | `positive_split_flag` |
| Controlled fade | `controlled_fade_score` |
| Session shape | `session_shape` |
| Behavioural profile | Aggregated across sessions by `ObjectiveUpdateService` |