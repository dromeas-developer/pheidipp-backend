# Phase 6 — Advanced Twin
*HMM segmentation, adaptation signature, three-dimensional load, personalised effort*

## Hypothesis

After 6+ months of real data, does the system's understanding of this specific
athlete make the coaching feel qualitatively different from a generic programme?
The twin should be able to say something accurate about how this athlete adapts,
how long they take to recover from different stimuli, and what training emphasis
produces results for them.

## Twin State at Completion

All five layers active. HMM segmentation producing probability distributions over
physiological states. Adaptation signature (Layer 3) building from block-level data.
Three-dimensional load model tracking aerobic, neuromuscular, and structural load
separately. Individual Banister time constants replacing population defaults.
Generation 3 personalised effort cost model where data allows.

## Sub-Phases

| Sub-phase | Title | Key deliverable |
|---|---|---|
| 6a | HMM Segmentation | Gen 3 segmentation, population HMM trained, confidence distributions |
| 6b | Personalised Weather Response | Individual weather curves replacing population adjustments |
| 6c | Three-Dimensional Load & Adaptation | AdaptationObservation, Layer 3 active, 3D TwinState |
| 6d | Individual Time Constants | Per-athlete Banister constants, full Layer 1 personalisation |
| 6e | Generation 3 Effort Model | Personalised physiological cost model, full terrain response |

## Done Criteria

- Post-workout analysis references probabilistic state inference — ambiguous
  segments are handled gracefully without fabricated claims.
- Adaptation signature visible: the plan's recovery buffer widens automatically
  after multiple blocks where data shows the athlete needs 72 hours to recover.
- Three separate load dimensions on TwinState, updated independently after sessions
  with different neuromuscular profiles.
- An athlete's individual Banister time constants differ from population defaults
  in a directionally meaningful way (measured from their recovery patterns).

## Go / No-Go (none — Phase 6 is the full product)

Phase 6 completion represents the full twin model. Maintenance and refinement
continue beyond Phase 6 but no new architectural layers are introduced.
