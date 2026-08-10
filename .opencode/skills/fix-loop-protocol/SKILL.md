---
name: fix-loop-protocol
description: >
  Loaded by the three fix agents — p-coder-fix-mode, p-tester-fix-mode,
  and p-infra-fixer — at session start. Contains the shared fix-session
  wrapper that sits around the verify loop: (1) services-check pre-flight
  before the first s-test-executor invocation, (2) the verify-loop wrapper
  that composes with the `test-execution-protocol` skill (s-test-executor
  mechanics), (3) conditional s-diagnostics-fixer invocation gated by
  whether at least one modified file ends in `.py`, (4) the per-agent
  "Fixes Applied" report-append template (parameterized by section name),
  and (5) the structured return-summary template (parameterized by agent
  name). Agent-specific task templates and per-finding triage logic stay
  inline in each agent's own prompt; this skill owns only the wrapper
  that all three fix agents share. p-test-runner does NOT load this
  skill (it writes its own fresh report on PASS rather than appending).
---

# Fix-Loop Protocol — Fix-Session Wrapper

All three fix agents (p-coder-fix-mode, p-tester-fix-mode, p-infra-fixer)
follow this wrapper around the verify loop. They read a report from
disk, filter to findings routed to them, apply fixes, and verify them.
This skill owns the shared steps; each agent's own prompt owns
finding-level triage logic and the agent-specific task templates.

`test-execution-protocol` (separate skill) owns the s-test-executor
delegation mechanics — sequential execution, scoped selectors,
iteration cap, Juice interpretation. This skill composes with it:
the verify-loop wrapper below delegates the actual test-execution
contract to `test-execution-protocol` and adds only the wrapper
around it.

---

## 1. Services-check pre-flight (before first s-test-executor invocation)

Before the FIRST `s-test-executor` invocation in the session, verify
Docker services are running by delegating to `s-devops-ops`:

```
Tool: task
Input:
{
  "subagent_type": "s-devops-ops",
  "description": "Verify services are running before test re-run",
  "prompt": "services-check"
}
```

If `s-devops-ops` returns STOP (services not running) → STOP and
report:

```
Services not running — operator must start them before fixes
can be verified. Run `bash scripts/docker-build.sh` or invoke
p-devops for services-up, then re-invoke <AgentName>.
```

Replace `<AgentName>` with the loading agent's own name
(`p-coder-fix-mode`, `p-tester-fix-mode`, or `p-infra-fixer`).

Skip this check for subsequent re-runs in the same session (services
don't stop mid-session).

**Agent-specific gating** (stated inline in each agent's prompt, not
here): p-infra-fixer skips the services-check for **prod-infra
findings** (config edits validated by syntax only — no test re-run
needed). p-coder-fix-mode and p-tester-fix-mode always run it before
the first re-run. The agent's prompt is the authoritative source for
whether the services-check applies in this session; this skill owns
the mechanics of how to invoke it once the agent decides it applies.

---

## 2. Verify-loop wrapper

The full s-test-executor delegation protocol is in the
`test-execution-protocol` skill — sequential execution (one call at
a time), scoped selectors only, 2-iteration cap, never run bash
directly, Juice interpretation. Do NOT restate those rules here.

After applying a fix for a specific finding (RC or routed row),
delegate a scoped re-run to `s-test-executor` with ONLY the
selectors from that finding's `Affected failures` list. Process
findings sequentially: fix finding 1 → verify finding 1 → fix
finding 2 → verify finding 2 → ...

Each agent names its own label format and s-test-executor prompt
template inline (the label differs — `verify-fix-RC<N>` for coder,
`verify-fix-RC<N>` for tester, `verify-infra-<RC-id>` for infra
fixer). The wrapper this skill defines is the **process**: apply →
verify → next finding. The label format is the agent's job.

The 2-iteration cap per finding is owned by `test-execution-protocol`:
if 2 fix iterations fail for the same finding, STOP and report
"iteration cap hit" in the return summary (Step 4 below).

---

## 3. Conditional s-diagnostics-fixer invocation (only when `.py` files modified)

**Gate:** invoke s-diagnostics-fixer ONLY when at least one file
modified in this session ends in `.py`. Files like `Dockerfile`,
`.env`, `docker-compose.yml`, `*.yaml`, `*.sh` do not produce
basedpyright diagnostics — invoking the fixer on a session that
only touched non-Python files is a no-op at best and an error at
worst.

Each fix agent invokes s-diagnostics-fixer as a final diagnostics
pass after all fixes are applied and the verify loop is complete.
The invocation pattern matches `coder-shared-core`'s "Completion
Verification — Diagnostics" pattern: batch up to 5 files per
invocation, group by proximity where possible. The fixer's own
batching gate will return a batching plan if any group is too
large — if that happens, split per the plan and re-invoke.

```
Tool: task
Input:
{
  "subagent_type": "s-diagnostics-fixer",
  "description": "Fix diagnostics on modified Python files for plan <plan-id>",
  "prompt": "plan_id: <plan-id>\n\nfiles:\n<path/to/file1.py>\n<path/to/file2.py>\n..."
}
```

After all invocations complete, verify each returned a text response
(per s-diagnostics-fixer's contract — it never writes report files):

- `✅ PASS — <file>: zero diagnostics` → the file was already clean.
  Note it and move on.
- A batching plan → file had too many diagnostics for one session.
  Create task items from the plan and process sequentially: invoke
  the fixer for one file, confirm the response, mark done, start
  next. Do NOT launch all in parallel.
- A fix summary (diagnostics found → fixed → remaining, final gate
  status) → check for unresolved errors and note them in the
  return summary (Step 4 below).

**Coder agents** (p-coder-fix-mode, p-coder-batch-mode) inherit
this unconditional version from `coder-shared-core` — their work
is always `.py`. **p-coder-fix-mode** does not need to call this
section's conditional explicitly; it inherits the unconditional
invocation via `coder-shared-core`.

**Tester agents** (p-tester-fix-mode) inherit unconditional from
`test-fix-mode-procedure` Step 7 — their work is always `test_*.py`.
They also do not need this section's conditional explicitly.

**p-infra-fixer** is the only agent that needs the conditional
explicitly: its scope spans both `.py` (conftest, utils) and
non-Python (Dockerfile, YAML, shell). It alone uses the gate as
stated above.

---

## 4. Report-append — "Fixes Applied" section (parameterized)

After all findings are addressed (or caps hit), append a structured
disposition section to the report on disk that this session read
from. The report path is the one the agent read at session start
(`reports/<plan-id>_devops.md` or `reports/<plan-id>_validation.md`
per the agent's own input spec).

Each agent uses its own section name:

| Agent | Section name |
|---|---|
| p-coder-fix-mode | `## Coder Fixes Applied` |
| p-tester-fix-mode | `## Test Fixes Applied` |
| p-infra-fixer | `## Infra Fixes Applied` |

Append via `edit` to the report file. Template:

```markdown
## <SectionName>

- <finding-id> (<sub-category, if applicable>): <file path> — <what changed>
  Verify: PASS (after <n> iteration(s)) | FAIL (capped after 2 iterations) | syntax valid (no test re-run) | STOP: <reason>
- <finding-id> (<sub-category>): <file path> — <what changed>
  Verify: PASS (after 1 iteration)
```

One row per finding addressed. The `<sub-category>` placeholder is
agent-specific (p-coder-fix-mode may distinguish validator-MINOR
vs devops-RC; p-infra-fixer distinguishes test-infra vs
prod-infra; p-tester-fix-mode uses Type A/B/C from its
`test-fix-mode-procedure` skill). The agent's own prompt defines
what sub-category to record; this skill owns only the row shape
and the section name table above.

**If no findings could be addressed** (all out of scope or
ambiguous), append:

```markdown
## <SectionName>

none — all findings out of scope or ambiguous. See STOP reasons in agent response.
```

**Concurrency note (not a mitigation requirement):** the pipeline's
correct usage is sequential — operator invokes one fix agent, waits,
then invokes the next. The append step is NOT concurrency-safe; two
fix agents running in parallel against the same report would clobber
each other's section. This is the same constraint p-infra-fixer
already works under; the recommendation extends it to the other
two fix agents without introducing a new failure mode.

The append happens **after the verify loop and diagnostics step
complete**, never before — so a killed session may leave a partial
audit trail (whichever findings reached the append step) but never
an audit trail that claims a verify PASS the agent didn't actually
observe.

---

## 5. Structured return-summary template (parameterized)

After all fixes are applied (or capped), the report is appended,
and diagnostics are complete, return a structured summary. The
operator reads this AND the on-disk section to decide whether to
re-invoke the upstream agent (p-test-runner or p-devops).

```
<AgentRole> fixes applied for plan <plan-id>.

Findings addressed:
- <finding-id> (<sub-category>): <file> — <one-line summary> → PASS
- <finding-id> (<sub-category>): <file> — <one-line summary> → syntax valid

Findings capped:
- <finding-id> (<sub-category>): fix attempts exhausted after 2 iterations. Last failure: <Juice>

Findings stopped:
- <finding-id> (<sub-category>): <file> — STOP: <reason>

Report updated: <report-path>
```

Replace `<AgentRole>` with the loading agent's role label
(`Coder`, `Test`, `Infra`). The four disposition states are:
- **PASS** — verify loop confirmed the fix landed (test-infra) or
  syntax validation passed (prod-infra, or non-test coder fixes)
- **syntax valid** — used by p-infra-fixer for prod-infra findings
  (no test re-run needed) and by p-coder-fix-mode for fixes that
  don't have associated test selectors in the report
- **capped** — 2-iteration verify cap hit
- **STOP** — finding was out of scope, ambiguous, or failed the
  no-silent-deviations boundary test

If all findings passed, the "capped" and "stopped" sections are
omitted. If any finding is capped or stopped, the operator must
read the on-disk report-append section for the full STOP reason
before re-invoking the upstream agent.

**Anti-pattern (do NOT):** returning "completion confirmation
only" without per-finding dispositions. The operator cannot tell
from a bare "done" message which RCs passed, which capped, which
stopped — and the next pipeline step depends on that
information. Every fix agent's final response uses this
structured shape, not a flat confirmation.

---

## What this skill does NOT own

To avoid scope creep, this skill explicitly does not own:

- **Finding-level triage** — p-tester-fix-mode's Type A/B/C
  classification, p-coder-fix-mode's row-routing-from-validator,
  p-infra-fixer's test-infra-vs-prod-infra split are each
  agent-specific and live in the agent's own prompt or its
  mode-specific procedure skill (`test-fix-mode-procedure`).
- **s-test-executor mechanics** — `test-execution-protocol` owns
  sequential execution, scoped selectors, iteration cap, Juice
  interpretation. This skill wraps it, not duplicates it.
- **Coder / tester shared core standards** — `coder-shared-core`
  owns code standards, command execution, file reading,
  migration rule, no-silent-deviations, comment discipline, type
  hygiene. `tester-shared-core` owns the equivalent for tester
  agents. This skill owns only the fix-session wrapper.
- **Report-routing rules** — which finding goes to which fix
  agent is decided by the upstream agent
  (p-implementation-validator, s-test-analyzer, p-devops) and
  recorded in the report's Routing Summary. This skill assumes
  the report's routing is authoritative and the loading agent
  has already filtered to its own findings.
