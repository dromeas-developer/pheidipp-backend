# Ecosystem Findings Cache

> Maintained by p-agent-architect. Overwritten after every review, never appended.
> Keep under 100 lines. Condense aggressively.

**Last review:** 2026-07-24 — Fixture precision, enforcement layers, mock boundaries, type-enforcement audit, diagnostics-fixer scope

## Open Issues

- p-diagnostics-fixer: `bash: allow` with prompt-only command restrictions — risk of model drift escaping the guard. (Carried.)
- p-documentation Cleanup Mode: judgment-heavy rows heuristic remains fragile. (Carried.)
- p-history-explorer: Available on-demand but not wired into any standard pipeline. (Carried.)
- p-test-architect: `bash: allow` with prompt-only restriction (only `scripts/pytest.sh --collect-only`). Same risk class as p-diagnostics-fixer. (Carried.)
- **pyrightconfig.json: `reportPrivateUsage` not suppressed for tests** — 14 `# type: ignore[reportPrivateUsage]` comments in test_signal_cleaning_service.py alone. Needs per-directory config override. (Resolved — user applied `executionEnvironments` config.)
- **No type-enforcement audit agent** — RESOLVED. Created `type-enforcement-conformance` skill + added Step 6b to p-implementation-validator. Supports both per-plan validation and retrospective audit mode (no plan needed).

## Pattern Debt

- Scattered `# type: ignore[reportPrivateUsage]` in test files — should be suppressed at config level for `tests/`, not per-line.

## Agent State

| Agent | Status | Notes |
|---|---|---|
| p-implementation-architect | ✅ Updated | RC1 fixture gate (computational invariants require numeric fixtures). RC6 extended (input enforcement layer classification). Test Scenario Grill updated (enforcement + mock boundary + RC1 fixtures). |
| p-test-architect | ✅ Updated | Step 1 loads Enforcement + Mock Boundary from -tests.md. Step 6 consumes enforcement classification (skip type-system, one test per DB constraint, full branch for app-logic). Mock boundary rules (none/external-only/db-session). |
| p-coder | ✅ | No changes needed — one-session-per-BRD discipline already enforces sequencing. |
| p-devops | ✅ | No changes needed — Root Cause Triage already handles fault attribution. |
| p-diagnostics-fixer | ⚠️ | Runs on both app/ and tests/ (pyrightconfig includes both). Needs scope clarification for tests — see open issues. |
| p-implementation-validator | ✅ Updated | Added Step 6b (Type-Enforcement Conformance) with retrospective audit mode. Loads `type-enforcement-conformance` skill. Delegates visibility/type checks to p-code-structure-explorer. |
| p-consistency-validator | ✅ | No changes needed. |
| p-agent-architect | ✅ | skill: allow, todowrite-discipline loaded |
| p-technical-advisor | ✅ | todowrite-discipline loaded |
| p-release-strategy-architect | ✅ | todowrite-discipline loaded |
| p-vision-and-architect-author | ✅ | todowrite-discipline loaded |
| p-documentation | ✅ | skill: allow, todowrite-discipline loaded |
| p-diagnostics-fixer | ⚠️ | Intentional anti-todo-list — mechanical loop |
| p-manifest-manager | ✅ | Subagent for promote-file and release-promote operations |
| p-doc-explorer | — | Single-purpose subagent |
| p-contract-verifier | — | Single-purpose subagent |
| p-state-explorer | — | Single-purpose subagent |
| p-impact-analyzer | — | Single-purpose subagent |
| p-code-explorer | — | Single-purpose subagent |
| p-code-structure-explorer | — | Single-purpose subagent |
| p-history-explorer | — | Single-purpose subagent |
| p-index-health-guard | — | Single-purpose subagent |

## Fixes Applied This Session

1. **RC1 fixture gate** — Computational invariants (formulas, decays, thresholds, numeric transformations) must ship with concrete numeric fixtures (input → expected output, with tolerance) in the plan. Qualitative description alone is a GAP, same severity as a missing event contract. Gate lives in architect's own RC1 reasoning, not in p-contract-verifier's output.
2. **RC6 enforcement layer extension** — Every input the plan's capabilities accept must state which layer rejects invalid input: type-system (Pydantic/Literal/Enum), database (constraint), or application-logic (service validation). Includes a classification table telling the test architect what to test vs. skip.
3. **Test Scenario Grill updated** — Scenarios for computational invariants must use RC1-pinned fixtures. Each scenario classified with Enforcement layer (type-system/database/application-logic) and Mock Boundary (none/external-only/db-session). Principle: mock at external boundary, not internal boundary.
4. **Template 3 updated** — `-tests.md` companion file now has Enforcement and Mock Boundary columns per scenario. Rules updated to explain both classifications.
5. **Test architect Step 6 updated** — Consumes enforcement classification: skip type-system scenarios (framework-enforced), one integration test per DB constraint, full branch coverage for application-logic. Consumes mock boundary: none (pure function), external-only (mock out-of-process only), db-session (unit test, mock session not collaborator). Principle: mock the transport, not the collaborator.
6. **Taxonomy refinement drafted** — Calculation Error disambiguation rule for root-cause-taxonomy.md. Three-way comparison (plan fixture vs code output vs test assertion) to classify numeric test failures. Drafted at reports/taxonomy-refinement-calculation-error.md for routing to p-vision-and-architect-author.
7. **Type-enforcement-conformance skill created** — Layer 4 audit rules externalized to skill. Four checks: visibility correctness, type strictness, enforcement layer placement, custom validator presence. Supports retrospective audit mode (no plan needed — codebase is the subject, findings route to p-coder).
8. **p-implementation-validator Step 6b added** — Loads type-enforcement-conformance skill. Delegates visibility and type-strictness checks to p-code-structure-explorer (which has get_importers/get_module_deps). Retrospective audit mode skips Steps 0-6, runs only 6b, produces standalone report at reports/type-enforcement-audit-<scope>.md.
9. **RC1 example bias removed** — Removed concrete decay/fixture examples from RC1 text that could bias the architect toward domain-specific patterns. Replaced with abstract description of the precision requirement.
10. **pyrightconfig.json executionEnvironments** — User applied per-directory config suppressing reportPrivateUsage, reportUnusedFunction, reportMissingParameterType for tests/. Eliminates 14+ scattered `# type: ignore[reportPrivateUsage]` comments in test files.
11. **Existing test impact assessment** — Added to p-implementation-architect Step 6: when modifying an existing capability, architect checks whether existing tests are still valid (REWRITE if behaviour changed, RETIRE if capability removed). Listed in plan's Testing Requirements. Test architect Step 3 consumes RETIRE/REWRITE entries — RETIRE deletes in Step 4, REWRITE updates in Step 6. Prevents stale test accumulation in regression suite.

## Skills Status

All skills updated as noted above. implementation-plan-templates Template 3 updated with Enforcement + Mock Boundary columns. New skill: type-enforcement-conformance (Layer 4 audit, loaded by p-implementation-validator).
