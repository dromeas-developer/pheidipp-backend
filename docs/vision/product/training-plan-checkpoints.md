# Training Plan Checkpoints
*How checkpoints provide data, reduce uncertainty, and validate progress throughout the training plan.*

---

## Checkpoint Hierarchy

A checkpoint is any scheduled moment of assessment that provides data, reduces uncertainty, and validates progress. Checkpoints give the system a common abstraction for reasoning about different types of assessment throughout the plan.

**Calibration Checkpoint.** A test workout targeting a specific physiological metric. Example: a submaximal tempo run to refine the LT2 estimate. Calibration checkpoints exist when the twin's confidence in a metric is medium or low, and the metric materially affects training targets.

**Benchmark Checkpoint.** A standardised session to measure progress against baseline. Example: a long run with heart rate drift assessment to evaluate aerobic development. Benchmark checkpoints occur at phase transitions, before the system commits to a new training emphasis.

**Race Simulation Checkpoint.** A race-pace effort to test readiness without full race stress. Example: a marathon-pace long run with the final 10K at race intensity. Race simulation checkpoints occur in the race-specific phase, before the taper begins.

**Secondary Race Checkpoint.** A B-race or C-race used as an assessment opportunity. Example: a half-marathon B-race to calibrate marathon pacing and threshold estimates. Secondary race checkpoints leverage existing race calendar entries rather than requiring additional standalone sessions.

**Progress Review Checkpoint.** A periodic assessment of overall training response. Example: a weekly form check combined with adaptation signature review. Progress review checkpoints occur every 3–4 weeks throughout the plan, providing regular signals about whether the training stimulus is producing the expected adaptation.

---

## Checkpoint Scheduling Logic

Checkpoints are scheduled during synthesis based on four factors:

1. **Confidence gaps.** Low or medium confidence in a metric triggers a calibration checkpoint targeting that specific metric.
2. **Race calendar.** B-races and C-races are naturally secondary race checkpoints. No additional scheduling is needed.
3. **Phase transitions.** Moving from base to build, or build to race-specific, triggers a benchmark checkpoint to confirm readiness for the next phase.
4. **Regular intervals.** Progress review checkpoints every 3–4 weeks provide continuous adaptation signals.

---

## Checkpoints vs. Regular Workouts

| Aspect | Regular Workout | Checkpoint |
|--------|-----------------|------------|
| Purpose | Training stimulus | Data collection |
| Target precision | Zone-based | Specific metric |
| Post-session analysis | Standard | Detailed metric update |
| Twin update | Load contribution | Potential threshold or confidence update |
| Replan trigger | No | Possibly, if confidence changes significantly |
| Coach framing | Training purpose | Assessment purpose |

---

## Checkpoint Completion Flow

When a checkpoint completes, the system analyses whether the target metric was updated and whether confidence changed. The flow differs based on what the checkpoint reveals:

**Metric Updated, Confidence Improved (LOW → MEDIUM).** The system removes conservative buffers and enables more precise targets for subsequent sessions. The coach communicates: "Your half-marathon confirms your threshold is around 4:10/km — better than the 4:15 we estimated. I've updated your training zones and increased your marathon pace target slightly."

**Metric Updated, Confidence Improved (MEDIUM → HIGH).** The system enables point estimates and removes ranges. The coach communicates: "I now have enough data to be precise. Your training targets will be specific numbers rather than ranges."

**Metric Updated, Confidence Unchanged.** The plan continues as designed. The metric update is noted but does not change the strategic approach.

**Metric Not Updated, Confidence Unchanged.** The checkpoint provided less useful data than expected. The plan continues, but the system may schedule an additional calibration checkpoint.

---

## Adaptive Recovery

Recovery after checkpoints and races is based on actual execution, not planned targets. If the athlete followed the prescribed effort, standard recovery applies. If the athlete overshot the target — running Zone 4 when Zone 3 was prescribed — recovery is extended by 2 days to account for the additional stress. If the athlete undershot, standard recovery applies but the data is flagged as less useful for twin calibration.

This ensures the twin's model reflects actual physiological stress rather than intended stress, preserving the accuracy of future predictions.

| Scenario | Target Effort | Actual Effort | Recovery Adjustment |
|----------|---------------|---------------|---------------------|
| Athlete followed plan | Zone 3 | Zone 3 | Standard recovery |
| Athlete overshot | Zone 3 | Zone 4 | Extend recovery (+2 days) |
| Athlete undershot | Zone 3 | Zone 2 | Standard recovery (data less useful) |

---

## Adaptive Evolution Triggers

Plans evolve in response to real training data, race results, and changing circumstances:

**Checkpoint Completed.** The twin state is updated with new metric estimates. If confidence improved, intensity targets are refined. If the confidence change is significant enough to warrant a different approach, replanning is triggered.

**B-race or C-race Completed.** The twin state is updated with race performance data. The remaining plan is reassessed — if the race revealed higher fitness than expected, targets may increase. If it revealed lower fitness, the plan may become more conservative.

**Athlete Adds Race.** The system validates the addition against the existing plan. If valid, the plan is adjusted. If the addition conflicts with A-race preparation, the coach advises against it.

**Athlete Removes Race.** The plan is re-optimised for the remaining races. Sessions that served the removed race may be repurposed or redistributed.

**Twin Confidence Upgrade.** When the twin's confidence in a key metric improves — for example, from LOW to MEDIUM — the system re-runs synthesis and instantiation. The improved data may enable a more precise or ambitious plan.

**Goal Date Change.** If the goal date moves by more than 7 days, the strategic framework is re-synthesised for the new timeline.

**Session Dropout.** If more than 20% of sessions within a 3-week window are skipped or missed, the system reassesses plan viability. This may trigger a coaching conversation about workload, motivation, or external factors.

---

## Load Adjustments

The twin's risk factors trigger specific load adjustments that modify the standard plan structure:

| Risk Factor | Adjustment | Example |
|-------------|------------|---------|
| structural_risk = HIGH | Replace flat intervals with hill repeats | 4x400m flat becomes 4x30s hill sprints |
| recovery_modifier = RED | Add extra recovery day after hard weeks | 3:1 hard:easy becomes 2:1 hard:easy |
| adaptation_signature = SLOW_INTENSITY | Reduce Zone 4–5 volume by 30% | 15% becomes 10% of weekly volume |
| cycle_phase = LUTEAL | Reduce long run distance by 10% | 20km becomes 18km |
| sport_background = CROSSOVER | Extend base phase by 20% | 8 weeks becomes 10 weeks |
| B-race week | Reduce load by 20% in the week before the race | Normal week 100% becomes 80% |

These adjustments are applied during synthesis, not as after-the-fact corrections. The strategic framework includes them explicitly so the athlete can see how their individual factors shape the plan.

---

## Cross-References

- Main plan generation overview: training-plan-generation
- Hypothesis generation and validation: training-plan-hypotheses
- Checkpoint entity and storage: checkpoint (architecture)
- Confidence model and levels: confidence-and-uncertainty
- Race roles and handling: training-plan-generation (Race Roles and Handling section)
