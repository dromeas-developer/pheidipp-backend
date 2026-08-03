# Agent & Skill Registry

> Maintained by p-agent-architect. Updated whenever an agent or skill is
> created, modified, or deprecated. Load this file on every review invocation.

## Agents

| Agent | Role | Model | Subagents Delegated | Skills Loaded | Direct MCP | Permissions |
|---|---|---|---|---|---|---|
| p-agent-architect | Ecosystem optimizer | nvidia/z-ai/glm-5.2 | none | todowrite-discipline (reads skills directly for review) | read, write, edit, glob, grep | task(deny all), skill(allow), bash(deny), todowrite(allow) |
| p-technical-advisor | Architecture decision authority | litellm-proxy/nvidia/kimi-k2.6 | s-doc-explorer, s-vision-and-architect-author, s-index-health-guard | todowrite-discipline | 15 tools: architecture (6), vision (3), release-plan (5), orchestrator (1) | read(allow), edit/write/bash/grep/glob(deny), skill(allow), webfetch(allow), todowrite(allow) |
| p-release-strategy-architect | Release sequencing | poolside/poolside/laguna-m.1 | s-index-health-guard, s-doc-explorer, s-impact-analyzer | retrieval-patterns, todowrite-discipline, sub-phase-document-template, release-planning-patterns | search_architecture, search_invariants, list_entities, get_entity_context, get_event_context, get_related_contracts, search_vision, list_vision_entities, get_vision_context, search_release_plan, list_release_plan_phases, list_release_plan_features, get_phase_context, get_feature_context, get_change_impact, refresh_release_plan, search_adr, list_adrs, get_adr_context, get_adrs_for_entity, get_related_adrs | task(s-index-health-guard/s-doc-explorer/s-impact-analyzer), read/write/edit(allow), bash(deny) |
| p-implementation-architect | Plan author | nvidia/z-ai/glm-5.2 | s-state-explorer, s-doc-explorer, s-impact-analyzer, s-code-structure-explorer, s-contract-verifier, s-index-health-guard | retrieval-patterns, impl-architect-overview-template, impl-architect-batch-brd-template, impl-architect-x-validation-template, impl-architect-test-scenarios-template, impl-architect-doc-updates-template, impl-architect-handoff-blocks, impl-architect-adr-template, impl-architect-x-validation-checklist, todowrite-discipline | search_invariants, get_related_contracts, get_change_impact, get_agent_dependencies, get_computation_pipeline, refresh_architecture, get_files, find_files, grep_files, search_codebase, search_symbols | task(s-state-explorer/s-doc-explorer/s-impact-analyzer/s-code-structure-explorer/s-contract-verifier/s-index-health-guard), read/write/edit(allow), bash(deny) |
| p-implementation-resolver | Resolution author | nvidia/z-ai/glm-5.2 | s-state-explorer, s-doc-explorer, s-code-structure-explorer, s-contract-verifier, s-index-health-guard | impl-resolver-mode-procedure, impl-architect-overview-template, impl-architect-batch-brd-template, impl-architect-handoff-blocks, impl-architect-adr-template, impl-resolver-delta-proposal-template, todowrite-discipline | none (all delegated to subagents) | task(s-state-explorer/s-doc-explorer/s-code-structure-explorer/s-contract-verifier/s-index-health-guard), read/write/edit(allow), bash(deny), skill(allow) |
| p-implementation-validator | Post-implementation audit | nvidia/z-ai/glm-5.2 | s-index-health-guard, s-state-explorer, s-contract-verifier, s-code-structure-explorer | git-session-delta, no-silent-deviations, stack-truth-conformance, validation-classification-and-report, type-enforcement-conformance, todowrite-discipline | get_files, find_files, grep_files, search_codebase, search_symbols, get_phase_context, get_computation_pipeline, get_arch_for_code | task(s-index-health-guard/s-state-explorer/s-contract-verifier/s-code-structure-explorer), edit/write(allow), bash(deny), read(deny), todowrite(allow) |
| p-coder-batch-mode | Batch implementation from BRD | opencode-go/mimo-v2.5-pro | s-diagnostics-fixer, s-documentation, s-impact-analyzer, s-code-structure-explorer, s-contract-verifier, s-index-health-guard | coder-shared-core, no-silent-deviations, infrastructure-reference, todowrite-discipline, type-hygiene-standards | get_files, find_files, grep_files, search_codebase, search_symbols, get_entity_context, get_arch_for_code | task(s-diagnostics-fixer/s-documentation/s-impact-analyzer/s-code-structure-explorer/s-contract-verifier/s-index-health-guard), read(deny→get_files), grep(deny→grep_files), glob(deny→find_files), skill(allow), write/edit/bash/todowrite(allow) |
| p-coder-fix-mode | Fix implementation from validator/devops reports | opencode-go/mimo-v2.5-pro | s-diagnostics-fixer, s-impact-analyzer, s-code-structure-explorer, s-contract-verifier, s-index-health-guard | coder-shared-core, no-silent-deviations, infrastructure-reference, todowrite-discipline, type-hygiene-standards | get_files, find_files, grep_files, search_codebase, search_symbols, get_entity_context, get_arch_for_code | task(s-diagnostics-fixer/s-impact-analyzer/s-code-structure-explorer/s-contract-verifier/s-index-health-guard), read(deny→get_files), grep(deny→grep_files), glob(deny→find_files), skill(allow), write/edit/bash/todowrite(allow) |
| p-tester-generate-mode | Test generator from BRD | poolside/poolside/laguna-s-2.1 | s-code-explorer, s-diagnostics-fixer, s-documentation, s-contract-verifier, s-index-health-guard, s-manifest-manager | tester-shared-core, todowrite-discipline, type-hygiene-standards, test-generate-mode-protocol | get_files, find_files, grep_files | task(s-code-explorer/s-diagnostics-fixer/s-documentation/s-contract-verifier/s-index-health-guard/s-manifest-manager), read/grep/glob(deny), skill(allow), edit/write/bash/todowrite(allow) |
| p-tester-fix-mode | Test fixer from devops RCs | poolside/poolside/laguna-s-2.1 | s-code-explorer, s-diagnostics-fixer, s-contract-verifier, s-index-health-guard, s-manifest-manager | tester-shared-core, todowrite-discipline, type-hygiene-standards, test-fix-mode-procedure | get_files, find_files, grep_files | task(s-code-explorer/s-diagnostics-fixer/s-contract-verifier/s-index-health-guard/s-manifest-manager), read/grep/glob(deny), skill(allow), edit/write/bash/todowrite(allow) |
| p-devops | Runtime/test/build executor + promotion owner | opencode/deepseek-v4-flash-free | s-index-health-guard, s-manifest-manager | infrastructure-reference, git-session-delta, devops-report-format, devops-testpack-report-format, todowrite-discipline, test-infrastructure | get_files | bash/edit/write/todowrite(allow), read/grep/glob(deny) |
| p-consistency-validator | Cross-implementation consistency | nvidia/z-ai/glm-5.2 | s-state-explorer, s-index-health-guard, s-code-structure-explorer | consistency-report-format, todowrite-discipline | get_files, find_files, grep_files, get_arch_for_code | edit/write(allow), read/grep/glob/bash(deny), todowrite(allow) |
| s-contract-verifier | Entity/event contract resolver | openrouter/inclusionai/ling-3.0-flash:free | none | none | get_entity_context, get_event_context, search_invariants, get_related_contracts, search_symbols, list_entities, search_architecture | task(deny all), skill(deny), bash(deny) — invoked by p-coder-batch-mode, p-coder-fix-mode, p-implementation-architect, p-implementation-resolver, p-tester-generate-mode, or p-implementation-validator |
| s-impact-analyzer | Blast-radius analysis (self-resolving: code-name → architecture entity) | opencode/mimo-v2.5-free | none | none | get_change_impact, search_symbols, get_arch_for_code, get_entity_context, get_related_contracts, get_dependency_chain, get_importers, get_module_deps | task(deny all), skill(deny), bash(deny) — invoked by p-coder-batch-mode, p-coder-fix-mode, p-implementation-architect, p-release-strategy-architect |
| s-code-explorer | Code file content resolver | deepseek-v4-flash-free | none | none | get_files, find_files, grep_files, search_codebase, search_symbols, get_entity_context | task(deny all), skill(deny), bash(deny) — invoked by p-tester-generate-mode, p-tester-fix-mode |
| s-code-structure-explorer | AST-based structure resolver | deepseek-v4-flash-free | none | none | get_module_context, get_class_context, get_function_context, list_imports, get_module_deps, get_importers, search_symbols, list_classes, list_functions, multi_code_query | task(deny all), skill(deny), bash(deny) — invoked by p-coder-batch-mode, p-coder-fix-mode, p-implementation-architect, p-implementation-validator |
| s-state-explorer | Codebase registry resolver | deepseek-v4-flash-free | none | retrieval-patterns | search_symbols, search_codebase, grep_files, find_files, get_files, get_code_for_entity, list_modules, list_classes, multi_code_query | task(deny all), bash(deny) |
| s-doc-explorer | Documentation corpus resolver | deepseek-v4-flash | none | retrieval-patterns | search_architecture, search_invariants, list_entities, get_entity_context, get_event_context, get_related_contracts, search_vision, list_vision_entities, get_vision_context, search_release_plan, list_release_plan_phases, list_release_plan_features, get_phase_context, get_feature_context, search_adr, list_adrs, get_adr_context, get_adrs_for_entity, get_related_adrs, multi_search, multi_context | task(deny all), bash(deny) |
| s-history-explorer | Prior reports/plans scanner | deepseek-v4-flash-free | none | retrieval-patterns | find_files, grep_files, get_files | task(deny all), bash(deny) — available on-demand; not wired into any standard pipeline |
| s-diagnostics-fixer | Static-analysis fixer | deepseek-v4-flash | none | no-silent-deviations | search_symbols | bash(allow), read/write/edit(allow) — invoked by p-coder-batch-mode, p-coder-fix-mode, p-tester-generate-mode, p-tester-fix-mode |
| s-documentation | README maintainer | deepseek-v4-flash | none | todowrite-discipline | get_files, find_files, grep_files, search_codebase, search_symbols | skill(allow), bash(deny), edit/write(allow), todowrite(allow) — invoked by p-coder-batch-mode, p-tester-generate-mode |
| s-index-health-guard | Index health + refresh | deepseek-v4-flash-free | none | none | check_index_health, get_index_stats, refresh_code, refresh_architecture, refresh_vision, refresh_release_plan, refresh_adr, refresh_implementation, refresh_testing | task(deny all), bash(deny), skill(deny) — invoked by p-coder-batch-mode, p-coder-fix-mode, p-implementation-architect, p-implementation-validator, p-tester-generate-mode, p-tester-fix-mode, p-devops |
| s-manifest-manager | Manifest write subagent: phase file authoring (write-phase) + promotion (promote-file, release-promote) | opencode/deepseek-v4-flash-free | none | none | read, edit, write | task(deny all), bash(deny) — invoked by p-tester-generate-mode, p-tester-fix-mode (write-phase) and p-devops (promote-file, release-promote) |

## Skills

| Skill | Purpose | Loaded By |
|---|---|---|
| retrieval-patterns | Section-name handling, search_invariants filter docs, get_feature_context usage, index maintenance rules | p-implementation-architect, p-release-strategy-architect, s-doc-explorer, s-state-explorer, s-history-explorer |
| sub-phase-document-template | Sub-phase document format template | p-release-strategy-architect |
| release-planning-patterns | Anti-patterns, sizing rules, challenge questions | p-release-strategy-architect |
| impl-architect-overview-template | Implementation overview template + writing rules + anti-patterns + sizing | p-implementation-architect |
| impl-architect-batch-brd-template | Batch BRD template + step writing rules + anti-patterns + sizing. Context tiers and Success Criteria in impl-architect-handoff-blocks. | p-implementation-architect |
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
| coder-shared-core | Boundaries, execution protocol, subagent delegation, todo-list discipline, tool usage, migration rules, code standards, diagnostics completion — shared by both coder agents. Comment discipline and contract gap check loaded on demand from separate skills. | p-coder-batch-mode, p-coder-fix-mode |
| coder-comment-discipline | Comment rules: never/write-only/rule-of-thumb. Loaded on demand when writing or editing source files. | p-coder-batch-mode, p-coder-fix-mode |
| coder-contract-gap-check | Contract gap resolution: when to delegate to s-contract-verifier, fallback path. Loaded on demand when a contract is unclear or absent. | p-coder-batch-mode, p-coder-fix-mode |
| no-silent-deviations | Six-bullet test for implementation/architecture boundary | p-coder-batch-mode, p-coder-fix-mode, p-implementation-validator |
| git-session-delta | File delta recovery from git for deviation detection | p-implementation-validator, p-devops |
| consistency-report-format | Disposition classification + consistency validation report format | p-consistency-validator |
| devops-report-format | Full Pipeline Mode report format (Checks, RC structure, Routing) | p-devops |
| devops-testpack-report-format | Test Pack Mode lightweight re-verification report format | p-devops |
| tester-shared-core | Role, command execution, implementation resolution, owned artifacts, test mode, manifest schema, fixture & mocking contract, test writing standards, comment discipline — shared by both test agents | p-tester-generate-mode, p-tester-fix-mode |
| todowrite-discipline | Standard task-tracking pattern for multi-step agent protocols | p-coder-batch-mode, p-coder-fix-mode, p-tester-generate-mode, p-tester-fix-mode, p-devops, p-implementation-architect, p-implementation-validator, p-technical-advisor, p-release-strategy-architect, s-vision-and-architect-author, p-consistency-validator, p-agent-architect |
| test-infrastructure | Canonical conftest patterns, directory structure rules, per-directory conftest conventions, factory/builder conventions, utils/ structure | p-tester-generate-mode, p-tester-fix-mode (primary), manifest-bootstrap (referenced) |
| type-hygiene-standards | Type annotation rules at code generation time — shared cascade prevention + import patterns; test-specific fixture annotations (§5-6); production-specific function/Pydantic annotations (§7-8). | p-tester-generate-mode, p-tester-fix-mode, p-coder-batch-mode, p-coder-fix-mode |
| test-fix-mode-procedure | Triaged RC fix procedure: Type A/B/C classification, escalation gates, plan recheck, pattern verification. Loaded at Fix Mode entry. | p-tester-fix-mode |
| test-generate-mode-protocol | Full Steps 1–8 test generation protocol: Load Inputs → Inventory → Existing Suite → Manifest → Generate → Collection → Coverage → Finalize. Loaded at Generate Mode entry. | p-tester-generate-mode |

## Delegation Graph

```
p-coder-batch-mode
  ├── s-index-health-guard     (pre-flight — index freshness)
  ├── s-impact-analyzer        (pre-modification — blast radius)
  ├── s-code-structure-explorer (on-demand — module structure)
  ├── s-contract-verifier      (on-demand — contract resolution)
  ├── s-diagnostics-fixer      (completion — typecheck cleanup)
  └── s-documentation          (completion — README updates)

p-coder-fix-mode
  ├── s-index-health-guard     (pre-flight — index freshness)
  ├── s-impact-analyzer        (pre-modification — blast radius)
  ├── s-code-structure-explorer (on-demand — module structure)
  ├── s-contract-verifier      (on-demand — contract resolution)
  └── s-diagnostics-fixer      (completion — typecheck cleanup)

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
  └── s-code-structure-explorer (Step 5 — deviation structure)
      ↓ routes findings via report classification
      p-implementation-resolver (for architecture-level findings)

p-consistency-validator
  ├── s-state-explorer            (Step 0 — codebase registry)
  ├── s-index-health-guard        (Step 2b — code index freshness)
  └── s-code-structure-explorer   (Step 2b — import survey)

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
  └── s-manifest-manager       (update — flip passed: false)

p-devops
  ├── s-index-health-guard     (session start — index freshness)
  ├── s-manifest-manager       (promotion — index/phase file updates)
      ↓ routes findings via report classification
      p-implementation-resolver (for architecture-level findings)
```

## Cross-Agent Patterns

- **Brief schema** (Header + Verification + Confidence): s-code-explorer, s-doc-explorer, s-state-explorer, s-code-structure-explorer, s-contract-verifier, s-impact-analyzer, s-history-explorer
- **Skill for shared coder core**: p-coder-batch-mode and p-coder-fix-mode both load `coder-shared-core` (execution protocol, tool usage, code standards, migration rules, subagent delegation, diagnostics completion)
- **Skill for output format**: p-implementation-architect (impl-architect-* templates, impl-architect-handoff-blocks), p-implementation-validator (validation-classification-and-report, stack-truth-conformance)
- **Subagent for structured retrieval**: p-implementation-architect + p-implementation-resolver + p-implementation-validator + p-test-architect delegate doc/code/contract retrieval to subagents; main agents hold only file access + search tools
- **Finding routing via report classification**: p-implementation-validator and p-devops route findings to p-implementation-resolver via RC category/owner in reports, not Task calls
- **Wildcard-first permission block**: all agents use `pheidipp-codebase-context_*: deny` then explicit allows
- **Manifest model**: two files (index.yaml + phase-N-Mx.yaml), per-function validation, pytest selectors. Test Architect writes phase files. DevOps owns promotion (phase file validation + index.yaml selection groups + coverage merge)
