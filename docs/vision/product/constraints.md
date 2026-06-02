# Product Constraints & Boundaries
*What Pheidipp deliberately does not do, and why*

## Running-Only Twin Model

The Digital Twin is built for running and only running. This is an accuracy decision, not a limitation. Multi-sport platforms attempt to normalise load across activities using conversion factors — a swim session translated into equivalent running stress, a strength session assigned an arbitrary score. These conversions introduce errors that compound over time, gradually corrupting the model's understanding of actual running fitness and fatigue.

Pheidipp makes no such conversions. All twin calibration — load computation, threshold tracking, execution pattern analysis, adaptation signature — uses exclusively running data where physiological signals are clean and comparable across sessions.

The coach can and does prescribe non-running work when it serves the athlete's running goals: aqua jogging during injury, strength and conditioning, yoga and mobility sessions. These appear in the training record and the coach references them where relevant. But they are excluded from twin learning entirely. The twin holds its judgement on those sessions and waits for the next run to tell it what it needs to know.

## No Workout Builder

Athletes cannot create, edit, or customise workouts. The coach owns all workout design. This is intentional, not missing functionality.

The athlete's agency over any given session is limited to three choices: accept the planned workout, substitute from coach-suggested alternatives, or skip. Skipped sessions are absorbed by the weekly coaching rhythm — the next week's planning accounts for the disruption without breaking the overall plan. This boundary prevents complexity spiral, maintains coaching quality control, and keeps the product honest about what it is — a coaching system, not a training tool.

## No Raw Data Surfaces

Pheidipp does not display raw workout charts — HR over time, pace over time, power curves, cadence graphs. Athletes already have Garmin Connect, Strava, and intervals.icu for this, and those platforms do it well. Duplicating them inside Pheidipp would produce an inferior version of something the athlete already has and would pull the product toward the dashboard experience it is deliberately designed to avoid.

Every visualisation in Pheidipp must pass a single test: does this require the twin's context to produce? If it could be shown by Garmin or Strava, it does not belong here.

## Unsynced Workout Handling

When data gaps occur — watch not synced, battery died, session not completed — the system asks before assuming. The coach surfaces a simple check-in rather than silently making assumptions that could corrupt the twin model.

If yes (completed): athlete is prompted to sync or upload. Plan holds while pending. If no (not completed): treated as a skip with rescheduling options.
If no response: system holds judgement and asks again at next app open.

This ambiguity-first approach protects model accuracy over convenience.

---

## Same-Day Training Sessions

Advanced athletes sometimes train twice a day — an easy morning run plus an evening intensity session, or a double threshold day. The system supports this through AM/PM session slots with primary and secondary designation.

The primary session receives full workout generation with precise targets. The secondary session may be a suggested non-running session (strength, yoga, mobility) without detailed targets. Recovery time is measured from primary session to primary session, not session to session, reflecting the physiological reality that a morning easy run plus an evening threshold session provides more recovery than two hard sessions on consecutive days.

The weekly plan accounts for total athlete availability, including doubles capacity, when defining macro load. This ensures the training load reflects what the athlete actually trains, not just session count.
