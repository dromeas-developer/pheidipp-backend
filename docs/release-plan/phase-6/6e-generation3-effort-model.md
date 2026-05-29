# 6e — Generation 3 Effort Model
*Personalised physiological cost model, full terrain response*

## Objective

Activate the full personalised physiological cost model. The system now answers
"what is the physiological cost of this effort for this athlete under these conditions?"
using a learned model rather than a formula. Load computation, session comparison,
and race prediction all become more accurate on varied terrain.

## Scope

`PersonalisedEffortModel` training. `EffortNormalisationService` Generation 3.
Load score reprocessing for athletes with sufficient data.

## Architecture References

- Generation 3 inputs and outputs (grade, surface, fatigue, terrain history, structural load):
  `architecture/effort-normalisation.md` → Generation 3
- Downstream effects on load scores and historical comparison:
  `architecture/effort-normalisation.md` → Downstream Effects
- The personalised cost model replacing GAP as primary concept:
  `architecture/effort-normalisation.md` → Target Framing for Generation 3

## Dependencies

Requires 5d (per-athlete GAP curve — Generation 3 extends Generation 2).
Requires 6c (structural load dimension — inputs the fatigue state into cost model).
Requires sufficient accumulated sessions across varied terrain
(typically 40+ outdoor sessions with elevation and varied surface types).

## Models Modified

**`AthleteProfile`** — adds `effort_model_version` (str, nullable).
Set to `personalised-v1` when Generation 3 model is active for this athlete.
Null means Generation 2 (per-athlete GAP) or Generation 1 (population).

## Services Modified

**`EffortNormalisationService`** (updated) — when `effort_model_version = personalised-v1`:
Computes effort cost using a learned model with inputs: grade, surface type,
current `structural_fatigue` from TwinState, historical terrain response from
accumulated session data. Output is a normalised effort cost with confidence interval.
Falls back to Generation 2 (per-athlete GAP) for athletes without the personalised model.

**`LoadComputationService`** (updated) — uses Generation 3 cost for athletes with
the personalised model. `ingestion_pipeline_version` incremented to `v3-personalised`.

**`RacePredictionService`** (updated) — course adjustment uses Generation 3 cost
for athletes with the personalised model, producing more accurate elevation adjustments.

## Done Criteria

- An athlete with 40+ varied-terrain outdoor sessions has `effort_model_version = personalised-v1`.
- Load scores for a hilly trail session differ from a flat road session of the
  same duration by more than the Gen 2 GAP formula would predict — reflecting
  this athlete's individual terrain response.
- Athletes below the threshold continue to use Generation 2 without errors.
