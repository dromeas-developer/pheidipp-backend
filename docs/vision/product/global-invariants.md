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

**The athlete is never exposed to system complexity.** When services fail, data is temporarily unavailable, or processing is delayed, the athlete sees a calm, honest message — not an error code, not a loading spinner, not a technical explanation. The system absorbs its own complexity and presents only what the athlete needs to know. Failures are communicated as temporary pauses, not broken states. The coach pauses and asks again later; it does not panic or disappear.

---

## Physiological Safety Invariants

These invariants protect the athlete from training patterns that increase injury or overtraining risk. They are enforced by the plan generation system and respected by all coaching logic.

**No unsafe load spikes.** Weekly training load must not increase by more than 10%. This prevents the rapid volume or intensity progressions that precipitate overuse injuries. The rule applies to total weekly load and to individual session load.

**No incompatible intensity stacking.** No hard sessions on consecutive days. Intense efforts require neuromuscular recovery that a single easy day does not provide. The system enforces at least one easy or rest day between quality sessions.

**Minimum recovery spacing.** At least 48 hours between intense efforts. This ensures adequate neuromuscular and structural recovery regardless of session type. A hard session Monday followed by another hard session Tuesday violates this invariant.

**No overlapping tapers.** The system cannot taper for multiple races simultaneously. Tapering reduces training stress to preserve fitness for a specific event. Tapering for two events at once means neither receives adequate preparation. When races are too close, the system selects the higher-priority race for tapering.

---

## Race Priority Invariants

These invariants preserve the integrity of the athlete's primary goal when secondary events exist.

**A-race always takes precedence.** When a conflict arises between a B-race or C-race and the A-race, the A-race wins. B- and C-races are tools to prepare for the A-race, not independent goals that compete for resources.

**Secondary events outside A-race taper.** B-races and C-races cannot be scheduled within the A-race taper or race week. The taper is a delicate physiological window. Introducing race stress during this period compromises the peak the entire plan was designed to produce.

---

## Planning Boundary Invariants

These invariants define the boundaries of what the system will and will not plan.

**Training length gate.** Goals beyond the planning horizon for their goal type and experience level trigger an intermediate goal proposal. Each race distance has a maximum planning window — longer horizons produce unreliable plans because too many variables remain uncertain. See plan-generation for the full gate logic.

**Running-only twin model.** Non-running activities are excluded from twin calibration. This is an accuracy decision. Cross-modal conversions — swim sessions translated into equivalent running stress, strength sessions assigned arbitrary scores — introduce errors that compound over time. The twin holds its judgement on non-running sessions and waits for the next run.

**Honesty invariant.** Plans never pretend to know more than the twin knows. If confidence is low, the plan says so. If a metric is uncertain, the plan uses conservative ranges rather than false precision. Trust is built through honesty, not through the appearance of certainty.

---

## Schedule Invariants

These invariants protect the athlete's autonomy and the plan's structural integrity.

**Workouts only on available days and times.** The plan respects the athlete's stated availability. Sessions are never placed on days the athlete has marked as unavailable, regardless of optimisation pressure.

**Primary sessions are scheduled to allow adequate recovery. Secondary sessions on the same day are permitted when they don't interfere with the primary session's recovery.** This supports doubles scheduling where secondary sessions (non-running suggestions like strength, yoga, mobility) are placed in the PM slot after a primary running session, without compromising the recovery window measured between primary sessions.
