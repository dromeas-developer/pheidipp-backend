# Agent Review: p-infra-fixer

**Date:** 2026-08-09
**Mode:** Single Agent Review (session transcript gap analysis)
**Reviewer:** p-agent-architect
**Target:** `.opencode/agents/p-infra-fixer.md`
**Evidence:** `session-ses_0188.md` — pre-redesign session transcript
**Peer agents compared:** p-coder-fix-mode, p-tester-fix-mode (same pipeline stage — operator-invoked fixers)

---

## 1. Executive Summary

This review analyzes session `ses_0188` — a pre-redesign session where
p-infra-fixer (running under the earlier prompt) committed repeated
boundary violations while fixing procrastinate test-infra failures.

The session predates the current prompt's prohibitions. The analysis
therefore asks two questions:

1. **Which violations are now covered by the current prompt?**
   (Confirmation that the redesign worked.)
2. **Which violations would the current prompt still fail to prevent?**
   (The real gap analysis.)

**Finding:** The current prompt comprehensively covers the mechanical
violations (running tests via bash, starting Docker services, querying
the database directly). Each is prohibited 3-4 times across
Non-Responsibilities, Tool Usage, and Boundaries. The redesign
succeeded here.

**Three gaps remain** — all related to the diagnosis/fix boundary:
- **Gap A:** The prompt allows reading `app/` production code to
  "understand an infra failure" (Step 3), creating a loophole for
  open-ended code investigation.
- **Gap B:** The prompt prohibits *editing* test files but is silent
  on *reading* them, enabling test-file-based diagnosis.
- **Gap C:** The prompt says "do NOT diagnose" but provides no
  structural mechanism to prevent multi-turn investigation, and no
  guidance for when the report's diagnosis is wrong or incomplete.

---

## 2. Overall Assessment

| Dimension | Rating |
|---|---|
| Responsibility clarity | Strong — single owner, clear scope |
| Mechanical boundary enforcement | Strong — bash/docker/psql prohibited 3-4x each |
| Diagnosis boundary enforcement | **Weak — 3 gaps identified** |
| Token efficiency | Good — prompt is ~480 lines, well-structured |
| Failure mode coverage | **Gap — wrong/incomplete report diagnosis unaddressed** |
| Cross-agent consistency | Good — matches p-coder-fix-mode / p-tester-fix-mode pattern |

---

## 3. Strengths

1. **Redundant mechanical prohibitions.** The `bash scripts/run-tests.sh`
   prohibition appears in Non-Responsibilities ¶4, Tool Usage table row 1,
   Step 6 ¶1, and Boundaries ¶5. Four independent locations means the
   LLM encounters the prohibition regardless of which section it's
   reasoning from. Same for docker lifecycle and psql.

2. **Tool Usage table is prescriptive.** The `| Operation | Tool | NEVER |`
   format gives the LLM a clear lookup table. The "If you are about to
   type a `bash` command that is not YAML validation..." stop-rule is
   exactly the right pattern — it catches the agent at the decision
   point, not in the abstract.

3. **Services-check pre-flight (Step 2).** Mandating `s-devops-ops`
   services-check before any test re-run eliminates the "services not
   running, I'll start them myself" failure mode visible in the
   transcript (V2: `bash scripts/docker-build.sh`).

4. **2-iteration verify loop cap.** Prevents infinite fix-test-fix
   cycling. The transcript shows the agent running tests 6+ times
   without any cap — the current prompt's "STOP after 2 iterations"
   rule would have terminated the session much earlier.

5. **Operator-invoked pattern.** Matching p-coder-fix-mode and
   p-tester-fix-mode — primary agent, not subagent-delegatable — is
   architecturally correct. No primary-to-primary delegation exists,
   and the operator is the routing authority.

---

## 4. Weaknesses

### Gap A: Step 3 carves out a "read production code" loophole

**Current text (Step 3):**
> "If you need to inspect production code to understand an infra
> failure (e.g. a fixture imports from `app/` and the import path
> changed), invoke `s-index-health-guard` with `Domains: code` to
> ensure the code index is fresh."

**Problem:** This explicitly permits reading `app/` code to
"understand an infra failure." In the transcript, the agent read
`app/worker/app.py` (530 lines) and `app/api/v1/activity.py` to
understand the procrastinate app setup and the upload route. It
justified this as "understanding the infra failure" — exactly what
Step 3 allows.

The Non-Responsibilities says "Do NOT diagnose" but Step 3 creates
an exception that swallows the rule. An LLM reading both sections
would reasonably conclude: "I can read app/ code if it's to understand
an infra failure, but I can't diagnose." The distinction between
"understanding an infra failure" and "diagnosing" is subjective and
unreliable.

**What happened in the transcript:** The agent read `app/worker/app.py`
to understand how the procrastinate app is constructed, then read the
procrastinate library's schema.py, schema.sql, psycopg_connector.py,
and manager.py — all to diagnose why `apply_schema_async()` wasn't
bringing the test DB up to the current schema. This is pure diagnosis,
enabled by the Step 3 carve-out.

### Gap B: Reading test assertion files is not prohibited

**Current text (Scope of Edits):**
> "You may NOT edit or create: Any `test_*.py` assertion file →
> route to `p-tester-fix-mode`"

**Problem:** This prohibits *editing* test files but says nothing
about *reading* them. In the transcript, the agent read
`tests/api/test_activity_upload.py` (411 lines) and
`tests/integration/test_procrastinate_worker_defer.py` (145+ lines)
to understand the test structure, fixtures, and expectations.

An LLM fixing a conftest fixture would naturally read the test file
to see what fixtures the test expects. The prompt doesn't prevent
this, and reading test files is a gateway to diagnosis: once the
agent is reading test assertions, it starts reasoning about what the
test expects vs. what the code does — which is diagnosis, not fixing.

### Gap C: No guidance for wrong/incomplete report diagnosis

**Current text (Non-Responsibilities ¶1):**
> "The report tells you what to fix; your job is to fix it."

**Problem:** In the transcript, the report said:
- RC1: "fixture scope/event-loop binding" — the actual root cause was
  a stale procrastinate schema (missing `procrastinate_job_to_defer_v1`
  type).
- RC2: "PROCRASTINATE_DATABASE_URL not overridden" — this was already
  fixed, but the test still failed because of the stale schema.

The report's diagnosis was **wrong**. The real problem (stale
procrastinate schema from an older version) was not in the report at
all. The agent had to investigate to find the actual root cause.

The current prompt says "do NOT diagnose" and "the report tells you
what to fix" — but what should the agent do when the report is wrong?
The prompt has no answer. The agent's options are:

1. **Follow the report literally** → apply the stated fix → verify
   fails → iterate → cap at 2 → STOP with "fix attempts exhausted."
   This is the prompt's implied behavior, but it would leave the real
   problem unsolved.
2. **Investigate to find the real cause** → this is what the agent
   did, and it's what the prompt prohibits ("do NOT diagnose").

The prompt needs a third path: **when the report's diagnosis appears
wrong after the first verify failure, STOP and report the discrepancy
rather than investigating.** The operator then routes to
s-test-analyzer for re-classification.

---

## 5. Architectural Findings

### AF-1: The diagnosis boundary is enforced by prose, not structure

The mechanical boundaries (bash, docker, psql) are enforced by
permission blocks (`bash: allow` but with prescriptive Tool Usage
table) and by the existence of subagent delegations
(s-test-executor, s-devops-ops). The agent *can* violate them, but
the prompt makes it clear at every decision point.

The diagnosis boundary is enforced only by prose ("Do NOT diagnose").
The agent has `read`, `grep`, `glob`, `get_files`,
`search_codebase`, and `search_symbols` — all of which enable
open-ended investigation. There is no structural constraint that
limits the agent to "read only the files named in the report."

**Recommendation:** Add a "Read Scope" rule: the agent may only read
files that are (a) named in the report's findings, (b) in the Scope
of Edits table, or (c) imported by files in the Scope of Edits table
(one level deep, for import resolution). Reading `app/worker/app.py`
or `app/api/v1/activity.py` would violate this rule because neither
is in the Scope of Edits table.

### AF-2: Step 3's index-health check enables rather than constrains

Step 3 says: "If you need to inspect production code... invoke
`s-index-health-guard`." This frames production code inspection as a
legitimate activity that needs index freshness — rather than as a
boundary violation that should trigger STOP.

**Recommendation:** Remove Step 3's "inspect production code" framing.
Replace with: "If the report's finding references an import from
`app/` that you need to resolve, read only the specific import target
via `get_files` — do not browse `app/` directories or read entire
modules." This narrows the exception to import resolution, not
general investigation.

### AF-3: The verify-loop failure path doesn't handle wrong diagnosis

Step 6 says: if verify FAILS, "iterate: adjust the fix and re-invoke
s-test-executor." This assumes the fix direction is correct and just
needs adjustment. But if the report's diagnosis is wrong, the fix
direction is wrong — no amount of adjustment will work.

**Recommendation:** After the first verify FAIL, add a diagnostic
gate: "If the first verify fails AND the failure reason is different
from the report's stated diagnosis, STOP and report: 'Report
diagnosis appears incorrect — verify failure indicates <actual reason>.
Re-classification needed.' Do not investigate further."

---

## 6. Prompt Findings

### PF-1: Non-Responsibilities ¶1 vs Step 3 contradiction

Non-Responsibilities ¶1: "Do NOT diagnose or classify failures."
Step 3: "If you need to inspect production code to understand an infra
failure..."

These contradict. "Understanding an infra failure" by reading
production code IS diagnosis. The LLM must resolve this contradiction,
and the resolution is unpredictable.

**Fix:** Remove the Step 3 carve-out. Replace with a narrow import-
resolution exception (see AF-2).

### PF-2: "Read" permission is unconstrained

The prompt has `read: allow` with no scoping. The agent can read any
file in the project. Combined with `get_files`, `search_codebase`,
and `search_symbols`, the agent has full codebase exploration
capability — which is what enabled the 15+ turn investigation in the
transcript.

**Fix:** Add a "Read Scope" rule to the prompt (see AF-1). The
permission block can't enforce this (read is binary), but the prompt
can constrain the agent's behavior with a clear rule.

### PF-3: No "wrong diagnosis" escalation path

The Escalation table has no entry for "report diagnosis appears
incorrect." The agent has no defined action when the report says
"fix X" but the verify fails for a reason unrelated to X.

**Fix:** Add an escalation row: "Verify fails for a reason different
from the report's stated diagnosis → STOP, report discrepancy,
operator routes to s-test-analyzer for re-classification."

---

## 7. Token Optimization Opportunities

### TO-1: Step 3 can be condensed

Current Step 3 (Index health) is 8 lines for a step that should be
a narrow exception. After the AF-2 fix, it becomes 3 lines.

**Estimated savings:** ~5 lines, ~150 tokens.

### TO-2: Boundaries section duplicates Non-Responsibilities

The Boundaries section (lines 416-437) repeats 8 prohibitions that
are already in Non-Responsibilities (lines 64-100). The redundancy is
intentional (belt-and-suspenders), but 8 items × 2 locations = 16
prohibition entries for the same 8 rules.

**Recommendation:** Keep the redundancy for the mechanical
prohibitions (bash, docker, psql — these need to be caught at the
decision point). But for the diagnosis-related prohibitions, the
Non-Responsibilities section is sufficient — the Boundaries section
can reference it rather than repeating.

**Estimated savings:** ~4 lines, ~120 tokens.

---

## 8. Documentation Extraction Opportunities

### DE-1: "Wrong diagnosis" handling pattern

The pattern "when the report's diagnosis is wrong, STOP and report
the discrepancy" is not unique to p-infra-fixer. p-coder-fix-mode and
p-tester-fix-mode face the same issue: a validator/devops report says
"fix X" but the fix doesn't work because the real problem is Y.

**Recommendation:** Extract to a skill: `fixer-wrong-diagnosis-handling`.
Contains the diagnostic gate rule (after first verify FAIL, check if
failure reason matches report diagnosis), the STOP-and-report format,
and the escalation path. Loaded by all three fix agents
(p-coder-fix-mode, p-tester-fix-mode, p-infra-fixer).

---

## 9. Agent Boundary Recommendations

### AB-1: p-infra-fixer vs s-test-analyzer — diagnosis ownership

The transcript shows p-infra-fixer doing diagnosis that should belong
to s-test-analyzer. The current prompt says "do NOT diagnose" but
doesn't define the handoff: when p-infra-fixer discovers the report's
diagnosis is wrong, where does the re-diagnosis happen?

**Why p-infra-fixer should NOT delegate to s-test-analyzer directly:**

s-test-analyzer is a subagent invoked by p-test-runner via `task`.
While p-infra-fixer *could* technically get `s-test-analyzer: allow`
added to its permissions, this would be an architectural mistake:

1. **It would defeat the boundary.** If p-infra-fixer can call
   s-test-analyzer, it's doing diagnosis-by-proxy — the analyzer
   re-classifies, the fixer applies the fix, all in one session. The
   fixer would be driving the diagnosis, just through a delegate.
2. **It breaks the linear pipeline.** The architecture is:
   p-test-runner → s-test-analyzer → report → operator → p-infra-fixer.
   The analyzer classifies BEFORE the fixer sees the report. If the
   classification is wrong, the correct path goes back through the
   operator, not sideways between fixer and analyzer.
3. **It creates a loop risk.** Fixer calls analyzer, analyzer says
   "it's actually Infrastructure category X", fixer tries X, fails
   again, calls analyzer again... The operator-in-the-loop pattern
   prevents this by forcing a human decision point between
   re-classification and re-fixing.

**Recommendation:** The escalation path should be:
p-infra-fixer → STOP + report discrepancy → **operator** →
p-test-runner (re-run with deeper context) → s-test-analyzer
(re-classify) → updated report → **operator** → p-infra-fixer
(re-fix).

This matches the existing pattern: fixers don't diagnose, analyzers
don't fix, the operator routes between them. p-infra-fixer should
NOT get `s-test-analyzer: allow` in its permissions.

### AB-2: p-infra-fixer vs p-coder-fix-mode — read scope

p-coder-fix-mode owns `app/` code. p-infra-fixer owns infra files.
But p-infra-fixer can currently read `app/` code (read: allow, no
scoping). This creates a soft boundary violation: p-infra-fixer
can't *edit* `app/` code, but it can read it and reason about it —
which is diagnosis of app code, p-coder-fix-mode's territory.

**Recommendation:** Add the Read Scope rule (AF-1) to p-infra-fixer.
p-coder-fix-mode doesn't need the same rule because its job IS to
understand app code — but p-infra-fixer's job is to fix infra files,
not to understand app code.

---

## 10. Failure Mode Analysis

| Failure Mode | Evidence from transcript | Current prompt coverage | Gap? |
|---|---|---|---|
| Running tests via bash | V1, V9 — 6+ times | ✅ Prohibited 4x | No |
| Starting Docker services | V2 — docker-build.sh | ✅ Prohibited 3x | No |
| Querying database via psql | V3 — 5+ times | ✅ Prohibited 3x | No |
| Inspecting packages via docker exec | V4 — pip show | ✅ Covered by docker exec prohibition | No |
| Reading procrastinate library internals | V5 — schema.py, connector.py | ✅ Covered by "do NOT diagnose" | **Partial — see Gap C** |
| Reading app/ production code | V6 — app/worker/app.py | ⚠️ Step 3 carve-out | **Gap A** |
| Reading test assertion files | V7 — test_activity_upload.py | ❌ Not prohibited | **Gap B** |
| Multi-turn root-cause investigation | V8 — 15+ turns | ⚠️ "Do NOT diagnose" but no structural constraint | **Gap C** |
| No services-check before tests | V10 | ✅ Step 2 mandates it | No |
| Infinite fix-test cycling | 6+ test runs, no cap | ✅ 2-iteration cap | No |
| Wrong report diagnosis | Report said "fixture scope" — real cause was stale schema | ❌ No guidance | **Gap C** |

---

## 11. Prioritized Recommendations

### Must Fix

**MF-1: Add "Read Scope" rule** (addresses Gaps A, B, and part of C)

Add to Non-Responsibilities:
> "Do NOT read files outside your scope to investigate failures. You
> may read: (a) files named in the report's findings, (b) files in
> the Scope of Edits table, (c) files imported by files in the Scope
> of Edits table (one level deep, for import resolution only). Reading
> `app/` modules, `test_*.py` assertion files, or third-party library
> internals to 'understand' the failure is diagnosis — route to
> s-test-analyzer via the operator instead."

**MF-2: Remove Step 3 carve-out** (addresses Gap A)

Replace Step 3's current text with:
> "If the report's finding references an import from `app/` that you
> need to resolve (e.g. a fixture imports `app.db.session` and the
> path changed), read only the specific import target via `get_files`.
> Do not browse `app/` directories, read entire modules, or investigate
> beyond the specific import. If the import target doesn't resolve
> the issue, STOP — the problem is likely misdiagnosed."

**MF-3: Add "wrong diagnosis" escalation path** (addresses Gap C)

Add to Step 6 (Verify loop), after the first FAIL:
> "After the first verify FAIL, check: does the failure reason match
> the report's stated diagnosis? If the failure is for a different
> reason than the report describes (e.g. report says 'fixture scope'
> but failure is 'type does not exist'), STOP and report: 'RC<N>:
> Report diagnosis appears incorrect. Stated: <report diagnosis>.
> Observed: <actual failure>. Re-classification needed.' Do not
> investigate the new failure — that is s-test-analyzer's job."

Add to Escalation table:
> "Verify fails for a reason different from the report's diagnosis |
> Operator → p-test-runner (re-run with deeper context) →
> s-test-analyzer (re-classify)"

Note: p-infra-fixer does NOT call s-test-analyzer directly. The
re-classification goes through the operator and p-test-runner, not
sideways from fixer to analyzer. See AB-1 for the rationale.

### Should Fix

**SF-1: Extract `fixer-wrong-diagnosis-handling` skill** (DE-1)

The "wrong diagnosis" pattern applies to all three fix agents. Extract
to a skill rather than duplicating the rule in three prompts.

**SF-2: Condense Boundaries section** (TO-2)

Remove diagnosis-related duplications from Boundaries — keep only the
mechanical prohibitions (bash, docker, psql) that need decision-point
reinforcement.

### Nice to Have

**NH-1: Add "investigation turn cap" to the prompt**

Even with the Read Scope rule, an LLM might find ways to investigate
within scope. A turn cap ("if you've made more than 5 tool calls
without applying a fix, STOP and reassess") would provide a structural
backstop. However, this is fragile — legitimate fixes might need 5+
reads (conftest, factories, .env.test, MOCKING_CONTRACT.md, etc.).

---

## 12. Expected Impact

| Fix | Impact |
|---|---|
| MF-1 (Read Scope) | Prevents the 15+ turn investigation pattern. Forces the agent to work from the report, not from codebase exploration. |
| MF-2 (Remove Step 3 carve-out) | Eliminates the "understand the infra failure" loophole that enabled reading app/worker/app.py and library internals. |
| MF-3 (Wrong diagnosis escalation) | Gives the agent a defined action when the report is wrong, instead of defaulting to investigation. Routes re-diagnosis to the correct agent (s-test-analyzer). |
| SF-1 (Skill extraction) | Ensures all three fix agents handle wrong diagnoses consistently. |
| SF-2 (Condense Boundaries) | ~120 token savings, no behavior change. |

---

## 13. Risks

| Risk | Mitigation |
|---|---|
| Read Scope rule too narrow — agent can't resolve legitimate import dependencies | The "one level deep" exception allows reading import targets. If a conftest imports `app.db.session`, the agent can read `app/db/session.py` — but not `app/worker/app.py`. |
| Wrong-diagnosis gate triggers too early — first verify FAIL might be a minor variant of the stated diagnosis | The gate checks whether the failure *reason* matches, not whether the failure *test* matches. A fixture-scope diagnosis with a fixture-scope failure is a match, even if the specific fix needs adjustment. |
| Removing Step 3 prevents legitimate code-index checks | Step 3's index-health check was for code inspection, which the Read Scope rule now constrains. If index health is needed for other reasons (e.g. search_codebase for finding infra files), the agent can still invoke s-index-health-guard — just not for production code inspection. |

---

## 14. Final Recommendation

**Apply MF-1, MF-2, and MF-3 to the current p-infra-fixer prompt.**
These three changes close the diagnosis-boundary gaps that the session
transcript exposed. The mechanical boundaries (bash, docker, psql)
are already well-covered by the current prompt — the redesign
succeeded there.

The three fixes are small (total ~20 lines of prompt changes) and
targeted. They don't change the agent's permissions, subagent
delegations, or execution protocol — they close loopholes in the
diagnosis boundary that the transcript proved were exploitable.

After applying, consider extracting the wrong-diagnosis pattern to a
skill (SF-1) for consistency across all three fix agents.
