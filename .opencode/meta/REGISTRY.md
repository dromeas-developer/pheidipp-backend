# Agent & Skill Registry

> Maintained by pheidipp-prompt-architect. Updated automatically whenever an
> agent or skill is created, modified, or deprecated. Load this file on every
> review invocation.
>
> Last baseline: 2026-08-09 (fix/fixer cluster consistency — APPLIED:
> fix-loop-protocol skill created [SF-A], p-infra-fixer s-diagnostics-fixer
> added [MF-A], all 3 fix agents report-append + structured return
> standardized [MF-B/SF-C], stale s-test-analyzer claims removed from
> p-coder-fix-mode + p-devops [SF-B], services-check block extracted to
> skill [NH-A]. Report: reports/agent-review-fix-fixer-cluster.md.
> Prior baseline: web research consolidation — s-web-researcher added,
> webfetch removed from p-technical-advisor, stack-reference-sources
> skill added)

## Agents — Primary (14)

| Agent | Role | Model | Subagents Delegated | Skills Loaded | Direct MCP | Key Permissions |
|---|---|---|---|---|---|---|
| p-agent-architect | Ecosystem optimizer — DEPRECATED, replaced by pheidipp-prompt-architect | nvidia/z-ai/glm-5.2 | s-web-researcher | todowrite-discipline (reads skills directly) | read, write, edit, glob, grep | task(s-web-researcher only), skill(allow), bash(deny), webfetch(deny), todowrite(allow) |
| p-technical-advisor | Architecture decision authority | opencode-go/kimi-k2.6 | s-doc-explorer, s-vision-and-architect-author, s-index-health-guard, s-web-researcher | todowrite-discipline | 15 tools: architecture (6), vision (3), release-plan (5), orchestrator (1) | read(allow), edit/write/bash/grep/glob(deny), skill(allow), webfetch(deny), todowrite(allow) |
| p-release-strategy-architect | Release sequencing | opencode-go/kimi-k2.6 | s-index-health-guard, s-doc-explorer, s-impact-analyzer | retrieval-patterns, todowrite-discipline, sub-phase-document-template, release-planning-patterns | search_architecture, search_invariants, list_entities, get_entity_context, get_event_context, get_related_contracts, search_vision, list_vision_entities, get_vision_context, search_release_plan, list_release_plan_phases, list_release_plan_features, get_phase_context, get_feature_context, get_change_impact, refresh_release_plan, search_adr, list_adrs, get_adr_context, get_adrs_for_entity, get_related_adrs | task(3 allows), read/write/edit(allow), bash(deny) |
| p-implementation-architect | Plan author | opencode-go/glm-5.2 | s-state-explorer, s-doc-explorer, s-impact-analyzer, s-code-structure-explorer, s-contract-verifier, s-index-health-guard, s-web-researcher | retrieval-patterns, impl-architect-* (8 template skills), todowrite-discipline | search_invariants, get_related_contracts, get_change_impact, get_agent_dependencies, get_computation_pipeline, refresh_architecture, get_files, find_files, grep_files, search_codebase, search_symbols | task(7 allows), read/write/edit(allow), bash(deny) |
| p-implementation-resolver | Resolution author | opencode-go/kimi-k2.7-code | s-state-explorer, s-doc-explorer, s-code-structure-explorer, s-contract-verifier, s-index-health-guard | impl-resolver-mode-procedure, impl-architect-overview-template, impl-architect-batch-brd-template, impl-architect-handoff-blocks, impl-architect-adr-template, impl-resolver-delta-proposal-template, todowrite-discipline | none (all delegated) | task(5 allows), read/write/edit(allow), bash(deny), skill(allow) |
| p-implementation-validator | Post-implementation audit | opencode-go/kimi-k2.7-code | s-index-health-guard, s-state-explorer, s-contract-verifier, s-code-structure-explorer | git-session-delta, no-silent-deviations, stack-truth-conformance, validation-classification-and-report, type-enforcement-conformance, todowrite-discipline | get_files, find_files, grep_files, search_codebase, search_symbols, get_phase_context, get_computation_pipeline, get_arch_for_code | task(4 allows), edit/write(allow), bash(deny), read(deny), todowrite(allow) |
| p-consistency-validator | Cross-implementation consistency | poolside/poolside/laguna-s-2.1 | s-state-explorer, s-index-health-guard, s-code-structure-explorer | consistency-report-format, todowrite-discipline | get_files, find_files, grep_files, get_arch_for_code | edit/write(allow), read/grep/glob/bash(deny), todowrite(allow) |
| p-coder-batch-mode | Batch implementation from BRD | opencode-go/minimax-m3 | s-diagnostics-fixer, s-documentation, s-impact-analyzer, s-code-structure-explorer, s-contract-verifier, s-index-health-guard, s-alembic | coder-shared-core, no-silent-deviations, todowrite-discipline, type-hygiene-standards | get_files, find_files, grep_files, search_codebase, search_symbols, get_entity_context, get_arch_for_code | task(7 allows), read/grep/glob(deny), skill(allow), write/edit(allow), **bash(deny)**, todowrite(allow) |
| p-coder-fix-mode | Fix implementation from validator/devops reports | opencode-go/minimax-m3 | s-diagnostics-fixer, s-impact-analyzer, s-code-structure-explorer, s-contract-verifier, s-index-health-guard, s-alembic, s-test-executor, s-devops-ops, s-web-researcher | coder-shared-core, no-silent-deviations, todowrite-discipline, type-hygiene-standards, test-execution-protocol, fix-loop-protocol | get_files, find_files, grep_files, search_codebase, search_symbols, get_entity_context, get_arch_for_code | task(9 allows), read/grep/glob(deny), skill(allow), write/edit(allow), **bash(deny)**, todowrite(allow) |
| p-tester-generate-mode | Test generator from BRD | opencode-go/minimax-m3 | s-code-explorer, s-diagnostics-fixer, s-documentation, s-contract-verifier, s-index-health-guard, s-manifest-manager | tester-shared-core, todowrite-discipline, type-hygiene-standards, test-generate-mode-protocol | get_files, find_files, grep_files | task(6 allows), read/grep/glob(deny), skill(allow), edit/write/bash(allow), todowrite(allow) |
| p-tester-fix-mode | Test fixer from devops RCs | poolside/poolside/laguna-s-2.1 | s-code-explorer, s-diagnostics-fixer, s-contract-verifier, s-index-health-guard, s-manifest-manager, s-test-executor, s-devops-ops, s-web-researcher | tester-shared-core, todowrite-discipline, type-hygiene-standards, test-fix-mode-procedure, test-execution-protocol, fix-loop-protocol | get_files, find_files, grep_files | task(8 allows), read/grep/glob(deny), skill(allow), edit/write/bash(allow), todowrite(allow) |
| p-infra-fixer | Infrastructure fixer (test-infra + prod-infra) | opencode-go/kimi-k2.7-code | s-test-executor, s-devops-ops, s-web-researcher, s-diagnostics-fixer | infrastructure-reference, no-silent-deviations, todowrite-discipline, test-execution-protocol, fix-loop-protocol | get_files, find_files, grep_files, search_codebase, search_symbols | task(4 allows), read/grep/glob(allow), skill(allow), edit/write/bash(allow), todowrite(allow) |
| p-devops | Release gate orchestrator (thin) | opencode/deepseek-v4-flash | s-devops-ops, s-alembic, s-manifest-manager, s-index-health-guard | infrastructure-reference, todowrite-discipline | get_files, find_files | task(4 allows), **bash/edit/write(deny)**, read/grep/glob(deny), skill(allow), todowrite(allow) |
| p-test-runner | Test execution orchestrator (primary, operator-invoked) | opencode/deepseek-v4-flash | s-devops-ops, s-alembic, s-test-executor, s-test-analyzer, s-index-health-guard | todowrite-discipline, test-execution-protocol | get_files | task(5 allows), bash/edit/write(deny), read/grep/glob(deny), skill(allow), todowrite(allow) |

## Agents — Subagents (17)

| Subagent | Role | Model | Invoked By | Permissions |
|---|---|---|---|---|
| s-contract-verifier | Entity/event contract resolver | openrouter/inclusionai/ling-3.0-flash:free | p-coder-batch-mode, p-coder-fix-mode, p-implementation-architect, p-implementation-resolver, p-tester-generate-mode, p-implementation-validator | task(deny all), skill(deny), bash(deny) — 7 MCP tools |
| s-impact-analyzer | Blast-radius analysis (self-resolving: code-name → architecture entity) | opencode/mimo-v2.5-free | p-coder-batch-mode, p-coder-fix-mode, p-implementation-architect, p-release-strategy-architect | task(deny all), skill(deny), bash(deny) — 8 MCP tools |
| s-code-explorer | Code file content resolver | deepseek-v4-flash-free | p-tester-generate-mode, p-tester-fix-mode | task(deny all), skill(deny), bash(deny) — 6 MCP tools |
| s-code-structure-explorer | AST-based structure resolver | deepseek-v4-flash-free | p-coder-batch-mode, p-coder-fix-mode, p-implementation-architect, p-implementation-validator, p-consistency-validator | task(deny all), skill(deny), bash(deny) — 9 MCP tools |
| s-state-explorer | Codebase registry resolver | deepseek-v4-flash-free | p-implementation-architect, p-implementation-resolver, p-implementation-validator, p-consistency-validator | task(deny all), bash(deny) — 10 MCP tools, skill: retrieval-patterns |
| s-doc-explorer | Documentation corpus resolver | deepseek-v4-flash | p-implementation-architect, p-implementation-resolver, p-technical-advisor | task(deny all), bash(deny) — 21 MCP tools, skill: retrieval-patterns |
| s-history-explorer | Prior reports/plans scanner | deepseek-v4-flash-free | available on-demand (not wired into standard pipeline) | task(deny all), bash(deny) — 3 MCP tools, skill: retrieval-patterns |
| s-diagnostics-fixer | Static-analysis fixer (typecheck, lint, format) | deepseek-v4-flash | p-coder-batch-mode, p-coder-fix-mode, p-tester-generate-mode, p-tester-fix-mode, p-infra-fixer | bash(allow), read/write/edit(allow), skill: no-silent-deviations — 1 MCP tool |
| s-documentation | README maintainer | deepseek-v4-flash | p-coder-batch-mode, p-tester-generate-mode | skill(allow), bash(deny), edit/write(allow), todowrite(allow) — 4 MCP tools |
| s-index-health-guard | Index health + refresh | deepseek-v4-flash-free | p-coder-batch-mode, p-coder-fix-mode, p-implementation-architect, p-implementation-validator, p-tester-generate-mode, p-tester-fix-mode, p-devops, p-test-runner, p-consistency-validator | task(deny all), bash(deny), skill(deny) — 9 MCP tools |
| s-manifest-manager | Manifest write: phase file authoring + promotion | opencode/deepseek-v4-flash | p-tester-generate-mode, p-tester-fix-mode (write-phase); p-devops (promote-file, release-promote) | task(deny all), bash(deny), read/edit/write(allow) |
| s-test-executor | Mechanical test execution (bash-only) | opencode/deepseek-v4-flash | p-test-runner, p-coder-fix-mode, p-tester-fix-mode | task(deny all), bash(allow), all others deny |
| s-test-analyzer | Test failure analysis, routing (analysis-only) | ollama-cloud/minimax-m3 | p-test-runner (on FAIL) | task(s-web-researcher only), bash(deny), read(escalation-only), write(report-only), edit(allow — required for write tool), s-web-researcher(allow) — 12 MCP tools, skill: devops-analyzer-output-format |
| s-alembic | Alembic migration lifecycle (generate + apply-test + pending-changes-check + apply-prod) | poolside/poolside/laguna-s-2.1 | p-coder-batch-mode, p-coder-fix-mode (generate); p-test-runner (apply-test — includes pending-changes check); p-devops (apply-prod) | task(deny all), bash/edit/write(allow), skill(allow) — 3 MCP tools, skill: infrastructure-reference |
| s-devops-ops | Docker services lifecycle (services-up, services-check, build-verify) | opencode/deepseek-v4-flash | p-devops, p-test-runner, p-coder-fix-mode, p-tester-fix-mode, p-infra-fixer | task(deny all), bash(allow), all others deny |
| s-web-researcher | Web research specialist (library docs, GitHub issues, changelogs) | opencode/deepseek-v4-flash-free | p-agent-architect, p-technical-advisor, s-test-analyzer, p-coder-fix-mode, p-tester-fix-mode, p-infra-fixer, p-implementation-architect | task(deny all), webfetch(allow), skill(allow), all others deny — skill: stack-reference-sources |
| s-vision-and-architect-author | Architecture/vision document author | opencode-go/hy3 | p-technical-advisor | (see agent file) |

## Skills (33)

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
| no-silent-deviations | Six-bullet test for implementation/architecture boundary | p-coder-batch-mode, p-coder-fix-mode, p-implementation-validator, p-infra-fixer |
| git-session-delta | File delta recovery from git for deviation detection | p-implementation-validator |
| consistency-report-format | Disposition classification + consistency validation report format | p-consistency-validator |
| devops-analyzer-output-format | DevOps Analyzer output contract: Header, RC structure, Routing Summary, Failure List | s-test-analyzer |
| tester-shared-core | Role, command execution, implementation resolution, owned artifacts, test mode, manifest schema, fixture & mocking contract, test writing standards, comment discipline — shared by both test agents | p-tester-generate-mode, p-tester-fix-mode |
| todowrite-discipline | Standard task-tracking pattern for multi-step agent protocols | p-coder-batch-mode, p-coder-fix-mode, p-tester-generate-mode, p-tester-fix-mode, p-infra-fixer, p-devops, p-implementation-architect, p-implementation-validator, p-technical-advisor, p-release-strategy-architect, p-consistency-validator, p-agent-architect |
| test-infrastructure | Canonical conftest patterns, directory structure rules, per-directory conftest conventions, factory/builder conventions | p-tester-generate-mode, p-tester-fix-mode (primary), manifest-bootstrap (referenced) |
| type-hygiene-standards | Type annotation rules at code generation time — shared cascade prevention; test-specific fixture annotations; production-specific function/Pydantic annotations | p-tester-generate-mode, p-tester-fix-mode, p-coder-batch-mode, p-coder-fix-mode |
| test-fix-mode-procedure | Triaged RC fix procedure: Type A/B/C classification, escalation gates, plan recheck, pattern verification | p-tester-fix-mode |
| test-generate-mode-protocol | Full Steps 1–8 test generation protocol | p-tester-generate-mode |
| manifest-bootstrap | Initial test manifest creation (conftest.py, MOCKING_CONTRACT.md, index.yaml) | p-tester-generate-mode (when manifest absent) |
| infrastructure-reference | Platform service map, database architecture, command inventory, TimescaleDB augmentation procedures | s-alembic (primary), s-devops-ops, p-infra-fixer, p-devops (reference) |
| stack-reference-sources | Curated list of authoritative web sources for the Pheidipp stack + general-purpose sites (SO, GitHub, dev.to) | s-web-researcher |
| test-execution-protocol | s-test-executor delegation protocol: sequential execution, scoped selectors, iteration cap, bash prohibition, Juice interpretation | p-test-runner, p-coder-fix-mode, p-tester-fix-mode, p-infra-fixer |
| fix-loop-protocol | Shared fix-session wrapper: services-check pre-flight, verify-loop composition with test-execution-protocol, conditional s-diagnostics-fixer invocation, report-append template, structured return-summary template | p-coder-fix-mode, p-tester-fix-mode, p-infra-fixer |

## Delegation Graph

```
p-agent-architect
  └── s-web-researcher         (on-demand — opencode patterns, LLM research, agent design practices)

p-technical-advisor
  ├── s-index-health-guard
  ├── s-doc-explorer
  ├── s-vision-and-architect-author
  └── s-web-researcher         (on-demand — external library knowledge)

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
  ├── s-code-structure-explorer (Step 6 — structural discovery)
  └── s-web-researcher         (on-demand — external library knowledge)

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
  ├── s-diagnostics-fixer      (completion — typecheck cleanup, via coder-shared-core)
  ├── s-alembic                (if fix touches models — migration generation)
  ├── s-devops-ops             (verify loop — services-check, via fix-loop-protocol §1)
  ├── s-test-executor          (verify loop — scoped re-run, via fix-loop-protocol §2)
  └── s-web-researcher         (on-demand — external library knowledge)

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
  ├── s-diagnostics-fixer      (after fixes — per modified file, via test-fix-mode-procedure Step 7)
  ├── s-manifest-manager       (update — promote files)
  ├── s-devops-ops             (verify loop — services-check, via fix-loop-protocol §1)
  └── s-test-executor          (verify loop — scoped re-run, via fix-loop-protocol §2)

p-infra-fixer (operator-invoked, after p-test-runner FAIL or p-devops FAIL)
  ├── s-devops-ops             (Step 2 — services-check, via fix-loop-protocol §1)
  ├── s-index-health-guard     (Step 3 — if code inspection needed)
  ├── s-diagnostics-fixer      (Step 5b — Python diagnostics, conditional on .py files, via fix-loop-protocol §3)
  └── s-test-executor          (Step 6 — verify loop — scoped re-run, via fix-loop-protocol §2)

p-devops (promotion gate — invoked by operator AFTER p-test-runner PASS)
  ├── s-devops-ops             (Step 1 — services up)
  ├── s-index-health-guard     (Step 4 — index freshness)
  ├── s-alembic                (Step 5 — apply-prod migration)
  ├── s-manifest-manager       (Step 6 — promote-file / release-promote)
  └── s-devops-ops             (Step 7 — build-verify)
      ↓ on config gap at Steps 1/5/7 → write finding to report, return FAIL
      ↓ operator invokes p-infra-fixer to fix, then re-invokes p-devops

p-test-runner (test execution — primary agent, invoked by operator)
  ├── s-index-health-guard     (pre-flight — index freshness)
  ├── s-devops-ops             (precondition — services check)
  ├── s-alembic                (precondition — apply-test, includes pending-changes check)
  ├── s-test-executor          (run tests → PASS or FAIL+Juice)
  └── s-test-analyzer          (on FAIL — classify + write report, analysis-only)
      ↓ on FAIL, report on disk → operator routes to fix-owner agents
      p-coder-fix-mode / p-tester-fix-mode / p-infra-fixer / p-implementation-resolver
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
       — if config gap discovered → write finding to report, return FAIL
       — operator invokes p-infra-fixer to fix, then re-invokes p-devops
    2. find_files — test-run report check (if exists = NOT PASS → STOP)
    3. find_files — validator report check (if missing → STOP)
    4. s-index-health-guard(Domains: code)
    5. s-alembic(apply-prod)
       — if migration fails on infra config → write finding, return FAIL
       — operator invokes p-infra-fixer to fix, then re-invokes p-devops
    6. s-manifest-manager(promote-file per passed file, or release-promote)
    7. s-devops-ops(build-verify)
       — if build fails on config → write finding, return FAIL
       — operator invokes p-infra-fixer to fix, then re-invokes p-devops
    → "PASS — promoted to prod"

FIX LOOP (at any stage after tests fail)
  operator reads reports/<plan-id>_devops.md or _validation.md
  operator → p-coder-fix-mode (Implementation findings)
    reads report → fixes → s-test-executor scoped verify (2-iter cap)
    → if touched app/models/: s-alembic(generate)
  operator → p-tester-fix-mode (Test Suite findings)
    reads report → fixes → s-test-executor scoped verify (2-iter cap)
    → s-manifest-manager (update phase classes)
  operator → p-infra-fixer (Infrastructure findings — test-infra + prod-infra)
    reads report → fixes → s-test-executor scoped verify (2-iter cap, test-infra only)
    → appends "Infra Fixes Applied" section to report
  operator → p-implementation-resolver (Plan Gap / Architecture findings)
    reads report → resolves → updates plan, writes ADRs
    produces: reports/<plan-id>_architect_resolution.md

  INFRASTRUCTURE FIXES — operator-invoked via p-infra-fixer:
    s-test-analyzer classifies Infrastructure RCs and writes them to
    the report (analysis-only — no direct fixes). The operator reads
    the report and invokes p-infra-fixer, which applies the fix and
    verifies it via s-test-executor (test-infra) or syntax validation
    (prod-infra). p-devops discovers prod-infra config gaps during
    promotion, writes them to the report, and returns FAIL — the
    operator invokes p-infra-fixer to fix, then re-invokes p-devops.
```

## Cross-Agent Patterns

- **Brief schema** (Header + Verification + Confidence): all explorer subagents (s-code-explorer, s-doc-explorer, s-state-explorer, s-code-structure-explorer, s-contract-verifier, s-impact-analyzer, s-history-explorer, s-test-analyzer)
- **Skill for shared coder core**: p-coder-batch-mode and p-coder-fix-mode both load `coder-shared-core`
- **Skill for output format**: p-implementation-architect (impl-architect-* templates), p-implementation-validator (validation-classification-and-report, stack-truth-conformance), s-test-analyzer (devops-analyzer-output-format), p-consistency-validator (consistency-report-format)
- **Subagent for structured retrieval**: primary agents delegate doc/code/contract retrieval to subagents; main agents hold only file access + search tools
- **Finding routing via report classification**: p-implementation-validator and p-test-runner/s-test-analyzer route findings via RC category/owner in reports, not Task calls. Fix-owner agents (p-coder-fix-mode, p-tester-fix-mode, p-infra-fixer, p-implementation-resolver) are all primary agents invoked by the operator after reading the report from disk.
- **Wildcard-first permission block**: all agents with MCP tools use `pheidipp-codebase-context_*: deny` then explicit allows
- **Manifest model**: two files (index.yaml + phase-N-Mx.yaml), file-level status tracking, class→function mapping. Test Architect writes phase files via s-manifest-manager. DevOps owns promotion via s-manifest-manager. Selectors: `filename.py` (file-level), `filename.py::ClassName` (class-level, release side), `{ path: filename.py, exclude: [ClassName, ...] }` (regression side of partial promotion).
- **Test execution separation**: p-test-runner is a **primary agent** invoked by the operator/pipeline (NOT a subagent delegated via task). It owns test execution orchestration; s-test-executor is the mechanical bash-only runner; s-test-analyzer classifies failures and applies infra fixes directly. p-devops is the **promotion gate** — a separate primary agent invoked by the operator AFTER p-test-runner returns PASS. p-devops does NOT delegate to p-test-runner; they are peers. Fix agents (p-coder-fix-mode, p-tester-fix-mode) are also primary agents — the operator invokes them after reading failure reports from disk.
- **Per-batch test execution**: The Implementation Architect produces per-batch test scenarios (`batch-N-<theme>-tests.md`). The test architect generates tests per-batch and updates the manifest per-batch (files marked `status: generated`). The manifest's per-file `status` field makes per-batch p-test-runner safe — it naturally skips `status: pending` and `status: promoted` files, running only what's ready. After all batches + validation, a final full-scope p-test-runner run serves as a regression safety net before promotion.
- **Migration lifecycle separation**: s-alembic owns the full Alembic lifecycle. Coder agents do NOT write migration files or run db-revision*.sh scripts. p-devops delegates prod migration to s-alembic. p-test-runner delegates test DB migration to s-alembic as a precondition — the `apply-test` operation now includes the pending-changes check (ORM drift detection) in the same call, so p-test-runner makes one s-alembic call instead of two.
- **Verify loop contract**: fix agents (p-coder-fix-mode, p-tester-fix-mode, p-infra-fixer) delegate scoped re-runs to s-test-executor with ONLY the selectors from the RC's `Affected failures` list. 2-iteration cap per RC. s-test-executor returns PASS (fix landed) or FAIL+Juice (iterate or cap-out). All three fix agents also delegate `services-check` to s-devops-ops before the first re-run — if services are not running, STOP and report (the operator starts them). Fix agents never run `bash scripts/run-tests.sh` or `docker compose` commands directly.
- **s-test-executor sequential execution (NON-NEGOTIABLE)**: All agents that delegate to s-test-executor (p-test-runner, p-coder-fix-mode, p-tester-fix-mode, p-infra-fixer) MUST issue ONE `task` call at a time and wait for the result before issuing the next. NEVER place two or more s-test-executor `task` calls in the same assistant message. Parallel runs against the same `test_pheidipp` database cause `asyncpg.exceptions.TooManyConnectionsError` (connection pool exhaustion) and cross-test interference (transactions, locks) that do not exist in single-pack runs. The full delegation protocol (sequential execution, scoped selectors, iteration cap, bash prohibition, Juice interpretation) is in the `test-execution-protocol` skill, loaded by all four delegating agents. s-test-executor's own Rules section documents the constraint defensively.
- **Dead permission cleanup (2026-08-05 audit)**: p-coder-batch-mode bash→deny, p-coder-fix-mode bash→deny, p-devops bash/edit/write→deny, p-test-runner find_files removed. All operational work delegated to subagents — primary agents are read-and-delegate only.
- **Infra fixer consolidation (2026-08-09)**: p-infra-fixer is the single executor for all infrastructure fixes — both test-infra (conftest, factories, .env.test, MOCKING_CONTRACT) and prod-infra (docker-compose, Dockerfile, .env, scripts, litellm_proxy). It replaces s-infra-config-editor (deprecated — subsumed) and s-test-analyzer's former direct-fix responsibility (s-test-analyzer is now analysis-only). p-infra-fixer is operator-invoked, same pattern as p-coder-fix-mode and p-tester-fix-mode. It delegates scoped re-runs to s-test-executor (verify loop, 2-iter cap) for test-infra findings, and uses syntax validation for prod-infra findings. p-devops discovers prod-infra config gaps during promotion, writes them to the report, and returns FAIL — the operator invokes p-infra-fixer to fix, then re-invokes p-devops to resume. s-test-analyzer classifies Infrastructure RCs and routes them to p-infra-fixer in the report — it no longer applies any fixes directly.
- **Web access consolidation (2026-08-09)**: s-web-researcher is the only agent in the ecosystem with `webfetch: allow`. All other agents delegate web research to it via `task`. p-technical-advisor and p-agent-architect both had `webfetch: allow` directly — both now have `webfetch: deny` and `s-web-researcher: allow` instead. s-web-researcher is a cheap subagent (deepseek-v4-flash-free) that accepts one or more research topics, searches the web (library docs, GitHub issues, Stack Overflow, changelogs), and returns a condensed factual brief per topic with source URLs. It loads the `stack-reference-sources` skill for a curated list of authoritative sources. It does NOT make recommendations — facts only, the caller decides. Invoked by: p-agent-architect, p-technical-advisor, s-test-analyzer, p-coder-fix-mode, p-tester-fix-mode, p-infra-fixer, p-implementation-architect.

## Deprecated Agents

| Agent | Status | Replaced By |
|---|---|---|
| s-devops-analyzer | DELETED (file removed) | s-test-analyzer |
| s-infra-config-editor | DEPRECATED (tombstone file retained) | p-infra-fixer |
