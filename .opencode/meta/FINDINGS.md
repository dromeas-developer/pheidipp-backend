# Findings

## Open Issues

None.

## Recent Changes

### Coder Split (Current Session)
- Split p-coder into p-coder-batch-mode and p-coder-fix-mode
- Extracted shared core (~400 lines) into `coder-shared-core` skill
- p-coder-batch-mode: BRD-driven batch implementation (~180 lines)
- p-coder-fix-mode: validator/devops report-driven fixes (~170 lines)
- Each agent loads `coder-shared-core` at session start
- Updated all references across agents, skills, and REGISTRY.md
- p-coder-fix-mode does NOT delegate to s-documentation (no BRD path in Fix Mode)
- Token savings: each agent is ~180 lines vs original 862 lines (79% reduction per invocation)

### Impact Analyzer Fix (Current Session)
- **s-impact-analyzer call explosion (57→3 calls typical):**
  Root cause: `get_change_impact` indexes architecture entity names
  (`plan-generation`), callers passed Python class names
  (`PlanGenerationService`) → primary call returned `not_found` → agent
  brute-forced 57 file-level calls to reconstruct what one architecture
  call could return.
- Subagent: added auto-resolution step (search_symbols → get_arch_for_code →
  retry get_change_impact); file-level tools gated behind explicit caller
  questions only; output contract updated to match actual response schema
- Updated all 4 call sites (p-implementation-architect, coder-shared-core,
  p-release-strategy-architect, retrieval-patterns) to pass architecture
  entity name alongside code name

### Coder De-duplication (Current Session)
- Extracted 2 on-demand skills from coder-shared-core:
  - `coder-comment-discipline` (38 lines) — loaded when writing source files
  - `coder-contract-gap-check` (41 lines) — loaded when a contract is unclear
- Removed redundant Boundaries sections from both coder agents (shared-core
  already owns them) — batch-mode: 18 lines, fix-mode: 18 lines
- No Silent Deviations completion checks slimmed to one-liners (~7 lines saved)
- Removed "all other rules apply unchanged" catch-all from fix-mode (2 lines)
- Subagent Delegation: 3 verbose Tool:task templates → compact table (50 lines saved)
- Net: shared-core 547→423 lines; batch-mode 237→214; fix-mode 204→182
- Total: 988→819 lines across the coder subsystem (17% reduction)

### Resolver De-duplication (Current Session)
- Removed duplicated Root Cause Analysis section (2 ASCII decision trees, 63 lines)
  — skill's R2-R3 already owns classification rules for Plan Gap, Plan Defect,
  Architecture Gap, Unauthorized Scope, and Misclassification
- Removed duplicated Architecture Authority section (14 lines) — skill's R4
  self-check already defines boundary rules
- Subagent Usage: 5 verbose Tool:task templates → compact table (73→12 lines)
- Net: p-implementation-resolver 276→130 lines (53% reduction)

### Architect De-duplication (Current Session)
- Removed Step 9 bullet list duplicating the routing table (7 lines)
- Removed redundant Location column from Available Skills table (8 lines)
- Compressed 4 verbose Tool:task templates (Steps 1, 2, 3, 6) to compact inline
  format (~40 lines saved)
- Trimmed Retrieval section: removed "codebase tools two distinct uses" (8
  lines — already covered by retrieval-patterns and Steps 1-6 prose)
- Fixed REGISTRY.md: 4 stale skill names → impl-architect-* prefixed names
- Net: p-implementation-architect 589→521 lines (12% reduction)

### Test Architect Split (Current Session)
- Split p-test-architect into p-tester-generate-mode + p-tester-fix-mode (same pattern as coder)
- Extracted tester-shared-core (274 lines) — role, command execution,
  implementation resolution, owned artifacts, test mode, manifest schema,
  fixture & mocking contract, test writing standards, comment discipline
- p-tester-generate-mode: 74 lines (mode dispatch + subagent table + protocol load)
- p-tester-fix-mode: 70 lines (mode dispatch + subagent table + protocol load)
- Removed: old p-test-architect.md (484 lines)
- Net: 484 → 418 lines (14% reduction); clean mode separation
- Updated REGISTRY agents/skills/delegation-graph; updated all subagent invocation lists

### Architect De-duplication (Previous Session)
- Gap Resolution: removed definitions from agent, now points to impl-architect-x-validation-checklist
- Step 9 file descriptions: replaced per-file prose with compact routing table
- impl-architect-batch-brd-template: removed context tiers + Batch
  Success Criteria tables (now exclusively in impl-architect-handoff-blocks)

### Ecosystem Fix (Previous Session)
- Fixed p-implementation-resolver: removed incorrect `mode: subagent` (all p-* are primary)
- Fixed s-code-explorer model string from `openrouter/inclusionai/ling-3.0-flash:free` to `deepseek-v4-flash-free`
- Confirmed no stale underscore skill directories remain
- Updated REGISTRY.md for p-implementation-resolver permissions (`skill: allow` was missing)
- **De-duplicated p-implementation-architect + skills overlap:**
  - Gap Resolution: removed definitions from agent, now points to impl-architect-x-validation-checklist
  - Step 9 file descriptions: replaced verbose per-file prose with compact routing table
  - impl-architect-batch-brd-template: removed context tiers + Batch Success Criteria tables (now exclusively in impl-architect-handoff-blocks)

### Agent Split (Previous Session)
- Split p-implementation-architect into Plan Mode only
- Created p-implementation-resolver for Resolution Mode + Gap Analysis
- Renamed skills with arch-/resolver- prefix convention
- Updated all routing references from p-implementation-architect to p-implementation-resolver
- Trimmed MCP tools from p-implementation-architect (removed 14 unused tools)
- Removed ALL MCP tools from p-implementation-resolver (delegates everything to subagents)

### Overview Refactor (Current Session)
- Replaced verbose overview.md (~184 lines) with thin summary (~20 lines)
- Created new cross-validation report format (`<plan-id>_x-validation.md`)
- Removed "Relevant Architecture Contracts" from batch BRDs (redundant with inline context)
- Removed "Relevant Event Contracts" from batch BRDs (tested by success criteria)
- Kept "Relevant Invariants" in batch BRDs (coder needs these inline)
- Updated p-implementation-architect.md Step 9 to produce three artifacts
- Updated arch-implementation-plan-templates SKILL.md with new templates
- Updated impl-architect-handoff-blocks SKILL.md references
- Updated p-implementation-validator.md to reference new format
- Updated impl-resolver-mode-procedure SKILL.md examples
- Updated REGISTRY.md skill descriptions
- Moved "Level of Detail" from agent prompt to skill — broken down by template and section
- Merged Context Needed into Steps (inline context per step)
- Removed "Architecture Principles To Enforce" from architect (~30 lines) — now loaded from architecture docs via Step 3
- Consolidated Step 9: load skills → resolve gaps → persist files (linear flow)

## Agent Status

| Agent | Status |
|---|---|
| p-coder-batch-mode | New — BRD-driven batch implementation, loads coder-shared-core |
| p-coder-fix-mode | New — report-driven fix implementation, loads coder-shared-core |
| p-implementation-architect | Plan Mode only, trimmed MCP tools, new output format |
| p-implementation-resolver | Resolution Mode + Gap Analysis, no direct MCP tools |
| p-implementation-validator | Updated to reference new plan format |
| p-devops | Routes findings to p-coder-fix-mode via report classification |

## Output Format Changes

### Before
```
docs/implementation/phase-N/phase-N-M/
  overview.md (184 lines — verbose, duplicated content)
  batch-1-<theme>.md (161 lines — included redundant sections)
  batch-2-<theme>.md (139 lines — included redundant sections)
  batch-N-<theme>-tests.md
  batch-N-architecture.md
```

### After
```
docs/implementation/phase-N/phase-N-M/
  overview.md (~20 lines — thin index only)
  <plan-id>_x-validation.md (~50 lines — RC1-7 record)
  batch-1-<theme>.md (~130 lines — removed redundant sections)
  batch-2-<theme>.md (~110 lines — removed redundant sections)
  batch-N-<theme>-tests.md
  batch-N-architecture.md
```

### Token Savings
- overview.md: -89% (184 → 20 lines)
- batch BRDs: -19% to -21% (removed redundant sections)
- Cross-validation report: +50 lines (new file)
- Net per plan: -36% (484 → 310 lines)

## Skill Naming Convention

- Agent-specific skills: prefix with short agent name (e.g., `arch-`, `resolver-`)
- Shared skills: plain names (e.g., `todowrite-discipline`, `retrieval-patterns`)
- All names use hyphens, not underscores
