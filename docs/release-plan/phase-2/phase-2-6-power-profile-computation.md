# Phase 2 — Power Profile Computation
## Sub-Phase ID: Phase-2.6

## Objective
Implement `PowerProfileService` to compute power-duration curve (PDC) anchors from calibration-eligible activities with power data. This enables trend analysis of performance expression across training blocks and provides structured context for coaching narratives without surfacing raw metrics to athletes.

## Challenge Notes
The `activity-power-profile` entity was added to architecture with clear scope: performance expression snapshots used exclusively for LLM context, never surfaced as charts or dashboards. This aligns with the vision's "anti-dashboard" philosophy.

**Key decision:** Power profile computation is decoupled from other Phase 2 work. It requires:
1. Activity has `calibration_eligible = true`
2. Activity has `has_power = true`
3. Cleaned power series available (from Phase 2.2)

The step-level decomposition (`step_profiles`) enables zone-specific load analysis and will be leveraged by ComparableSessionService in future phases.

**Deferral:** Full capability trend aggregation (`CapabilityTrend` service) is noted as "not yet implemented" in architecture — deferred to Phase 3+.

## Capabilities Delivered
- `PowerProfileService.compute()` extracts power-duration anchors (5s, 1m, 5m, 20m) from power time-series
- `ActivityPowerProfile` records created for qualifying activities
- Anchor sources marked as 'direct', 'interpolated', or 'modeled'
- `critical_power_watts` and `w_prime_kj` computed from session data
- `data_quality_score` computed and stored for downstream filtering
- `step_profiles` populated when session has ≥2 distinct power zones
- `power_profile_computed` event fires on successful creation

## Architectural Contracts Required
- `01-entities/activity-power-profile.md`
- `01-entities/activity.md` — `power_profile_id` FK and `has_power` flag
- `00-platform/object-storage-client.md` — cleaned power series input
- `02-computations/load-computation.md` — power-based structural load inputs

## Vision References Required
- `twin/load-fatigue.md` — "how the athlete's system behaves under stress, not just how much stress"
- `twin/adaptation-signature.md` — performance expression trend analysis
- `twin/training-zones.md` — power zone definitions for step profiles

## Upstream Dependencies
- Phase-2.1 — `has_power` and `calibration_eligible` flags must be properly set
- Phase-2.2 — Cleaned power series required for quality PDC computation
- Phase-1.6 — `Activity` schema with `power_profile_id` FK exists

## Downstream Enablement
- Phase-3+ — `ComparableSessionService` uses `step_profiles` for zone-targeted matching
- Phase-3+ — `ObjectiveUpdateService` uses structural capability metrics for tolerance objectives
- Phase-4+ — Capability trend analysis aggregates power profiles over sessions

## Invariants To Preserve
- One `ActivityPowerProfile` per `Activity` where `calibration_eligible = true` AND `has_power = true`
- `ActivityPowerProfile` is append-only — new computation versions create new records with new `id`
- `computation_basis = 'insufficient_data'` results in empty `anchors` array and null CP/W'
- If data quality score < 0.5, record created but flagged for filtering (not rejected)
- `Activity.power_profile_id` is null when no power data or Tier 6 activity
- Power profiles never exposed directly to athletes or API endpoints

## Exit Gate
- For a `calibration_eligible = true` activity with power data, `ActivityPowerProfile` record exists with populated `anchors` array.
- `Activity.power_profile_id` references the created power profile.
- Sessions with multiple power zones have `step_profiles` populated.
- `data_quality_score` computed and stored (0.0–1.0 range).
- `power_profile_computed` event fires with activity_id and power_profile_id.
- Power profiles are accessible to `ContextBudgetService` for agent context assembly.