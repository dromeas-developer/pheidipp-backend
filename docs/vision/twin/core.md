# The Digital Twin — Core Concept
*What it is, what it sees, and what it deliberately does not see*

## What the Twin Is

The Digital Twin is the engine underneath everything. It models the athlete's physiological
state based on all available data — training history, wellness metrics, recovery trends,
workout execution patterns. It is the source of truth for all coaching decisions and is
continuously updated as new data arrives.

The twin is a running model. Every layer — load computation, threshold tracking, execution
analysis, adaptation signature — is calibrated for running physiology, running mechanics,
and running-specific data signals.

## The Running-Only Boundary

Non-running activities appear in the training record and the coach acknowledges them.
The coach can prescribe aqua jogging during injury recovery, strength and conditioning
sessions, yoga and mobility work. But these activities are excluded from twin calibration
entirely.

They do not contribute to fitness or fatigue scores, threshold estimates, adaptation
signature learning, or execution pattern analysis.

This is not a limitation — it is the decision that keeps the running model accurate. A twin
that absorbs swimming and strength sessions alongside running introduces cross-modal
conversion errors that corrupt the signals the model depends on. The boundary is clean:
**the twin sees running; the training record sees everything.**

## The Twin Is Always Honest About Confidence

Every estimate the twin produces carries an internal confidence level that affects
downstream decisions. Conservative coaching language, target ranges rather than point
estimates, and cautious plan structures are the natural output of a low-confidence twin.
As real data accumulates and the model learns this specific athlete, confidence grows and
coaching becomes more precise.

The twin never pretends to know more than it does. This is an invariant, not a UX choice.
