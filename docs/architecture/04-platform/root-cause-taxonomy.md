# Root Cause Taxonomy

Shared vocabulary for classifying failures in DevOps and validation
reports. Consumed by `p-devops` (primary) and referenced by
`p-implementation-validator` for routing alignment. Both agents use the
same category definitions, owner mapping, and confidence levels so that
routing is consistent regardless of which agent triages first.

---

## Grouping Rule

Before assigning categories, cluster failures that share the same
underlying cause into a single Root Cause (RC). If 50 tests fail because
of one enum-serialization bug, that is one RC listing its member tests —
not 50 RC entries. Use error type, traceback signature, and shared
module/file as your clustering signal. List representative test names
(a handful) plus a total count when the member list is long; the
exhaustive list still belongs in `## Full Failure Detail`, tagged by
RC id.

---

## Category → Owner Mapping

| Category | Meaning | Default Owner |
|---|---|---|
| **Implementation** | Application code contradicts the plan/contract, or is genuinely wrong relative to intended behaviour. | `p-coder` |
| **Test Suite** | The test *content* is wrong — a bad assertion, stale expectation, incorrect fixture data, or a test helper that computes or wires the wrong thing (e.g. a foreign-key helper building the wrong relationship, a default timestamp that's simply incorrect). This is about what a test or its support code *returns or asserts*, not about the platform it runs on. | `p-test-architect` |
| **Infrastructure** | Environment, tooling, or platform failure — Docker configuration, CI environment, dependency installation, Alembic configuration, PostgreSQL startup, permissions, networking, path configuration, pytest plugin configuration, environment variables. This is about whether the run could execute at all, not about what any individual test does. | `p-devops` |
| **Specification / Plan Gap** | Code and test are internally consistent with each other, but the plan does not clearly state which behaviour is correct, so category cannot be determined from plan text alone. | `p-architect` (the plan owner in this pipeline — same routing `p-implementation-validator` uses for its own "PLAN GAP" findings) |
| **Investigation Required** | None of the above could be established at Medium confidence or higher. | `Unassigned` |

**Infrastructure and Test Suite are the pair most likely to be confused —
they are not the same thing.** Infrastructure is about whether the
platform runs at all: containers, connections, configuration, the
environment underneath the tests. Test Suite is about whether the test's
own logic and data are correct: what a fixture returns, what a helper
computes, what an assertion expects. The question to ask is **"does the
fix live in test *content* (what a fixture/helper/assertion does), or in
the platform/tooling underneath it?"** Content → Test Suite. Platform →
Infrastructure.

### Illustrative examples

| Symptom | Category | Owner |
|---|---|---|
| A test's own setup uses a stale or incorrect default timestamp | Test Suite | p-test-architect |
| A foreign-key test helper builds the wrong relationship | Test Suite | p-test-architect |
| A Docker container fails to start or never reports healthy | Infrastructure | p-devops |
| Alembic cannot connect to the database, or a required extension is missing | Infrastructure | p-devops |
| An enum is serialized with `.value` where the contract expects `str(enum)` (or vice versa) | Implementation | p-coder |
| No migration revision file exists because the coder never generated one | Implementation | p-coder — the omission is the coder's, not the environment's |
| Migration generation was attempted but the script itself failed due to environment/Alembic configuration | Infrastructure | p-devops — distinct from the row above: here generation was attempted and the tooling broke, not skipped |

### Default owners may be overridden — with a stated reason

The table above gives defaults, not absolutes. Override a default owner
only when the *remedy*, not just the mechanical category, genuinely
belongs elsewhere — and always state the override reason explicitly in
the RC entry; never deviate silently. For example, a failed manifest
write is mechanically an Infrastructure-category problem, but its remedy
is a manual correction to a file only `p-test-architect` owns, so it
routes there by explicit override rather than to `p-devops` by default.

---

## Confidence Levels

| Level | Criterion |
|---|---|
| **Confirmed** | You traced the exact failing line/mechanism AND compared it directly against explicit plan text (or, for a Test Suite issue, against the test's own code) with no reasonable alternative reading. |
| **High** | The category is strongly implied by error type/location/pattern, but you did not do a direct word-for-word plan comparison, or the plan strongly implies the answer without stating it explicitly. |
| **Medium** | A plausible category was pattern-matched from the traceback shape alone, without confirming against plan text at all — or the plan text exists but is not fully unambiguous. |
| **Low** | Multiple explanations remain plausible, or no useful textual evidence could be gathered. |

**Any RC at Low confidence is routed to `Unassigned` regardless of its
tentative category.** A low-confidence guess routed to `p-coder` or
`p-test-architect` is exactly the misrouting failure mode this structure
exists to prevent — say what you suspect, but do not assign ownership on
a guess.

---

## Evidence Standard

Every RC's `Evidence` field is a short bulleted list of what you actually
did and observed — the specific assertions/traceback lines you looked at,
which file you inspected, what you found there, and the conclusion it
supports — not a single summary sentence. The goal is that the owner
reading your report does not have to repeat your investigation to trust
your conclusion.

---

## Comparing Against the Plan

For Implementation vs. Test Suite vs. Specification/Plan Gap calls
specifically, fetch the implementation plan named in the validator report
header (`docs/implementation/<path-to-plan>.md`) via `get_files`, once,
batched with any other fetches. Read only the Implementation Steps,
Invariants, or Event Contracts sections relevant to the failing RC's
subject — do not read the whole plan speculatively for every RC if one
targeted section answers it. Infrastructure-category calls do not need
this — they are diagnosed from the platform/environment evidence itself,
not the plan.
