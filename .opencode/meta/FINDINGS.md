# Ecosystem Findings Cache

> Maintained by p-agent-architect. Overwritten after every review, never appended.
> Keep under 100 lines. Condense aggressively.

**Last review:** 2026-07-27 — p-test-architect Fix Mode analysis (ses_059a)

## Open Issues

- p-diagnostics-fixer: `bash: allow` with prompt-only restrictions. (Carried.)
- p-documentation Cleanup Mode: judgment-heavy rows heuristic remains fragile. (Carried.)
- p-history-explorer: Not wired into standard pipeline. (Carried.)
- p-test-architect Fix Mode: lacks RC triage step — treats all Test Suite RCs as assertion drift. 5,800-line thinking spiral on RC6 (MissingGreenlet) without producing a single edit. (New.)

## Pattern Debt

- **Bare tool names in procedure text (7 agents).** p-coder, p-devops, p-implementation-architect, p-implementation-validator, p-history-explorer, p-state-explorer, p-consistency-validator, p-code-explorer still reference bare tool names instead of MCP-prefixed. Fixed: p-documentation. (Carried.)
- **Fix Mode procedure too narrow (p-test-architect).** Only covers assertion drift. No triage for flow redesign or infrastructure pattern changes. See report: `reports/agent-review-p-test-architect-ses059a.md`. (New.)

## Agent State

| Agent | Status | Notes |
|---|---|---|
| p-test-architect | ⚠️ | Fix Mode needs triage + escalation gates per ses_059a review |
| All other agents | ✅ | No changes needed. |

## Skills Status

All skills up to date.

## MOCING_CONTRACT.md

New anti-pattern added at line 40: `Monkeypatching repository add → MissingGreenlet` with correct pattern (SQLAlchemy `before_flush` event listener). This is the right knowledge resource — make Fix Mode check it before attempting non-trivial fixes.
