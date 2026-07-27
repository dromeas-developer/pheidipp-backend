# Ecosystem Findings Cache

> Maintained by p-agent-architect. Overwritten after every review, never appended.
> Keep under 100 lines. Condense aggressively.

**Last review:** 2026-07-26 — task template `description` field fixes

## Open Issues

- p-diagnostics-fixer: `bash: allow` with prompt-only command restrictions — risk of model drift escaping the guard. (Carried.)
- p-documentation Cleanup Mode: judgment-heavy rows heuristic remains fragile. (Carried.)
- p-history-explorer: Available on-demand but not wired into any standard pipeline. (Carried.)
- p-test-architect: `bash: allow` with prompt-only restriction (only `scripts/pytest.sh --collect-only`). Same risk class as p-diagnostics-fixer. (Carried.)

## Pattern Debt

- (None.)

## Agent State

| Agent | Status | Notes |
|---|---|---|
| p-implementation-architect | ✅ Updated | Task templates fixed (added `description` field). |
| p-test-architect | ✅ Updated | Enforcement + Mock Boundary, test-infrastructure skill, factory conventions, `.archive/` guard, diagnostics-fixer batching clarification. |
| p-coder | ✅ Updated | Task templates fixed (added `description` field). |
| p-devops | ✅ Updated | test-infrastructure skill, cleaned up infrastructure files list, NOT NULL remediation → factory content bug, task templates fixed. |
| p-diagnostics-fixer | ⚠️ | Runs on both app/ and tests/ — scope clarification needed. |
| p-implementation-validator | ✅ Updated | Task templates fixed (added `description` field). |
| p-consistency-validator | ✅ Updated | Task templates fixed (added `description` field). |
| p-agent-architect | ✅ | skill: allow, todowrite-discipline loaded |
| p-technical-advisor | ✅ Updated | Task templates fixed (added `description` field). |
| p-release-strategy-architect | ✅ Updated | Task templates fixed (added `description` field). |
| p-vision-and-architect-author | ✅ | todowrite-discipline loaded |
| p-documentation | ✅ | skill: allow, todowrite-discipline loaded |
| p-manifest-manager | ✅ Updated | Task templates fixed. Subagent for promote-file and release-promote operations |
| p-contract-verifier | ✅ Updated | Added `list_entities` + `search_architecture` tools. Rewrote resolution pipeline with 3-attempt circuit breaker, explicit "no source files" rules, and Step 3 stop-and-report path. Fixes infinite loop when entity name doesn't match architecture index (e.g., "RefreshToken" → "athlete-auth"). REGISTRY model field corrected to match frontmatter. |
| p-doc-explorer | — | Single-purpose subagent |
| p-state-explorer | ✅ Updated | multi_code_query permission, Step 4 batching. |
| p-impact-analyzer | — | Single-purpose subagent |
| p-code-explorer | — | Single-purpose subagent |
| p-code-structure-explorer | ✅ Updated | multi_code_query permission, Step 3 batching. |
| p-history-explorer | — | Single-purpose subagent |
| p-index-health-guard | — | Single-purpose subagent |

## Fixes Applied This Session

1. **Task template `description` field fixes** — Added missing `description` field to all `task` templates across 8 agents (38 total templates):
   - p-coder: 8 templates
   - p-implementation-architect: 6 templates
   - p-implementation-validator: 5 templates
   - p-consistency-validator: 4 templates
   - p-technical-advisor: 2 templates
   - p-release-strategy-architect: 4 templates
   - p-devops: 3 templates
   - p-manifest-manager: 2 templates
   - p-test-architect: 6 templates (already had description field)

2. **p-test-architect diagnostics-fixer batching clarification** — Updated lines 887-926 to clarify that only test files (matching `test_*.py`) should be batched, not utility files (`tests/utils/*.py`) or infrastructure files (`tests/conftest.py`). Added explicit note about counting files correctly before invoking (6+ triggers the batching gate).

## Skills Status

All skills up to date. New skills this cycle: test-infrastructure.