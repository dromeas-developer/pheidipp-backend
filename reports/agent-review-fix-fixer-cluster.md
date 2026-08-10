# Agent Review: Fix / Fixer + Touch-Code Cluster

**Date:** 2026-08-09
**Mode:** Cluster Review (cross-cutting — all agents that modify application, test, or infrastructure code)
**Reviewer:** p-agent-architect
**Scope:** Behavioural consistency across the 5 touch-code agents + 1 subagent:
- `p-coder-batch-mode`
- `p-coder-fix-mode`
- `p-tester-generate-mode`
- `p-tester-fix-mode`
- `p-infra-fixer`
- `s-diagnostics-fixer` (the shared callee — input contract reference)
**Peer comparison:** each agent compared against the other four to surface drift.
**Prior work:** builds on `reports/agent-review-s-test-executor-delegation.md` (verify-loop protocol extracted to `test-execution-protocol` skill) and `reports/agent-review-p-infra-fixer.md` (3 diagnosis-boundary gaps fixed).
**Status:** ANALYSIS (no agent edits applied — this is the in-depth review the operator requested before extending to all touch-code agents).

---

## 1. Executive Summary

After the `test-execution-protocol` skill was extracted, the s-test-executor delegation call site became consistent across the three verify-loop agents. **Three further consistency gaps remain in the touch-code cluster**, two of which the operator flagged directly:

1. **s-diagnostics-fixer invocation is missing on `p-infra-fixer`** (the `code-touches-python-files-but-skips-typecheck` gap you spotted). The other four touch-code agents all invoke it on completion; p-infra-fixer edits `tests/utils/*.py` and `tests/conftest.py` (real Python) yet has no s-diagnostics-fixer delegation step.

2. **Report-append "Fixes Applied" section is inconsistent.** Only `p-infra-fixer` appends a structured `## Infra Fixes Applied` block to the devops report. `p-coder-fix-mode` and `p-tester-fix-mode` leave the operator to read their inline response text — there is no audit trail on disk once the fix session closes. The batch / generate agents don't need to append (they own their own artifacts), but the three fix agents are *consumer-driven* — they read a report, modify code, and return. Without an append step, the report on disk does not reflect what the fixer actually did.

3. **The services-check pre-flight block is duplicated inline across 3 agents** despite the `test-execution-protocol` skill being intended to own the verify-loop protocol. The skill holds the s-test-executor delegation protocol but the `s-devops-ops services-check` precondition lives as a verbatim ~15-line block in p-coder-fix-mode, p-tester-fix-mode, AND p-infra-fixer.

Two stale claims about `s-test-analyzer` were also found in `p-coder-fix-mode` (line 121) and `p-devops` (line 199) — both still describe s-test-analyzer as "applying infra fixes during test-run analysis," which predates the infra-fixer consolidation (FINDINGS.md 2026-08-09). These are lowest-priority but real textual contradictions.

**Recommendation:** extract two shared skills — one for the services-check + verify-loop wrapper (extends the existing `test-execution-protocol` skill), one for the "append `Fixes Applied` section to the source report" pattern that all three fix agents should follow. Add the missing s-diagnostics-fixer delegation step to `p-infra-fixer`. Defer the stale `s-test-analyzer` claims to a follow-up cleanup pass.

---

## 2. Overall Assessment

**Cluster health:** Good, with three definable drift points. The cluster is **not** in disarray — the agents have clear single responsibilities, the shared cores (`coder-shared-core`, `tester-shared-core`) are well-factored, and the verify-loop protocol was successfully extracted last cycle. The remaining gaps are the kind that accumulate silently after a consolidation: a new agent (`p-infra-fixer`) was created without inheriting two patterns the existing fix agents already followed, and the report-append pattern was only ever embedded in one agent prompt rather than extracted as a shared convention.

**Severity profile:**

| Severity | Count | Examples |
|---|---|---|
| Must Fix | 2 | Missing s-diagnostics-fixer on p-infra-fixer; missing report-append on p-coder-fix-mode & p-tester-fix-mode |
| Should Fix | 3 | Services-check block duplicated inline x3; stale s-test-analyzer claims; extend the fix-loop skill to cover services-check |
| Nice to Have | 2 | Harmonize "Output" section wording across fix agents; consolidate Stop-on-services-not-running message wording |

---

## 3. Strengths

What the cluster already does well — to make sure the recommendations preserve it.

- **Shared cores do the heavy lifting.** `coder-shared-core` (~411 lines) owns the diagnostics completion protocol, command execution, file reading, migration rule, code standards, comment discipline, type hygiene, no-silent-deviations, and todo-list discipline for both coder agents. `tester-shared-core` (~274 lines) does the same for both tester agents. The thin agent prompts (~125 lines for p-coder-fix-mode, ~125 for p-tester-fix-mode, ~510 for p-infra-fixer) defer correctly to their shared core.
- **Verify-loop protocol extraction (last cycle) succeeded.** `test-execution-protocol` (62 lines) is loaded by all 4 delegating agents. The s-test-executor call site is consistent: same template, same sequential rule, same Juice interpretation.
- **Boundary clarity on file scope.** Every fix agent has an explicit "what I do NOT touch" list mapping to a peer: `app/` → p-coder-fix-mode, `test_*.py` → p-tester-fix-mode, infra → p-infra-fixer, migrations → s-alembic. No overlap.
- **`p-infra-fixer` already leads on report-append.** Its Step 8 ("Append to report") is the only structured audit trail on disk — exactly the pattern the other two fix agents should adopt.
- **`s-diagnostics-fixer` input contract is well-defined.** The callee prompt makes single-file vs multi-file vs full-repo mode explicit, has hard gates against directory/glob arguments, and returns compact text (no report files). A consistent caller-side template can rely on that contract.

---

## 4. Weaknesses

The behavioural inconsistencies across the cluster.

### 4.1 — s-diagnostics-fixer invocation matrix

| Agent | Invokes s-diagnostics-fixer? | Where defined | On what file set | Template |
|---|---|---|---|---|
| p-coder-batch-mode | ✅ | `coder-shared-core` "Completion Verification — Diagnostics" | every file the batch touched (≤5/group, group by proximity) | `plan_id: <id>\n\nfiles:\n<path>...` |
| p-coder-fix-mode | ✅ | inherits via `coder-shared-core` | same | same |
| p-tester-generate-mode | ✅ | `test-generate-mode-protocol` Step 8 ("Post-generation diagnostics") | test files only — `test_*.py`, NO `tests/utils/*.py` or conftest.py in these batches | same |
| p-tester-fix-mode | ✅ | `test-fix-mode-procedure` Step 7 | each test file the fixer modified — one invocation per file | same |
| **p-infra-fixer** | ❌ **never** | — | — | — |

**Empirical confirmation** (grep across agent prompts and skills):
```
p-coder-batch-mode.md:11    s-diagnostics-fixer: allow
p-coder-fix-mode.md:11      s-diagnostics-fixer: allow
p-tester-generate-mode.md:12  s-diagnostics-fixer: allow
p-tester-fix-mode.md:12       s-diagnostics-fixer: allow
p-infra-fixer.md:             (no s-diagnostics-fixer in task block)
REGISTRY.md:39              Invoked By: p-coder-batch-mode, p-coder-fix-mode, p-tester-generate-mode, p-tester-fix-mode  ← p-infra-fixer absent
```

**Why this matters.** `p-infra-fixer`'s Scope of Edits table (lines 171-188) includes real Python files: `tests/conftest.py`, `tests/<layer>/conftest.py`, `tests/utils/*.py`. Editing a `conftest.py` to fix a fixture scope can easily leave dangling imports, stale type annotations, or unused helpers — exactly what s-diagnostics-fixer exists to clean up. The agent's Step 5 validates YAML / shell / Dockerfile syntax but has **no typecheck or lint step for Python edits**. A conftest edit landing in the report's verify loop with a pyright cascade is a real failure mode.

**Counter-consideration.** p-infra-fixer also edits non-Python infra files (`.env`, `docker-compose.yml`, `Dockerfile`, `litellm_proxy/*.yaml`, `scripts/*.sh`). The diagnostics-fixer is for `*.py` only. So the fix is not "always invoke s-diagnostics-fixer" — it's "invoke it when at least one modified file is `.py`".

### 4.2 — Report-append "Fixes Applied" matrix

| Agent | Reads a report from disk? | Appends a "Fixes Applied" section to it? | What the operator sees |
|---|---|---|---|
| p-coder-batch-mode | no (BRD-driven) | n/a | the code itself |
| p-coder-fix-mode | ✅ reads `reports/<plan-id>_validation.md` OR `reports/<plan-id>_devops.md` | ❌ **no append step** | inline response text, no on-disk audit |
| p-tester-generate-mode | no (BRD-driven) | n/a | the test files + manifest |
| p-tester-fix-mode | ✅ reads `reports/<plan-id>_devops.md` | ❌ **no append step** | inline response text only — `test-fix-mode-procedure` ends at Step 9 with "Run this procedure, then STOP" |
| p-infra-fixer | ✅ reads `reports/<plan-id>_devops.md` | ✅ Step 8 appends `## Infra Fixes Applied` with per-RC disposition | structured audit trail on disk |

**Empirical confirmation:**
```
p-infra-fixer.md:370  "After all fixes are applied (or the iteration cap is hit), append an
p-infra-fixer.md:371   `## Infra Fixes Applied` section to ..."
p-infra-fixer.md:375  ## Infra Fixes Applied        ← the template

p-coder-fix-mode.md     (no "append" or "Fixes Applied" anywhere)
p-tester-fix-mode.md    (no "append" or "Fixes Applied" anywhere)
test-fix-mode-procedure/SKILL.md   (no "append" or "Fixes Applied" — ends "Run this procedure, then STOP")
```

**Why this matters.** The three fix agents are all operator-invoked, peer-positioned consumers of the same kind of artifact — a report on disk. The operator's workflow is:
1. Read the report on disk to identify which agent owns each RC.
2. Invoke the matching fix agent.
3. **Re-invoke `p-test-runner` (or p-devops for prod-infra) to resume the pipeline.**

Without an append step, step 3 happens against a report that does not record what step 2 actually did. The operator has to read the agent's chat output, remember it, and trust it. If the session was killed, the audit trail is gone. If a second fix agent is invoked on the same report, the second agent has no signal about what the first agent already addressed.

`p-infra-fixer` solved this with `## Infra Fixes Applied`. The other two fix agents need the same pattern — with their own section name (`## Coder Fixes Applied`, `## Test Fixes Applied`) so the report accumulates a per-owner audit trail.

### 4.3 — Services-check block duplicated inline ×3

The services-check pre-flight block is **identical, line for line**, in three agents:

```
p-coder-fix-mode.md:204-220    (17 lines, "Verify Loop / Services check (before first re-run)")
p-tester-fix-mode.md:77-93     (17 lines, same heading, same wording)
p-infra-fixer.md:222-243       (22 lines, "Step 2 — Services check", same call + same STOP message)
```

The only differences:
- p-infra-fixer gates the block behind a "test-infra findings only" condition (lines 224-225) because its prod-infra findings need no test re-run. The other two always run the check before the first re-run.
- The "operator must start them" message names the invoking agent differently (`re-invoke p-coder-fix-mode` / `p-tester-fix-mode` / `p-infra-fixer`).

`test-execution-protocol` already owns the s-test-executor delegation protocol but does **not** own the services-check pre-flight. Its description says "Agent-specific task templates, sequencing examples, and services-check preconditions remain inline in each agent's own prompt." That was the original design choice — but the block turned out to be almost entirely shared, with only the agent-name placeholder differing. Three verbatim copies of a 17-line block is exactly the kind of duplication the skill-extraction dimension is meant to catch.

### 4.4 — Stale `s-test-analyzer` claims (lowest priority)

Two prompts still describe s-test-analyzer as the agent that lands infra fixes — pre-consolidation language that contradicts the current pipeline:

```
p-coder-fix-mode.md:120-121
  "Infrastructure fixes
  are applied directly by s-test-analyzer during the test-run analysis
  pass — they are already landed before the report reaches you."

p-devops.md:199
  "s-test-analyzer applies infra fixes during test-run analysis"
```

Both contradict FINDINGS.md (2026-08-09 — infra fixer consolidation): s-test-analyzer is **analysis-only**, p-infra-fixer is the executor, p-devops discovers prod-infra gaps and writes them to the report and returns FAIL.

p-coder-fix-mode's stale block has a downstream effect: it tells the coder that any infra fix it sees in the report was "already landed" — which is false. The coder should treat infra findings as out of scope (which it does, one line earlier: "Do not touch: ... test infrastructure files"), so the stale claim is on a dead branch of the prompt — but it's still a contradiction a careful LLM might reason about and an obvious thing for a future reviewer to flag.

---

## 5. Architectural Findings

### AF-1 — The fix agents need a shared "fix-loop wrapper" skill

The cluster has three fix agents (p-coder-fix-mode, p-tester-fix-mode, p-infra-fixer) that share a near-identical protocol shape:

1. Read a report from disk
2. Filter to findings routed to me
3. For each finding: triage → apply fix → verify via s-test-executor (test-infra only for p-infra-fixer)
4. Services-check pre-flight (before first re-run)
5. Append "Fixes Applied" section to the report ← only p-infra-fixer does this today
6. Return completion summary

Steps 4 and 5 are duplicated or inconsistent. The `test-execution-protocol` skill is the natural home for both, OR a sibling skill `fix-loop-protocol` could own the full fix-session wrapper (services-check + verify-loop + report-append), with `test-execution-protocol` continuing to own just the s-test-executor delegation mechanics. Recommendation: keep `test-execution-protocol` focused (it's already loaded by p-test-runner, which has a different shape — it doesn't append to the report because on PASS it writes its own fresh report) and create a new `fix-loop-protocol` skill loaded by the three fix agents only.

### AF-2 — `s-diagnostics-fixer` should be in p-infra-fixer's `task` block

Simplest fix in the report. p-infra-fixer needs `s-diagnostics-fixer: allow` added to its frontmatter `task` block and a "Python diagnostics" step added after its Step 5 (apply fixes + syntax validation). The step should be conditional: **invoke only when at least one modified file ends in `.py`** — non-Python infra files (Dockerfile, YAML, shell) do not produce basedpyright diagnostics.

The invocation template can either live in `p-infra-fixer`'s prompt (one-task block, agent-specific) or in the proposed `fix-loop-protocol` skill (shared, with the same condition). Recommend the skill home since the template would be identical to `coder-shared-core`'s.

### AF-3 — Stale-language cleanup is a documentation-strategy issue

The two stale `s-test-analyzer` claims survived a consolidation that touched both files. The pattern: when an agent's role changes (s-test-analyzer went from fixer to analysis-only), every prompt that described the old role needs a sweep. We have no mechanism for this today — the agent-architect's FINDINGS.md records the change, but no automated check verifies that prompts stop referencing the old behaviour.

**Recommendation (process, not code):** when an agent's role changes, the consolidation prompt should include a `grep` for the agent's name across `.opencode/agents/` and `.opencode/skills/` to catch downstream references. This is what I just did manually in this review — it surfaced both stale claims in one grep. Adding it to the consolidation playbook makes it repeatable.

---

## 6. Prompt Findings

### PF-1 — `p-tester-fix-mode.md` Output section is too thin

```
## Output

Write test fixes and manifest updates via tools only — never in response
text. Final response: completion confirmation only.
```

That's the entire Output section — 2 lines. By contrast, `p-infra-fixer`'s Step 9 (Return) defines a structured summary with per-RC PASS / FAIL / capped statuses. `p-coder-fix-mode`'s "Completion Verification" section enumerates exactly what every in-scope row should look like.

**Risk:** when p-tester-fix-mode finishes, the operator gets an unstructured "completion confirmation only." They cannot tell from the response alone how many RCs were Type A vs Type B, how many passed on first iteration, how many capped. This blocks the operator's decision about re-invoking p-test-runner.

**Recommendation:** standardize the fix agents' final response shape — aligns with AF-1's `fix-loop-protocol` skill (which would also own the report-append template, so the response text and the on-disk section stay consistent).

### PF-2 — `p-coder-fix-mode.md` Step 0b has a stale parenthetical

Line 184: "no test-infrastructure file was modified (those belong to DevOps's own remediation pass, already completed before the report reached you)" — DevOps no longer remediates test-infra; p-infra-fixer does. This is the same staleness as AF-3 in a different location. (Found via a grep on "DevOps's own" which surfaced this line; included here as a prompt-quality finding rather than architecture because it's a verification-criterion text bug, not a routing bug.)

### PF-3 — `test-fix-mode-procedure` does not mention services-check

The `test-fix-mode-procedure` skill says nothing about verifying Docker services are running before the first s-test-executor invocation. That step lives only in the inline `p-tester-fix-mode.md` "Verify Loop" section. If p-tester-fix-mode is the agent that loads the skill, the services-check is still covered — but the skill is incomplete as a standalone protocol document, and any future fix agent that loads the same skill would re-invent the services-check block instead of inheriting it.

This is the same gap that AF-1's `fix-loop-protocol` skill would close: extract the services-check + verify-loop + report-append wrapper so the protocol is complete in one place, not split between an agent prompt and a skill.

### PF-4 — p-infra-fixer's "Stop" wording differs from the other two fix agents

Same content, three different wordings:

```
p-coder-fix-mode:   "... Run `bash scripts/docker-build.sh` or invoke p-devops for services-up,
                     then re-invoke p-coder-fix-mode."

p-tester-fix-mode:  "... Run `bash scripts/docker-build.sh` or invoke p-devops for services-up,
                     then re-invoke p-tester-fix-mode."

p-infra-fixer:      "... Run `bash scripts/docker-build.sh`
                     or invoke p-devops for services-up, then re-invoke p-infra-fixer."
```

Trivial in isolation but it's the kind of drift the operator noticed — three agents in the same pipeline stage saying the same thing slightly differently. Extraction to a skill removes the drift permanently.

---

## 7. Token Optimization Opportunities

### TO-1 — Services-check block × 3 → 1 skill reference

Current cost: 17 + 17 + 22 lines = **56 lines of inline duplication** across 3 agents.

Proposed: each agent's "Verify Loop / Services check" subsection becomes a one-line reference: "Before the first s-test-executor invocation, run the services-check pre-flight defined in the `fix-loop-protocol` skill (or `test-execution-protocol` skill if we extend that one instead)."

Net savings: ~50 lines across the cluster. The skill itself would be ~25 lines, so the net is ~25 lines positive, but the bigger win is **single-source-of-truth** — the wording only ever changes in one place.

### TO-2 — Report-append template lives in the skill, not in p-infra-fixer

p-infra-fixer's Step 8 (lines 368-390) is the template for the `## Infra Fixes Applied` section. If the same template (parameterized by section name) lives in a `fix-loop-protocol` skill, p-infra-fixer can reference it in 1 line and the three fix agents share one canonical template. p-infra-fixer's prompt shrinks by ~22 lines; p-coder-fix-mode and p-tester-fix-mode each add ~1 line of reference (net positive on consistency, neutral on tokens for them, big win for p-infra-fixer).

### TO-3 — p-infra-fixer's Step 9 (Return) template

Lines 392-419 (27 lines) define the structured return summary. Same argument as TO-2: this is a fix-agent-wide pattern, not infra-specific. Move to the skill, parameterize by agent name. Saves ~20 lines in the p-infra-fixer prompt.

### TO-4 — Stale `s-test-analyzer` block in p-coder-fix-mode

Lines 119-124 (5 lines) describe a remediation flow that no longer happens. Removing them saves 5 lines and removes a contradiction. Net: -5 lines, +0 contradictions.

**Cluster token savings estimate:** ~50 lines from TO-1, ~25 from TO-2 + TO-3 combined, 5 from TO-4. Total ~80 lines of prompt text that becomes shared or removed — small in absolute terms but high-value because it's the verbatim-duplicated block most likely to drift again.

---

## 8. Documentation Extraction Opportunities

| Content | Current Home | Recommended Home | Loaded By |
|---|---|---|---|
| Services-check pre-flight + STOP-on-services-not-running | inline × 3 agent prompts | new `fix-loop-protocol` skill (or extend `test-execution-protocol`) | p-coder-fix-mode, p-tester-fix-mode, p-infra-fixer |
| "Fixes Applied" report-append template + per-RC disposition block | inline in p-infra-fixer only | new `fix-loop-protocol` skill, parameterized by section name | same 3 fix agents |
| Fix-agent structured return summary (Step 9 template) | inline in p-infra-fixer only | new `fix-loop-protocol` skill | same 3 fix agents |
| s-diagnostics-fixer conditional invocation (only when `.py` modified) | ad-hoc — in p-coder-fix-mode via `coder-shared-core`; absent from p-infra-fixer | new `fix-loop-protocol` skill (covers p-infra-fixer); coder agents continue to inherit via `coder-shared-core` | p-infra-fixer (new); p-coder-* continue via `coder-shared-core` |
| Cross-agent sweep checklist after role change | not documented | add to agent-architect's own FINDINGS.md-update procedure or a `consolidation-checklist` micro-skill | p-agent-architect |

**Skill design decision — extend `test-execution-protocol` or create `fix-loop-protocol`?**

Option A — extend `test-execution-protocol`:
- Pros: single skill for the whole verify-loop surface; 4 agents load it (p-test-runner + 3 fix agents).
- Cons: p-test-runner does NOT append to reports (it writes its own fresh `_test-result.md` on PASS) and does NOT need a conditional s-diagnostics-fixer invocation. Loading a fix-loop skill on p-test-runner makes it carry dead sections.

**Option B (recommended) — create `fix-loop-protocol`:**
- A new skill, loaded only by the 3 fix agents.
- It owns: services-check pre-flight, verify-loop wrapper around `test-execution-protocol`, conditional s-diagnostics-fixer invocation (only when `.py` files modified), report-append template (parameterized by section name), structured return-summary template (parameterized by agent name).
- `test-execution-protocol` stays focused on s-test-executor mechanics, loaded by all 4 delegating agents.
- Clean separation: `test-execution-protocol` = the callee protocol; `fix-loop-protocol` = the fix-session wrapper that USES the callee protocol + adds services-check + diagnostics + report-append.

---

## 9. Agent Boundary Recommendations

### 9a — Inline content that belongs in a skill (Dimension 9a)

- **Services-check pre-flight block** in p-coder-fix-mode, p-tester-fix-mode, p-infra-fixer → extract to `fix-loop-protocol` skill (see §8).
- **Report-append "Fixes Applied" template** in p-infra-fixer → extract to `fix-loop-protocol` skill, parameterized by section name. Other two fix agents load the same skill and use `## Coder Fixes Applied` and `## Test Fixes Applied` respectively.
- **Step 9 (Return) template** in p-infra-fixer → extract to `fix-loop-protocol` skill, parameterized by agent name.
- **Conditional s-diagnostics-fixer invocation** → extract the "only when `.py` modified" condition + the standard template into `fix-loop-protocol`. Coder agents continue to use the unconditional version from `coder-shared-core` (their work is always `.py`); p-infra-fixer uses the conditional version from `fix-loop-protocol`.

### 9b — MCP tools that should be subagent-delegated

None. None of the touch-code agents hold structured-data MCP tools that an existing subagent wraps better. The fix agents call s-test-executor and s-devops-ops and s-diagnostics-fixer — all correct delegations.

### 9c — Missing subagent task templates

- **p-infra-fixer has no s-diagnostics-fixer task template.** Recommended template (would live in `fix-loop-protocol`):
  ```
  Tool: task
  Input:
  {
    "subagent_type": "s-diagnostics-fixer",
    "description": "Fix diagnostics on infra-modified Python files for plan <plan-id>",
    "prompt": "plan_id: <plan-id>\n\nfiles:\n< path/to/conftest.py >\n< path/to/utils_file.py >"
  }
  ```
  …gated by: "only when at least one modified file ends in `.py`."

### 9d — Dead permissions

- **`p-infra-fixer` is missing a permission it needs:** `s-diagnostics-fixer: allow` is absent from its `task` block. This is not a dead permission — it's the inverse, a missing allow for a needed delegation. Fix: add `s-diagnostics-fixer: allow` to p-infra-fixer's frontmatter `task` block.
- **No dead permissions found** in any of the 5 touch-code agents. Every allow in every task block maps to an invocation described in the prompt or its shared core.
- One borderline case: `p-tester-fix-mode` and `p-tester-generate-mode` both have `bash: allow` in their permission block. The `tester-shared-core` skill restricts bash to a single command (`bash scripts/pytest.sh --collect-only`). This is intentional (collection self-check) and documented in the shared core. Not a dead permission, but worth noting that the permission is broader than the documented use — a future agent-architect review could narrow it to a script-allow-list if opencode supports that.

### 9e — Cross-agent consistency

| Pattern | Consistent? | Drift found |
|---|---|---|
| s-test-executor delegation (templates, sequencing, Juice) | ✅ | already extracted to `test-execution-protocol` skill last cycle |
| Services-check pre-flight before first re-run | ❌ | duplicated inline ×3, three slightly different wordings (see PF-4) |
| Report-append "Fixes Applied" section | ❌ | only p-infra-fixer does it; other 2 fix agents leave no on-disk audit trail (see 4.2) |
| s-diagnostics-fixer invocation on modified `.py` files | ❌ | 4 of 5 touch-code agents do it; p-infra-fixer does not (see 4.1) |
| Final response / completion confirmation shape | ❌ | p-infra-fixer has a structured summary; p-tester-fix-mode has a 2-line "completion confirmation only"; p-coder-fix-mode references shared core but doesn't define a per-RC summary (see PF-1) |
| File-scope boundaries (what NOT to touch) | ✅ | every fix agent has explicit non-overlapping scope |
| Permission block pattern (wildcard-first then allow) | ✅ | all 5 agents use `"*": deny` then explicit allows for task, and `pheidipp-codebase-context_*: deny` then explicit allows for MCP |
| Agent descriptions in frontmatter / REGISTRY.md vs reality | ✅ | all 5 match; agent descriptions are accurate about who invokes them and what they own |
| Shared-core skill pattern | ✅ | coder-shared-core covers both coder agents; tester-shared-core covers both tester agents; p-infra-fixer has no shared core (it's the only fix agent for its file surface — correct, no peer to share with) |

---

## 10. Failure Mode Analysis

### FM-1 — p-infra-fixer lands a Python edit with a type cascade

**Scenario:** p-infra-fixer edits `tests/utils/factories.py` to fix a factory signature drift. The fix changes a parameter type. Without s-diagnostics-fixer, the type cascade propagates to every test file that imports the factory. On the next p-test-runner run, those tests fail with `reportUnknownParameterType` errors — not the infra failure the report originally described. The operator sees a fresh wave of failures and assumes the infra fix was wrong.

**Likelihood:** Moderate. p-infra-fixer edits Python files in maybe 30% of invocations (the rest are YAML / Dockerfile / shell). Of those, a non-trivial fraction changes signatures.

**Mitigation:** add the s-diagnostics-fixer step from AF-2 / 9c. The type cascade is exactly what s-diagnostics-fixer exists to catch, and the verify loop in p-infra-fixer's Step 6 runs s-test-executor immediately after — so the cascade would surface as a verify FAIL with confusing diagnostics. Better to catch it at the diagnostics step where the cause is obvious.

### FM-2 — Fix session dies; operator has no on-disk record of what was fixed

**Scenario:** p-coder-fix-mode processes 5 RCs from a validation report. It fixes 4 successfully, fails on the 5th, and the session is killed (network drop, model timeout, operator interrupts). The inline response is gone. The report on disk still shows all 5 RCs as `Route = p-coder-fix-mode`. The operator re-invokes p-coder-fix-mode — it re-reads the report, assumes all 5 RCs are still outstanding, and re-fixes the 4 that were already done. One of the re-fixes breaks because the first session's edit is still in place and the second session's edit conflicts.

**Likelihood:** Low for any single session, but the cluster runs many fix sessions per release.

**Mitigation:** adopt p-infra-fixer's `## Fixes Applied` append pattern on all 3 fix agents. The append happens after each RC, not just at session end — so a killed session still leaves a partial audit trail of which RCs were completed.

### FM-3 — Stale `s-test-analyzer` claim causes the coder to misroute

**Scenario:** p-coder-fix-mode reads a devops report with an Infrastructure-category RC. It sees the line "Infrastructure fixes are applied directly by s-test-analyzer during the test-run analysis pass — they are already landed before the report reaches you." The coder reasons: "this infra RC is already fixed; I should ignore it." But s-test-analyzer is now analysis-only — the infra RC is unfixed and waiting for p-infra-fixer. The coder silently skips it. The pipeline resumes with an unfixed infra failure.

**Likelihood:** Low — the coder's primary routing rule ("only act on Route = p-coder-fix-mode") would correctly exclude the Infrastructure RC anyway, because the routing summary would route it to `p-infra-fixer`. But if an RC's routing is ambiguous or the report's Routing Summary is malformed, the stale claim becomes load-bearing.

**Mitigation:** remove the stale block (TO-4). One edit.

### FM-4 — p-tester-fix-mode returns "completion confirmation only" and operator assumes success

**Scenario:** p-tester-fix-mode processes 3 Type B RCs (test flow redesign). Two have documented patterns; one does not — the procedure says "STOP and flag" for the undocumented one. p-tester-fix-mode correctly applies the two documented patterns, STOPS at the third, and returns "completion confirmation only" per its Output section. The operator reads this as "all 3 done" and re-invokes p-test-runner. The third RC's test still fails. The operator reruns p-test-runner, gets the same failure, and has to dig into the chat log to discover the STOP.

**Likelihood:** Moderate — Type B / Type C RCs without documented patterns are exactly the "STOP and flag" cases the procedure anticipates.

**Mitigation:** the structured return summary (PF-1) and the on-disk "Fixes Applied" append (4.2) would surface the STOP explicitly. Both come from the proposed `fix-loop-protocol` skill.

---

## 11. Prioritized Recommendations

### Must Fix

1. **MF-A — Add s-diagnostics-fixer to p-infra-fixer.** Add `s-diagnostics-fixer: allow` to the frontmatter `task` block. Add a "Python diagnostics" step (after Step 5, before Step 6) that invokes s-diagnostics-fixer only when at least one modified file ends in `.py`. Template the invocation per `coder-shared-core`'s pattern. **Rationale:** closes the type-cascade failure mode (FM-1) that the other 4 touch-code agents are already protected against.

2. **MF-B — Add "Fixes Applied" report-append step to p-coder-fix-mode and p-tester-fix-mode.** Each appends a per-RC disposition section to the report it read from disk: `## Coder Fixes Applied` and `## Test Fixes Applied` respectively. Use p-infra-fixer's existing template as the canonical form. **Rationale:** closes the killed-session failure mode (FM-2) and gives the operator a structured audit trail before they re-invoke p-test-runner.

### Should Fix

3. **SF-A — Extract `fix-loop-protocol` skill** (Option B from §8). Loaded by the 3 fix agents. Owns: services-check pre-flight, verify-loop wrapper around `test-execution-protocol`, conditional s-diagnostics-fixer invocation (for p-infra-fixer), report-append template (parameterized by section name), structured return-summary template (parameterized by agent name). p-coder-fix-mode and p-tester-fix-mode shrink; p-infra-fixer shrinks significantly; all three gain single-source-of-truth for the fix-session wrapper.

4. **SF-B — Remove stale `s-test-analyzer` claims** from p-coder-fix-mode (lines 119-124) and p-devops (line 199). Two-line edits.

5. **SF-C — Standardize the fix agents' structured return summary** via `fix-loop-protocol` (closes PF-1). p-tester-fix-mode's 2-line Output section becomes a reference to the skill's return template, parameterized by `Test Fixes Applied`.

### Nice to Have

6. **NH-A — Harmonize the "services not running" STOP message wording** (PF-4). Becomes free once SF-A lands — the skill owns the wording, parameterized only by agent name.

7. **NH-B — Add a cross-agent sweep step to the consolidation playbook** (AF-3): when an agent's role changes, `grep` for its name across `.opencode/agents/` and `.opencode/skills/` as part of the FINDINGS.md update. Prevents the next stale-claim drift.

8. **NH-C — Tighten `bash: allow` on tester agents** to a script allow-list, if opencode's permission model ever supports that. Today it's documented but broad. Defer to a future opencode capability.

---

## 12. Expected Impact

| Recommendation | Effort | Risk | Payoff |
|---|---|---|---|
| MF-A (s-diagnostics-fixer on p-infra-fixer) | Small (one frontmatter line + one prompt block) | Low — adds a step, doesn't change existing ones | Closes FM-1 (type cascade on infra Python edits) |
| MF-B (report-append on 2 fix agents) | Small-Medium (per-RC disposition loop + edit-to-report template) | Low — additive; p-infra-fixer already does this successfully | Closes FM-2 (killed-session audit gap) and FM-4 (silent STOP) |
| SF-A (`fix-loop-protocol` skill) | Medium (write skill + edit 3 agent prompts to reference it) | Low — pure extraction, no behaviour change | ~50 lines of duplication removed; single source of truth for fix-session wrapper; future drift blocked |
| SF-B (stale claims removal) | Tiny (two targeted edits) | Near-zero | Removes a textual contradiction (FM-3) |
| SF-C (structured return summary) | Small (moves into SF-A's skill) | Low | Removes PF-1; operator sees per-RC PASS/FAIL/CAPPED directly |
| NH-A (STOP message wording) | Free (rides on SF-A) | None | Cosmetic consistency |
| NH-B (consolidation sweep checklist) | Tiny (add to agent-architect's procedure) | None | Prevents the class of drift that caused SF-B |
| NH-C (bash allow-list on tester agents) | Out of scope today | None | Future cleanup |

**Cluster state after Must + Should fixes:** 3 fix agents share one `fix-loop-protocol` skill for their fix-session wrapper; all 5 touch-code agents invoke s-diagnostics-fixer on `.py` modifications; all 3 fix agents append a per-RC "Fixes Applied" section to the report they read; no stale s-test-analyzer claims; no inline services-check duplication.

---

## 13. Risks

- **MF-A might cause p-infra-fixer to invoke s-diagnostics-fixer on non-Python edits.** Mitigated by the "only when `.py` modified" condition. The condition must be stated explicitly in the prompt — if it's implicit, an LLM might invoke the fixer on YAML files, which would no-op or error. The skill (SF-A) is the right place to encode this condition so it's stated once, not three times.

- **MF-B might produce conflicting report state if two fix agents are invoked on the same report in parallel.** This is already true for p-infra-fixer's existing append step. The recommendation does not introduce a new failure mode — it extends an existing one to two more agents. The pipeline's correct usage is sequential (operator invokes one fix agent, waits, invokes the next), not parallel. No mitigation needed beyond documenting that the append is not concurrency-safe.

- **SF-A might tempt future agent designers to put fix-loop logic for non-fix agents into the same skill.** Mitigated by naming: the skill is `fix-loop-protocol`, not `agent-loop-protocol`. The description should state it's loaded only by fix agents.

- **Extracting the services-check block weakens each agent's ability to express its own precondition nuances.** p-infra-fixer's "test-infra findings only" gating is a real difference from the other two agents. The extraction must preserve it — either as a parameter the skill accepts, or as a one-line condition the agent prompt states before invoking the skill's services-check step. Recommend the latter: the agent prompt keeps the one-line condition ("skip this for prod-infra findings") and the skill owns the actual s-devops-ops delegation + STOP handling.

---

## 14. Final Recommendation

**Apply Must Fixes (MF-A, MF-B) first as targeted edits.** They are low-risk, two agents each, and close the two concrete failure modes the operator identified. They don't require the skill extraction.

**Then apply SF-A (`fix-loop-protocol` skill) as the consistency consolidation.** This is the real fix for the "different steps should be a shared skill" point the operator raised — it makes the three fix agents inherit a single fix-session wrapper, so future additions (a sixth fix agent, a new verify-loop step) land in one place. The skill extraction should subsume MF-A's conditional-s-diagnostics-fixer condition and MF-B's report-append template, so the two Must Fixes become concrete applications of the skill rather than duplicated inline blocks.

**Run SF-B (stale-claim removal) in the same pass as SF-A** — it's a 2-line cleanup that the grep-driven sweep (NH-B) would have caught. Adding NH-B to the consolidation playbook prevents recurrence.

**Defer NH-C (bash allow-list narrowing) to a future opencode capability.**

**Extension to all touch-code agents:** the cluster analysis above already covers all 5 touch-code agents (the 2 batch/generate agents were compared against the 3 fix agents). The only touch-code-specific recommendations are MF-A (single agent: p-infra-fixer) and the fix-loop-protocol skill (3 fix agents only — the 2 batch/generate agents do not read reports from disk and do not have verify loops). The batch/generate agents are already consistent with each other via their respective shared cores (`coder-shared-core`, `tester-shared-core`); no further touch-code-wide skill is needed beyond what this report recommends.

---

## Appendix A — Evidence Index

Grep results that established each inconsistency (all run against `.opencode/` tree):

- `s-diagnostics-fixer` invoker list: 5 matches in agents (4 allows + REGISTRY's "Invoked By" line which lists 4 callers, p-infra-fixer absent).
- `Infra Fixes Applied|append.*report|## .*Fixes Applied` over agents: matched only p-infra-fixer.md (6 hits across frontmatter comment + Step 8 + todo-list line).
- `services-check|services not running|s-devops-ops` over agents: matched 4 agents (p-devops, p-coder-fix-mode, p-infra-fixer, p-tester-fix-mode) + s-devops-ops + s-test-executor + p-test-runner. The 3 fix agents share near-identical inline blocks.
- `s-test-analyzer` over agents: matched p-test-runner (current — analyzer is analysis-only callee), p-devops line 199 (stale), p-infra-fixer (current — references it correctly as analysis-only), p-coder-fix-mode line 121 (stale), s-devops-ops line 42 (current). Two stale.

---

**End of report.**

Next action: operator decides whether to apply MF-A + MF-B as immediate edits, or sequence the full SF-A skill extraction first. Reviewer recommends MF-A + MF-B → SF-A (so the extraction subsumes them) — but if the operator prefers one pass, applying SF-A directly (with MF-A and MF-B as derivations from the new skill) is also viable.
