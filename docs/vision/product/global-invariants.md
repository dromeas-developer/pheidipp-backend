# Global Invariants
*The immutable truths that govern all Pheidipp decisions — from product behaviour to coaching logic to architectural choices.*

---

This document defines the immutable truths of Pheidipp. These principles shape product behavior, coaching behavior, UX decisions, adaptation systems, and platform boundaries. Any feature or implementation that violates these invariants is misaligned with the product.

---

## Product Identity Invariants

These invariants define what Pheidipp is and is not. They protect the product's strategic clarity and prevent identity drift.

**Pheidipp is a coach, not a dashboard.** The product exists to guide athletes through expert running coaching, not to maximize metrics exposure or become an analytics platform. Data exists solely to support coaching decisions and athlete understanding.

**Complexity must remain hidden.** Internal sophistication should never create UX complexity. The athlete receives clarity, direction, and concise guidance because the system absorbs all complexity.

**The digital twin is the single source of truth.** The system continuously maintains an evolving, running-specific understanding of the athlete, and all adaptation, coaching, and recommendations flow through this twin. There is no parallel decision path — the twin is the intelligence layer of the product.

**Running performance requires sport-specific modeling.** General fitness proxies are insufficient for running adaptation, so running remains central to progression measurement, adaptation learning, and performance understanding. Other activities may influence recovery context but never calibrate the core model.

---

## Trust Invariants

These invariants protect the athlete's trust in the system. Trust is the product's most valuable asset and its most fragile.

**The system must never pretend certainty.** Confidence must match available evidence, which means low-confidence situations produce softer recommendations, cautious interpretation, and reduced decisiveness. False precision permanently damages trust.

**Conclusions matter more than metrics.** Athletes should rarely need to interpret raw data manually because the system synthesizes information into actionable guidance, clear decisions, and meaningful context. If coaching requires metric interpretation, it has failed.

**Trust compounds slowly and breaks instantly.** The system prioritizes honesty about limitations, transparency in reasoning, consistency in behavior, and predictability in outcomes. This is especially critical under uncertainty — the product never optimizes for short-term engagement over long-term trust.

**Simplicity compounds value.** Every additional setting, workflow, metric, chart, or customization surface must justify its existence against core coaching value. Minimalism is intentional and protective of the athlete experience.

---

## Physiological Safety Invariants

These invariants protect the athlete from training patterns that increase injury or overtraining risk. They are enforced by the plan generation system and respected by all coaching logic.

**No unsafe load spikes.** Acute load increase must not exceed 10% week-over-week. This prevents the rapid volume or intensity progressions that precipitate overuse injuries. The rule applies to total weekly load and to individual session load.

**No incompatible intensity stacking.** No back-to-back Zone 4–5 sessions. High-intensity efforts require neuromuscular recovery that a single easy day does not provide. The system enforces at least one easy or rest day between quality sessions.

**Minimum recovery spacing.** At least 48 hours between hard sessions. This ensures adequate neuromuscular and structural recovery regardless of session type. A threshold session Monday and a VO2max session Tuesday violates this invariant.

**No overlapping tapers.** The system cannot taper for multiple races simultaneously. Tapering reduces training stress to preserve fitness for a specific event. Tapering for two events at once means neither receives adequate preparation. When races are too close, the system selects the higher-priority race for tapering.

---

## Race Priority Invariants

These invariants preserve the integrity of the athlete's primary goal when secondary events exist.

**A-race always takes precedence.** When a conflict arises between a B-race or C-race and the A-race, the A-race wins. B- and C-races are tools to prepare for the A-race, not independent goals that compete for resources.

**Secondary events outside A-race taper.** B-races and C-races cannot be scheduled within the A-race taper or race week. The taper is a delicate physiological window. Introducing race stress during this period compromises the peak the entire plan was designed to produce.

---

## Planning Boundary Invariants

These invariants define the boundaries of what the system will and will not plan.

**Training length gate.** Goals more than 24 weeks away trigger an intermediate goal proposal. The system does not attempt to plan training horizons where too many variables remain uncertain. See training-plan-generation for the full gate logic.

**Running-only twin model.** Non-running activities are excluded from twin calibration. This is an accuracy decision. Cross-modal conversions — swim sessions translated into equivalent running stress, strength sessions assigned arbitrary scores — introduce errors that compound over time. The twin holds its judgement on non-running sessions and waits for the next run.

**Honesty invariant.** Plans never pretend to know more than the twin knows. If confidence is low, the plan says so. If a metric is uncertain, the plan uses conservative ranges rather than false precision. Trust is built through honesty, not through the appearance of certainty.

---

## Schedule Invariants

These invariants protect the athlete's autonomy and the plan's structural integrity.

**Workouts only on available days and times.** The plan respects the athlete's stated availability. Sessions are never placed on days the athlete has marked as unavailable, regardless of optimisation pressure.

**One session per day.** A plan never schedules two sessions on the same day. This preserves the structural clarity of the plan and prevents the accumulation of fatigue from multiple daily efforts.
