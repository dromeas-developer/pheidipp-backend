# Twin Data Philosophy
*The deliberate accuracy decisions behind how the twin learns*

## Real Signals, Not Assumptions

The twin uses actual physiological data rather than estimated or inferred metrics wherever
possible. Grade-adjusted pace replaces raw pace to handle terrain variations honestly.
RR intervals are preferred over optical HR where available. Overnight minimum HR is used
as the resting HR anchor rather than a morning spot measurement that athletes stop taking.

Lab/test uploads are accepted as valid calibration inputs when properly documented with
provenance and measurement conditions. They represent the athlete's actual measured physiology
and are weighted accordingly in the signal hierarchy.

Where high-quality data is unavailable, the twin works with what exists and is explicit
about the resulting reduction in confidence.

## Data Quality Over Quantity

Sessions without device data — manual input, missing hardware — are logged for the
training record but excluded from twin calibration. Noisy or incomplete data corrupts
the model more than gaps do. A twin that learns from low-quality inputs drifts from
reality gradually and silently.

The twin always knows the data quality tier of each session and weights its learning
accordingly. The confidence level of its estimates reflects the quality of the data it
has been trained on.

## Continuous Learning From Real Training

The twin updates from every real training session, getting smarter over time rather than
applying static templates. Individual time constants, threshold estimates, adaptation
patterns, and behavioural profiles all improve as data accumulates. An athlete training
with Pheidipp for a year has a substantially more personalised twin than one who has
trained for a month.

## Non-Running Data Does Not Corrupt the Running Model

Strength sessions, swimming, cycling, yoga — all logged, none calibrated into the twin.
The temptation to assign arbitrary conversion factors ("this strength session was
equivalent to X minutes of running stress") is resisted entirely. These conversions
introduce small errors that compound over time into a model that no longer accurately
represents running fitness.

The twin waits for the next run. That is the signal it trusts.

## The Honesty Invariant

The twin is always honest about its confidence level. Conservative language, target ranges
rather than point estimates, and cautious plan structures are the natural output of genuine
uncertainty — not a product limitation. As confidence grows through accumulated data,
coaching becomes correspondingly more specific and more useful.
