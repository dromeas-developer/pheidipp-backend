# Cold Start Strategy
*How the twin initialises before an athlete has real training data*

## Three Confidence Tiers

The twin starts from one of three tiers depending on what data is available at onboarding. The system is always honest about which tier it is operating from, and all downstream decisions — plan conservatism, target ranges, coaching certainty — are weighted accordingly.

**Tier 1 — Imported training history.** The athlete connects an existing training platform and the system ingests real historical workout data. The twin is built from actual physiology, not assumptions. This is the richest starting point and produces the most personalised initial coaching. Athletes in this tier can also supplement with lab/test uploads to provide additional threshold precision.

> **Implementation:** Tier 1 athletes start at LOW confidence but transition quickly (1–3 sessions to MEDIUM). See [`confidence-model.md`](../../architecture/00-foundations/confidence-model.md#initial-confidence-by-onboarding-tier) for evidence weight thresholds and transition conditions.

**Tier 2 — Peer-similar athletes OR Lab/Test Uploads.** For athletes with no importable history, the twin bootstraps either from anonymised models of similar athletes OR from athlete-provided physiological benchmarks. Lab/test uploads provide higher threshold confidence than peer-based inference, but execution patterns and adaptation signatures still require real training data to develop.

> **Implementation:** Lab tests provide immediate high-weight evidence (12–15 units), often jumping tested metrics directly to MEDIUM. Peer-similar bootstrapping starts at LOW with faster transition than Tier 3. See [`confidence-model.md`](../../architecture/00-foundations/confidence-model.md#initial-confidence-by-onboarding-tier) for threshold details.

Confidence transitions are quality-weighted. Each physiological parameter accumulates evidence independently based on observation quality. A single lab test carries more evidence than multiple easy sessions with optical HR. The system weighs observation quality when determining when to upgrade confidence levels — it is the quality of the data, not just the quantity, that drives confidence forward. For LT1 specifically, the system builds confidence passively from natural training patterns — analyzing HR response in easy runs, drift during long efforts, and recovery after stopping — without requiring special test sessions.

**Tier 3 — Questionnaire inputs only.** The most conservative baseline, built from onboarding responses alone. Initial targets are expressed as ranges or effort descriptions rather than precise numbers. The twin becomes more confident and specific as real training data accumulates over the following weeks.

> **Implementation:** Initial confidence is LOW. This tier requires the most real training data to accumulate evidence (6–10 sessions to MEDIUM). See [`confidence-model.md`](../../architecture/00-foundations/confidence-model.md#initial-confidence-by-onboarding-tier) for transition conditions and velocity estimates.

## What Honest Confidence Looks Like

A Tier 3 athlete does not receive aggressive targets on day one. The coach language reflects genuine uncertainty: "based on what you've described," "let's see how this feels," "we'll calibrate as we see your actual data." This is not a degraded experience — it is accurate coaching at the information level available.

As sessions accumulate and the twin observes real execution, threshold estimates, recovery patterns, and fatigue responses, confidence upgrades and the coaching becomes correspondingly more precise. The athlete earns specificity from the model by training with it.

## Onboarding Time to Value

The model build takes a few minutes — not instant, not an hour. This communicates that something real is being computed, not a template being applied. While the model builds, the athlete explores the app and sets their goal race or objectives. When the model is ready, the first coach message appears.