# Evidence Source to Metric Mapping

This document maps each evidence source to the specific metrics it contributes to, with weights and conditions.

## Evidence Source → Metric Mapping

| Evidence Source | LT1 HR | LT2 HR | LT1 Power | LT2 Power | CP | LT1 Pace | LT2 Pace | VO2max | Max HR |
|---|---|---|---|---|---|---|---|---|---|
| `questionnaire_estimate` | 0.5 | 0.5 | 0.5 | 0.5 | 0.5 | 0.5 | 0.5 | 0.5 | 0.5 |
| `training_hr_deflection` | 1.0 | 1.0 | — | — | — | — | — | — | 0.5 |
| `training_rr_inflection` | 2.5 | 2.5 | — | — | — | — | — | — | 0.5 |
| `training_power_hr_ratio` | — | — | — | — | 1.5 | — | — | — | — |
| `field_test` (LT1) | 2.0 | — | 1.5 | — | — | 1.5 | — | — | 1.0 |
| `field_test` (LT2) | — | 4.0 | — | 3.0 | 3.0 | — | 3.0 | — | 1.5 |
| `field_test` (CP) | — | — | 2.0 | — | 5.0 | — | — | — | 1.0 |
| `lab_test` (LT1) | 12.0 | — | 10.0 | — | — | 10.0 | — | — | 8.0 |
| `lab_test` (LT2) | — | 15.0 | — | 12.0 | 12.0 | — | 12.0 | — | 8.0 |
| `lab_test` (VO2max) | — | — | — | — | — | — | — | 15.0 | 8.0 |

## Key Principles

1. **Per-metric accumulation**: Each evidence source contributes to specific metrics only. A field test for LT2 does not increase LT1 confidence.

2. **Weight hierarchy**: Lab tests (12-15) >> Field tests (2-5) >> Training-derived (0.5-2.5) >> Questionnaire (0.5).

3. **RR inflection carries higher weight**: RR data is richer than HR data alone, so `training_rr_inflection` carries weight 2.5 vs 1.0 for `training_hr_deflection`.

4. **Power-to-HR ratio is supplementary**: `training_power_hr_ratio` only contributes to CP, not LT1/LT2 directly.

5. **Max HR accumulates from all sources**: Max HR is updated from observed maximum HR across all session types.

## Transition Thresholds

Confidence transitions are per-metric and based on accumulated evidence weight:

| Transition | Threshold | Approximate Sessions |
|---|---|---|
| LOW → MEDIUM | 4.0 evidence units | ~4 HR deflection sessions, or 1 field test, or 1 lab test |
| MEDIUM → HIGH | 8.0 evidence units | ~8 HR deflection sessions, or 2 field tests, or 1 lab test |

**Note**: These are initial defaults. Real convergence data should validate these thresholds.

## Example Accumulation Scenarios

### Scenario 1: Athlete with chest strap (Tier 3)
- Week 1-4: 4 easy runs with HR deflection → 4 × 1.0 = 4.0 weight → LT1 HR reaches MEDIUM
- Week 5-8: 4 more easy runs + 1 RR session → 4 × 1.0 + 1 × 2.5 = 6.5 weight → LT1 HR approaching HIGH
- Week 9-12: 4 more easy runs + 2 RR sessions → 4 × 1.0 + 2 × 2.5 = 9.0 weight → LT1 HR reaches HIGH

### Scenario 2: Athlete with power meter (Tier 1)
- Week 1-2: 1 field test for LT2 → 1 × 4.0 = 4.0 weight → LT2 HR reaches MEDIUM
- Week 3-6: 4 easy runs with HR deflection → 4 × 1.0 = 4.0 weight → LT1 HR reaches MEDIUM
- Week 7-8: 1 lab test for LT2 → 1 × 15.0 = 15.0 weight → LT2 HR reaches HIGH

### Scenario 3: Athlete with optical HR (Tier 4)
- Week 1-8: 8 easy runs with HR deflection → 8 × 1.0 = 8.0 weight → LT1 HR reaches HIGH
- No RR data, so LT1 HR confidence relies solely on HR deflection
- LT2 HR confidence accumulates more slowly without RR inflection

## Cross-References

- Confidence model: `00-foundations/confidence-model.md`
- Observation weights: `02-computations/physiology-update.md`
- LT1 detection: `02-computations/lt1-detection.md`
- Threshold detection: `02-computations/threshold-detection.md`
- Data tiers: `00-foundations/data-tiers.md`
