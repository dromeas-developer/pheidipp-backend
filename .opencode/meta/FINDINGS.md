# Findings

## Ecosystem State

**Baseline: 2026-08-09 (fix/fixer cluster consistency — APPLIED)**
— All recommendations from the fix/fixer cluster review have been
applied: fix-loop-protocol skill created [SF-A], p-infra-fixer
s-diagnostics-fixer added [MF-A], all 3 fix agents report-append +
structured return standardized [MF-B/SF-C], stale s-test-analyzer
claims removed from p-coder-fix-mode + p-devops [SF-B], services-check
block extracted to skill [NH-A]. 33 skills (was 32). REGISTRY.md
updated. Report: reports/agent-review-fix-fixer-cluster.md.

## Open Issues

None blocking. NH-C (bash allow-list narrowing on tester agents)
deferred to future opencode capability.

## Applied Changes (this cycle)

### MF-A — p-infra-fixer s-diagnostics-fixer (APPLIED)
- Added `s-diagnostics-fixer: allow` to frontmatter task block
- Added Step 5b "Python diagnostics (conditional)" — only when
  `.py` files modified, per fix-loop-protocol §3
- Updated Subagent Delegation table + Skills table

### MF-B — Fix agents report-append (APPLIED)
- p-coder-fix-mode: added "## Report Append and Return" section
  with `## Coder Fixes Applied` section name
- p-tester-fix-mode: replaced thin 2-line Output section with
  "## Report Append and Return" section with `## Test Fixes Applied`
- p-infra-fixer: Step 8 + Step 9 replaced with fix-loop-protocol
  §4/§5 references (section name `## Infra Fixes Applied` retained)

### SF-A — fix-loop-protocol skill (APPLIED)
- New skill at .opencode/skills/fix-loop-protocol/SKILL.md
- Owns: services-check pre-flight (§1), verify-loop wrapper (§2),
  conditional s-diagnostics-fixer invocation (§3), report-append
  template (§4), structured return-summary template (§5)
- Loaded by: p-coder-fix-mode, p-tester-fix-mode, p-infra-fixer
- NOT loaded by p-test-runner (different shape — writes fresh report)
- All 3 fix agents: inline services-check block replaced with
  skill reference; inline verify-loop protocol restatement replaced
  with skill reference (agent-specific task template kept inline)

### SF-B — Stale s-test-analyzer claims (APPLIED)
- p-coder-fix-mode: removed "Infrastructure fixes are applied
  directly by s-test-analyzer" (replaced with correct routing to
  p-infra-fixer + p-tester-fix-mode)
- p-coder-fix-mode: removed "DevOps's own remediation pass" (replaced
  with "p-infra-fixer, invoked separately by the operator")
- p-devops: removed "s-test-analyzer applies infra fixes during
  test-run analysis" (replaced with "p-infra-fixer owns test-infra
  fixes, invoked by the operator after reading the report")

### SF-C — Structured return summary (APPLIED)
- All 3 fix agents now reference fix-loop-protocol §5 for the
  return summary template, parameterized by agent role label
  (Coder / Test / Infra)
- p-tester-fix-mode's "completion confirmation only" anti-pattern
  replaced with per-finding dispositions

### NH-A — STOP message wording harmonized (APPLIED)
- All 3 fix agents now use fix-loop-protocol §1's parameterized
  STOP message (only the agent name differs)

### NH-B — Cross-agent sweep checklist (APPLIED — this entry)
- Added to FINDINGS.md as a procedure note: when an agent's role
  changes, grep its name across .opencode/agents/ and
  .opencode/skills/ to catch downstream references. This is what
  surfaced the stale s-test-analyzer claims in SF-B.

## Cross-Agent Sweep Checklist (NH-B — procedure)

When an agent's role changes (rename, deprecation, responsibility
shift), run this sweep as part of the FINDINGS.md update:

1. `grep -r "<old-agent-name>" .opencode/agents/ .opencode/skills/`
2. For each match, check whether the reference describes the old
   role or the new role. If old → update or remove.
3. `grep -r "<new-agent-name>" .opencode/agents/ .opencode/skills/`
4. For each match, verify the reference is consistent with the
   new role.

This prevents the class of drift that caused SF-B (stale
s-test-analyzer claims survived a consolidation that touched both
files because no sweep was run).

## Deferred Items (carry forward)

| ID | Item | Risk | Action |
|---|---|---|---|
| F6 | `reports/<plan-id>_devops.md` named after p-devops, but s-test-analyzer writes it. Rename to `_test-run.md` touches 5+ prompts. | Low | Next maintenance window |
| F7 | Consistency validator writes to `docs/implementation/` while all other reports go to `reports/`. | Low | Next maintenance window |
| NH-C | `bash: allow` on tester agents is documented but broader than the single allowed command. Tighten if opencode adds script allow-list. | Low | Future opencode capability |

## Subagent Fallback — Simplified Design (2026-08-09)

**Design:** Primary sessions use abort+replay (work preserved).
Subagent sessions use abort-without-replay (work lost, but parent
re-delegates and the new subagent uses the fallback via
`chat.message` rewrite).

**Flow:** subagent hits rate limit → plugin sets cooldown → aborts
subagent (no replay) → parent sees failure and re-delegates → new
subagent's `chat.message` hook sees cooldown and rewrites model to
fallback → completes on fallback. Cooldown 3600s sufficient.

## Cluster Consistency Matrix (post-application state)

| Behaviour | p-coder-batch | p-coder-fix | p-tester-gen | p-tester-fix | p-infra-fix |
|---|---|---|---|---|---|
| s-diagnostics-fixer on `.py` edits | ✅ | ✅ | ✅ | ✅ | ✅ MF-A |
| Report-append "Fixes Applied" | n/a (BRD) | ✅ MF-B | n/a (BRD) | ✅ MF-B | ✅ (lead) |
| Verify loop (s-test-executor) | n/a | ✅ | n/a | ✅ | ✅ (test-infra only) |
| Services-check pre-flight | n/a | ✅ via skill | n/a | ✅ via skill | ✅ via skill NH-A |
| Structured return summary | n/a | ✅ SF-C | n/a | ✅ SF-C | ✅ SF-C |
| Shared core skill loaded | coder-shared-core | coder-shared-core | tester-shared-core | tester-shared-core | fix-loop-protocol |
| Stale s-test-analyzer claim | — | ✅ fixed SF-B | — | — | — |

## Cross-Agent Patterns (updated)

- Brief schema across explorer subagents
- Skill for shared coder core / tester core
- Skill for output format (impl-architect, validator, analyzer, consistency-validator)
- Subagent for structured retrieval
- Finding routing via report classification
- Wildcard-first permission blocks
- Manifest model (two files, file-level status)
- Test execution separation (p-test-runner primary, s-test-executor mechanical)
- Per-batch test execution
- Migration lifecycle separation (s-alembic owns full lifecycle)
- Verify loop contract (fix agents delegate scoped re-runs, 2-iter cap)
- s-test-executor sequential execution (NON-NEGOTIABLE)
- Dead permission cleanup (2026-08-05)
- Infra fixer consolidation (2026-08-09 — p-infra-fixer sole infra executor)
- Web access consolidation (2026-08-09 — s-web-researcher sole webfetch)
- **Fix-loop protocol (2026-08-09 — NEW)**: 3 fix agents share
  `fix-loop-protocol` skill for services-check pre-flight, verify-loop
  wrapper, conditional s-diagnostics-fixer, report-append template,
  and structured return-summary. `test-execution-protocol` stays
  focused on s-test-executor mechanics (loaded by 4 agents incl.
  p-test-runner). All 5 touch-code agents now invoke
  s-diagnostics-fixer on `.py` modifications. All 3 fix agents
  append a per-RC "Fixes Applied" section to the report they read.

## Agent Status

| Agent | Status |
|---|---|
| p-agent-architect | Stable — review author + applied changes |
| p-technical-advisor | Stable |
| p-release-strategy-architect | Stable |
| p-implementation-architect | Stable |
| p-implementation-resolver | Stable |
| p-implementation-validator | Stable |
| p-consistency-validator | Stable |
| p-coder-batch-mode | Stable |
| p-coder-fix-mode | Updated — fix-loop-protocol loaded, inline verify-loop replaced with skill ref, report-append + structured return added, stale s-test-analyzer claim removed |
| p-tester-generate-mode | Stable |
| p-tester-fix-mode | Updated — fix-loop-protocol loaded, inline verify-loop replaced with skill ref, report-append + structured return added (replaces thin Output section) |
| p-infra-fixer | Updated — s-diagnostics-fixer permission added, Step 5b conditional Python diagnostics added, fix-loop-protocol loaded, inline services-check + verify-loop + report-append + return replaced with skill refs |
| p-devops | Updated — stale s-test-analyzer claim removed |
| p-test-runner | Stable |
| s-test-analyzer | Stable — analysis-only |
| s-test-executor | Stable |
| s-web-researcher | Stable — sole webfetch agent |
| s-diagnostics-fixer | Updated — Invoked By list now includes p-infra-fixer |
| s-infra-config-editor | DEPRECATED — subsumed by p-infra-fixer |
| All other s-* subagents | Stable |

## Pipeline Completeness

All stages verified complete (unchanged):
1. Planning → p-implementation-architect ✅
2. Implementation → p-coder-batch-mode ✅
3. Test generation → p-tester-generate-mode ✅
4. Validation → p-implementation-validator ✅
4b. Consistency → p-consistency-validator (optional) ✅
5. Test execution → p-test-runner ✅
6. Promotion gate → p-devops ✅
Fix loop → p-coder-fix-mode, p-tester-fix-mode, p-infra-fixer,
p-implementation-resolver — all primary, all operator-invoked ✅