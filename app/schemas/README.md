# app/schemas/

## Purpose
Pydantic v2 request and response contracts for the public API surface. Every schema is a `BaseModel` with `from_attributes=True` on response types so that ORM-to-JSON mapping is centralized. Schemas own wire-format validation — no business logic, no ORM coupling beyond `model_validate`.

## Contents
### Auth
| File | Responsibility |
|---|---|
| `auth.py` | Register, login, refresh request/response schemas; `AthleteResponse` public shape excluding credentials |

### Athlete
| File | Responsibility |
|---|---|
| `activity.py` | Activity upload response, list/detail schemas, and post-workout analysis response with coaching message summary |
| `onboarding.py` | Onboarding request (profile, preferences, goal), status response, twin-state history, and PATCH schemas |

### Training
| File | Responsibility |
|---|---|
| `plan.py` | Training plan, planned session, upcoming sessions, and checkpoint response schemas |
| `workout.py` | Today's workout view, generated workout, workout step, and explicit generation response/conflict schemas |

### Coach
| File | Responsibility |
|---|---|
| `coaching.py` | Coaching message list, single message response, and first-message conflict schemas |

## Architecture Notes
- All response schemas use `ConfigDict(from_attributes=True)` so `model_validate(row)` maps ORM rows directly to Pydantic models.
- Onboarding schemas enforce strict validation at the boundary: IANA timezone validation via `zoneinfo`, per-`GoalType` required-field rules, and immutable-field rejection on profile PATCH.
- JSONB columns are declared as `dict` — shape enforcement lives in the service layer, not schemas.
- `WorkoutTarget` schema preserves `theoretical_targets` / `adjusted_targets` as a two-column shape even when they are byte-equal (Phase 1.5b), preventing data-shape migrations when modifier services land.
