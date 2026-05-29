# Physiological Thresholds — Layer 2
*Dynamic functional zones that evolve with the athlete's actual training*

## Philosophy

RPE is intentionally not a primary signal. It is too subjective and too noisy at the
individual level — the same effort feels different after poor sleep, in heat, or at
different points in a training block. The twin derives threshold estimates from objective
signals captured during normal training.

Thresholds — LT1, LT2, FTP, max HR, VO2max estimate — are not static numbers set at
onboarding. They are living values, tracked continuously and updated from training data
rather than waiting for dedicated test sessions.

## Signal Hierarchy

The richness of threshold detection depends on available hardware. The twin works with
whatever signal is available and is explicit about the confidence level of its estimates.

**Raw RR intervals from chest strap** — the richest signal. The twin processes raw RR
interval data, performs artifact detection and cleaning internally, and extracts HRV
inflection points during appropriate workout types. This enables continuous passive
threshold tracking — the athlete trains normally and the model updates without any
dedicated test sessions required.

**HR-based signals without RR** — for athletes using optical HR or chest straps that
do not expose RR data. The twin works with HR deflection patterns, pace or power at a
given HR over time, and post-interval HR recovery curves. Less precise than RR-based
detection but meaningful accumulated over enough sessions.

**Dedicated calibration sessions** — structured sessions designed to elicit clear threshold
signals: progressive intensity blocks where the twin reads HR and power or pace response
at each step. A field approximation of a lab test using a protocol the system designed and
knows how to interpret. These are scheduled periodically, especially for athletes without
RR data.

**Lab/Test Uploads** — athlete-provided physiological benchmarks from recent lab tests,
field tests, or validated external assessments. These are treated as high-quality
calibration events when properly timestamped and contextualized. Unlike pure athletic
input, lab/test uploads carry documented provenance and measurement conditions that
allow the twin to weight them appropriately in the signal hierarchy.

When lab/test values diverge from observed training execution, the coach addresses this
through guided conversation rather than silent model adjustment. "Your recent 5K race
suggests higher sustainable HR than your lab test indicated. Want to explore this in
a calibration session?" This maintains the honesty invariant while respecting athlete
expertise.

**Inference from training history** — for athletes with limited data. Threshold
estimates derived from best efforts at various durations and the initial questionnaire
inputs. Confidence is low and flagged accordingly.

## Calibration Confidence Degradation

Threshold confidence degrades over time without fresh calibration signal, even for athletes
with extensive training history. Thresholds derived from lab tests or dedicated sessions lose
certainty as months pass without re-measurement. The twin tracks the time since last
calibration event and reflects this in its confidence scoring.

An athlete who uploaded a lab test 18 months ago should see coaching language that
acknowledges uncertainty: wider target ranges, more frequent calibration sessions suggested,
and coach language like "your lab test suggested X, but recent race performances indicate
you may have shifted." The model does not silently expire calibration, but it does
reflect growing uncertainty through its recommendations.

## Passive Calibration From Normal Training

The system continuously scans the training plan for sessions that will naturally produce
strong threshold signal — progressive tempo runs, longer threshold interval sessions, time
trial efforts. These are treated as dual-purpose sessions. The athlete executes their
normal training; the twin reads it as a calibration event simultaneously. No extra burden
on the athlete, no awareness required.

## New Athlete Calibration Period

Athletes with limited or no training history begin with a structured first period designed
to give the twin enough signal across different intensity domains to establish initial
threshold estimates with reasonable confidence. This is not framed as a test battery —
it is presented as an introduction to training with Pheidipp. It also serves as the
athlete's first full experience of the daily coaching voice, building the habit of engaging
with the product before serious training begins.

## Dynamic Test Frequency

How often dedicated calibration sessions are scheduled depends on data richness per athlete.
Athletes with RR interval data have passive monitoring every session, so dedicated tests are
infrequent — roughly once per training block or when the model detects an anomaly that
passive monitoring cannot resolve. Athletes without RR data receive more frequent
calibration sessions woven into the training plan.

Lab/test uploads are always welcome as calibration refresh events, regardless of hardware
tier. An athlete who completes a new threshold test should be able to upload results and
immediately benefit from updated threshold confidence.

## Two-Column Target Display

Every generated workout shows two sets of targets side by side:
- **Theoretical targets** — derived from the athlete's current dynamic zones as modelled
  by the twin. These reflect the twin's live understanding of the athlete's fitness state.
- **Adjusted targets** — the coach's recommendation for today, after applying current
  recovery and readiness state and the weather forecast for the athlete's training window.

The athlete always sees both. This distinction teaches the athlete over time how fatigue
and conditions affect their numbers — building genuine self-awareness rather than
just compliance with a single number.
