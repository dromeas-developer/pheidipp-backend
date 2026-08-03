---
name: git-session-delta
description: >
  Load this when validating or fingerprinting a plan that has just been
  implemented — the skill tells you how to recover the commit range and
  file delta for this plan from git. Do not load this for open-ended
  repository exploration.
---

# Git Session-Delta

Recover the session boundary and file changes for the plan that was just
implemented, using git history alone — no hand-written state files or
scripts required.

## Workflow Precondition

The operator commits any pending work before starting a plan's
implementation. This holds by operator practice, not by tooling. Under
this precondition, `HEAD^` is always the commit immediately before this
plan's work. If ever violated, the delta is over-inclusive (recoverable
via caller cross-reference against the plan's Scope) — the skill does
not defend against it.

## Commands

Run these four git commands. No others.

### 1. Base and Current Commit

```bash
base_commit=$(git rev-parse --short HEAD^)
current_commit=$(git rev-parse --short HEAD)
```

No fallback path. No convention to enforce. No file to read from. `HEAD^`
is the base commit.

### 2. File Delta (Committed Changes)

```bash
git diff --name-status --find-renames <base_commit>..HEAD
```

Classify each line's status code:
- `A` or `C` → added
- `D` → deleted
- `M`, `R`, `T`, or `U` → modified

Filter out any path whose parts include a directory in `SKIP_DIRS`:

```
.git, .mypy_cache, .opencode, .pytest_cache, .ruff_cache, .venv,
__pycache__, docs, scripts, venv
```

### 3. File Delta (Uncommitted Changes)

Necessary because the FIX loop may run this skill before the coder
commits the fix (e.g. Test Pack Mode runs after fixes land but may run
before a committing step).

```bash
git status --porcelain
```

Classify using the same status-code mapping above. For untracked
directories (`??` entries), unroll to individual file entries — recurse
into the directory and emit one line per real file, skipping
`SKIP_DIRS`.

Union the committed and uncommitted results into three final lists:
Added, Modified, Deleted.

### 4. Deviation Notes

```bash
git log <base_commit>..HEAD --format="%H%n%s%n%b" --no-merges
```

Extract each commit's SHA, subject, and body verbatim. Return them as
raw text organized by commit.

Do NOT interpret, summarize, or classify deviations — that is the
caller's job.

- A commit with no body (only a subject) contributes just its SHA + subject
- Empty output → no commits in range → not an error. The caller should
  check whether all the plan's changes are uncommitted
  (`git status --porcelain` non-empty) before flagging

## Touched Areas Classification

Apply these area-priority rules, in this order, to any path that survives
the `SKIP_DIRS` filter:

```
models       — app/models
repositories — app/repositories
services     — app/services
api          — app/api
app          — app (fallback for any other app/ subdirectory)
schemas      — app/schemas
core         — app/core
migrations   — alembic/versions, migrations/versions
```

Any path that matches none of these prefixes maps to `root` (if it has
no slash) or `other`.

## Output Shape

Return a compact header plus the four data blocks. No interpretation,
no classification, no routing:

```
## Session Delta

Base commit: <sha>
Current commit: <sha>

### Files Added
- <path>
- <path>

### Files Modified
- <path>
- <path>

### Files Deleted
- <path>
- (or "none")

### Touched Areas
- <area>, <area>

### Deviation Notes (raw commit messages)
<commit sha>
<commit subject>
<commit body>

<commit sha>
<commit subject>
<commit body>

(Empty if no commits in range — check Files Added/Modified for
uncommitted work)
```

## When Not To Load This Skill

- Open-ended repository exploration (use `s-code-explorer` or
  `s-state-explorer`)
- "What already exists" queries (use `s-state-explorer`, which queries
  the live codebase — its brief is always current)
- Historical artifact scanning (use `s-history-explorer`)
- Retrieving entity/service/registration facts (use `s-state-explorer`)
- "Does this specific file exist and what does it contain?" (use
  `s-code-explorer`)

## Non-Responsibilities

The skill does NOT:

- Discover DB revision (DevOps Step 4 owns this via
  `db-revision-test.sh "check"`)
- Resolve Verified Facts sections — entities, services, repositories,
  routes, registrations, event producers, transaction boundaries
  (State Explorer owns this)
- Classify deviations (callers do this)
- Make routing decisions
- Run any command other than the four named git commands: `rev-parse`,
  `diff --name-status`, `status --porcelain`, `log --format`
- Modify any file
- Make architecture judgments about whether the file delta is "correct"
- Persist anything to disk — it is a stateless procedure, not a
  generator

## Failure Modes

| Failure | Mitigation |
|---|---|
| Git not initialized or not a git repo | Report STOP, callers must abort |
| Base commit == HEAD | Return empty delta + empty commit history, report `no_changes_since_base`. Valid state — may happen if the operator ran the skill against a commit where no plan was implemented, or if DevOps re-validates the same commit after a non-code-only fix |
| Uncommitted files present when caller is DevOps in Test Pack Mode | The skill must include `git status --porcelain` output even if `git diff HEAD^..HEAD` is empty, to catch working-tree changes. Union of the two is always returned; the caller does not have to know which path produced which file |
| Empty deviation-notes output | Valid if the coder wrote terse commits or did not commit at all. Not an error. The caller should check whether the empty body is because there were no deviations, or because the coder wrote no commit messages (in which case `git status --porcelain` still carries the file delta) |
| Operator violated the precondition (multi-plan session without commits in between) | Delta from `HEAD^` is over-inclusive, includes work from earlier plans in the same session. The skill cannot detect this — it is a deviation from the documented workflow precondition. Caller detects it by cross-referencing the plan's Scope section against the delta and noting files that do not belong |
