---
name: type-enforcement-conformance
description: >
  Load this at Step 6b of the implementation validation protocol when
  auditing type-system strictness, visibility correctness, and
  enforcement-layer placement in the implementation. Contains the
  check definitions, severity mappings, and illustrative classification
  rules for Layer 4 (Type-Enforcement Conformance). Loaded by
  p-implementation-validator only. Also used for retrospective audits
  of existing codebases where no plan exists — the codebase itself
  becomes the "plan" and findings route to p-coder-fix-mode for fixes.
---

# Type-Enforcement Conformance — Layer 4 Audit

## Purpose

This skill defines the fourth audit layer for `p-implementation-validator`.
Layers 1–3 (Plan Conformance, Contract Conformance, Deviation Detection)
check whether the code matches the plan. Layer 4 checks whether the code's
*type system* is used correctly to enforce contracts at the right boundary,
and whether visibility (public/private) is correct by design intent.

This layer is independent of the plan's stated contracts — it audits the
code's type discipline itself. A plan may not specify "use `Literal`
instead of `str`" (that's an implementation detail per the architect's
Level of Detail rules), but the code's type strictness still matters:
a loose type (`str` where `Literal` is implied) lets invalid data through
the schema boundary and into the service, where it becomes a bug that
tests cannot catch because the test also uses the loose type.

## When to Apply

**Per-plan validation:** Run as Step 6b, after Stack-Truth Conformance
(Step 6) and before Classification (Step 7). Audit every file loaded in
Step 2 (the plan's scope files).

**Retrospective audit (no plan):** When invoked to audit an existing
codebase with no plan, the codebase itself is the subject. Every file
in the requested scope is audited against the rules below. Findings
route to `p-coder-fix-mode` for fixes — there is no plan to route back to.

## Checks

### Check 1 — Visibility Correctness

For every function and method in scope, verify visibility is correct:

| Signal | Finding | Severity |
|---|---|---|
| Function/method is public (no `_` prefix) but only called internally within the same module | Should be private | MINOR |
| Function/method is private (`_` prefix) but referenced from outside its module (imported or called cross-module) | Should be public | MAJOR |
| Function/method is private and only used in tests (accessed via `# type: ignore` or direct `_` access) | Design smell — either make it public with a clear contract, or restructure the test to use the public API | MINOR (flag as observation, not a fix) |

**How to detect:** Use `s-code-structure-explorer` to get the module's
classes and functions, then `get_importers` to find cross-module references.
A private symbol referenced from outside its defining module is a MAJOR
finding. A public symbol with no cross-module references is a MINOR
finding.

### Check 2 — Type Strictness

For every function/method signature and Pydantic schema field in scope,
verify the type is as strict as the contract implies:

| Signal | Finding | Severity |
|---|---|---|
| Parameter or return type is `str` where the domain implies a fixed set of values | Should use `Literal[...]` or an `Enum` | MINOR |
| Parameter or return type is `Any` where a concrete type is inferable from the contract | Should use the concrete type | MINOR |
| Pydantic field uses `str` where the architecture defines an `Enum` for the same concept | Should use the `Enum` | MAJOR |
| Optional field (`X | None`) where the contract says the field is always present | Should be non-optional | MAJOR |
| Return type annotation missing on a public function | Should be annotated | MINOR |
| Parameter type annotation missing on a public function | Should be annotated | MINOR |

**How to detect:** Use `s-code-structure-explorer` to get function
signatures (parameters, return types). Cross-reference `str`-typed
fields against architecture enums via `s-contract-verifier`. Missing
annotations are visible directly from the structure report.

### Check 3 — Enforcement Layer Placement

For every input validation rule the plan specifies (from RC6's
enforcement-layer classification), verify the enforcement is at the
stated layer:

| Plan says enforcement is at | Code actually enforces at | Finding | Severity |
|---|---|---|---|
| Type system (Pydantic schema) | Service-layer validation | Enforcement at wrong layer — schema should reject before service sees it | MAJOR |
| Type system (Pydantic schema) | Database constraint | Enforcement at wrong layer — too late, invalid data reaches the service | MAJOR |
| Application logic (service) | Pydantic schema | Enforcement at wrong layer — business rule in the schema, not the service | MAJOR |
| Database constraint | Service-layer validation | Acceptable — defense in depth, but the DB constraint should also exist | MINOR (flag missing constraint) |
| Not stated in plan | Any layer | Plan gap — route to p-implementation-resolver | MAJOR (Plan Gap) |

**How to detect:** Cross-reference the plan's RC6 enforcement-layer
classification (if present in the `-tests.md` scenarios or the plan's
Invariants section) against the actual code. If the plan says "Pydantic
schema rejects negative values" but the code has the check in the
service, that's a MAJOR finding. If the plan has no RC6 classification
for an input the code validates, that's a Plan Gap.

**Retrospective audit (no plan):** Skip this check — without a plan's
RC6 classification, there is no stated enforcement layer to compare
against. Checks 1 and 2 still apply.

### Check 4 — Custom Validator Presence

For every custom validation rule in scope (rules that cannot be expressed
by a type annotation alone — cross-field validation, conditional
required fields, format checks beyond what Pydantic provides natively):

| Signal | Finding | Severity |
|---|---|---|
| Custom validation rule exists in the plan or is implied by the contract, but no `@field_validator` or `@model_validator` exists in the schema | Missing custom validator | MAJOR |
| `@field_validator` exists but does not cover a boundary case the contract implies | Incomplete validator | MAJOR |
| `@field_validator` exists but the validation logic duplicates a check already in the service | Enforcement duplication — remove from service or schema, not both | MINOR |

**How to detect:** Use `s-code-structure-explorer` to find
`@field_validator` and `@model_validator` decorators in schema files.
Cross-reference against the plan's stated validation requirements.

## Severity Summary

| Severity | Route | Resolution Path |
|---|---|---|
| MAJOR (visibility, type strictness, enforcement layer, missing validator) | p-coder-fix-mode | Implementation Fix (unless it crosses an architecture boundary — then p-implementation-resolver) |
| MINOR (naming, missing annotation, observation) | p-coder-fix-mode | Direct fix, no Resolution Path needed |
| MAJOR (Plan Gap — enforcement layer not stated in plan) | p-implementation-resolver | Architecture Change Required — plan needs RC6 classification |

## Output

Findings from this layer feed into the existing Validation Report
format (from the `validation-classification-and-report` skill). Add
them as a new section:

```markdown
## Layer 4: Type-Enforcement Conformance

| Check | Item | Severity | Route | Finding |
|-------|------|----------|-------|---------|
| Visibility | <symbol> | MAJOR/MINOR | p-coder-fix-mode/p-implementation-resolver | <description> |
| Type Strictness | <field/param> | MAJOR/MINOR | p-coder-fix-mode | <description> |
| Enforcement Layer | <input> | MAJOR | p-coder-fix-mode/p-implementation-resolver | <description> |
| Custom Validator | <schema> | MAJOR | p-coder-fix-mode | <description> |
```

For retrospective audits (no plan), produce a standalone report at
`reports/type-enforcement-audit-<scope>.md` using the same table
structure, with all findings routing to `p-coder-fix-mode` (no plan to route
back to).
