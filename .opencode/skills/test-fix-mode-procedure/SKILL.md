---
name: test-fix-mode-procedure
description: >
  Load this when p-test-architect enters Fix Mode — i.e. a devops report's
  Routing Summary routes one or more RCs to p-test-architect (Category
  Test Suite). Contains the full 9-step triaged RC fix procedure including
  Type A/B/C classification, escalation gates, skill loading, and pattern
  verification. Not needed in Generate Mode (unless Step 2b triggers).
  Load exactly once at mode entry; do not reload during the session.
---

# Test Suite RC Fix Procedure

When a devops report routes Test Suite RCs to this agent, run this
procedure. It handles test assertion drift (error messages, enum values,
column expectations) and, where documented patterns exist, test flow
redesign and infrastructure pattern changes.

1. Read the devops report's `## Routing Summary` and identify every RC
   routed to `p-test-architect` with Category `Test Suite`.
2. For each in-scope RC, read its `## Root Cause Analysis` entry. The
   `Evidence` and `Affected failures` fields name the test files and
   the root cause.

3. **Triage each RC before attempting any fix.** Classify every in-scope
   RC into exactly one category. This triage is your own fix-strategy
   classification — it applies regardless of what category DevOps assigned
   in the Routing Summary.

   **Type A — Simple assertion drift.** The test's logic and flow are
   correct; only the expected value or error message string is stale
   (enum value changed, column width changed, error message format
   changed). Evidence: the RCA describes an assertion mismatch where
   updating a string, integer, or enum reference fixes it. → Fix
   directly. Proceed to step 4.

   **Type B — Test flow redesign.** The test's assertions are correct for
   what they intend to verify, but the test's logical flow doesn't reach
   the intended code path (e.g., a constraint violation fires before the
   target behaviour is exercised). Evidence: the RCA says the test fails
   at an unexpected step, not at the assertion. → Before proceeding:
   (a) load the test plan (the batch BRD that originally defined these
   tests) from `docs/implementation/` to reconfirm the expected test
   scenario and behaviour; (b) check `tests/MOCKING_CONTRACT.md` Known
   Anti-Patterns and `tests/README.md` for a documented fix pattern.
   If a documented pattern exists → apply it in step 4. If no pattern
   exists → STOP and flag: "Type B — <RC-id>: requires test flow
   redesign; no documented pattern found. Needs test architect review."

   **Type C — Infrastructure pattern change.** The fix requires changing
   how failure injection works (monkeypatch → event listener), how
   fixtures are scoped, how mocks are constructed, or any change to
   `conftest.py`. Evidence: the RCA says the test fails with an
   infrastructure-level error (`MissingGreenlet`, `InterfaceError`,
   fixture-not-found) that is not caused by a wrong assertion. → Before
   proceeding: (a) load the test plan from `docs/implementation/` to
   reconfirm the expected test scenario; (b) check
   `tests/MOCKING_CONTRACT.md` Known Anti-Patterns for a documented
   pattern. If a documented pattern exists → apply it in step 4. If no
   pattern exists → STOP and flag: "Type C — <RC-id>: requires
   infrastructure pattern change; no documented pattern found. Flag for
   next devops cycle."

   Do not attempt to design a new infrastructure pattern or test flow
   from scratch. If the pattern isn't documented in
   `tests/MOCKING_CONTRACT.md` or `tests/README.md`, STOP.

4. **Apply fixes for all triaged RCs.** For Type A: update the assertion
   strings or values to match current model/schema state. For Types B
   and C (with documented patterns): apply the documented pattern exactly
   as written — do not adapt it. Before editing any test file, load the
   `type-hygiene-standards` skill for canonical fixture types (§5-§6).
   Use `s-code-explorer` via `task` if you
   need implementation-file context to confirm the current model state,
   same delegation rule as Step 6 of the full Protocol.

5. **Skills for Fix Mode.** If any RC is Type B or C, load the
   `test-infrastructure` skill before attempting the fix. This skill
   contains canonical fixture patterns, engine lifecycle rules, and
   conftest conventions — the patterns for infrastructure-adjacent
   fixes live there.

6. Update the sub-phase manifest for the corrected tests. For each
   file with corrected functions: flip `passed: false` on those functions
   (leave `executable` as-is — DevOps will re-verify after your fix
   lands, same flow as a newly generated test).

7. Invoke `s-diagnostics-fixer` via `task` on each test file you modified,
   one invocation per file — same pattern as Step 9 in the full Protocol.
   Modified assertions can carry stale imports, type mismatches from enum
   changes, or unused references.

8. Run Step 7 (self-check via collection) on every file the fixer touched,
   plus any file you modified that the fixer didn't change — assertion
   edits can introduce import or syntax errors the fixer may not catch.
   The only command this agent may ever run is `bash scripts/pytest.sh
   --collect-only <path> [<path> ...]`. Never run bare `pytest`.

9. **Verify pattern application for Types B and C.** If you applied a
   documented pattern, re-read the pattern's source
   (`tests/MOCKING_CONTRACT.md` or `tests/README.md`) and confirm your
   edit matches the correct approach exactly. If the pattern doesn't
   cleanly apply, STOP and flag rather than adapting it — adapted patterns
   become undocumented patterns.

Run this procedure, then STOP. Do NOT run the full Protocol
(Steps 1–9). Do NOT generate new tests for unrelated capabilities.
