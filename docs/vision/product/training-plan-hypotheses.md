# Training Plan Hypotheses
*How the LLM generates, validates, and scores strategic hypotheses for training plans.*

---

## Hypothesis Generation

The LLM generates three distinct hypotheses using four primary dimensions. Each hypothesis represents a genuinely different coaching philosophy, not a minor variation of the same approach.

### The Four Dimensions

**Methodology** defines the overall training philosophy. Options include Polarized, Pyramid, Threshold-Focused, Block Periodization, Reverse Periodization, HILF (High Intensity Low Frequency), and LIHF (Low Intensity High Frequency).

**Approach** defines how load progresses over time. Options include Linear, Non-Linear, Block, Undulating, Step, and Exponential.

**Recovery Cycle** defines the recovery structure. Options include Frequent, Infrequent, Micro-Cycles, and Macro-Cycles.

**Load Distribution** defines the zone allocation across training. Options include Polarized (80/5/15), Pyramid (60/20/20), Threshold (50/30/20), Speed-Focused (40/20/40), and Endurance-Focused (70/20/10).

### Core Rule for Distinctness

Each hypothesis must differ in at least two of the four primary dimensions, while respecting all twin constraints and the race calendar. This ensures the coach evaluates genuinely different strategic perspectives, not superficial variations of a single approach.

### Generation Process

The LLM first analyses the athlete profile: strengths, weaknesses, constraints, race priorities, and confidence gaps. It then selects three orthogonal combinations of the four dimensions, ensuring each combination is logically coherent and appropriate for the athlete's situation.

For each hypothesis, the LLM justifies the methodology choice, addresses how it targets the athlete's weaknesses, ensures all hard constraints are respected, incorporates the race calendar, and schedules checkpoints at optimal times.

The output includes the hypothesis name, methodology, approach, recovery cycle, load distribution, race considerations, phase emphasis, checkpoint schedule, rationale, and risk notes.

---

## Constraint-First Validation

Before any hypothesis is evaluated, the system checks hard invariants. These are non-negotiable constraints derived from physiological safety principles and product identity.

**Hard Invariants:**
- No unsafe load spikes — acute load increase must not exceed 10% week-over-week.
- No incompatible intensity stacking — no back-to-back Zone 4–5 sessions.
- Minimum recovery spacing — at least 48 hours between hard sessions.
- No schedule violating constraints — workouts only on athlete's available days and times.
- Running-only — no non-running activities in twin calibration.
- Honesty invariant — plans never pretend to know more than the twin knows.
- No overlapping tapers — cannot taper for multiple races simultaneously.
- A-race priority — the A-race always takes precedence over B- and C-races.
- Secondary events outside A-race taper — B- and C-races cannot be scheduled within A-race taper or race week.
- Training length gate — goals more than 24 weeks away trigger intermediate goal proposal.

Any hypothesis violating any of these invariants is discarded immediately. There is no scoring, no partial credit, no "close enough." The invariant either holds or the hypothesis is invalid.

---

## Hypothesis Scoring

Valid hypotheses are scored on three criteria:

| Criterion | Weight | Description |
|-----------|--------|-------------|
| **Twin Alignment** | 50% | Addresses strengths and weaknesses identified in the twin analysis |
| **Goal Fit** | 30% | Aligns with the goal type, distance, and race calendar |
| **Injury Safety** | 10% | Mitigates twin-identified structural and recovery risks |

The coach selects the best hypothesis based on scores and contextual judgement. The athlete does not choose. This is a deliberate authority boundary — see decision-authority for the full rationale.

---

## Hypothesis Output

Each hypothesis is a complete strategic approach:

```json
{
  "name": "Aerobic-First with Structured Recovery",
  "methodology": "Polarized",
  "approach": "Linear",
  "recovery_cycle": "Micro-Cycles",
  "load_distribution": {"zone1_2": 80, "zone3": 5, "zone4_5": 15},
  "phase_emphasis": [
    {"name": "Base", "weeks": 8, "focus": ["aerobic_fitness", "structural_resilience"]},
    {"name": "Build", "weeks": 8, "focus": ["threshold_power", "B-race_prep"]},
    {"name": "Peak", "weeks": 3, "focus": ["marathon_specific_endurance"]}
  ],
  "checkpoints": [
    {"type": "progress_review", "week": 4, "metric": "adaptation_signature"},
    {"type": "benchmark", "week": 8, "metric": "aerobic_fitness"},
    {"type": "calibration", "week": 10, "metric": "LT2"},
    {"type": "secondary_race", "week": 16, "metric": "race_readiness"},
    {"type": "race_simulation", "week": 20, "metric": "marathon_pace"}
  ],
  "rationale": "Leverages your high aerobic fitness (Polarized) and fast volume adaptation (Linear). Micro-Cycles manage structural risk.",
  "risk_notes": ["May lack speed work; monitor anaerobic progress."]
}
```

---

## Cross-References

- Main plan generation overview: training-plan-generation
- Checkpoint hierarchy and scheduling: training-plan-checkpoints
- Decision authority for hypothesis selection: decision-authority
- Hard invariants source: global-invariants
- Twin confidence and its effect on plan generation: confidence-and-uncertainty
