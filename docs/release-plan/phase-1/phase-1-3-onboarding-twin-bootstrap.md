# Phase 1 — Onboarding & Twin Bootstrap
## Sub-Phase ID: Phase-1.3

## Objective
Accept the onboarding questionnaire and produce the initial athlete state in one atomic transaction. This is the first sub-phase that writes to the database — all prior sub-phases established schema only. The twin is bootstrapped from population norms (Tier 3, questionnaire only, LOW confidence). No historical data, no peer matching, no LLM involvement. Pure Python computation.

## Challenge Notes
Early drafts used `TrainingBlock` (single goal type). Current architecture has `TrainingGoal` with five goal types. For Phase 1, we support only `race_event` and `target_performance` — `fitness_improvement`, `maintenance`, and `recovery` are deferred because they require historical data, baseline fitness computation, or injury assessment that doesn't exist at Tier 3. The plan generation service (1.4) will call `plan-generation-race.md` (unified with `plan-generation-target-performance.md` in architecture).

The onboarding transaction is heavy — it creates `AthleteProfile`, `AthletePreferences`, `TrainingGoal`, `AthletePhysiology`, `AthleteFitness`, and `TwinState` atomically. If any step fails, all prior steps roll back. The `onboarding_complete` flag gates access to plan, coaching, and workout endpoints.

## Capabilities Delivered
- `POST /athletes/{id}/onboarding` — atomic transaction creating:
  1. `AthleteProfile` (demographics, structural risk flag)
  2. `AthletePreferences` (training config, data tier inference)
  3. `TrainingGoal` (`race_event` or `target_performance` only)
  4. `AthletePhysiology` (bootstrapped from age-graded population norms, LOW confidence)
  5. `AthleteFitness` (zero fitness/fatigue, population time constants)
  6. `TwinState` (LOW confidence, `trigger = questionnaire`)
  7. Sets `athlete.onboarding_complete = true`
- `GET /athletes/{id}/onboarding` — returns current onboarding status
- `GET /athletes/{id}/twin` — returns latest `TwinState`
- `GET /athletes/{id}/twin/history` — all snapshots
- `GET /athletes/{id}/profile` — read AthleteProfile
- `PATCH /athletes/{id}/profile` — update mutable fields
- `GET /athletes/{id}/preferences` — read AthletePreferences
- `PATCH /athletes/{id}/preferences` — update mutable fields

## Architectural Contracts Required
- `01-entities/athlete.md`
- `01-entities/athlete-profile.md`
- `01-entities/athlete-preferences.md`
- `01-entities/training-goal.md`
- `01-entities/training-plan.md`
- `01-entities/twin-state.md`
- `01-entities/athlete-physiology.md`
- `01-entities/athlete-fitness.md`
- `00-foundations/data-tiers.md` (data tier inference)
- `00-foundations/confidence-model.md`

## Vision References Required
- `product/plan-generation.md` — strategic roadmap concept
- `twin/cold-start.md` — Tier 3 bootstrap philosophy
- `twin/confidence-and-uncertainty.md` — communication under uncertainty
- `coach/first-message.md` — voice and content of first coach message (prepared for in 1.5a)

## Upstream Dependencies
- Phase-1.1 (Auth) — `Athlete` must exist and be authenticated
- Phase-1.2a (Profile & Preferences) — schema must exist
- Phase-1.21 (Plan & Sessions) — `TrainingGoal` schema must exist
- Phase-1.2c (Twin & Fitness) — `TwinState`, `AthletePhysiology`, `AthleteFitness` schema must exist

## Downstream Enablement
- Phase-1.4 (Plan Generation) — requires `TrainingGoal`, `TwinState`
- Phase-1.5a (First Coach Message) — triggered after onboarding completes
- Phase-1.5b (Workout Generation) — requires `TwinState` for target generation
- Phase-1.6 (FIT Import) — updates `AthleteFitness` and creates new `TwinState`

## Invariants To Preserve
- The entire onboarding sequence runs in one database transaction. If any step fails, all prior steps roll back. The athlete remains in `onboarding_complete = false` state.
- `TwinBootstrapService` is pure Python. No LLM call, no external API call. Must complete within 200ms.
- Re-onboarding is not supported. Calling `POST /athletes/{id}/onboarding` when `onboarding_complete = true` returns 409. Athletes update preferences via PATCH.
- `TrainingGoal` enforces single active goal per athlete (409 on second creation).
- `AthleteProfile.structural_risk_flag` is computed from `AthletePreferences.sport_background`.
- Data tier is inferred from `hr_source` and `power_source` on `AthletePreferences`.
- Threshold estimates (`lt1_*`, `lt2_*`, `max_hr`) are bootstrapped from age-graded population norms using `AthleteProfile.date_of_birth`.
- `AthleteFitness` is initialised to zero fitness, zero fatigue.
- `TwinState.confidence_level = low`, `trigger = questionnaire`.

## Non-Goals
- `fitness_improvement`, `maintenance`, `recovery` goal types — deferred
- `Objective` seeding — deferred to Phase 4 (requires data)
- Menstrual cycle tracking (`CyclePhaseLog`) — deferred to Phase 3
- WeeklPlan creation — this is plan generation (1.4), not onboarding
- First coach message generation — this is 1.5a, not onboarding

## Exit Gate
- Submitting a complete questionnaire creates all six entities in one transaction.
- Simulating a failure mid-transaction leaves no partial records.
- Attempting to onboard twice returns 409.
- `GET /athletes/{id}/twin` returns a `TwinState` with `confidence_level = low` and non-null threshold estimates derived from population norms.

## Risks
- **Heavy transaction**: 8 entities created in one transaction. Consider if any can be split (e.g., `AthleteProfile`/`AthletePreferences` as a separate "profile creation" step before the full onboarding). However, the atomicity invariant is strict — partial onboarding is worse than slow onboarding.
- **Data tier inference edge cases**: If `hr_source` or `power_source` are not set, the data tier inference must have a sensible fallback. Mitigation: default to manual entry (Tier 6) and let the athlete update later.

