---
id: ADR-XXX
status: accepted | proposed | deprecated | superseded
tags: [tag1, tag2]          # e.g. database, async, architecture, timescale, api
supersedes: ~               # ADR-XXX or ~ if none
superseded-by: ~            # ADR-XXX or ~ if none
---

# ADR XXX: Title

## Rules
<!-- Machine-readable. Pure directives. No explanation. No duplication of stack-truth.md rules.
     Only rules that are unique to this decision and not already enforced globally. -->
- **Rule name**: one-line directive.
- **Rule name**: one-line directive.

## Decision
<!-- One paragraph. What was decided and the single clearest reason why.
     Do not re-explain what stack-truth.md or product-vision.md already covers. -->

## Rationale
<!-- Why this option over the alternatives. Concise — 3–6 bullets max.
     Do not explain FastAPI, SQLAlchemy, or other foundational choices already captured elsewhere. -->
- Reason one.
- Reason two.

## Alternatives Rejected

| Option | Why Rejected |
|---|---|
| Alternative A | One-line rejection reason. |
| Alternative B | One-line rejection reason. |

## Tradeoffs
<!-- What this decision costs. Honest, not defensive. -->
- **Pro**: one line.
- **Con**: one line.

## Compliance

**Compliant**
```python
# Minimal example — the smallest code that demonstrates the rule.
```

**Non-compliant**
```python
# Minimal counter-example — one clear violation.
```

## Cross-References
<!-- Link related ADRs. One line per reference — what the relationship is, not what the ADR says. -->
- [ADR-XXX: Title](./XXX-slug.md) — relationship to this decision.