# Findings

## Ecosystem State

**Baseline: 2026-08-05** — Post-restructuring + permission audit +
primary-agent-vs-subagent correction.
Ecosystem is stable. Pipeline is complete. All subagents wired.

## Open Issues

None blocking. Two deferred naming items (see below).

## Primary Agent Architecture Correction (2026-08-05)

**Issue:** p-devops had `p-test-runner: allow` in its task
permissions and its prompt said "Delegate to p-test-runner." But
p-test-runner is a **primary agent**, not a subagent — primary
agents cannot be invoked via `task` from other primary agents. Only
subagents (prefixed `s-`) can be task-delegated.

**Fix applied:**
1. p-devops frontmatter: removed `p-test-runner: allow` from task
   permissions. Now has 4 subagent allows (s-devops-ops, s-alembic,
   s-manifest-manager, s-index-health-guard).
2. p-devops prompt: rewritten as **promotion gate** — invoked by
   operator AFTER p-test-runner returns PASS. No test execution
   step. Pre-flight checks for test-run report existence (if exists
   = tests failed = STOP).
3. p-test-runner prompt: clarified it's a **primary agent** invoked
   by the operator/pipeline, not by p-devops. Updated role, return,
   and escalation sections to reference the operator, not p-devops.
4. Architecture: p-test-runner and p-devops are **peer primary
   agents** — operator invokes p-test-runner first, gets PASS,
   then invokes p-devops for promotion. The fix loop (p-coder-fix-
   mode, p-tester-fix-mode, p-implementation-resolver) is also
   operator-invoked — fix agents are primary agents that read
   reports from disk in their own sessions.

## Permission Audit (2026-08-05)

Applied — all dead permissions removed:

| Agent | Removed | Reason |
|---|---|---|
| p-coder-batch-mode | bash: allow → deny | All bash work delegated (migration→s-alembic, diagnostics→s-diagnostics-fixer, tests→s-test-executor) |
| p-coder-fix-mode | bash: allow → deny | Same as batch-mode; typecheck/lint/format delegated to s-diagnostics-fixer |
| p-devops | bash/edit/write: allow → deny | Thin orchestrator; all ops delegated to s-devops-ops, s-alembic, s-manifest-manager |
| p-test-runner | find_files: allow → removed | Never called find_files; only uses get_files for manifest reads |

Stale description fixed:

| Agent | Fix |
|---|---|
| s-devops-ops | Description removed p-coder-batch-mode and p-coder-fix-mode (neither has s-devops-ops in task permissions) |

## Deferred Items

| ID | Item | Risk | Action |
|---|---|---|---|
| F6 | `reports/<plan-id>_devops.md` named after p-devops, but s-test-analyzer writes it now. Rename to `_test-run.md` touches 5+ downstream prompts. | Low — naming only, no functional impact | Next maintenance window |
| F7 | Consistency validator writes to `docs/implementation/consistency-<scope>.md` while all other reports go to `reports/`. | Low — path convention only | Next maintenance window |

## Agent Status

| Agent | Status |
|---|---|
| p-agent-architect | DEPRECATED — replaced by pheidipp-prompt-architect |
| p-technical-advisor | Stable |
| p-release-strategy-architect | Stable |
| p-implementation-architect | Stable |
| p-implementation-resolver | Stable |
| p-implementation-validator | Stable |
| p-consistency-validator | Stable |
| p-coder-batch-mode | Updated — bash→deny (permission audit) |
| p-coder-fix-mode | Updated — bash→deny (permission audit) |
| p-tester-generate-mode | Stable |
| p-tester-fix-mode | Stable |
| p-devops | Updated — bash/edit/write→deny + rewritten as promotion gate (no p-test-runner delegation) |
| p-test-runner | Updated — find_files removed + clarified as primary agent (operator-invoked, not p-devops-delegated) |
| s-contract-verifier | Stable |
| s-impact-analyzer | Stable |
| s-code-explorer | Stable |
| s-code-structure-explorer | Stable |
| s-state-explorer | Stable |
| s-doc-explorer | Stable |
| s-history-explorer | Stable (not wired into standard pipeline) |
| s-diagnostics-fixer | Stable |
| s-documentation | Stable |
| s-index-health-guard | Stable |
| s-manifest-manager | Stable |
| s-test-executor | Stable |
| s-test-analyzer | Stable |
| s-alembic | Stable |
| s-devops-ops | Updated — description fixed (permission audit) |
| s-vision-and-architect-author | Stable |

## Pipeline Completeness

All stages verified complete:
1. Planning → p-implementation-architect (6 subagents) ✅
2. Implementation → p-coder-batch-mode (7 subagents) ✅
3. Test generation → p-tester-generate-mode (6 subagents) ✅
4. Validation → p-implementation-validator (4 subagents) ✅
4b. Consistency → p-consistency-validator (3 subagents, optional) ✅
5. Test execution → p-test-runner (5 subagents, operator-invoked) ✅
6. Promotion gate → p-devops (4 subagents, operator-invoked after PASS) ✅
Fix loop → p-coder-fix-mode (7), p-tester-fix-mode (5), p-implementation-resolver (5) ✅
All fix agents are primary agents invoked by operator, NOT task-delegated.

No missing steps. No uninvoked required subagents. No boundary violations.
No primary agents misused as subagents.
