# Global Invariants

This document defines the immutable truths of Pheidipp. These principles shape product behavior, coaching behavior, UX decisions, adaptation systems, and platform boundaries. Any feature or implementation that violates these invariants is misaligned with the product.

Pheidipp is a coach, not a dashboard. The product exists to guide athletes through expert running coaching, not to maximize metrics exposure or become an analytics platform. Data exists solely to support coaching decisions and athlete understanding.

Complexity must remain hidden. Internal sophistication should never create UX complexity. The athlete receives clarity, direction, and concise guidance because the system absorbs all complexity.

The digital twin is the single source of truth. The system continuously maintains an evolving, running-specific understanding of the athlete, and all adaptation, coaching, and recommendations flow through this twin. There is no parallel decision path — the twin is the intelligence layer of the product.

The system must never pretend certainty. Confidence must match available evidence, which means low-confidence situations produce softer recommendations, cautious interpretation, and reduced decisiveness. False precision permanently damages trust.

Running performance requires sport-specific modeling. General fitness proxies are insufficient for running adaptation, so running remains central to progression measurement, adaptation learning, and performance understanding. Other activities may influence recovery context but never calibrate the core model.

Conclusions matter more than metrics. Athletes should rarely need to interpret raw data manually because the system synthesizes information into actionable guidance, clear decisions, and meaningful context. If coaching requires metric interpretation, it has failed.

Simplicity compounds value. Every additional setting, workflow, metric, chart, or customization surface must justify its existence against core coaching value. Minimalism is intentional and protective of the athlete experience.

Trust compounds slowly and breaks instantly. The system prioritizes honesty about limitations, transparency in reasoning, consistency in behavior, and predictability in outcomes. This is especially critical under uncertainty — the product never optimizes for short-term engagement over long-term trust.