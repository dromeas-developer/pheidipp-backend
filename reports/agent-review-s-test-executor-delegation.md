# Agent Review: s-test-executor Sequential Execution Constraint

**Date:** 2026-08-09
**Mode:** Single Agent Review (cross-cutting — all delegating agents)
**Trigger:** Operator report of false failures from parallel test-pack runs
**Status:** APPLIED

---

## 1. Executive Summary

All four agents that delegate to `s-test-executor` (p-test-runner,
p-coder-fix-mode, p-tester-fix-mode, p-infra-fixer) lacked an explicit
prohibition against issuing multiple `task` calls to s-test-executor in
the same assistant message. An LLM reasoning about "verify each RC" or
"run each pack" could naturally batch multiple `task` calls in one turn.
Since all packs hit the same `test_pheidipp` database, parallel runs
cause `asyncpg.exceptions.TooManyConnectionsError` (connection pool
exhaustion) and cross-test interference (transactions, locks) that do
not exist in single-pack runs — producing false failures.

A **Sequential Execution Constraint** has been added to all four
delegating agents and to s-test-executor's own Rules section
(defensively). REGISTRY.md and FINDINGS.md updated.

---

## 2. Overall Assessment

**Severity: Must Fix** — this is a runtime correctness issue, not a
style preference. False failures from parallel test runs waste
operator time, trigger unnecessary fix loops, and can mask real
regressions behind connection-pool noise.

**Root cause:** The verify-loop sections in the fix agents described
*what* to do (delegate scoped re-runs per RC) but not *how* to sequence
the calls. The AGENTS.md Batching Discipline instruction ("Prefer one
batched call over multiple sequential calls for independent
information") actively encourages parallel calls for independent work —
and test packs appear independent to the LLM even though they share a
database. Without an explicit override, the LLM's default behavior is
to batch.

---

## 3. Strengths

- The existing verify-loop design is otherwise sound: scoped selectors,
  2-iteration cap, services-check precondition, Juice extraction.
- The `s-test-executor` contract is minimal and clear — it runs one
  pack per invocation and returns PASS/FAIL+Juice.
- The delegation graph is well-documented in REGISTRY.md — all four
  delegating agents were easy to identify.

---

## 4. Weaknesses

- **Missing sequencing constraint.** No agent explicitly prohibited
  parallel `task` calls to s-test-executor. The AGENTS.md batching
  discipline creates pressure in the opposite direction.
- **No shared constraint text.** Each verify-loop section was
  independent prose, so a constraint added to one would not
  automatically propagate to the others.
- **s-test-executor's own contract was silent on the matter.** It
  documents "one pack per invocation" but not that callers must not
  run multiple invocations in parallel.

---

## 5. Architectural Findings

### AF-1: Parallel test execution against a shared database is a systemic risk

The `test_pheidipp` database is a shared resource. All test packs
connect to it via the same asyncpg connection pool. Parallel pytest
sessions exhaust the pool and interfere via transactions and locks.
This is not a test-executor bug — it's an architectural constraint of
the test infrastructure. The constraint belongs in the agent prompts
because the agents decide when and how to invoke the executor.

### AF-2: AGENTS.md batching discipline needs a known exception

The global AGENTS.md instruction "Prefer one batched call over multiple
sequential calls for independent information" is correct for retrieval
tools but dangerous for test execution. The new constraint in each
agent's verify-loop section overrides this for s-test-executor calls
specifically. A future ecosystem review should consider whether other
shared-resource subagents (e.g., s-alembic, which runs migrations
against the same database) need similar constraints.

---

## 6. Prompt Findings

### PF-1: p-test-runner Step 4 — no sequencing guidance

**Before:** Step 4 said "Delegate to s-test-executor with the
selectors" and showed one task template. No mention of sequencing.

**After:** Added a NON-NEGOTIABLE constraint block after the task
template: "Issue ONE s-test-executor task call at a time. Wait for it
to return before issuing the next. NEVER place two or more
s-test-executor calls in the same assistant message." Plus the
rationale (connection pool exhaustion, cross-test interference) and
the p-test-runner-specific note: "builds one selector set per
invocation and makes one call — do not split it into parallel packs."

### PF-2: p-coder-fix-mode Verify Loop — no sequencing guidance

**Before:** The Scoped re-run section said "After applying a fix for a
specific RC, delegate a scoped re-run..." with one task template. The
"Move to the next RC" instruction implied sequential processing but
did not prohibit parallel calls.

**After:** Added the NON-NEGOTIABLE constraint block before the task
template, with the explicit sequence: "fix RC1 → verify RC1 → fix RC2
→ verify RC2 → ..."

### PF-3: p-tester-fix-mode Verify Loop — no sequencing guidance

**Before:** Same pattern as p-coder-fix-mode. Same gap.

**After:** Same constraint text, with the same RC sequencing example.

### PF-4: p-infra-fixer Step 6 — no sequencing guidance

**Before:** Step 6 said "you MUST delegate a scoped re-run to
s-test-executor via task" with one task template. No mention of
sequencing across multiple findings.

**After:** Added the NON-NEGOTIABLE constraint block before the task
template, with the explicit sequence: "fix finding 1 → verify finding
1 → fix finding 2 → verify finding 2 → ..."

### PF-5: s-test-executor Rules — no defensive documentation

**Before:** The Rules section listed "One bash call to run tests. One
bash call to extract results." but nothing about caller sequencing.

**After:** Added a new first rule: "Sequential execution only. The
caller MUST issue one task call at a time..." with the rationale and
the note that "s-test-executor itself runs one pack per invocation and
cannot detect parallel siblings." This is defensive — s-test-executor
cannot enforce the constraint, but documenting it makes the contract
complete for anyone reading the subagent's prompt.

---

## 7. Token Optimization Opportunities

The constraint block is ~8 lines per agent × 4 agents = ~32 lines
added. This is acceptable for a NON-NEGOTIABLE safety constraint. The
wording is consistent across all four agents to avoid drift. No
further optimization needed — the cost of a false-failure debug
session far exceeds the token cost of the constraint.

---

## 8. Documentation Extraction Opportunities

The constraint text is duplicated across four agents. A future
extraction could move it to a shared skill (e.g.,
`test-execution-constraints`) loaded by all four agents. However, at
~8 lines each, the duplication is below the threshold where skill
extraction pays for itself (skill loading adds its own token cost).
**Recommendation: Nice to Have — defer until a third or fourth
shared test-execution rule emerges, then extract.**

---

## 9. Agent Boundary Recommendations

No boundary changes. The four delegating agents are the correct set —
REGISTRY.md confirms no other agent holds `s-test-executor: allow` in
its task permissions. The constraint is scoped to exactly the agents
that need it.

---

## 10. Failure Mode Analysis

| Failure Mode | Risk | Mitigation Applied |
|---|---|---|
| LLM batches multiple s-test-executor calls in one message | High — false failures, connection pool exhaustion | Explicit NON-NEGOTIABLE constraint in all four agents + s-test-executor |
| LLM reads AGENTS.md batching discipline and applies it to test execution | Medium — global instruction encourages batching | Constraint block explicitly overrides for s-test-executor calls |
| Future agent added with s-test-executor permission but without the constraint | Low — REGISTRY.md cross-agent pattern now documents the requirement | Pattern documented in REGISTRY.md; new agents should follow it |
| Constraint text drifts across agents over time | Low — all four use identical wording | Drift detection is part of ecosystem review; wording is simple enough to stay stable |

---

## 11. Prioritized Recommendations

### Must Fix (Applied)

1. ✅ Add sequential execution constraint to p-test-runner Step 4
2. ✅ Add sequential execution constraint to p-coder-fix-mode Verify Loop
3. ✅ Add sequential execution constraint to p-tester-fix-mode Verify Loop
4. ✅ Add sequential execution constraint to p-infra-fixer Step 6
5. ✅ Add defensive documentation to s-test-executor Rules section
6. ✅ Document cross-agent pattern in REGISTRY.md
7. ✅ Update FINDINGS.md ecosystem state

### Should Fix (Deferred)

8. Consider whether s-alembic needs a similar constraint — it runs
   migrations against the same database. However, s-alembic is
   typically invoked once per pipeline stage (not per-RC in a loop),
   so the parallel-call risk is lower. Defer to next ecosystem review.

### Nice to Have (Deferred)

9. Extract the constraint to a shared `test-execution-constraints`
   skill once a third or fourth shared rule emerges. At two rules
   (sequential + 2-iter cap), inline duplication is cheaper than
   skill loading.

---

## 12. Expected Impact

- **False failures eliminated:** Parallel test-pack runs that caused
  `TooManyConnectionsError` and cross-test interference will no
  longer occur. The LLM now has an explicit, NON-NEGOTIABLE
  instruction to issue one call at a time.
- **Operator time saved:** No more debugging false failures from
  parallel runs, no more unnecessary fix loops triggered by
  connection-pool noise.
- **Token cost:** ~32 lines added across 5 files. Negligible compared
  to the cost of a single false-failure debug session.

---

## 13. Risks

- **Risk:** The constraint is prompt-level, not enforcement-level. An
  LLM could still issue parallel calls if it ignores the instruction.
  **Mitigation:** The constraint is marked NON-NEGOTIABLE and placed
  directly in the verify-loop section where the decision is made. The
  rationale (specific exception name) makes it concrete, not abstract.
  True enforcement would require an opencode plugin that blocks
  parallel task calls to the same subagent — out of scope for
  agent-architect.

- **Risk:** The constraint text is duplicated, not extracted to a
  skill. Future edits to one copy could drift from the others.
  **Mitigation:** The wording is simple and stable. REGISTRY.md
  documents the pattern. Ecosystem review catches drift.

---

## 14. Final Recommendation

**Applied.** The sequential execution constraint is now in place
across all four delegating agents and s-test-executor itself. The
REGISTRY.md cross-agent pattern ensures future agents that gain
s-test-executor permission will follow the same rule. No further
action needed unless s-alembic or another shared-resource subagent
shows similar parallel-call issues.
