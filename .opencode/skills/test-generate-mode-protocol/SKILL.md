---
name: test-generate-mode-protocol
description: >
  Load this when p-test-architect enters Generate Mode (default). Contains
  the full Steps 1–9 protocol: Load Inputs → Infrastructure Ingest →
  Process Routed RCs → Capability Inventory → Load Existing Suite →
  Update Manifest → Generate Tests Staged Narrow-to-Broad → Self-Check
  via Collection → Classify Coverage → Finalize (diagnostics + docs).
  Not needed in Fix Mode (load test-fix-mode-procedure instead). Load
  exactly once at mode entry; do not reload during the session.
---

# Generate Mode — Full Protocol (Steps 1–9)

## Command Execution (NON-NEGOTIABLE)

The only command this agent may ever run, for any reason, is:

```bash
bash scripts/pytest.sh --collect-only <path> [<path> ...]
```

Always use `scripts/pytest.sh`, never bare `pytest` — pytest is installed
in `.venv`, which a bare `pytest` invocation will not have activated, and
the check will fail with "pytest not installed" even though it is. This
is an environment problem, not a real collection failure; do not report it
as one.

Never run `pytest` directly. Never run `run-tests.sh`, `docker-*.sh`,
`db-*.sh`, or any other script. Never invoke bash for any purpose other
than the Step 7 self-check. Test execution, environment management, and
database migration belong entirely to DevOps — this allowance does not
change that boundary.

---

### Step 1 — Load Inputs

Before any retrieval, verify the code index is fresh by invoking `p-index-health-guard`:

```
Tool: task
Input:
{
  "subagent_type": "p-index-health-guard",
  "description": "Verify code index is fresh before test generation",
  "prompt": "Domains: code"
}
```

This ensures `p-code-explorer` returns current results for all subsequent delegation calls.

**Check for missing manifest.** If `tests/test-manifest/index.yaml` does not
exist, load the `manifest-bootstrap` skill to create the initial infrastructure
files (index.yaml, MOCKING_CONTRACT.md, conftest.py, first phase file) before
proceeding. The skill contains the creation logic; this prompt does not.

**Check for missing conftest.py.** If `tests/conftest.py` does not exist
(manifest exists but was created by an older bootstrap that didn't include
conftest.py), load the `test-infrastructure` skill for the canonical fixture
patterns, then delegate to `p-code-explorer` to resolve the production imports
(model classes, app factory, session factory, Base metadata) and create the
file. The skill provides the structural patterns; the explorer provides the
specific import paths. Write the file yourself — the explorer does not write code.

Load in this order, in a single batched `get_files` call where possible:

1. Implementation plan — the batch BRD
   (`docs/implementation/phase-N/phase-N-M/batch-N-<theme>.md`)
2. **Test scenarios companion file** — if the batch BRD has a companion
   `-tests.md` file at `docs/implementation/phase-N/phase-N-M/batch-N-<theme>-tests.md`,
   load it in the same batched call. Each scenario in this file is a
   concrete input/output pair that must become at least one test case,
   classified by Enforcement layer (type-system / database / application-logic)
   and Mock Boundary (none / external-only / db-session). Consume both
   classifications in Step 6 — they determine what to test and what to
   mock. If the file does not exist (purely structural batch, no behavioural
   changes), skip — the test architect derives tests from contracts alone.
3. Validator report for this plan (if available — do not block if missing)
4. DevOps report from the most recent execution cycle for this plan or
   sub-phase (if available — do not block if missing; this feeds Step 2)
5. `tests/test-manifest/index.yaml` and the current sub-phase file
   (`tests/test-manifest/phase-N-Mx.yaml`), if they exist. Load prior
   sub-phase files only if this plan extends a test file that a prior
   sub-phase also modified — you need to see the existing function list
   to avoid duplication. If this plan already has file entries in the
   sub-phase file with functions listed, that is the inventory from a
   prior session's Step 3 — see Step 3 for what to do with it.
 6. `tests/README.md` and `tests/MOCKING_CONTRACT.md` — accumulated
    do/don't lessons from real test failures (async session pitfalls,
    schema-inspection anti-patterns, determinism issues, etc.) and the
    current fixture/mock boundary rules. These are load-bearing inputs, not
    background reading: Step 2 depends on the former, Step 6 depends on
    the latter.
 7. **Per-folder test READMEs** — `tests/unit/README.md`,
    `tests/integration/README.md`, `tests/api/README.md`,
    `tests/behaviour/README.md`, and `tests/smoke/README.md`, if they
    exist. Load all of them in the same batched call as items 5 and 6.
    Each README's `## Contents` table lists what test files exist and what
    they cover — this is the map of the test suite, and it makes Step 4
    (Load Existing Suite) much cheaper by telling you what's in each
    directory before you open any test file. If a README doesn't exist for
    a directory, skip it — the doc-writer hasn't baselined it yet.

Do not load implemented files here. The capability inventory (Step 3) is
built entirely from the plan — routes, service methods, repository
methods, events, invariants, and acceptance criteria are all *described*
in the plan's own sections. Code files are only needed once you know
which specific test you're about to write, and different test types need
different amounts of it — loading everything now, before that's known,
means carrying the whole plan's implementation surface through every
step whether or not most of it is ever used. See Step 6 for staged,
per-test-type retrieval.

If the implementation plan is missing → STOP and report it.

### Step 2 — Ingest DevOps Infrastructure Fixes (MANDATORY when a DevOps report exists)

Skip only if no DevOps report exists yet. Read the report's
`## Infrastructure Fixes` section. For each entry, classify as one-off
(single file, unlikely to recur) or reusable failure class (async
session scope, mock boundary, schema-inspection anti-pattern, ordering
assumption, JWT/datetime determinism, etc.).

For every reusable class: append a dated entry to `tests/README.md` in
the existing do/don't format — symptom, root cause, failed pattern,
correct pattern.

If the fix crossed a mocking boundary: update `tests/MOCKING_CONTRACT.md`
directly — README records the lesson, the contract enforces it.

If a class already has ≥2 prior README entries: note it in this session's
completion confirmation — what the recurring failure class is, why it
persists, and whether it should move into a shared `conftest.py` fixture.

The goal: the same failure class should not recur more than twice before
it is either fixed structurally (a fixture) or made impossible to miss
(the contract).

### Step 2b — Process Routed Test Suite RCs (MANDATORY when the report routes RCs to this agent)

Skip only if no devops report exists, or if the report's `## Routing Summary`
has no row for `p-test-architect`. If it does: load the
`test-fix-mode-procedure` skill and run its steps, then continue to Step 3.

This runs during a normal Generate cycle when a devops report happens to be
available as context — fix stale assertions before generating new tests to
prevent "drift upon drift." Fix Mode is the dedicated-invocation equivalent
that skips the full Protocol entirely; both use the same procedure.

### Step 3 — Build Capability Inventory

**Check for an existing inventory first.** If the sub-phase file loaded
in Step 1 already has file entries for this plan with functions listed,
this is not the first session working on this plan — skip straight to the
paragraph below on verifying it, do not rebuild from scratch.

Verify the existing inventory against the plan you just loaded: if the
plan hasn't changed since the file list was recorded, use it as-is. If
the plan has changed (new steps, changed scope), update only the affected
file entries — add files the plan gained, remove ones it no longer has,
leave everything else untouched. Then proceed to Step 4.

**If no existing inventory exists** (first session on this plan, in any
Test Mode), build it from the plan alone — no implemented files needed
yet — extracting everything that needs testing:

* API routes (path, method, expected responses, error conditions)
* Service methods (business rules, validation, error handling)
* Repository methods (persistence, uniqueness constraints, retrieval)
* Events (produced events, payload fields, ordering requirements)
* Invariants (from the plan's Invariants section)
* Acceptance criteria (from the plan's Testing Requirements section)
* **RETIRE/REWRITE entries** — if the plan's Testing Requirements section
  lists existing tests to RETIRE (delete — capability no longer exists)
  or REWRITE (update — capability changed), record them in the inventory.
  RETIRE entries are acted on in Step 4 (Load Existing Suite): the listed
  test files are deleted, not classified KEEP/MODIFY/EXTEND. REWRITE
  entries are acted on in Step 6: the listed test files are updated to
  match the new behaviour, not regenerated from scratch.

**If the plan doesn't state a detail, the inventory doesn't contain it.**
Do not open the implementation to fill the gap — not "just to check," not
to make a capability's description more precise, not to pre-derive an
exact formula or error condition for use later at Step 6. A capability
entry at this step is a name, a one-line description of what it verifies,
a `test_type`, and a `file_scope` — nothing that required reading code to
write. If you find yourself wanting to open an `app/` file to answer a
question at this step, that question belongs to `p-code-explorer` at
Step 6, not to you here. This is the same rule as Implementation
Resolution above; Step 3 is where it's most tempting to break, because
"just one look to be accurate" feels harmless — it is not: it is the
exact behaviour that produced four separate re-reads of the same file
with advancing line offsets in a session that prompted this rule.

Use `p-contract-verifier` to find invariants for the primary entities in the
plan and to confirm event payload requirements. Delegate via the `task` tool:

```
Tool: task
Input:
{
  "subagent_type": "p-contract-verifier",
  "description": "Resolve entity contracts and invariants for test capability inventory",
  "prompt": "Entity: <entity_name>"
}
```

The Contract Verifier returns entity schema, events, invariants, and storage
rules. Use this for contract verification instead of direct tool calls.

Build a capability → verification map: for each capability, what must be
asserted to consider it verified? Tag each capability with two things the
plan already states, since this is what Step 6 uses to stage retrieval —
you are not inferring anything new here, just carrying forward what the
plan's own Scope and step descriptions already say:

* **Test type** — `unit`, `integration`, `api`, or `behaviour`. A
  repository or service method in isolation is `unit`. A service calling
  a repository, or two services interacting, is `integration`. A route
  handler is `api`. A capability that only makes sense as part of a full
  user journey spanning multiple layers is `behaviour`.
* **File path** — the test file that will contain this capability's test(s).
  Most capabilities map to one file; group related capabilities under the
  same file. The plan's Scope section names the implementation files —
  derive test file names from them (e.g., `app/services/auth_service.py` →
  `test_auth_service.py`).

**Persist the file list immediately, regardless of Test Mode.** Write
every file this plan will need to the sub-phase file in Step 5a, right now,
before Step 6 generates anything — whether or not this session's Test Mode
will generate functions for it this time. Empty `functions` block for each,
`status: pending`. This is what makes a later, separate-session request
cheap: it reads the file list instead of re-deriving it from the plan.

### Step 4 — Load Existing Suite

Inspect existing tests to avoid duplication and identify gaps.

**Scope: `tests/` only.** The existing test suite lives in the standard
test directories (`tests/unit/`, `tests/integration/`, `tests/api/`,
`tests/behaviour/`, `tests/smoke/`). Never search or read anything under
`.archive/tests/` — those are test files from a previous codebase iteration
with different architecture, models, and patterns. They will bias your
inventory toward old conventions that no longer apply.

**Use per-folder READMEs as the map.** Before opening any test file, check
the `## Contents` table in the relevant directory's README (loaded in
Step 1). It lists every test file in that directory and what it covers.
Use this to triage:

* Test files whose `Covers` description doesn't overlap with the current
  plan's capabilities → skip them. Don't open them. They're not relevant.
* Test files whose `Covers` overlaps → flag them for inspection.
* Capabilities in the BRD that have no matching entry in any README's
  `## Contents` → they need new tests. That's a gap, not a duplicate.

After triage, open only the flagged files via `get_files` in one batched
call. Classify each as: KEEP, MODIFY, EXTEND, or REMOVE.

Do not inspect tests for features unrelated to the current plan's scope.

If a Test Mode is active (see Test Mode above), scope this inspection to
only the matching test directory (`tests/unit/` for `unit` mode, and so
on) — there is no reason to inspect `tests/integration/` while working in
`unit` mode. In `all` mode, inspect all four directories as before.

### Step 5 — Update Manifest (MANDATORY — runs every execution, in two parts)

The manifest is authoritative. Both parts delegate YAML writing to
`p-manifest-manager` (cheap model — deepseek-v4-flash). You provide
structured input; the manager writes the YAML file. You never write
phase YAML directly — formatting boilerplate on an expensive model
wastes tokens with zero reasoning value.

The input format is compact and line-based:

```
write-phase
plan_id: <string>
sub_phase: <string>
migrations: <bool>
phase: tests/test-manifest/phase-N-Mx.yaml
---
<file_path> <type> [generated]
  <ClassName> <fn1> <fn2> ...
---
coverage_events:
  <event_name>
coverage_invariants:
  <invariant_text>
```

- Each file starts with `<path> <type>` on its own line.
- Add the keyword `generated` after the type if the file has functions
  (Step 5b). Omit it for pending files (Step 5a).
- Indented lines after a file: `<ClassName>` followed by space-separated
  function names. One line per class.
- Files separated by `---`.

**Step 5a — runs immediately after Step 3, before Step 6 generates
anything.** Persist the file inventory now, regardless of which Test Mode
this session covers:

 * **If the manifest does not exist:** load the `manifest-bootstrap` skill
   to create `tests/test-manifest/index.yaml`, `tests/MOCKING_CONTRACT.md`,
   and `tests/conftest.py`. Then delegate the first phase file to
   p-manifest-manager.
 * **If the manifest exists:** delegate to p-manifest-manager with the
   file list from Step 3's inventory — every file this plan will need.
   No `generated` keyword, no function lines — manager writes all files
   with `status: pending` and empty `functions: {}`.

Format the input and invoke:

```
Tool: task
Input:
{
  "subagent_type": "p-manifest-manager",
  "description": "Write pending phase file for plan <plan-id>",
  "prompt": "write-phase\nplan_id: <plan-id>\nsub_phase: <N.M>\nmigrations: <bool>\nphase: tests/test-manifest/phase-N-Mx.yaml\n---\ntests/unit/test_<service>.py unit\ntests/integration/test_<service>.py integration\ntests/api/test_<endpoint>.py api\n..."
}
```

After the manager writes the file, proceed to Step 6.

**Step 5b — runs after Step 6 completes, before Step 7.** Collect the
function→class mappings from the Step 7 collection output (or, if
collection hasn't run yet, from the test files you just wrote).
Delegate to p-manifest-manager with the COMPLETE updated state:

- Include ALL files from Step 5a — both the ones this session
  generated (with `generated` keyword + function lines) and any still
  pending (no `generated`, no functions). The manager writes the
  complete phase file from your input.
- For each file this session generated: one indented line per class,
  with space-separated function names under that class. Derive from
  `pytest --collect-only -q <paths>` output — the `::` separators map
  directly: `file.py::ClassName::function_name` → function `function_name`
  under class `ClassName`.
- Add `coverage_events` and `coverage_invariants` from Step 8's coverage
  classification (if Step 8 hasn't run yet at this timing, defer coverage
  to a follow-up invocation after Step 8 completes — but the file list
  and functions must be written now).
- Do NOT set `executable` or `passed` — the manager always writes
  `executable: false, passed: false`. Those are DevOps-owned.

Format and invoke:

```
Tool: task
Input:
{
  "subagent_type": "p-manifest-manager",
  "description": "Write generated phase file for plan <plan-id>",
  "prompt": "write-phase\nplan_id: <plan-id>\nsub_phase: <N.M>\nmigrations: <bool>\nphase: tests/test-manifest/phase-N-Mx.yaml\n---\ntests/unit/test_<service>.py unit generated\n  Test<ClassName> test_<scenario_a> test_<scenario_b>\n  Test<OtherClass> test_<scenario_c>\ntests/integration/test_<service>.py integration generated\n  Test<ClassName> test_<scenario_d> test_<scenario_e>\ntests/api/test_<endpoint>.py api\n---\ncoverage_events:\n  <event_type>\ncoverage_invariants:\n  <invariant_id>: <invariant description>"
}
```

You never write to `index.yaml`. DevOps owns selection groups and promotion.

### Step 6 — Generate Tests, Staged Narrow-to-Broad

If a Test Mode was named for this invocation, run only the matching stage
below and stop — do not proceed to the other three. If Test Mode is `all`
or was not specified, work through every stage in this fixed order: unit
→ integration → api → behaviour. Each stage resolves its own file scope
from Step 3's tags via the `task` → `p-code-explorer` call shown under
Implementation Resolution above — that section's rule and fallback apply
here without exception; this step only adds the per-stage grouping logic.
In `all` mode, if a later stage's group has a file scope already fully
covered by an earlier stage's Testing Brief in this same session, reuse
that brief — don't invoke the Explorer again for the same files. In a
single-mode session, that carry-forward benefit doesn't apply — you're
paying only for this one stage's scope, which is the point.

**Stage 1 — Unit.** Group every capability tagged `unit` in Step 3 by
file scope — related capabilities sharing the same file(s) go in one
group. For each group, call `task` with `p-code-explorer` before writing
anything — for example:

```
Tool: task
Input:
{
  "subagent_type": "p-code-explorer",
  "description": "Resolve implementation details for unit test generation: app/services/threshold_detection_service.py",
  "prompt": "Mode: Test Architect\n\nGroup: unit — app/services/threshold_detection_service.py\n\nCapabilities:\n- hr_deflection_detects_lt1_lt2: HR deflection algorithm, ≥3 intensity steps, R² ≥ 0.80\n- rr_inflection_requires_min_duration: RR inflection needs ≥8 min per intensity level\n\nCanonical Fixtures (from tests/MOCKING_CONTRACT.md):\n<paste the table>"
}
```

Generate that group's unit tests from the returned Testing Brief, then
move to the next group — do not call `get_files` on
`threshold_detection_service.py` or any other `app/` path yourself; the
brief above is what you write assertions from. If the brief's Tagging
Check flags a capability as likely `integration` rather than `unit`,
apply the correction — this is the same signal Step 6 has always used
(a unit test wanting a third or fourth file is a mis-tag), just surfaced
earlier, before you start writing instead of mid-write. Correct
`type` in the phase file at Step 5b when this happens, not just in
your own reasoning for this session — a later `integration`-mode session
needs the corrected tag to know this capability is its responsibility.

**Keep the Capabilities list in the prompt at the detail level shown
above — a one-line plan-level description per capability, nothing more.**
Do not write out exact formulas, exact JSONB shapes, or exact error
conditions in this list. If you find yourself typing something like
`posterior mean = (current.value * decayed_weight + obs.value *
obs.weight) / new_total_weight` into a Capabilities entry, stop — that
level of precision is what you're asking `p-code-explorer` to derive
and return in its Signatures and behaviour section, not something you
supply going in. Writing it yourself means you already read the source
to get it, which is the violation this whole section exists to prevent.
A thin capability list produces a better brief, not a worse one — it's
what tells the Explorer what to look for without pre-answering the
question.

**Stage 2 — Integration.** Group `integration`-tagged capabilities by
interaction — the specific service+repository pair, or the specific pair
of services, involved. Same `task` → `p-code-explorer` call as Stage 1, one
per interaction group, skipping any group whose file scope is already
fully covered by a Stage 1 brief from this session.

**Stage 3 — API.** Group `api`-tagged capabilities by router file. Same
call pattern, one per router group: the router itself, its request/
response schemas, and the service(s) it calls, unless already covered by
an earlier stage's brief this session.

**Stage 4 — Behaviour.** By the time you reach this stage, most of what a
behaviour test needs is likely already covered by briefs from the
narrower stages before it — a behaviour test exercises the same
underlying code, just across a full journey rather than in isolation.
Call `p-code-explorer` only for file scope genuinely not covered by an
earlier brief: files spanning a user journey that no single narrower
capability already touched.

Before writing any test, load the `type-hygiene-standards` skill.
Apply the canonical type annotations from §5 (Fixture Annotations) and
§6 (Helper & Inner Functions) — every fixture parameter, helper function
parameter, and inner function parameter must carry its type annotation.
One untyped `db_session` parameter cascades to 100+ `reportUnknown*`
errors in pyright strict mode; annotating at generation time costs one
line per parameter and eliminates the entire cascade. Skip §7-§8
(production-specific — those are for p-coder).

Before writing any test, check it against `tests/MOCKING_CONTRACT.md`:
* If the Testing Brief already named a reusable fixture for this
  capability's dependencies, use it — do not re-derive the check from
  scratch, the Explorer already ran it against the Canonical Fixtures
  table you gave it
* Confirm the target layer's boundary rules (what is mocked, what is real)
  and write to that boundary, not to whatever is easiest for this case
* If neither the brief's fixture match nor an existing boundary rule
  covers this test, update `tests/MOCKING_CONTRACT.md` in this same
  execution, before writing the test that depends on it

Write tests to the appropriate directory — `tests/unit/`, `tests/integration/`,
`tests/api/`, `tests/behaviour/` match the stage above.

Rules (apply across all stages):
* Extend existing test files before creating new ones
* Do not create duplicate test files for the same capability
* Assert behaviour, not implementation — test what the code does, not how
* Every invariant from Step 3 must have at least one test
* Every event contract from Step 3 must have at least one ordering test
* Every Testing Requirement from the plan must have a corresponding test
* Negative paths (wrong input, missing data, auth failure) are as important
  as positive paths — the brief's error-branch detail in Test Architect
  Mode exists specifically to make these visible before you write, not
  just the positive path

**Shared infrastructure (conftest.py and tests/utils/).** When writing
tests that need fixtures or helpers beyond what already exists, load the
`test-infrastructure` skill. It is the single source of truth for:
per-directory conftest creation rules, `tests/utils/` module structure,
factory vs inline construction decisions, and MOCKING_CONTRACT.md
registration. Do not restate these rules — the skill already defines them.

**Enforcement-layer consumption (from the `-tests.md` scenarios).** The
test scenarios companion file now classifies each scenario with an
Enforcement layer and a Mock Boundary. Consume both:

* **`type-system` enforcement** — the invalid input is rejected by
  Pydantic, `Literal`, `Enum`, or a type hint at the schema boundary,
  before the service sees it. **Skip this scenario.** The framework
  enforces it; testing it tests Pydantic, not your code. Exception:
  custom `@field_validator` functions are your logic — test those.
  One schema-level integration test confirming the schema exists is
  enough; do not write per-field tests for type-enforced inputs.
* **`database` enforcement** — the invalid input is rejected by a
  PostgreSQL constraint (NOT NULL, UNIQUE, CHECK, FK) on commit. Write
  **one integration test per constraint** confirming it fires. Do not
  write one test per invalid value — the constraint rejects all of them
  the same way.
* **`application-logic` enforcement** — the invalid input passes the
  schema and the database constraints but is rejected by service-layer
  validation or a business rule. **Write full branch coverage.** Every
  branch, every boundary value, every error condition. This is where
  bugs live.

**Mock Boundary consumption.** The scenario's Mock Boundary tells you
what to mock:

* **`none`** — pure function, mock nothing. Let everything run real.
* **`external-only`** — mock only out-of-process dependencies (HTTP
  calls to external services, S3/MinIO, LLM proxy). Let all internal
  code run real — services calling repositories, models being
  persisted, event emission. The test should exercise the maximum
  amount of production code.
* **`db-session`** — unit test. Mock the DB session (AsyncSession)
  so the test doesn't need a live database. Let the service logic run
  real — the mock is for the session, not for the service's internal
  collaborators.

**The principle: mock at the external boundary, not the internal
boundary.** Mock things that leave the process. Do not mock things
inside the process. A test that mocks a repository to test a service
is testing the mock, not the service-repository interaction. A test
that mocks the DB session to test a service is testing the service
logic in isolation, which is the point of a unit test. The difference
is what you mock: the *transport* (session) vs. the *collaborator*
(repository). Mock the transport; let the collaborator run real.

Extending an existing test file still requires fetching that file yourself
before editing it — `p-code-explorer` never touches `tests/`, and its brief
covers only the implementation under test, not your own prior test code.

### Step 7 — Self-Check via Collection

Run after all tests from Step 6 are written, before classifying coverage.

For every test file created or modified in Step 6, run:

```bash
bash scripts/pytest.sh --collect-only <path> [<path> ...]
```

This is the only bash command this agent may ever run. It requires no
docker stack and no live database — collection imports the test modules
and discovers tests and fixtures; it does not execute test bodies or open
connections. If a fixture eagerly connects at import time rather than
lazily inside the fixture function, that is itself a conftest defect worth
reporting (candidate for `tests/README.md` or `tests/MOCKING_CONTRACT.md`),
not a reason to skip this check.

Interpret the result:

* **Collection succeeds** → proceed to Step 8.
* **Collection fails with an import error, `NameError`, `AttributeError`,
  fixture-not-found error, or syntax error** → this is exactly the class
  of failure this check exists to catch before DevOps ever sees it. Fix
  the file and re-run collection. Do not hand a file to DevOps that
  cannot even be imported.
* **Command fails with "pytest not installed", "pytest: command not
  found", or similar** → this means `scripts/pytest.sh` was not used, or
  does not exist at the expected path. This is not a valid outcome to
  report as a limitation. Confirm the command was exactly
  `bash scripts/pytest.sh --collect-only <path>` and retry once. If it
  still fails after that, STOP and report the exact command and error —
  do not silently skip Step 7 or write a note claiming the check could
  not be run in this environment.
* **Collection fails with a connection error** (cannot reach a database,
  Redis, or other live service) — after confirming `scripts/pytest.sh`
  was used and the failure is not the "not installed" case above — this
  is an environment dependency, not a defect in the test file. Note it in
  your completion confirmation under a one-line "Self-Check" note and
  proceed. Do not attempt to start infrastructure or loop on an error
  this agent has no ability to resolve.

This check exists to catch the single class of bug that costs the most
downstream iteration for the least effort to fix — a test file that never
even imports. It is not test execution and does not replace DevOps's
Step 5 execution and remediation. `validation.executable` and
`validation.passed` remain DevOps-owned regardless of what this finds.

### Step 8 — Classify Coverage

For each capability in the inventory from Step 3, classify:

* **Covered** — at least one test asserts this capability
* **Partial** — tested but edge cases or negative paths are missing
* **Missing** — no test exists for this capability

Record the classification in the current sub-phase file's `coverage`
section (events and invariants covered). This is merged into index.yaml
by DevOps at release promotion.

### Step 9 — Finalize

Confirm the sub-phase file, `tests/README.md`, and
`tests/MOCKING_CONTRACT.md` were saved (as applicable). If Step 2
flagged a recurring infrastructure risk (≥2 prior README entries for the
same failure class), note it in your completion confirmation — what the
class is, why it recurs, and whether it should move into a shared
`conftest.py` fixture. The manifest is the authoritative record; there is
no separate test pack file.

**Post-generation diagnostics:** Invoke `p-diagnostics-fixer` via the
`task` tool — batch **test files only** (files matching `test_*.py`) in groups
of up to 5 per invocation, one invocation per group. Do NOT include utility files
(`tests/utils/*.py`) or infrastructure files (`tests/conftest.py`) in these
batches — those are handled separately if needed. The fixer's own batching gate
will stop and return a batching plan if any group is too large — if that happens,
split per the plan and re-invoke. Group by proximity where possible (files in
the same test directory together). Invoke groups in order:

```
Tool: task
Input:
{
  "subagent_type": "p-diagnostics-fixer",
  "description": "Fix diagnostics on generated test files for plan <plan-id>",
  "prompt": "plan_id: <plan-id>\n\nfiles:\n<path/to/test_file1.py>\n<path/to/test_file2.py>\n..."
}
```

No `max_iterations` — the fixer's own batching gates keep each invocation
bounded. After all invocations complete, verify each returned
a text response: a fix summary (diagnostics found → fixed → remaining,
final gate status), a batching plan, or a zero-diagnostics confirmation
(`✅ PASS — <file>: zero diagnostics`). The diagnostics-fixer never writes
report files — all results are returned as text in its response.

**Handling a zero-diagnostics confirmation:** The file is already clean —
note it and move on. No file was written; that is expected.

**Handling a batching plan response:** If the fixer returns a batching plan
(text, no file), create a `todowrite` tasklist from it. Each file in the
plan becomes one task item. Process sequentially — invoke the fixer for one
file, confirm the report was saved, mark the task complete, then start the
next. Do NOT launch all invocations in parallel — the batching plan exists
specifically because the workload is too large for concurrent processing.

**Important:** Count files correctly before invoking. The batching gate is
triggered at 6+ files for plan-based multi-file mode. If you need to include
utility files (`tests/utils/*.py`) or infrastructure files, invoke them
separately in single-file mode, not as part of a multi-file batch.

After all tasks are complete, invoke `p-documentation` via the `task` tool to update or create
  per-folder READMEs in the test directories this invocation touched.
  Provide the sub-phase manifest path and the list of test files created
  or modified:

  ```
  Tool: task
  Input:
  {
    "subagent_type": "p-documentation",
    "description": "Update per-folder test READMEs for plan <plan-id>",
    "prompt": "Manifest: tests/test-manifest/phase-N-Mx.yaml\n\nFiles:\n<path/to/test_file1.py>\n<path/to/test_file2.py>\n..."
  }
  ```

  The doc-writer reads the manifest for file-to-function mappings and
  capability descriptions, and updates or creates `README.md` files in
  `tests/unit/`, `tests/integration/`, etc. One invocation covers all test
  directories — the doc-writer batches its own checks internally.

Then STOP.
