# 6a — HMM Segmentation
*Gen 3 pipeline, population HMM, confidence distributions, historical reprocessing*

## Objective

Replace heuristic segmentation with a Hidden Markov Model that produces posterior
probability distributions over physiological states. Ambiguous transitions are
handled correctly — the model preserves uncertainty rather than collapsing it.
Downstream systems that read `PhysiologicalSegment` gain higher-quality inferences.

## Scope

Population HMM training from labelled Gen 1 segments. `HmmSegmentationService`.
`segmentation_version = hmm-v1`. `state_probabilities` JSONB populated.
Historical reprocessing task. Per-athlete fine-tuning trigger.

## Non-Goals

- Per-athlete HMM fine-tuning trigger before 30 labelled segments — the population
  model is used until then (fine-tuning is triggered automatically once the threshold
  is crossed, within this sub-phase)

## Architecture References

- HMM architecture (7 states, feature vectors, transition matrix, emission distributions):
  `architecture/segmentation-pipeline.md` → Generation 3: HMM Inference
- Why HMM fits this problem (4 reasons):
  `architecture/segmentation-pipeline.md` → Why HMM Fits This Problem
- `state_probabilities` field on PhysiologicalSegment (null in Gen 1, populated here):
  `architecture/data-models.md` → Segmentation Layer
- Population model first, per-athlete fine-tuning after 30+ segments:
  `architecture/segmentation-pipeline.md` → HMM Architecture

## Dependencies

Requires 5b (Gen 1 `PhysiologicalSegment` records — used as training labels).
Requires sufficient labelled segments across the athlete base for population model.

## Services Introduced

**`HmmTrainingService`** (offline, Python) — trains the population HMM.
Not a runtime service — run as a one-off job when sufficient labelled data exists.
Uses Gen 1 `PhysiologicalSegment` records as labels with confidence ≥ 0.6.
Stores trained model parameters in object storage: `models/hmm/population_v1.pkl`.

**`HmmSegmentationService`** (sync, Python).
- `segment(cleaned_stream, workout_steps, athlete_id) → list[PhysiologicalSegment]`
  Loads the population model (or per-athlete fine-tuned model if ≥ 30 segments exist).
  Runs Viterbi algorithm for most-likely state sequence.
  Runs forward-backward algorithm for posterior distributions.
  Sets `state_probabilities` JSONB for each segment.
  Sets `inferred_state = unknown` when max posterior probability < 0.45.
  Sets `confidence` to the posterior probability of the inferred state.
  Sets `segmentation_version = hmm-v1`.

**`HmmFineTuningTask`** (async worker — triggered when athlete reaches 30
labelled PhysiologicalSegment records). Produces a per-athlete model stored as
`models/hmm/athlete_{id}_v1.pkl`. Subsequent segmentation for this athlete uses
the fine-tuned model.

**`ReprocessSegmentationTask`** (async worker) — reprocesses historical activities
through the HMM. Old `PhysiologicalSegment` records receive `superseded_at`.
New records with `segmentation_version = hmm-v1` are inserted.

## Key Constraints

- Old Gen 1 `PhysiologicalSegment` records are superseded, not deleted.
- Downstream systems that read `PhysiologicalSegment` must handle both
  `segmentation_version = heuristic-v1` (for unreprocessed historical records)
  and `hmm-v1` (for new and reprocessed records).
- `state_probabilities` is null for Gen 1 records — consumers must null-check.
- The population model is used until per-athlete fine-tuning threshold is reached.
  Athletes with < 30 labelled segments receive population-model segmentation.

## Done Criteria

- New sessions produce `PhysiologicalSegment` records with `segmentation_version = hmm-v1`
  and non-null `state_probabilities`.
- Ambiguous transitions (e.g. warmup/low_aerobic boundary) produce segments with
  `inferred_state = unknown` and `confidence < 0.45` rather than a forced classification.
- An athlete with 30+ Gen 1 segments triggers per-athlete fine-tuning.
- Historical reprocessing produces new segments without modifying old records.
