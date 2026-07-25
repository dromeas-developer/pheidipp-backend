# Taxonomy Refinement — Calculation Error Disambiguation Rule

> Drafted by p-agent-architect. Route to p-vision-and-architect-author
> (via p-technical-advisor) for application to
> `docs/architecture/04-platform/root-cause-taxonomy.md`.
> This is a documentation change to an architecture doc — outside
> p-agent-architect's direct authority.

## Target File

`docs/architecture/04-platform/root-cause-taxonomy.md`

## Target Section

"Comparing Against the Plan" (currently lines 96–106)

## Proposed Addition

Append the following after the existing "Comparing Against the Plan"
section content (after the current last paragraph about Infrastructure-
category calls not needing plan comparison):

```markdown
### Calculation Error Disambiguation

When a test failure is a numeric mismatch — the code's output for a
computational invariant (formula, decay, threshold, ratio) does not
match the test's expected value — use the three-way comparison below
to classify the root cause. This applies only to computational
invariants, not to structural failures (missing fields, wrong event
ordering, layer violations).

| Plan fixture | Code output | Test assertion | Category | Owner |
|---|---|---|---|---|
| Exists, pins expected value | ≠ fixture | = fixture | Implementation | p-coder |
| Exists, pins expected value | = fixture | ≠ fixture | Test Suite | p-test-architect |
| Exists, pins expected value | ≠ fixture | ≠ fixture | Implementation (code is wrong; test may also be wrong — fix code first, re-check test) | p-coder |
| Does not exist | any | any | Specification / Plan Gap | p-implementation-architect |

The third case (Specification / Plan Gap) should shrink toward zero
once the implementation architect's RC1 fixture gate is enforced —
computational invariants without a pinned fixture fail contract
saturation before the plan reaches the coder.

**Evidence requirement:** For Implementation or Test Suite
classifications, the RC entry must cite the plan fixture's exact
values (input, expected output, tolerance) alongside the observed
code output or test assertion. "The number is wrong" is not
sufficient evidence — state both numbers.
```

## Rationale

The current taxonomy has a three-way split (Implementation / Test Suite /
Specification/Plan Gap) but no disambiguation rule for the specific case
where a computational invariant's numeric output is wrong. Without this
rule, triage agents (p-devops, p-implementation-validator) must
re-derive the three-way call from first principles each time a numeric
test fails, leading to inconsistent routing.

The RC1 fixture gate (applied to p-implementation-architect) ensures
plans now pin numeric fixtures for computational invariants. This
taxonomy refinement is the downstream complement: it tells the triage
agent how to use that fixture to route the failure correctly.

## Scope

This is a Minor Gap per the taxonomy's own classification — it adds
clarification to an existing section without changing the Category →
Owner table, confidence levels, or grouping rules. It does not
introduce a new category; it refines the decision procedure for an
existing three-way call.
