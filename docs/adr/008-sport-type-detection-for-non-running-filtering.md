---
id: ADR-008
status: accepted
tags: [architecture, data-pipeline]
supersedes: ~
superseded-by: ~
---

# ADR 008: Sport Type Detection for Non-Running Activity Filtering

## Rules
- **Sport Type Field**: `sport_type` must be populated on every `Activity` record before it is committed to the database.
- **Detection Source**: For `source != 'manual_entry'`, sport type must be derived from `FitParserService` parsing the FIT sport field or from Intervals.icu activity type metadata.
- **Non-Running Gate**: Activities with `sport_type != 'running'` must have `calibration_eligible = false` and `data_tier = 6` by the `CalibrationEligibilityService`.
- **Default Unknown**: If sport type cannot be determined, the parser must default to `'unknown'`, which also implies non-running exclusion.

## Decision

We add a `sport_type` field to the `Activity` entity and enforce non-running exclusion at the `CalibrationEligibilityService` gate. This closes an architectural gap that made Principle #8 ("Non-running activities are excluded from twin calibration") unenforceable, as the system had no mechanism to identify whether an activity was running or not.

## Rationale

- **Principle #8 was a promise without a mechanism**: The architecture mandated non-running exclusion but provided no way to detect sport type at ingestion.
- **FIT protocol provides the signal**: The FIT `sport` field and Intervals.icu activity type are reliable, standardized sources that can be parsed deterministically at ingestion time.
- **Failure is safe**: Mapping ambiguity defaults to `'unknown'`, which is treated as non-running — a conservative choice that preserves model integrity.
- **No conversion factors needed**: Once sport type is known, the system simply excludes non-running activities from the calibration pipeline instead of attempting risky cross-sport normalization.

## Alternatives Rejected

| Option | Why Rejected |
|---|---|
| Infer sport from sensor patterns | Unreliable and error-prone; cycling HR patterns can resemble easy runs, leading to false positives |
| Manual athlete tagging only | Athletes forget or tag incorrectly; FIT/Intervals.icu sources are authoritative and automatic |
| No sport-type filtering (accept all) | Violates the core product vision and Principle #8; would corrupt twin model with non-running data |

## Tradeoffs
- **Pro**: Preserves twin model accuracy by rigorously excluding non-running calibration inputs.
- **Con**: Athletes who accidentally record non-running activities (e.g., cycling warmup) will see them logged but not analyzed.
- **Pro**: Uses standardized protocol fields, minimizing custom logic and maintenance burden.

## Compliance

**Compliant**
```python
# FitParserService populates sport_type before Activity creation
if fit_sport == "running":
    activity.sport_type = "running"
elif fit_sport == "cycling":
    activity.sport_type = "cycling"
else:
    activity.sport_type = "unknown"  # safe default

# CalibrationEligibilityService enforces the gate
def is_calibration_eligible(activity):
    if activity.sport_type != "running":
        return False
    # ... continue with other gates
```

**Non-compliant**
```python
# Violates the sport-type gate invariant
def is_calibration_eligible(activity):
    return (
        activity.has_hr and
        activity.source != 'manual_entry'
        # Missing sport_type check
    )

# Violates the detection source invariant
activity.sport_type = "running"  # hardcoded, not derived from FIT/metadata
```

## Cross-References
- [ADR-001: Layer Architecture](./001-layer-architecture.md) — sport-type detection lives in Layer 1 (Raw Sensor Ingestion)
- [ADR-004: Transactional Outbox](./004-transactional-outbox-for-event-persistence.md) — `sport_type_detected` event uses standard outbox pattern