# Sport Type Detection

## Purpose
Determines the sport category of an ingested activity before it is passed to downstream twin calibration services. Implements the vision principle "Non-Running Data Does Not Corrupt the Running Model" and the architectural invariant that non-running activities are excluded from twin calibration.

## Inputs
- `fit_file_key`: path to the raw FIT file in object storage
- `source`: `'intervals_icu'`, `'garmin_direct'`, or `'manual_upload'`
- `external_id`: source platform ID (for Intervals.icu metadata lookup)

## Output
- `sport_type`: `SportType` enum value
- `detection_confidence`: `'high' | 'low' | 'unknown'`
- `detection_version`: pipeline version string

## Detection Strategy

### Primary: FIT File Sport Field
The FIT protocol defines a `sport` message (message index 12) and a `sub_sport` field. `FitParserService` reads this field at parse time.

**Garmin / Ant+ Sport Mappings:**

| FIT `sport` value | `sub_sport` (if relevant) | Mapped `sport_type` |
|-------------------|---------------------------|---------------------|
| 1 (running)       | —                         | `running`           |
| 1 (running)       | 14 (trail)                | `running`           |
| 2 (cycling)       | —                         | `cycling`           |
| 2 (cycling)       | 8 (indoor cycling)        | `cycling`           |
| 3 (transition)    | —                         | `other`             |
| 4 (fitness_equipment)| —                      | `strength`          |
| 5 (swimming)      | —                         | `swimming`          |
| 14 (walking)      | —                         | `other`             |
| 254 (all)         | —                         | `unknown`           |
| 0 (generic) / missing | —                   | `unknown`           |

> **Note:** Running is the only sport that contributes to twin calibration. All other mappings result in `sport_type != 'running'`, which downstream services treat as a calibration stop.

### Secondary: Intervals.icu API Metadata
When syncing from Intervals.icu, the /activities endpoint returns a `type` field. The mapping is:

| Intervals `type` | Mapped `sport_type` |
|------------------|---------------------|
| `Run`            | `running`           |
| `Ride`           | `cycling`           |
| `Swim`           | `swimming`          |
| `WeightTraining` | `strength`          |
| `Yoga` / `Pilates` | `yoga_mobility`  |
| (any other)      | `other`             |

### Fallback: Manual Upload
For `source = 'manual_upload'`, the athlete is prompted to select a sport type during upload. If they select "Other", the system defaults to `other`.

### Failure Mode
If `FitParserService` cannot extract a sport field (corrupt FIT, unsupported device), it sets:
- `sport_type = 'unknown'`
- `detection_confidence = 'unknown'`

Activities with `sport_type = 'unknown'` are **not** calibration-eligible. They appear in the training record but do not feed load computation, threshold detection, or adaptation modelling. A coach message is generated explaining why the session was not analysed.

## Invariants
- `sport_type` is populated before `Activity` record creation.
- `sport_type = 'unknown'` implies `calibration_eligible = false`.
- `sport_type != 'running'` implies `calibration_eligible = false` and `data_tier = 6` (manual-entry equivalent).
- The sport type mapping is versioned (`sport_type_detection_version`) to enable reprocessing if mappings change.

## Event Contract
### Produced
| Event | Trigger | Payload |
|---|---|---|
| `sport_type_detected` | After `FitParserService` identifies sport | `{ activity_id, sport_type, detection_confidence, detection_version }` |

### Consumed
| Event | Action |
|---|---|
| `activity_ingested` | Sport type is embedded in the `Activity` record |

## Cross-References
- `01-entities/activity.md` — `sport_type` field definition
- `02-computations/load-computation.md` — `isCalibrationEligible` sport-type gate
- `principles.md` — Invariant #8 enforcement
- `docs/vision/twin/data-philosophy.md` — "Non-Running Data Does Not Corrupt the Running Model"