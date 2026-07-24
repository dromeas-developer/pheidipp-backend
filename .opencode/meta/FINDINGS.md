# Ecosystem Findings Cache

> Maintained by p-agent-architect. Overwritten after every review, never appended.
> Keep under 100 lines. Condense aggressively.

**Last review:** 2026-07-23 — DevOps agent improvements from session-ses_06e9 analysis

## Open Issues

- p-diagnostics-fixer: `bash: allow` with prompt-only command restrictions — risk of model drift escaping the guard. Platform limitation. (Carried.)
- p-documentation Cleanup Mode: judgment-heavy rows heuristic remains fragile. (Carried.)
- p-history-explorer: Available on-demand but not wired into any standard pipeline. (Carried.)
- p-test-architect: `bash: allow` with prompt-only restriction (only `scripts/pytest.sh --collect-only`). Same risk class as p-diagnostics-fixer. (Carried.)

## Pattern Debt

- (None active.)

## Agent State

| Agent | Status | Notes |
|---|---|---|
| p-test-architect | ✅ Redesigned | 2 modes (Generate, Fix). Manifest-bootstrap skill for initial file creation. Per-function validation with optional `class` field. |
| p-devops | ✅ Improved | Added `class` field support in manifest for class-based test selectors. `--collect-only` now a fallback, not primary method. Added before_insert listener guidance for NOT NULL fixes. Added always-produce-report directive. |
| p-manifest-manager | ✅ New | Subagent for promote-file and release-promote operations. Owns split/collapse algorithm. |
| p-coder | ✅ | todowrite-discipline loaded |
| p-implementation-architect | ✅ | todowrite-discipline loaded |
| p-implementation-validator | ✅ | todowrite-discipline loaded |
| p-technical-advisor | ✅ | todowrite-discipline loaded |
| p-release-strategy-architect | ✅ | todowrite-discipline loaded |
| p-vision-and-architect-author | ✅ | todowrite-discipline loaded |
| p-consistency-validator | ✅ | todowrite-discipline loaded |
| p-documentation | ✅ | skill: allow, todowrite-discipline loaded |
| p-agent-architect | ✅ | skill: allow, todowrite-discipline loaded |
| p-diagnostics-fixer | ⚠️ | Intentional anti-todo-list — mechanical loop |
| p-doc-explorer | — | Single-purpose subagent |
| p-contract-verifier | — | Single-purpose subagent |
| p-state-explorer | — | Single-purpose subagent |
| p-impact-analyzer | — | Single-purpose subagent |
| p-code-explorer | — | Single-purpose subagent |
| p-code-structure-explorer | — | Single-purpose subagent |
| p-history-explorer | — | Single-purpose subagent |
| p-index-health-guard | — | Single-purpose subagent |

## Fixes Applied This Session

1. **Redesigned manifest architecture** — two files: `index.yaml` (selection groups by type, pytest selectors, coverage) and `phase-N-Mx.yaml` (per-file entries with per-function inline validation + sub-phase coverage). Eliminated: history, description, protects, impacts, execution_groups, cross_phase_dependencies, selection.feature.
2. **SCHEMA.md** — Complete rewrite. Phase files immutable. DevOps owns promotion.
3. **p-test-architect** — Stripped promotion, no index.yaml writes except bootstrap. Creates phase files with per-file schema. Updated Step 5/8/9, Manifest Schema, Bootstrap exception.
4. **p-devops** — Four scopes. Feature: selective function running via `::function`. Delegates promote-file and release-promote to p-manifest-manager.
5. **p-manifest-manager** — New subagent. Two operations: promote-file (split check + selection.release) and release-promote (collapse check + coverage merge).
6. **Path compression** — index.yaml uses pytest selectors grouped by type dir. DevOps prefixes `tests/{type}/`.
7. **Token reduction** — DevOps loads ~150 lines instead of ~1754 (92% reduction). Phase files: ~150 lines instead of 1502 (90% reduction).
8. **Inline YAML templates removed** — Agents reference SCHEMA.md. No duplicated format definitions in prompts.
9. **p-devops Pre-Flight Step 3** — Added `--collect-only` step before constructing pytest selectors. Manifest stores function names only; tests may be class-based, requiring class-qualified paths (`file.py::ClassName::test_func`). Without this, pytest reports "not found" for every class-based test.
10. **p-devops Step 5a** — Added `before_insert` listener pattern guidance for NOT NULL constraint violations. conftest.py already has listeners for WeeklyPlan, AthleteProfile, etc. — extending this pattern for new models is infrastructure wiring, not content changes.
11. **p-devops Output Format** — Added "always produce a report" directive. Agent must produce a report even with many failures or uncertain root causes.
13. **Manifest class hierarchy** — Added optional `class` field to function entries in phase files and SCHEMA.md. DevOps constructs `file.py::ClassName::function_name` when `class` is present, `file.py::function_name` when absent. `--collect-only` is now a fallback for missing class fields, not the primary method. Updated phase-2-7.yaml, index.yaml, p-devops Step 3, p-manifest-manager (promote-file and release-promote), p-test-architect (Step 5b + Manifest Schema), and infrastructure-reference skill. Also fixed duplicate `test_orders_by_target_date_ascending` entry in phase-2-7.yaml.
14. **Merged Bootstrap into Generate** — p-test-architect now has 2 modes (Generate, Fix) instead of 3 (Bootstrap, Generate, Fix). Bootstrap was 90% identical to Generate, differing only in initial file creation. Extracted initial creation logic into `manifest-bootstrap` skill, loaded conditionally when `index.yaml` doesn't exist. Removed ~40 lines of duplicated Bootstrap mode section from the prompt. Generate Step 1 now checks for missing manifest and loads the skill if needed. Skill references SCHEMA.md for manifest structure (no duplication) and only provides MOCKING_CONTRACT.md template + creation logic. Skill explicitly instructs agent to read SCHEMA.md via `get_files` before creating files.
15. **Removed Baseline Mode from p-implementation-architect** — The `docs/implementation/archive/` directory is empty and all phase directories use the new BRD format. Baseline Mode (old-format plan migration) is dead weight. Removed the entire Baseline Mode section (Entry Mode description + B0-B6 Procedure, ~111 lines). p-implementation-architect now has 2 modes: Plan and Resolution. Updated all references from "three" to "two" modes.
16. **Fixed p-devops MCP tool usage** — Two issues: (1) `pheidipp-codebase-context_find_files` was denied by the wildcard rule but the prompt referenced it extensively — added explicit `allow`. (2) `get_files` requires `paths` as a JSON array of strings, but the prompt never showed the correct invocation format — added a usage note in the Pre-Flight section showing `paths` must be an array, never a bare string. This was causing `Input validation error: 'paths' is a required property` when the agent tried to read files.
17. **Added documentation-test prohibition to p-implementation-architect** — Added a note in the Test Scenario Grill section: test scenarios must validate implementation behaviour, never documentation content. Do not draft scenarios that check whether a doc file exists, whether a doc contains specific text, or whether documentation matches expectations. Tests verify code behaviour against architecture contracts — not prose against prose.
18. **Fixed p-release-strategy-architect denied tool references** — The prompt referenced `multi_search` and `multi_context` in Steps 2, 3, and Brainstorming Behaviour, but these tools are denied by the wildcard rule (`pheidipp-codebase-context_*: deny`) and not in the allow list. The Retrieval section already correctly said to use `p-doc-explorer` instead. Updated all three locations to delegate to `p-doc-explorer` via `task` tool, matching the Retrieval section's guidance.
19. **Completed in-depth review of p-release-strategy-architect** — See `reports/agent-review-p-release-strategy-architect.md`. Key findings: (1) Must Fix: load `retrieval-patterns` skill, add `p-impact-analyzer` delegation, add ADR check to challenge questions, add ADR search tools to permission block, update REGISTRY.md model field. (2) Should Fix: extract Sub-Phase Document Format template and Anti-Patterns/Sizing Rules to skills (~89 lines savings). (3) Nice to Have: add `p-contract-verifier` delegation. (4) Total potential savings: ~115 lines (~20% reduction) plus ecosystem consistency.
20. **Applied all Must Fix and Should Fix items to p-release-strategy-architect** — (1) Loaded `retrieval-patterns` skill, removed redundant 32-line Retrieval section. (2) Added `p-impact-analyzer: allow` to task permissions, updated Step 2 to delegate to it instead of using `get_change_impact` directly. (3) Added explicit ADR check question to Step 2 challenge list. (4) Added 5 ADR search tools to permission block. (5) Updated REGISTRY.md model field to `poolside/poolside/laguna-m.1`. (6) Created `sub-phase-document-template` skill, replaced 54-line inlined template with skill reference. (7) Created `release-planning-patterns` skill, replaced 40-line inlined Anti-Patterns/Sizing Rules with skill reference. (8) Fixed Mode A/C references to denied `multi_search` tool. (9) Updated Brainstorming Behaviour to use p-impact-analyzer delegation. (10) Updated REGISTRY.md with new skills and delegation. Total savings: ~120 lines (519→399). This eliminates the permission denial and the inconsistency between prompt sections.

## Skills Status

All skills updated as noted above.
