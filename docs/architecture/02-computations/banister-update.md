# Banister Update — Fitness/Fatigue Impulse-Response Model

## Purpose
- Defines the Banister impulse-response update formula applied to `AthleteFitness` after every calibration-eligible activity
- Owns time constant semantics (population defaults and individual fitting)
- Owns the form-to-descriptor mapping consumed by LLM agents

## Inputs
```typescript
type BanisterUpdateInputs = {
  current: DimensionalScores        // current fitness, fatigue, form
  load: number                      // aerobic_load from Activity (or per-dimension load in Phase 6c+)
  constants: BanisterTimeConstants  // fitness_tau_days, fatigue_tau_days, source
  days_since_last_update: number    // days since AthleteFitness.last_activity_id session
}
```

## Update Formula
Applied by `FitnessUpdateService` after every calibration-eligible activity:

```typescript
function banisterUpdate(
  current: DimensionalScores,
  load: number,          // the relevant load score from Activity (aerobic/neuromuscular/structural)
  constants: BanisterTimeConstants,
  days_since_last_update: number
): DimensionalScores {
  // Natural decay since last activity
  const fitness_decay = Math.exp(-days_since_last_update / constants.fitness_tau_days)
  const fatigue_decay = Math.exp(-days_since_last_update / constants.fatigue_tau_days)

  const new_fitness = current.fitness * fitness_decay + load
  const new_fatigue = current.fatigue * fatigue_decay + load
  const new_form = new_fitness - new_fatigue

  return { fitness: new_fitness, fatigue: new_fatigue, form: new_form }
}
```

This runs independently for each dimension once three-dimensional scoring is active (Phase 6c). Before that, `load` is the combined aerobic + neuromuscular load and only `aggregate` is updated.

> **Recovery timing semantics:** The `days_since_last_update` parameter reflects primary session spacing. Recovery windows are measured from primary session to primary session. Secondary sessions (double-day PM sessions, suggested non-running workouts) do not reset the recovery clock. A morning easy run followed by an evening threshold session provides more recovery between primary efforts than two hard sessions on consecutive days. The weekly plan respects this when scheduling quality sessions. See `docs/vision/twin/load-fatigue.md#recovery-timing-and-session-priority`.

## Population Defaults
- `fitness_tau_days = 42` — aerobic fitness decays slowly over ~6 weeks
- `fatigue_tau_days = 7` — fatigue clears over ~1 week

These defaults apply until individual time constants are fitted (Phase 6d).

## Individual Time Constants (Phase 6d+)

Population defaults are `fitness_tau = 42 days, fatigue_tau = 7 days`. Some athletes carry fatigue for 10+ days; others clear in 5. Individual constants are fitted from the athlete's response history by `TimeConstantFittingService` when ≥ 12 weeks of calibration-eligible data exist.

> **Vision rationale:** Population defaults are starting points, not accurate for all athletes. The vision documents that some athletes carry aerobic fatigue for 10+ days while others clear in 5. Individual constants are fitted from observed response patterns to avoid applying population defaults that may be significantly wrong for a given person. The twin learns these individual constants rather than applying population defaults. See `docs/vision/twin/load-fatigue.md#individual-time-constants`.

Once fitted, `BanisterTimeConstants.source` transitions from `population_default` to `individual_fitted` and subsequent updates use the individual values. The `TwinState` `model_version` increments to reflect the change.

## Form as a Readiness Signal

`form = fitness - fatigue` at the aggregate level is the primary readiness indicator consumed by `TwinContextAssemblerService`. It drives the descriptive readiness language surfaced to LLM agents:

```typescript
function formToDescriptor(form: number): string {
  if (form > 15)  return 'peaked — near-optimal readiness'
  if (form > 5)   return 'building — good readiness with fitness accumulating'
  if (form > -5)  return 'training load — normal accumulated fatigue'
  if (form > -15) return 'heavy load — significant accumulated fatigue'
  return 'overreached — fatigue substantially exceeds fitness'
}
```

This descriptor (not the raw number) is what the LLM agent receives. Raw form scores are never surfaced to athletes.

## Cross-References
- `AthleteFitness` entity (where scores are stored): `01-entities/athlete-fitness.md`
- Load scores that feed this formula: `02-computations/load-computation.md`
- Data tier constraints on load availability: `00-foundations/data-tiers.md`
- Individual time constant fitting service: `01-entities/athlete-profile.md` (stores fitted constants)
- **Vision — load fatigue rationale (individual time constants, recovery timing, dimension interaction):** `docs/vision/twin/load-fatigue.md`

## Version History
| Version | Change |
|---|---|
| `v1` | Population defaults only (Phase 1-6c) |
| `v2-individual` | Individual time constant fitting (Phase 6d) |
| `v3-dimensional` | Per-dimension update: aerobic, neuromuscular, structural (Phase 6c) |
