# Predicted Race Time & Weather Response
*A living estimate that improves as the athlete does*

## The Predicted Race Time

The twin continuously produces a predicted finish time for the athlete's goal event. This
is a living number that updates as fitness evolves through the training block — not a
one-time estimate calculated at onboarding and forgotten.

The predicted time is visible on the home view. Watching it improve as fitness builds
through a training block is one of the most quietly motivating elements of the product.
The number makes abstract fitness gains concrete and visible.

For athletes pursuing race goals with registered B-races, secondary predictions are also produced. See secondary-events for the coaching approach. These appear alongside the primary prediction and serve a different
coaching purpose. Where the primary prediction shows "what you're aiming for," the
B-race prediction shows "what I recommend targeting" — a conservative, controlled
effort based on your current fatigue state and fitness level. The coach message specifies
the exact pace/power/time target to ensure the B-race provides valuable feedback while
protecting your primary goal preparation. This preserves the training plan integrity
while still providing meaningful race experience.

## Baseline Prediction

Derived from the twin's current threshold estimates, aerobic capacity indicators, and
running economy signals. Assumes standard conditions: flat course, moderate weather,
well-rested athlete. Updated after every significant training block as the twin's fitness
estimates shift.

## Weather-Adjusted Prediction

In the weeks before the race, the system fetches the race day weather forecast and applies
the athlete's personalised weather response to produce a weather-adjusted estimate. Both
the baseline and weather-adjusted predictions are shown with a plain-language explanation
of the difference. "Based on the forecast for race day — 26°C and humid — your adjusted
target is around two minutes slower than your baseline estimate."

This is not a generic calculator correction. It is a projection based on this athlete's
actual execution history in similar conditions, not a population average adjustment.

## Course Profile Adjustment

If the race course profile is available — ideally provided by the athlete at goal-setting
— the prediction incorporates elevation data. A hilly course with significant climbing
adjusts the target time based on the athlete's demonstrated performance on grade-adjusted
efforts.

Course data is also a training input: a race with substantial elevation triggers
hill-specific sessions in the plan, downhill running practice for quad conditioning,
and appropriate adjustment of volume distribution across terrain types.

## Personalised Weather Response Modelling

The twin accumulates data on how this specific athlete's performance responds to
environmental conditions across every session. Not how athletes in general respond to
heat — how this athlete responds. Some are heat resilient. Others degrade significantly
above 18°C. Some are affected more by humidity than dry heat. These individual response
curves are learned from actual execution data, not assumed from population averages.

After every session the post-workout analysis includes the environmental conditions as
context for interpreting execution. A pace that looks slow in isolation looks different
when the system notes it was 28°C with 80% humidity. Over time this builds a rich picture
of the athlete's performance envelope across conditions.

The weather response model also feeds back into training design. If an athlete consistently
trains in mild conditions but their goal race is in summer heat, the system identifies this
as a preparation gap and proactively suggests deliberate heat exposure sessions as part
of the plan.
