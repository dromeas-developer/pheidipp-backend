# Execution Manifest — Phase-2.3-P2 Validation-Fix Batch 1

**Plan:** `docs/implementation/phase-2/phase-2-3-p2-physiology-update.md`
**Validation report:** `reports/phase-2-3-p2_validation.md`
**Batch:** 1 of 1

---

## Origin

The Phase-2.3-P2 validator (`reports/phase-2-3-p2_validation.md`, 2026-07-12)
classified the result as **PASS WITH MINORS**. Two findings were raised:

- **MAJOR** — confidence monotonicity ratchet not implemented. The
  architect has addressed this; per the user, no work remains on it.
- **MINOR** — write amplification on `update_in_place`. This manifest
  addresses that finding.

The validator's routing for the MINOR finding: *"p-coder + this report —
the service should track which JSONB columns were touched in
`working_state` and only pass those to `update_in_place`, per Step 6's
'minimise write amplification' requirement."*

This is the entire scope of this manifest. No other Coder-owned work is
in scope.

---

## Steps

### Step 1 — Minimise JSONB write amplification on `update_in_place`

**Scope.** Modify the `update_in_place` call site in
`PhysiologyUpdateService.apply_observations` (currently at
`app/services/physiology_update_service.py:589-594`) so the service
only passes the JSONB columns that were actually mutated during the
current call, instead of always passing all four (`lt1`, `lt2`, `cp`,
`max_hr`).

**Concretely:**

1. Compute the set of touched outer column names from
   `working_state.keys()` using the existing `_PARAMETER_PATH` table
   (mapping `PhysiologyParameter` → `(column_name, sub_key)`). This is
   the same lookup `_apply_updated_states` already performs.
2. At the `update_in_place` call site, build the kwargs so:
   - `lt1` is `physiology.lt1` if `"lt1" in touched_columns`, else `None`.
   - `lt2` is `physiology.lt2` if `"lt2" in touched_columns`, else `None`.
   - `cp` is `physiology.cp` if `"cp" in touched_columns`, else the
     `_UNSET` sentinel from `app/repositories/athlete_physiology_repository.py`.
   - `max_hr` is `physiology.max_hr` if `"max_hr" in touched_columns`,
     else the `_UNSET` sentinel.
3. The default-import pattern: the `_UNSET` sentinel is module-private
   in the repository. Either:
   - (a) import it explicitly from the repository module, or
   - (b) reproduce the sentinel inline in the service.
   Prefer (a) — promote `_UNSET` to a module-level named export in the
   repository (e.g. `_UNSET_SENTINEL`) and import it in the service.
   This keeps the single source of truth for the sentinel in the
   repository. **Do not** rename the existing `_UNSET` — that breaks
   any other call sites; just add a new public-ish alias
   (`_UNSET_SENTINEL`) and use it from the service.

   If the architect (or stack-truth conventions) disallow cross-layer
   reach-in for a module-private symbol, fall back to (b) — define
   `_UNSET: object = object()` at module level in the service module
   and use that. The repository's `_UNSET` continues to be
   module-private; the two sentinels are intentionally distinct
   objects, which is correct (the repository compares by identity
   against its own `_UNSET`).

4. Do not change the signature or behaviour of `update_in_place` in the
   repository. The repository's existing guards
   (`if lt1 is not None`, `if lt2 is not None`,
   `if cp is not _UNSET`, `if max_hr is not _UNSET`) already do
   exactly what is needed — the bug is purely on the service side,
   which is currently passing all four columns every time.

5. Do not change `_apply_updated_states`. It already updates only the
   columns whose parameters appear in `working_state`; the issue is
   that the *subsequent* `update_in_place` call re-writes all four
   columns regardless.

6. Do not change the call ordering, the flush behaviour, the event
   firing logic, the shift detection, or any other branch of
   `apply_observations`. The fix is a local refactor of kwargs
   construction for one method call.

**Why this is the right fix.** The repository's `update_in_place`
already supports the "only some columns" mode — its `if lt1 is not
None` and `if cp is not _UNSET` guards skip columns the caller did
not pass. The Coder-only fix is on the caller side: stop passing
unchanged columns.

**Why this is a MINOR (not MAJOR).** The values written are correct —
they are the current in-memory state of the row, identical to what
they would be after a no-op write. The concern is write amplification
(extra JSONB bytes emitted to PostgreSQL, extra `WAL` records, extra
`flag_modified` work, although that one is already limited to touched
columns in `_apply_updated_states`). No correctness, invariant, or
contract change.

**Forbidden (for this step):**
- `app/services/twin_recalibration_service.py` — the MAJOR finding
  lives architect-side; do not touch.
- `app/repositories/athlete_physiology_repository.py` — beyond
  optionally promoting the `_UNSET` alias per (a) above, do not modify
  the repository. The fix is service-side.
- The MAJOR finding's code path (`_compute_metric_confidence`,
  `_detect_confidence_transitions`, `metric_confidence` output) — out
  of scope for this batch.
- Tests — `[OWNER: Test Architect]`. Do not add, edit, or run tests.

**No migration.** The fix is service-side; no ORM model changes; no
Alembic revision. DevOps does not own this batch — there is nothing
for DevOps to do.

---

## Batch Success Criteria

This batch is complete when:

1. **Service-side** — `apply_observations` passes only the JSONB
   columns that were touched in `working_state` to `update_in_place`.
   Inspecting the call site shows `lt1`/`lt2` as `None` when not
   touched, and `cp`/`max_hr` as the `_UNSET` sentinel when not
   touched.

2. **Behaviour preservation** — the values written to each column are
   identical to the pre-fix values (because `physiology.lt1` etc. are
   already the in-memory post-`_apply_updated_states` state). An
   observations-only-touching-`cp` call does not re-write `lt1`,
   `lt2`, or `max_hr`. Verified by reading the post-edit call site and
   confirming the kwargs are conditional on `touched_columns`.

3. **Sentinel consistency** — if the (a) path is taken, the service
   imports the repository's sentinel by name (not by redefinition).
   If the (b) path is taken, the service defines its own `_UNSET`
   sentinel and uses it. The two paths are equivalent in behaviour;
   pick one and stay consistent within the file.

4. **No out-of-scope edits** — only the
   `update_in_place` call site in
   `app/services/physiology_update_service.py` and, if path (a) is
   chosen, the `_UNSET` alias in
   `app/repositories/athlete_physiology_repository.py` are modified.
   No other files touched.

5. **No new imports left unused** — the import of `_UNSET` (or
   whichever name) is added to the existing import block, not
   appended as a separate `from <module> import` line.

6. **No `flag_modified` regression** — `_apply_updated_states` still
   calls `flag_modified` on every column in `touched_columns` (this
   is unchanged by the fix; verify by reading the method after the
   edit).

7. **No tests run, no tests added, no migrations generated** — the
   Coder role does not own these for this batch. The Test Architect
   will pick the fix up in their next pass.

---

## Context Needed

Step 1:
  Primary:    `app/services/physiology_update_service.py` (the
              `update_in_place` call site at lines 589-594, the
              `working_state` accumulation logic, and
              `_apply_updated_states` for context on which columns
              are touched),
              `app/repositories/athlete_physiology_repository.py`
              (the `_UNSET` sentinel and the `update_in_place`
              guards)
  Secondary:  `docs/implementation/phase-2/phase-2-3-p2-physiology-update.md`
              Step 6 ("Only update columns that have changed — leave
              unchanged columns untouched to minimise write
              amplification")
  Fallback:   —
  Forbidden:  `app/services/twin_recalibration_service.py` (MAJOR
              finding — architect-owned),
              `app/services/physiology_update_service.py` lines
              974-1007 (`_compute_metric_confidence` — MAJOR finding
              territory, not this step's concern),
              any `tests/**` file (Test Architect scope)
