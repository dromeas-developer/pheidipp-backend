# Phase 1 — Skeleton MVP
*The full coaching loop with no real training data*

## Hypothesis

Can the coaching voice feel personal and useful before any real training data exists?
An athlete should be able to onboard, receive a first coach message that feels specific
to them, see a generated workout, log a session manually, and receive a post-workout
analysis — all without a single FIT file or device sync.

## Twin State at Completion

Tier 3 bootstrap throughout. Confidence: LOW. Coaching language is conservative —
targets expressed as effort descriptions and ranges, never precise numbers.
All threshold estimates from age-graded population norms. No real training data.

## Sub-Phases

| Sub-phase | Title | Key deliverable |
|---|---|---|
| 1a | Core Domain Models | Full DB schema: all domain models built right first time |
| 1b | Authentication & Security | JWT auth, token lifecycle, route protection |
| 1c | Onboarding API | Atomic questionnaire → twin bootstrap transaction |
| 1d | Plan Generation | Pure-Python periodised training plan from twin state |
| 1e | Coaching Agents Foundation | First message + day-of workout generation agents |
| 1f | Activity Logging & Post-Workout | Manual session logging + first post-workout analysis |

## Done Criteria

- Onboard as a new athlete and receive a first coach message that feels written for
  this specific athlete — not a template. Paragraphs reference the athlete's sport
  background, structural risk if flagged, and the arc toward their goal event.
- Receive a generated workout appropriate for the athlete's data tier and estimated
  fitness. Targets are coherent relative to the plan phase.
- Log a session manually and receive a post-workout analysis that references the
  planned session, notes compliance or divergence, and coaches specifically on what
  was done — not what the plan said.
- The training plan shows a coherent multi-phase periodised structure with the correct
  phase arc for the goal event distance and time available.

## Go / No-Go for Phase 2

All four done criteria must pass. Additionally:
- Coach messages pass a voice quality review — no template feel, no raw numbers
  without context, no generic encouragement
- The onboarding transaction is atomic — partial onboarding state is impossible
- All athlete-scoped routes require a valid JWT and athlete identity match
