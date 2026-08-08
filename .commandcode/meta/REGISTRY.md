# Agent & Skill Registry

> Maintained by pheidipp-prompt-architect. Updated automatically whenever an
> agent or skill is created, modified, or deprecated. Load this file on every
> review invocation.
>
> Last baseline: 2026-08-05 (post-restructuring + permission audit + per-batch workflow)

## Agents — Primary (13)

| Agent | Role | Model | Subagents Delegated | Skills Loaded | Direct MCP | Key Permissions |
|---|---|---|---|---|---|---|
| p-agent-architect | Ecosystem optimizer — DEPRECATED, replaced by pheidipp-prompt-architect | nvidia/z-ai/glm-5.2 | none | todowrite-discipline (reads skills directly) | read, write, edit, glob, grep | task(deny all), skill(allow), bash(deny), todowrite(allow) |
| p-technical-advisor | Architecture decision authority | opencode-go/kimi-k2.6 | s-doc-explorer, s-vision-and-architect-author, s-index-health-guard | todowrite-discipline | 15 tools: architecture (6), vision (3), release-plan (5), orchestrator (1) | read(allow), edit/write/bash/grep/glob(deny), skill(allow), webfetch(allow), todowrite(allow) |
| p-release-strategy-architect | Release sequencing | opencode-go/kimi-k2.6 | s-index-health-guard, s-doc-explorer, s-impact-analyzer | retrieval-patterns, todowrite-discipline, sub-phase-document-template, release-planning-patterns | search_architecture, search_invariants, list_entities, get_entity_context, get_event_context, get_related_contracts, search_vision, list_vision_entities, get_vision_context, search_release_plan, list_release_plan_phases, list_release_plan_features, get_phase_context, get_feature_context, get_change_impact, refresh_release_plan, search_adr, list_adrs, get_adr_context, get_adrs_for_entity, get_related_adrs | task(3 allows), read/write/edit(allow), bash(deny) |
| p-implementation-architect | Plan author | opencode-go/glm-5.2 | s-state-explorer, s-doc-explorer, s-impact-analyzer, s-code-structure-explorer, s-contract-verifier, s-index-health-guard | retrieval-patterns, impl-architect-* (8 template skills), todowrite-discipline | search_invariants, get_related_contracts, get_change_impact, get_agent_dependencies, get_computation_pipeline, refresh_architecture, get_files, find_files, grep_files, search_codebase, search_symbols | task(6 allows), read/write/edit(allow), bash(deny) |
| p-implementation-resolver | Resolution author | opencode-go/kimi-k2.7-code | s-state-explorer, s-doc-explorer, s-code-structure-explorer, s-contract-verifier, s-index-health-guard | impl-resolver-mode-procedure, impl-architect-overview-template, impl-architect-batch-brd-template, impl-architect-handoff-blocks, impl-architect-adr-template, impl-resolver-delta-proposal-template, todowrite-discipline | none (all delegated) | task(5 allows), read/write/edit(allow), bash(deny), skill(allow) |
| p-implementation-validator | Post-implementation audit | opencode-go/kimi-k2.7-code | s-index-health-guard, s-state-explorer, s-contract-verifier, s-code-structure-explorer | git-session-delta, no-silent-deviations, stack-truth-conformance, validation-classification-and-report, type-enforcement-conformance, todowrite-discipline | get_files, find_files, grep_files, search_codebase, search_symbols, get_phase_context, get_computation_pipeline, get_arch_for_code | task(4 allows), edit/write(allow), bash(deny), read(deny), todowrite(allow) |
| p-consistency-validator | Cross-implementation consistency | poolside/poolside/laguna-s-2.1 | s-state-explorer, s-index-health-guard, s-code-structure-explorer | consistency-report-format, todowrite-discipline | get_files, find_files, grep_files, get_arch_for_code | edit/write(allow), read/grep/glob/bash(deny), todowrite(allow) |
| p-coder-batch-mode | Batch implementation from BRD | opencode-go/minimax-m3 | s-diagnostics-fixer, s-documentation, s-impact-analyzer, s-code-structure-explorer, s-contract-verifier, s-index-health-guard, s-alembic | coder-shared-core, no-silent-deviations, todowrite-discipline, type-hygiene-standards | get_files, find_files, grep_files, search_codebase, search_symbols, get_entity_context, get_arch_for_code | task(7 allows), read/grep/glob(deny), skill(allow), write/edit(allow), **bash(deny)**, todowrite(allow) |
| p-coder-fix-mode | Fix implementation from validator/devops reports | opencode-go/minimax-m3 | s-diagnostics-fixer, s-impact-analyzer, s-code-structure-explorer, s-contract-verifier, s-index-health-guard, s-alembic, s-test-executor | coder-shared-core, no-silent-deviations, todowrite-discipline, type-hygiene-standards | get_files, find_files, grep_files, search_codebase, search_symbols, get_entity_context, get_arch_for_code | task(7 allows), read/grep/glob(deny), skill(allow), write/edit(allow), **bash(deny)**, todowrite(allow) |
| p-tester-generate-mode | Test generator from BRD | opencode-go/minimax-m3 | s-code-explorer, s-diagnostics-fixer, s-documentation, s-contract-verifier, s-index-health-guard, s-manifest-manager | tester-shared-core, todowrite-discipline, type-hygiene-standards, test-generate-mode-protocol | get_files, find_files, grep_files | task(6 allows), read/grep/glob(deny), skill(allow), edit/write/bash(allow), todowrite(allow) |
| p-tester-fix-mode | Test fixer from devops RCs | poolside/poolside/laguna-s-2.1 | s-code-explorer, s-diagnostics-fixer, s-contract-verifier, s-index-health-guard, s-manifest-manager, s-test-executor | tester-shared-core, todowrite-discipline, type-hygiene-standards, test-fix-mode-procedure | get_files, find_files, grep_files | task(6 allows), read/grep/glob(deny), skill(allow), edit/write/bash(allow), todowrite(allow) |
| p-devops | Release gate orchestrator (thin) | opencode/deepseek-v4-flash | s-devops-ops, s-alembic, s-manifest-manager, s-index-health-guard | infrastructure-reference, todowrite-discipline | get_files, find_files | task(4 allows), **bash/edit/write(deny)**, read/grep/glob(deny), skill(allow), todowrite(allow) |
| p-test-runner | Test execution orchestrator (primary, operator-invoked) | opencode/deepseek-v4-flash | s-devops-ops, s-alembic, s-test-executor, s-test-analyzer, s-index-health-guard | todowrite-discipline | get_files | task(5 allows), bash/edit/write(deny), read/grep/glob(deny), skill(allow), todowrite(allow) |

## Agents — Subagents (16)

| Subagent | Role | Model | Invoked By | Permissions |
|---|---|---|---|---|
| s-contract-verifier | Entity/event contract resolver | openrouter/inclusionai/ling-3.0-flash:free | p-coder-batch-mode, p-coder-fix-mode, p-implementation-architect, p-implementation-resolver, p-tester-generate-mode, p-implementation-validator | task(deny all), skill(deny), bash(deny) — 7 MCP tools |
| s-impact-analyzer | Blast-radius analysis (self-resolving: code-name → architecture entity) | opencode/mimo-v2.5-free | p-coder-batch-mode, p-coder-fix-mode, p-implementation-architect, p-release-strategy-architect | task(deny all), skill(deny), bash(deny) — 8 MCP tools |
| s-code-explorer | Code file content resolver | deepseek-v4-flash-free | p-tester-generate-mode, p-tester-fix-mode | task(deny all), skill(deny), bash(deny) — 6 MCP tools |
| s-code-structure-explorer | AST-based structure resolver | deepseek-v4-flash-free | p-coder-batch-mode, p-coder-fix-mode, p-implementation-architect, p-implementation-validator, p-consistency-validator | task(deny all), skill(deny), bash(deny) — 9 MCP tools |
| s-state-explorer | Codebase registry resolver | deepseek-v4-flash-free | p-implementation-architect, p-implementation-resolver, p-implementation-validator, p-consistency-validator | task(deny all), bash(deny) — 10 MCP tools, skill: retrieval-patterns |
| s-doc-explorer | Documentation corpus resolver | deepseek-v4-flash | p-implementation-architect, p-implementation-resolver, p-technical-advisor | task(deny all), bash(deny) — 21 MCP tools, skill: retrieval-patterns |
| s-history-explorer | Prior reports/plans scanner | deepseek-v4-flash-free | available on-demand (not wired into standard pipeline) | task(deny all), bash(deny) — 3 MCP tools, skill: retrieval-patterns |
| s-diagnostics-fixer | Static-analysis fixer (typecheck, lint, format) | deepseek-v4-flash | p-coder-batch-mode, p-coder-fix-mode, p-tester-generate-mode, p-tester-fix-mode | bash(allow), read/write/edit(allow), skill: no-silent-deviations — 1 MCP tool |
| s-documentation | README maintainer | deepseek-v4-flash | p-coder-batch-mode, p-tester-generate-mode | skill(allow), bash(deny), edit/write(allow), todowrite(allow) — 4 MCP tools |
| s-index-health-guard | Index health + refresh | deepseek-v4-flash-free | p-coder-batch-mode, p-coder-fix-mode, p-implementation-architect, p-implementation-validator, p-tester-generate-mode, p-tester-fix-mode, p-devops, p-test-runner, p-consistency-validator | task(deny all), bash(deny), skill(deny) — 9 MCP tools |
| s-manifest-manager | Manifest write: phase file authoring + promotion | opencode/deepseek-v4-flash | p-tester-generate-mode, p-tester-fix-mode (write-phase); p-devops (promote-file, release-promote) | task(deny all), bash(deny), read/edit/write(allow) |
| s-test-executor | Mechanical test execution (bash-only) | opencode/deepseek-v4-flash | p-test-runner, p-coder-fix-mode, p-tester-fix-mode | task(deny all), bash(allow), all others deny |
| s-test-analyzer | Test failure analysis, routing, direct infra fixes | opencode-go/kimi-k2.7-code | p-test-runner (on FAIL) | task(deny all), bash(deny), read(escalation-only), edit/write(allow) — 12 MCP tools, skill: devops-analyzer-output-format |
| s-alembic | Alembic migration lifecycle (generate + apply-test + pending-changes-check + apply-prod) | poolside/poolside/laguna-s-2.1 | p-coder-batch-mode, p-coder-fix-mode (generate); p-test-runner (apply-test, pending-changes-check); p-devops (apply-prod) | task(deny all), bash/edit/write(allow), skill(allow) — 3 MCP tools, skill: infrastructure-reference |
| s-devops-ops | Docker services management (services-up, services-check, build-verify) | opencode/deepseek-v4-flash | p-devops, p-test-runner | task(deny all), bash(allow), all others deny |
| s-vision-and-architect-author | Architecture/vision document author | opencode-go/hy3 | p-technical-advisor | (see agent file) |

## Skills (31)

| Skill | Purpose | Loaded By |
|---|---|---|
| retrieval-patterns | Section-name handling, search_invariants filter docs, get_feature_context usage, index maintenance rules | p-implementation-architect, p-release-strategy-architect, s-doc-explorer, s-state-explorer, s-history-explorer |
| sub-phase-document-template | Sub-phase document format template | p-release-strategy-architect |
| release-planning-patterns | Anti-patterns, sizing rules, challenge questions | p-release-strategy-architect |
| impl-architect-overview-template | Implementation overview template + writing rules + anti-patterns + sizing | p-implementation-architect |
| impl-architect-batch-brd-template | Batch BRD template + step writing rules + anti-patterns + sizing | p-implementation-architect |
| impl-architect-x-validation-template | Cross-validation report template + writing rules | p-implementation-architect |
| impl-architect-test-scenarios-template | Test scenarios template + writing rules | p-implementation-architect |
| impl-architect-doc-updates-template | Architecture documentation updates template + writing rules | p-implementation-architect |
| impl-architect-handoff-blocks | BRD inline context tiers, Batch Success Criteria, architecture handoff conventions | p-implementation-architect, p-implementation-resolver |
| impl-resolver-mode-procedure | R0-R5 resolution procedure + Resolution Report Format | p-implementation-resolver |
| impl-architect-adr-template | ADR decision criteria, ADR file template, Architecture Delta Proposal Format | p-implementation-architect, p-implementation-resolver |
| impl-architect-x-validation-checklist | RC1-RC7 check definitions, computational invariant fixture gate, input validation enforcement table, Test Scenario Grill procedure, Enforcement/Mock Boundary tables | p-implementation-architect |
| stack-truth-conformance | Severity mapping for stack-truth violations (CRITICAL/MAJOR/MINOR) | p-implementation-validator |
| validation-classification-and-report | Severity definitions, Resolution Path, examples, output report format | p-implementation-validator |
| type-enforcement-conformance | Layer 4 audit: visibility, type strictness, enforcement layer placement, custom validators | p-implementation-validator |
| coder-shared-core | Boundaries, execution protocol, subagent delegation, todo-list discipline, tool usage, migration rules, code standards, diagnostics completion — shared by both coder agents | p-coder-batch-mode, p-coder-fix-mode |
| coder-comment-discipline | Comment rules: never/write-only/rule-of-thumb. Loaded on demand when writing or editing source files. | p-coder-batch-mode, p-coder-fix-mode |
| coder-contract-gap-check | Contract gap resolution: when to delegate to s-contract-verifier, fallback path. Loaded on demand. | p-coder-batch-mode, p-coder-fix-mode |
| no-silent-deviations | Six-bullet test for implementation/architecture boundary | p-coder-batch-mode, p-coder-fix-mode, p-implementation-validator |
| git-session-delta | File delta recovery from git for deviation detection | p-implementation-validator |
| consistency-report-format | Disposition classification + consistency validation report format | p-consistency-validator |
| devops-analyzer-output-format | DevOps Analyzer output contract: Header, RC structure, Routing Summary, Failure List | s-test-analyzer |
| tester-shared-core | Role, command execution, implementation resolution, owned artifacts, test mode, manifest schema, fixture & mocking contract, test writing standards, comment discipline — shared by both test agents | p-tester-generate-mode, p-tester-fix-mode |
| todowrite-discipline | Standard task-tracking pattern for multi-step agent protocols | p-coder-batch-mode, p-coder-fix-mode, p-tester-generate-mode, p-tester-fix-mode, p-devops, p-implementation-architect, p-implementation-validator, p-technical-advisor, p-release-strategy-architect, p-consistency-validator, p-agent-architect |
| test-infrastructure | Canonical conftest patterns, directory structure rules, per-directory conftest conventions, factory/builder conventions | p-tester-generate-mode, p-tester-fix-mode (primary), manifest-bootstrap (referenced) |
| type-hygiene-standards | Type annotation rules at code generation time — shared cascade prevention; test-specific fixture annotations; production-specific function/Pydantic annotations | p-tester-generate-mode, p-tester-fix-mode, p-coder-batch-mode, p-coder-fix-mode |
| test-fix-mode-procedure | Triaged RC fix procedure: Type A/B/C classification, escalation gates, plan recheck, pattern verification | p-tester-fix-mode |
| test-generate-mode-protocol | Full Steps 1–8 test generation protocol | p-tester-generate-mode |
| manifest-bootstrap | Initial test manifest creation (conftest.py, MOCKING_CONTRACT.md, index.yaml) | p-tester-generate-mode (when manifest absent) |
| infrastructure-reference | Platform service map, database architecture, command inventory, TimescaleDB augmentation procedures | s-alembic (primary), p-devops (reference) |

## Delegation Graph

```
p-technical-advisor
  ├── s-index-health-guard
  ├── s-doc-explorer
  └── s-vision-and-architect-author

p-release-strategy-architect
  ├── s-index-health-guard
  ├── s-doc-explorer
  └── s-impact-analyzer

p-implementation-architect
  ├── s-index-health-guard     (Step 1 — index freshness)
  ├── s-state-explorer         (Step 1 — codebase registry)
  ├── s-doc-explorer           (Step 2 — documentation context)
  ├── s-impact-analyzer        (Step 3 — blast radius)
  ├── s-contract-verifier      (Step 5 RC1 — contract saturation)
  └── s-code-structure-explorer (Step 6 — structural discovery)

p-implementation-resolver
  ├── s-index-health-guard     (R0 — index freshness)
  ├── s-state-explorer         (R2 — implementation state)
  ├── s-doc-explorer           (R2 — architecture context)
  ├── s-contract-verifier      (R2 — contract verification)
  └── s-code-structure-explorer (R2 — implementation structure)

p-implementation-validator
  ├── s-index-health-guard     (Step 5 — code index freshness)
  ├── s-state-explorer         (Step 1b — registry context)
  ├── s-contract-verifier      (Step 4 — contract conformance)
  └── s-code-structure-explorer (Step 5+6b — deviation structure + visibility)
      ↓ routes findings via report classification
      p-implementation-resolver (architecture-level findings)
      p-coder-fix-mode          (implementation-level findings)

p-consistency-validator
  ├── s-state-explorer          (Step 0 — codebase registry)
  ├── s-index-health-guard      (Step 2b — code index freshness)
  └── s-code-structure-explorer (Step 2b — import survey)

p-coder-batch-mode
  ├── s-index-health-guard     (pre-flight — index freshness)
  ├── s-impact-analyzer        (pre-modification — blast radius)
  ├── s-code-structure-explorer (on-demand — module structure)
  ├── s-contract-verifier      (on-demand — contract resolution)
  ├── s-diagnostics-fixer      (completion — typecheck cleanup)
  ├── s-documentation          (completion — README updates)
  └── s-alembic                (completion — migration generation, ALWAYS)

p-coder-fix-mode
  ├── s-index-health-guard     (pre-flight — index freshness)
  ├── s-impact-analyzer        (pre-modification — blast radius)
  ├── s-code-structure-explorer (on-demand — module structure)
  ├── s-contract-verifier      (on-demand — contract resolution)
  ├── s-diagnostics-fixer      (completion — typecheck cleanup)
  ├── s-alembic                (if fix touches models — migration generation)
  └── s-test-executor          (verify loop — scoped re-run after fix, 2-iter cap)

p-tester-generate-mode
  ├── s-index-health-guard     (Step 1 — index freshness)
  ├── s-code-explorer          (Step 5 — implementation resolution)
  ├── s-contract-verifier      (Step 2 — entity contracts)
  ├── s-manifest-manager       (Steps 4a/4b — YAML phase file authoring)
  ├── s-diagnostics-fixer      (Step 8 — typecheck cleanup)
  └── s-documentation          (Step 8 — per-folder READMEs)

p-tester-fix-mode
  ├── s-index-health-guard     (session start — index freshness)
  ├── s-code-explorer          (on-demand — implementation context)
  ├── s-diagnostics-fixer      (after fixes — per modified file)
  ├── s-manifest-manager       (update — promote files)
  └── s-test-executor          (verify loop — scoped re-run after fix, 2-iter cap)

p-devops (promotion gate — invoked by operator AFTER p-test-runner PASS)
  ├── s-devops-ops             (Step 1 — services up)
  ├── s-index-health-guard     (Step 4 — index freshness)
  ├── s-alembic                (Step 5 — apply-prod migration)
  ├── s-manifest-manager       (Step 6 — promote-file / release-promote)
  └── s-devops-ops             (Step 7 — build-verify)

p-test-runner (test execution — primary agent, invoked by operator)
  ├── s-index-health-guard     (pre-flight — index freshness)
  ├── s-devops-ops             (precondition — services check)
  ├── s-alembic                (precondition — apply-test + pending-changes-check)
  ├── s-test-executor          (run tests → PASS or FAIL+Juice)
  └── s-test-analyzer          (on FAIL — classify + direct infra fixes + report)
      ↓ on FAIL, report on disk → operator routes to fix-owner agents
      p-coder-fix-mode / p-tester-fix-mode / p-implementation-resolver
      (all primary agents, invoked by operator — NOT task-delegated)
```

## Pipeline Flow (Per Sub-Phase)

```
STAGE 1 — PLANNING (operator-invoked)
  operator → p-implementation-architect
    produces: overview.md + batch-N-<theme>.md (BRDs)
              + batch-N-<theme>-tests.md (test scenarios per batch)
              + <plan-id>_x-validation.md

STAGE 2 — IMPLEMENTATION + TEST GENERATION (per batch, sequential)
  ┌─────────────────────────────────────────────────────────────┐
  │ BATCH N:                                                     │
  │  operator → p-coder-batch-mode (batch-N BRD)                │
  │    implements steps → s-alembic(generate) at batch end     │
  │                                                              │
  │  operator → p-tester-generate-mode (batch-N BRD + -tests)   │
  │    generates test files → s-manifest-manager (phase file    │
  │    updated: batch N's files marked status: generated)      │
  │                                                              │
  │  operator → p-test-runner (scope=feature)                  │
  │    manifest skips status: pending/promoted files            │
  │    runs ONLY batch N's tests (cumulative if prior batches)  │
  │    PASS → proceed to batch N+1                              │
  │    FAIL → fix loop → re-run → PASS → batch N+1             │
  └─────────────────────────────────────────────────────────────┘
  (repeat for each batch in the sub-phase)

STAGE 3 — VALIDATION (operator-invoked, after ALL batches)
  operator → p-implementation-validator
    audits full implementation against overview.md + x-validation.md
    produces: reports/<plan-id>_validation.md
    routes: Implementation Fix → p-coder-fix-mode
            Architecture Change → p-implementation-resolver

  (optional) operator → p-consistency-validator
    cross-implementation drift + technical debt
    produces: docs/implementation/consistency-<scope>.md

STAGE 4 — FINAL TEST VERIFICATION (operator-invoked)
  operator → p-test-runner (scope=feature, full regression)
    runs ALL generated tests across all batches
    PASS → proceed to STAGE 5
    FAIL → report on disk → operator routes to fix agents

STAGE 5 — PROMOTION (operator-invoked, only after final PASS)
  operator → p-devops (the promotion gate)
    1. s-devops-ops(services-up)
    2. find_files — test-run report check (if exists = NOT PASS → STOP)
    3. find_files — validator report check (if missing → STOP)
    4. s-index-health-guard(Domains: code)
    5. s-alembic(apply-prod)
    6. s-manifest-manager(promote-file per passed file, or release-promote)
    7. s-devops-ops(build-verify)
    → "PASS — promoted to prod"

FIX LOOP (at any stage after tests fail)
  operator reads reports/<plan-id>_devops.md or _validation.md
  operator → p-coder-fix-mode (Implementation findings)
    reads report → fixes → s-test-executor scoped verify (2-iter cap)
    → if touched app/models/: s-alembic(generate)
  operator → p-tester-fix-mode (Test Suite findings, infra fallback)
    reads report → fixes → s-test-executor scoped verify (2-iter cap)
    → s-manifest-manager (update phase classes)
  operator → p-implementation-resolver (Plan Gap / Architecture findings)
    reads report → resolves → updates plan, writes ADRs
    produces: reports/<plan-id>_architect_resolution.md

  INFRASTRUCTURE FIXES — handled automatically:
    s-test-analyzer applies conftest/factory/env fixes DIRECTLY during
    the p-test-runner session (before report reaches fix agents).
    p-test-runner re-runs s-test-executor to verify. If infra fix
    insufficient, routes to p-tester-fix-mode as fallback.
```

## Cross-Agent Patterns

- **Brief schema** (Header + Verification + Confidence): all explorer subagents (s-code-explorer, s-doc-explorer, s-state-explorer, s-code-structure-explorer, s-contract-verifier, s-impact-analyzer, s-history-explorer, s-test-analyzer)
- **Skill for shared coder core**: p-coder-batch-mode and p-coder-fix-mode both load `coder-shared-core`
- **Skill for output format**: p-implementation-architect (impl-architect-* templates), p-implementation-validator (validation-classification-and-report, stack-truth-conformance), s-test-analyzer (devops-analyzer-output-format), p-consistency-validator (consistency-report-format)
- **Subagent for structured retrieval**: primary agents delegate doc/code/contract retrieval to subagents; main agents hold only file access + search tools
- **Finding routing via report classification**: p-implementation-validator and p-test-runner/s-test-analyzer route findings via RC category/owner in reports, not Task calls
- **Wildcard-first permission block**: all agents with MCP tools use `pheidipp-codebase-context_*: deny` then explicit allows
- **Manifest model**: two files (index.yaml + phase-N-Mx.yaml), file-level status tracking, class→function mapping. Test Architect writes phase files via s-manifest-manager. DevOps owns promotion via s-manifest-manager. Selectors: `filename.py` (file-level), `filename.py::ClassName` (class-level, release side), `{ path: filename.py, exclude: [ClassName, ...] }` (regression side of partial promotion).
- **Test execution separation**: p-test-runner is a **primary agent** invoked by the operator/pipeline (NOT a subagent delegated via task). It owns test execution orchestration; s-test-executor is the mechanical bash-only runner; s-test-analyzer classifies failures and applies infra fixes directly. p-devops is the **promotion gate** — a separate primary agent invoked by the operator AFTER p-test-runner returns PASS. p-devops does NOT delegate to p-test-runner; they are peers. Fix agents (p-coder-fix-mode, p-tester-fix-mode) are also primary agents — the operator invokes them after reading failure reports from disk.
- **Per-batch test execution**: The Implementation Architect produces per-batch test scenarios (`batch-N-<theme>-tests.md`). The test architect generates tests per-batch and updates the manifest per-batch (files marked `status: generated`). The manifest's per-file `status` field makes per-batch p-test-runner safe — it naturally skips `status: pending` and `status: promoted` files, running only what's ready. After all batches + validation, a final full-scope p-test-runner run serves as a regression safety net before promotion.
- **Migration lifecycle separation**: s-alembic owns the full Alembic lifecycle. Coder agents do NOT write migration files or run db-revision*.sh scripts. p-devops delegates prod migration to s-alembic. p-test-runner delegates test DB migration + pending-changes-check to s-alembic as preconditions.
- **Verify loop contract**: fix agents (p-coder-fix-mode, p-tester-fix-mode) delegate scoped re-runs to s-test-executor with ONLY the selectors from the RC's `Affected failures` list. 2-iteration cap per RC. s-test-executor returns PASS (fix landed) or FAIL+Juice (iterate or cap-out).
- **Dead permission cleanup (2026-08-05 audit)**: p-coder-batch-mode bash→deny, p-coder-fix-mode bash→deny, p-devops bash/edit/write→deny, p-test-runner find_files removed. All operational work delegated to subagents — primary agents are read-and-delegate only.

## Deprecated Agents

| Agent | Status | Replaced By |
|---|---|---|
| s-devops-analyzer | DELETED (file removed) | s-test-analyzer |
