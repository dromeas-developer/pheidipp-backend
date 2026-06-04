# Confidence and Uncertainty

## The Core Principle

The twin is always honest about how much it knows. Evidence confidence is not a performance metric — it is a trust mechanism. Every estimate the twin produces carries an evidence confidence level that affects downstream decisions. Conservative coaching language, target ranges rather than point estimates, and cautious plan structures are the natural output of a low-evidence-confidence twin.

The twin never pretends to know more than it does. This is an invariant, not a UX choice.

---

## Why Confidence Matters

False precision destroys trust permanently. An athlete who receives a precise threshold target that turns out to be wrong will trust the coach less than one who was told "this is an estimate based on limited data — let's see how it feels." Confidence calibration ensures the coaching matches the evidence.

The system must never optimise for the appearance of accuracy over the reality of uncertainty. A low-confidence twin that communicates honestly builds more trust than a high-confidence twin that occasionally surprises the athlete with unexpected results.

---

## How Confidence Evolves

Evidence confidence grows through accumulated real training data. The twin starts from assumptions — questionnaire inputs, peer-similar models, or imported history — and progressively replaces those assumptions with observed physiology. Each calibration-eligible session provides evidence that refines the model.

The rate of evidence confidence growth depends on data quality. Athletes with chest straps and power meters accumulate evidence faster than those with optical HR only. Lab tests accelerate the process significantly. The twin is transparent about which data quality tier it is working with.

Evidence confidence is **per-metric**: each physiological parameter (LT1, LT2, CP, VO2max) accumulates evidence independently. A field test for LT2 increases LT2 confidence, not LT1 confidence. A lab test for LT1 increases LT1 confidence, not LT2 confidence. The system tracks accumulated evidence weight per metric, not just session count.

Evidence confidence transitions are quality-weighted. A single lab test carries more evidence than four easy sessions with optical HR. The system weighs observation quality when determining when to upgrade evidence confidence levels. For LT1 specifically, the system infers confidence from natural training patterns — HR ceiling in easy runs, HR drift analysis, and HR recovery analysis — building LT1 confidence passively from the 80% of training that occurs around aerobic intensity.

---

## What Confidence Controls

Evidence confidence affects three things:

**Coaching language precision.** At low evidence confidence, the coach speaks in ranges and effort descriptions. At high evidence confidence, the coach makes specific claims about thresholds and targets.

**Plan structure conservatism.** Low evidence confidence produces wider recovery buffers, more checkpoints, and more conservative load progressions. High evidence confidence enables tighter periodisation and more precise session targeting.

**Race prediction availability.** Race predictions are not surfaced at low evidence confidence. The system refuses to produce a number it cannot defend.

---

## The Honesty Invariant

Confidence represents evidence accumulated about the athlete. It is monotonic — it ratchets upward and never decreases. Evidence does not disappear when an athlete takes time off; the data remains valid even if the athlete has detrained. What changes is recommendation strength and calibration freshness, not the underlying evidence confidence. When the system accumulates evidence that supports a higher confidence level, it upgrades. The system handles two distinct scenarios differently:

**Data staleness:** When an athlete stops training or data becomes old, confidence stays at its current level. The prior decay mechanism handles uncertainty within the current confidence level — older observations carry less weight, making the estimate less certain without demoting the level. This avoids jarring coaching language changes from temporary data gaps.

**Algorithm improvement:** When a new algorithm improves interpretation, evidence confidence remains unchanged — the data itself has not changed. What changes is estimation certainty: the system's interpretation of that data has become more rigorous. The coach communicates this honestly: "We've improved our detection methods, and the precision of your threshold estimate has increased. Your targets will be more specific now."

The distinction is between time (data staleness) and correctness (algorithm improvement). The first is handled gracefully within the current level. The second requires honest reassessment.

---

## Algorithm Improvements

When the twin's calibration algorithms improve, recent history is reprocessed through the updated methodology. This means the athlete benefits from better threshold detection, improved adaptation modelling, or refined execution analysis without waiting for new data to accumulate.

The reprocessing is transparent. The coach explains what changed and why it matters for training. The athlete sees their targets adjust not because their fitness changed, but because the system's understanding of their fitness became more precise.

Historical coaching decisions are not retroactively modified. The athlete can see what the twin knew at each point in time, even if the twin's knowledge has since improved. This preserves the integrity of the coaching relationship while allowing the system to get smarter over time.

Coaching recommendations are always made using the best understanding available at the time. Improved models may produce more accurate future guidance, but they do not imply previous recommendations were incorrect.

---

## Communication Under Uncertainty

The coach never says "I don't know." Instead, it communicates the boundaries of what it knows:

- "Based on what you've described..." (Tier 3 cold start)
- "Your recent sessions suggest..." (low evidence confidence)
- "Your data shows..." (medium evidence confidence)
- "Your threshold is..." (high evidence confidence)

The athlete learns to read confidence through the specificity of the coaching. More specific language means more data behind it. This builds genuine self-awareness rather than blind compliance.

---

## Recommendation Strength

Recommendation strength is distinct from evidence confidence. It represents how strongly the coach is willing to act on the current model.

| Factor | Effect on Recommendation Strength |
|---|---|
| Stale calibration data | Decreases |
| Poor execution consistency | Decreases |
| Recent calibration signal | Increases |
| High data tier (RR + power) | Increases |

Recommendation strength can decrease while evidence confidence remains constant. An athlete with 500 workouts and lab testing has high evidence confidence. If they disappear for 6 months, their recommendation strength drops because the evidence is stale — but the evidence itself remains valid.

This separation creates an elegant athlete experience:
- Evidence confidence: "The system knows a lot about this athlete"
- Recommendation strength: "The system is cautious about current recommendations"