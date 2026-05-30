# Training Plan Generation
*How Pheidipp designs adaptive, LLM-driven training plans with hypothesis-driven coaching and constraint-first validation.*

---

## Core Philosophy

The LLM is the coach. It uses the twin as its brain, the taxonomy as its playbook, the athlete's data as its compass, and the race calendar as its roadmap. Every plan begins with what the twin knows and what it does not know. The system never pretends to have certainty it has not earned.

Five principles govern plan generation:

**Twin-First Reasoning.** All reasoning starts with the twin model's data, confidence, and constraints. The twin's confidence level determines what the plan can assume and what it must verify. A plan generated at LOW confidence carries more conservative buffers and more calibration checkpoints than one generated at HIGH confidence.

**Structured Hypotheses.** The LLM does not produce a single plan. It generates three distinct strategic hypotheses, each representing a different coaching approach. The coach then selects the best hypothesis for this athlete at this moment. This prevents anchoring bias and ensures the athlete benefits from genuinely different strategic perspectives. See training-plan-hypotheses for the full generation methodology.

**Checkpoint-Driven Structure.** The plan is built around checkpoints — scheduled moments of assessment that provide data, reduce uncertainty, and validate progress. Checkpoints are not interruptions to training. They are the mechanism by which the plan learns whether its assumptions are correct and adjusts accordingly. See training-plan-checkpoints for the full checkpoint hierarchy.

**Constraint-First Validation.** Invalid hypotheses are discarded before scoring. The system checks hard invariants — no unsafe load spikes, no incompatible intensity stacking, no schedule violations — and rejects any hypothesis that breaks them. Only valid hypotheses proceed to evaluation. See training-plan-hypotheses for the full validation logic.

**Coach Decides.** The coach selects the best hypothesis. The athlete accepts or abandons the plan. This preserves coaching authority while respecting athlete autonomy. The athlete is never asked to choose between multiple plans — that is a product decision, not an athlete decision.

---

## System Workflow

Plan generation proceeds through four phases:

**Phase 0: Training Length Gate.** The system evaluates whether the goal timeline is appropriate. Goals more than 24 weeks away trigger an intermediate goal proposal focused on physiological foundations. Goals fewer than 8 weeks away with low fitness trigger a shorter goal proposal. Goals within appropriate range proceed directly to hypothesis generation.

**Phase 1: Generate Strategic Hypotheses.** The LLM analyses the athlete's twin state, preferences, goal, race calendar, and confidence gaps. It produces three distinct hypotheses, each varying across four primary dimensions. Each hypothesis is a complete strategic approach — not a partial sketch. See training-plan-hypotheses for the full generation methodology.

**Phase 2: Validate and Synthesize Strategic Framework.** Hard invariants are checked first. Hypotheses violating any invariant are discarded immediately. Valid hypotheses are scored on twin alignment (50%), goal fit (30%), and injury safety (10%). The coach selects the best hypothesis and synthesises a strategic framework covering macrocycle structure, race schedule, checkpoint schedule, intensity distribution, progression model, and recovery model. See training-plan-hypotheses for validation and scoring details.

**Phase 3: Instantiate Executable Plan.** The strategic framework is converted into PlannedSession records covering the full plan duration. Each session includes session type, intent description, approximate duration, target date, week number, and phase label. Checkpoint sessions are flagged with checkpoint metadata. Specific workout targets are not generated here — that happens on the day via the workout generation agent, using the freshest available data about the athlete's current state.

**Phase 4: Adaptive Evolution.** The plan evolves based on checkpoint completions, race results, calendar changes, twin confidence upgrades, and dropout patterns. Each trigger causes the system to reassess whether the current plan remains optimal or whether replanning is warranted. See training-plan-checkpoints for checkpoint completion handling and adaptive evolution triggers.

---

## Strategic Framework

After hypothesis selection, the system synthesises a strategic framework. This is the bridge between the high-level hypothesis and the executable plan of sessions.

The framework specifies:

**Macrocycle Structure.** The overall plan duration and phase arc — how many weeks of base building, threshold development, race-specific training, taper, and race week.

**Race Schedule.** Each race in the calendar with its role (A, B, or C), taper requirements, and recovery window.

**Checkpoint Schedule.** All checkpoints with their types, target metrics, timing, and session types. See training-plan-checkpoints for checkpoint scheduling logic.

**Phase Adjustments.** How races and checkpoints modify the standard phase structure — reduced load before B-races, extended recovery after, taper windows for the A-race.

**Intensity Distribution.** The zone allocation across the full plan, derived from the selected hypothesis's load distribution.

**Progression Model.** Volume and intensity progression rules for each phase, including sport-specific adjustments for crossover athletes and cycle-phase-aware modifications.

**Recovery Model.** The recovery cycle type, standard structure, and race-specific recovery windows.

**Risk Mitigations.** Applied adjustments based on the twin's risk factors — hill repeats instead of flat intervals for structural risk, extra recovery days for RED-S risk, reduced intensity for adaptation signature concerns.

---

## Race Roles and Handling

Every race in the calendar has a defined role that determines how it integrates into the plan.

**A-race.** The primary goal. The plan peaks for this event. Taper is 2–3 weeks. Recovery is 2 weeks. The A-race is the only true peak. All other races serve preparation for it.

**B-race.** A tune-up or confidence-building event. Moderate taper of 3–7 days. Recovery of 5–7 days. The coach sets a controlled target based on current fitness, not all-out effort. B-races are natural secondary race checkpoints — they provide threshold calibration, pacing feedback, and race experience without the stress of a full race effort.

**C-race.** A training opportunity. No taper. Treated as a hard workout in the session distribution. Recovery of 3–5 days. The coach frames it as a hard training day with a starting line.

Athletes often add B-races after the plan is generated. When this happens, the system validates whether the B-race fits within the existing plan structure. If it does, the plan is adjusted to accommodate it. If it would compromise the A-race timeline, the coach explains the conflict and recommends against the addition.

---

## Confidence Subsystem

Confidence determines how precisely the plan can target training stimuli and how much conservative buffering is required.

**HIGH confidence.** Full adaptation speed. No checkpoint needed for this metric. The plan can use point estimates for training targets.

**MEDIUM confidence.** The system proposes a calibration checkpoint for the specific metric. The checkpoint is strongly recommended but not mandatory. If declined, the plan continues with moderate conservative buffers.

**LOW confidence.** The system strongly recommends a calibration checkpoint. If declined, the plan uses conservative estimates with wide ranges. The coach communicates this explicitly: "I don't have enough data to be precise here, so I'm building in extra margin to keep you safe."

Checkpoints are the system's mechanism for improving confidence. They are not information-gain optimisation exercises — they are timely assessments scheduled at moments that matter most: before race-specific phases, before key workouts, and at regular intervals throughout the plan. See training-plan-checkpoints for checkpoint scheduling and completion details.

---

## Layered Fallback Model

When the full adaptive synthesis pipeline cannot produce a valid plan, the system falls back through progressively simpler approaches:

1. **Full Adaptive Synthesis.** The standard pipeline: hypothesis generation, validation, scoring, synthesis, instantiation. This produces the highest-quality plan.
2. **Semi-Adaptive Constrained Synthesis.** Reduced hypothesis space with tighter constraints. Used when twin confidence is very low or when unusual calendar constraints limit the strategic options.
3. **Template Adaptation.** A pre-built plan template adjusted for the athlete's goal type, fitness level, and calendar. Used when the LLM cannot produce valid hypotheses within the constraint space.
4. **Static Fallback.** A conservative, evidence-based plan that requires no twin data beyond goal type and fitness level. The last resort.

The fallback model ensures every athlete receives a plan, even when the system's confidence is too low for full adaptive synthesis. The coach communicates the reduced precision explicitly.
