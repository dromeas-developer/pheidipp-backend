# tests/behaviour/

## Purpose

Behaviour tests simulate full user journeys through the public HTTP surface, exercising every layer from route handler to database. They are fully integrated — no external services are mocked. A regression in any layer (validation, service, repository, event publisher, dependency) appears here first. These tests serve as the exit-gate scenarios for the implementation plans they accompany.

## Contents

### Authentication
| File | Covers |
|---|---|
| `test_auth_user_journey.py` | Auth flow: register, login, token refresh, audit-log scanning invariant |

### Onboarding
| File | Covers |
|---|---|
| `test_onboarding_user_journey.py` | Onboarding flow: register → login → onboard → PATCH profile/preferences → read twin/twin history |

### Activity Pipeline
| File | Covers |
|---|---|
| `test_signal_cleaning_user_journey.py` | Signal cleaning flow: register → onboard → POST /upload → GET /activities — cleaning-pipeline-version transitions |

### Physiology & Threshold Detection
| File | Covers |
|---|---|
| `test_physiology_update_user_journey.py` | Physiology update: register → activity → signal clean → threshold detect → physiology update service |
| `test_threshold_detection_user_journey.py` | Threshold detection: register → onboard → activity → signal clean → threshold detection service → observation contract |

### Plans
| File | Covers |
|---|---|
| `test_plan_user_journey.py` | Plan flow: register → onboard → generate_plan worker task in-process → plan endpoints — includes 404-between-onboarding-and-task contract |

### Twin Recalibration
| File | Covers |
|---|---|
| `test_twin_recalibration_calibration_user_journey.py` | Twin recalibration: threshold detect → physiology update → twin recalibration pipeline |

## Mock Boundaries

- None — behaviour tests are fully integrated end-to-end. See `tests/MOCKING_CONTRACT.md` for the authoritative per-layer table.
- Worker task bodies (e.g. `generate_plan`) are invoked in-process via `AsyncSessionLocal` monkey-patch where the test needs plan data for subsequent read-endpoint assertions.
