# Phase 3 — Environmental Context
*Wellness signals, weather, menstrual cycle, recovery modifier*

## Hypothesis

Does the twin's daily adjustment feel accurate when it has wellness data?
The coach should catch real fatigue patterns before the athlete consciously
notices them. Adjusted targets on a suppressed day should feel appropriate —
not aggressive, not overly conservative.

## Twin State at Completion

Layer 4 (External Modifiers) active. Wellness baseline established after
3+ weeks of data. Recovery modifier (GREEN/AMBER/RED) feeding workout targets.
Menstrual cycle tracking live for female athletes. Weather adjustments applied
to every generated workout.

## Sub-Phases

| Sub-phase | Title | Key deliverable |
|---|---|---|
| 3a | Wellness Ingestion | AthleteWellness model, passive data from wearables |
| 3b | Recovery Modifier | Baseline computation, trend detection, GREEN/AMBER/RED |
| 3c | Menstrual Cycle Integration | CyclePhaseLog, phase computation, modifier stacking |
| 3d | Weather Integration | WeatherForecast, heat/wind adjustment, two-column distinction |

## Done Criteria

- Log wellness data for 2 weeks. After a hard training block, `recovery_modifier_level`
  transitions to `amber` or `red` and adjusted targets are measurably reduced.
- On a green day following full recovery, adjusted targets match theoretical targets.
- Weather adjustment fires correctly — a 28°C humid day produces visibly reduced
  adjusted targets with a plain-language explanation.
- Female athlete: after logging cycle day one, `GET /athletes/{id}/twin` reflects
  the current cycle phase and the luteal phase thermoregulatory modifier is applied.

## Go / No-Go for Phase 4

- Wellness baseline requires ≥ 14 non-null data points in the past 28 days.
  Athletes without sufficient data still receive workouts (default GREEN) — no errors.
- Recovery modifier classification is deterministic — given the same input wellness
  data, it always produces the same result.
- Weather fetch failures degrade gracefully — adjusted_targets fallback to
  theoretical_targets; no errors surfaced to the athlete.
