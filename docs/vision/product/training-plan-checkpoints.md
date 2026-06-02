# training-plan-checkpoints

## Checkpoint Hierarchy

A checkpoint is any scheduled moment of assessment that provides data, reduces uncertainty, and validates progress. Checkpoints give the system a common abstraction for reasoning about different types of assessment throughout the plan.

**Calibration Checkpoint.** A test workout targeting a specific physiological metric. Example: a submaximal tempo run to refine the LT2 estimate. Calibration checkpoints exist when the twin's confidence in a metric is medium or low, and the metric materially affects training targets.

**Benchmark Checkpoint.** A standardised session to measure progress against baseline. Example: a long run with heart rate drift assessment to evaluate aerobic development. Benchmark checkpoints occur at phase transitions, before the system commits to a new training emphasis.

**Race Simulation Checkpoint.** A race-pace effort to test readiness without full race stress. Example: a marathon-pace long run with the final 10K at race intensity. Race simulation checkpoints occur in the race-specific phase, before the taper begins.

**Secondary Race Checkpoint.** A B-race or C-race used as an assessment opportunity. Example: a half-marathon B-race to calibrate marathon pacing and threshold estimates. Secondary race checkpoints leverage existing race calendar entries rather than requiring additional standalone sessions.

**Progress Review Checkpoint.** A periodic assessment of overall training response. Example: a weekly form check combined with adaptation signature review. Progress review checkpoints occur every 3–4 weeks throughout the plan, providing regular signals about whether the training stimulus is producing the expected adaptation.

---

## Checkpoint Scheduling

Checkpoints are scheduled during plan synthesis based on four factors:

1. **Confidence gaps.** Low or medium confidence in a metric triggers a calibration checkpoint targeting that specific metric.
2. **Race calendar.** B-races and C-races are naturally secondary race checkpoints. No additional scheduling is needed.
3. **Phase transitions.** Moving from base to build, or build to race-specific, triggers a benchmark checkpoint to confirm readiness for the next phase.
4. **Regular intervals.** Progress review checkpoints every 3–4 weeks provide continuous adaptation signals.

---

## Checkpoints vs. Regular Workouts

| Aspect | Regular Workout | Checkpoint |
|--------|-----------------|------------|
| Purpose | Training stimulus | Data collection |
| Target precision | Range-based | Specific metric |
| Post-session analysis | Standard | Detailed metric update |
| Twin update | Load contribution | Potential threshold or confidence update |
| Replan trigger | No | Possibly, if confidence changes significantly |
| Coach framing | Training purpose | Assessment purpose |

---

## Checkpoint Completion

When a checkpoint completes, the system analyses whether the target metric was updated and whether confidence changed. The flow differs based on what the checkpoint reveals:

**Metric Updated, Confidence Improved (LOW → MEDIUM).** The system removes conservative buffers and enables more precise targets for subsequent sessions. The coach communicates: "Your half-marathon confirms your threshold is around 4:10/km — better than the 4:15 we estimated. I have updated your training zones and increased your marathon pace target slightly."

**Metric Updated, Confidence Improved (MEDIUM → HIGH).** The system enables point estimates and removes ranges. The coach communicates: "I now have enough data to be precise. Your training targets will be specific numbers rather than ranges."

**Metric Updated, Confidence Unchanged.** The plan continues as designed. The metric update is noted but does not change the strategic approach.

**Metric Not Updated, Confidence Unchanged.** The checkpoint provided less useful data than expected. The plan continues, but the system may schedule an additional calibration checkpoint.

---

## Adaptive Recovery

Recovery after checkpoints and races is based on actual execution, not planned targets. If the athlete followed the prescribed effort, standard recovery applies. If the athlete ran harder than prescribed, recovery is extended to account for the additional stress. If the athlete ran easier than prescribed, standard recovery applies but the data is less useful for twin calibration.

The recovery extension scales with the athlete's individual recovery profile when sufficient adaptation data exists. For athletes without individual data, a conservative default applies. Personalised recovery scaling becomes available only after the twin has reached high confidence and has accumulated at least three complete adaptation window observations. Until then, a standard recovery extension is applied.

This ensures the twin's model reflects actual physiological stress rather than intended stress, preserving the accuracy of future predictions.

| Scenario | What Was Prescribed | What Happened | Recovery Adjustment |
|----------|---------------------|---------------|---------------------|
| Athlete followed plan | Easy moderate effort | Easy moderate effort | Standard recovery |
| Athlete overshot | Easy moderate effort | Hard threshold effort | Extended recovery (scales with athlete profile) |
| Athlete undershot | Easy moderate effort | Very easy effort | Standard recovery (data less useful) |

---

## Adaptive Evolution

Plans evolve in response to real training data, race results, and changing circumstances. Most evolution happens at the weekly level — the weekly coaching rhythm absorbs disruptions and adjusts tactical details without changing the strategic roadmap.

**Checkpoint Completed.** The twin state is updated with new metric estimates. If confidence improved, the weekly coaching rhythm can use more precise targets. If the confidence change is significant enough to warrant a different strategic approach, replanning is triggered.

**B-race or C-race Completed.** The twin state is updated with race performance data. The weekly rhythm absorbs the race impact — adjusting the next week's load and emphasis. The strategic roadmap stays intact unless the race reveals a fundamental shift in fitness that requires restructuring the phase arc.

**Athlete Adds Race.** The system validates the addition against the existing plan. If valid, the plan is adjusted. If the addition conflicts with A-race preparation, the coach advises against it.

**Athlete Removes Race.** The plan is re-optimised for the remaining races. Sessions that served the removed race may be repurposed or redistributed by the weekly rhythm.

**Twin Confidence Upgrade.** When the twin's confidence in a key metric improves — for example, from LOW to MEDIUM — the system regenerates the plan with more precise methodology. The improved data enables a more targeted strategic roadmap.

**Goal Date Change.** If the goal date moves by more than 7 days, the strategic roadmap is re-synthesised for the new timeline.

**Session Disruption.** Missed sessions, schedule changes, and slower-than-expected recovery are absorbed by the weekly coaching rhythm — not by plan regeneration. The next week's review adjusts emphasis, session count, and intensity to account for the disruption. The strategic direction stays intact.

If session disruption becomes persistent — more than 20% of sessions missed across multiple weeks — the coach initiates a conversation about workload, motivation, or external factors. This may lead to a plan adjustment, but it starts as a coaching conversation, not an automatic system response.

---

## Load Adjustments

The twin's risk factors trigger specific load adjustments that modify the standard plan structure:

| Risk Factor | Adjustment | Example |
|-------------|------------|---------|
| High structural risk | Replace flat intervals with hill repeats | Flat track intervals become hill sprints |
| Reduced recovery capacity | Add extra recovery day after hard weeks | Three hard days per week becomes two |
| Slow intensity adaptation | Reduce hard training volume proportionally | Hard work allocation scales down based on demonstrated yield |
| Luteal phase | Reduce long run distance proportionally | Long run distance scales with individual phase sensitivity |
| Crossover athlete (not running-primary) | Extend base phase and cap structural load | Structural capacity builds before volume increases |
| B-race week | Reduce load before the race | Normal week load drops to accommodate race effort |

These adjustments are applied during weekly synthesis, not as after-the-fact corrections. The weekly coaching rhythm includes them so the athlete sees how their individual factors shape each week.

---

## Cross-References

- Plan generation overview: plan-generation
- Hypothesis selection: hypothesis-selection
- Weekly coaching rhythm: weekly-coaching-rhythm
- Checkpoint entity and storage: checkpoint (architecture)
- Confidence model and levels: confidence-and-uncertainty
