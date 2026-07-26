# Ecosystem Findings Cache

> Maintained by p-agent-architect. Overwritten after every review, never appended.
> Keep under 100 lines. Condense aggressively.

**Last review:** 2026-07-25 — p-contract-verifier infinite-loop fix (list_entities + search_architecture + circuit breaker)

## Open Issues

- p-diagnostics-fixer: `bash: allow` with prompt-only command restrictions — risk of model drift escaping the guard. (Carried.)
- p-documentation Cleanup Mode: judgment-heavy rows heuristic remains fragile. (Carried.)
- p-history-explorer: Available on-demand but not wired into any standard pipeline. (Carried.)
- p-test-architect: `bash: allow` with prompt-only restriction (only `scripts/pytest.sh --collect-only`). Same risk class as p-diagnostics-fixer. (Carried.)
- **Missing `description` field in `task` templates across 4 agents** — p-coder (8 templates), p-implementation-architect (6), p-implementation-validator (5), p-consistency-validator (4). The `task` tool schema requires `description` in addition to `subagent_type` and `prompt`. p-test-architect was fixed (6 templates), but all other delegating agents still use the old two-field format. These will fail with `SchemaError(Missing key at ["description"])` when invoked. (2026-07-25)

## Pattern Debt

- (None.)

## Agent State

| Agent | Status | Notes |
|---|---|---|
| p-implementation-architect | ✅ Updated | RC1 fixture gate, RC6 enforcement layer, Test Scenario Grill updated. |
| p-test-architect | ✅ Updated | Enforcement + Mock Boundary, test-infrastructure skill, factory conventions, `.archive/` guard. |
| p-coder | ✅ | One-session-per-BRD discipline enforces sequencing. |
| p-devops | ✅ Updated | test-infrastructure skill, cleaned up infrastructure files list, NOT NULL remediation → factory content bug. |
| p-diagnostics-fixer | ⚠️ | Runs on both app/ and tests/ — scope clarification needed. |
| p-implementation-validator | ✅ Updated | Step 6b (Type-Enforcement Conformance), retrospective audit mode. |
| p-consistency-validator | ✅ | No changes needed. |
| p-agent-architect | ✅ | skill: allow, todowrite-discipline loaded |
| p-technical-advisor | ✅ | todowrite-discipline loaded |
| p-release-strategy-architect | ✅ | todowrite-discipline loaded |
| p-vision-and-architect-author | ✅ | todowrite-discipline loaded |
| p-documentation | ✅ | skill: allow, todowrite-discipline loaded |
| p-manifest-manager | ✅ | Subagent for promote-file and release-promote operations |
| p-contract-verifier | ✅ Updated | Added `list_entities` + `search_architecture` tools. Rewrote resolution pipeline with 3-attempt circuit breaker, explicit "no source files" rules, and Step 3 stop-and-report path. Fixes infinite loop when entity name doesn't match architecture index (e.g., "RefreshToken" → "athlete-auth"). REGISTRY model field corrected to match frontmatter. |
| p-doc-explorer | — | Single-purpose subagent |
| p-state-explorer | ✅ Updated | multi_code_query permission, Step 4 batching. |
| p-impact-analyzer | — | Single-purpose subagent |
| p-code-explorer | — | Single-purpose subagent |
| p-code-structure-explorer | ✅ Updated | multi_code_query permission, Step 3 batching. |
| p-history-explorer | — | Single-purpose subagent |
| p-index-health-guard | — | Single-purpose subagent |

## Fixes Applied This Session

1. **p-contract-verifier infinite-loop fix** — Diagnosed from session export. Two root causes:
   (a) Missing `list_entities` and `search_architecture` tools — agent could not discover canonical architecture entity names when the exact name failed.
   (b) No circuit breaker in prompt — agent repeatedly tried same tools in a loop (get_entity_context → fail → try get_files (unavailable) → search_symbols → retry).
   Decision: did NOT add `get_files` — p-contract-verifier operates on the architecture index, not source code. Reading model files would confuse "what the architecture says" with "what the code does." Instead: added `list_entities` + `search_architecture`, rewrote resolution pipeline with 5-step sequence, 3-attempt hard stop, and explicit "no file reading" rules. REGISTRY.md updated (tools + model field corrected from stale `deepseek-v4-flash-free` to actual `openrouter/inclusionai/ling-3.0-flash:free`).

## Skills Status

All skills up to date. New skills this cycle: test-infrastructure.
