# Agent & Skill Registry

> Maintained by p-agent-architect. Updated whenever an agent or skill is
> created, modified, or deprecated. Load this file on every review invocation.

## Agents

| Agent | Role | Model | Subagents Delegated | Skills Loaded | Direct MCP | Permissions |
|---|---|---|---|---|---|---|
| p-agent-architect | Ecosystem optimizer | nvidia/z-ai/glm-5.2 | none | todowrite-discipline (reads skills directly for review) | read, write, edit, glob, grep | task(deny all), skill(allow), bash(deny), todowrite(allow) |
| p-technical-advisor | Architecture decision authority | litellm-proxy/nvidia/kimi-k2.6 | p-doc-explorer, p-vision-and-architect-author, p-index-health-guard | todowrite-discipline | 15 tools: architecture (6), vision (3), release-plan (5), orchestrator (1) | read(allow), edit/write/bash/grep/glob(deny), skill(allow), webfetch(allow), todowrite(allow) |
| p-vision-and-architect-author | Vision & architecture doc author | — | — | todowrite-discipline | — | — |
| p-release-strategy-architect | Release sequencing | poolside/poolside/laguna-m.1 | p-index-health-guard, p-doc-explorer, p-impact-analyzer | retrieval-patterns, todowrite-discipline, sub-phase-document-template, release-planning-patterns | search_architecture, search_invariants, list_entities, get_entity_context, get_event_context, get_related_contracts, search_vision, list_vision_entities, get_vision_context, search_release_plan, list_release_plan_phases, list_release_plan_features, get_phase_context, get_feature_context, get_change_impact, refresh_release_plan, search_adr, list_adrs, get_adr_context, get_adrs_for_entity, get_related_adrs | task(p-index-health-guard/doc-explorer/impact-analyzer), read/write/edit(allow), bash(deny) |
| p-implementation-architect | Plan author + resolution | nvidia/z-ai/glm-5.2 | p-state-explorer, p-doc-explorer, p-impact-analyzer, p-code-structure-explorer, p-contract-verifier, p-index-health-guard | retrieval-patterns, implementation-plan-templates, resolution-mode-procedure, implementation-handoff-blocks, architecture-decision-templates, todowrite-discipline | get_files, find_files, grep_files, search_codebase, search_symbols, search_architecture, search_invariants, list_entities, get_entity_context, get_event_context, get_related_contracts, search_vision, list_vision_entities, get_vision_context, search_release_plan, list_release_plan_phases, list_release_plan_features, get_phase_context, get_feature_context, get_agent_dependencies, refresh_architecture | task(p-state-explorer/doc-explorer/impact-analyzer/structure-explorer/contract-verifier/index-health-guard), read/write/edit(allow), bash(deny) |
| p-implementation-validator | Post-implementation audit | nvidia/z-ai/glm-5.2 | p-index-health-guard, p-state-explorer, p-contract-verifier, p-code-structure-explorer | git-session-delta, no-silent-deviations, stack-truth-conformance, validation-classification-and-report, type-enforcement-conformance, todowrite-discipline | get_files, find_files, grep_files, search_codebase, search_symbols, get_phase_context | task(index-health-guard/state-explorer/contract-verifier/structure-explorer), edit/write(allow), bash(deny), read(deny), todowrite(allow) |
| p-coder | Implementation code writer | nvidia/minimaxai/minimax-m3 | p-diagnostics-fixer, p-documentation, p-impact-analyzer, p-code-structure-explorer, p-contract-verifier, p-index-health-guard | no-silent-deviations, infrastructure-reference, todowrite-discipline | get_files, find_files, grep_files, search_codebase, search_symbols, get_entity_context | task(diagnostics-fixer/documentation/impact-analyzer/structure-explorer/contract-verifier/index-health-guard), read(deny→get_files), grep(deny→grep_files), glob(deny→find_files), skill(allow), write/edit/bash/todowrite(allow) |
| p-test-architect | Test generator | nvidia/minimaxai/minimax-m3 | p-code-explorer, p-diagnostics-fixer, p-documentation, p-contract-verifier, p-index-health-guard | todowrite-discipline | get_files, find_files, grep_files | task(code-explorer/diagnostics-fixer/documentation/contract-verifier/index-health-guard), read/grep/glob(deny), skill(allow), edit/write/bash/todowrite(allow) |
| p-devops | Runtime/test/build executor + promotion owner | opencode/deepseek-v4-flash-free | p-index-health-guard, p-manifest-manager | infrastructure-reference, git-session-delta, devops-report-format, devops-testpack-report-format, todowrite-discipline | get_files | bash/edit/write/todowrite(allow), read/grep/glob(deny) |
| p-consistency-validator | Cross-implementation consistency | nvidia/z-ai/glm-5.2 | p-state-explorer, p-index-health-guard, p-code-structure-explorer | consistency-report-format, todowrite-discipline | get_files, find_files, grep_files | edit/write(allow), read/grep/glob/bash(deny), todowrite(allow) |
| p-contract-verifier | Entity/event contract resolver | deepseek-v4-flash-free | none | none | get_entity_context, get_event_context, search_invariants, get_related_contracts, search_symbols | task(deny all), skill(deny), bash(deny) |
| p-impact-analyzer | Blast-radius analysis | deepseek-v4-flash-free | none | none | get_change_impact, get_related_contracts, get_dependency_chain, get_importers, get_module_deps, search_symbols | task(deny all), skill(deny), bash(deny) — invoked by p-coder, p-implementation-architect |
| p-code-explorer | Code file content resolver | deepseek-v4-flash-free | none | none | get_files, find_files, grep_files, search_codebase, search_symbols, get_entity_context | task(deny all), skill(deny), bash(deny) |
| p-code-structure-explorer | AST-based structure resolver | deepseek-v4-flash-free | none | none | get_module_context, get_class_context, get_function_context, list_imports, get_module_deps, get_importers, search_symbols | task(deny all), skill(deny), bash(deny) — invoked by p-coder, p-implementation-architect, p-implementation-validator |
| p-state-explorer | Codebase registry resolver | deepseek-v4-flash-free | none | retrieval-patterns | search_symbols, search_codebase, grep_files, find_files, get_files, get_code_for_entity | task(deny all), bash(deny) |
| p-doc-explorer | Documentation corpus resolver | deepseek-v4-flash | none | retrieval-patterns | search_architecture, search_invariants, list_entities, get_entity_context, get_event_context, get_related_contracts, search_vision, list_vision_entities, get_vision_context, search_release_plan, list_release_plan_phases, list_release_plan_features, get_phase_context, get_feature_context, search_adr, list_adrs, get_adr_context, get_adrs_for_entity, get_related_adrs, multi_search, multi_context | task(deny all), bash(deny) |
| p-history-explorer | Prior reports/plans scanner | deepseek-v4-flash-free | none | retrieval-patterns | find_files, grep_files, get_files | task(deny all), bash(deny) — available on-demand; not wired into any standard pipeline |
| p-diagnostics-fixer | Static-analysis fixer | deepseek-v4-flash | none | no-silent-deviations | search_symbols | bash(allow), read/write/edit(allow) |
| p-documentation | README maintainer | deepseek-v4-flash | none | todowrite-discipline | get_files, find_files, grep_files, search_codebase, search_symbols | skill(allow), bash(deny), edit/write(allow), todowrite(allow) |
| p-index-health-guard | Index health + refresh | deepseek-v4-flash-free | none | none | check_index_health, get_index_stats, refresh_code, refresh_architecture, refresh_vision, refresh_release_plan, refresh_adr, refresh_implementation, refresh_testing | task(deny all), bash(deny), skill(deny) — invoked by p-coder, p-implementation-architect, p-implementation-validator, p-test-architect, p-devops |
| p-manifest-manager | Manifest promotion operations (split/collapse/merge) | opencode/deepseek-v4-flash-free | none | none | read, edit (on manifest files only) | task(deny all), bash(deny) — invoked by p-devops |

## Skills

| Skill | Purpose | Loaded By |
|---|---|---|
| retrieval-patterns | Bulk vs targeted retrieval guidance, tool selection reference | p-implementation-architect, p-release-strategy-architect, p-doc-explorer, p-state-explorer, p-history-explorer |
| sub-phase-document-template | Sub-phase document format template | p-release-strategy-architect |
| release-planning-patterns | Anti-patterns, sizing rules, challenge questions | p-release-strategy-architect |
| implementation-plan-templates | Overview.md + batch BRD templates, anti-patterns, sizing rules | p-implementation-architect |
| implementation-handoff-blocks | BRD Context Needed tiers, Batch Success Criteria, architecture handoff conventions | p-implementation-architect |
| resolution-mode-procedure | R0-R5 resolution procedure + Resolution Report Format | p-implementation-architect |
| architecture-decision-templates | ADR file template + Architecture Delta Proposal Format | p-implementation-architect |
| stack-truth-conformance | Severity mapping for stack-truth violations (CRITICAL/MAJOR/MINOR) | p-implementation-validator |
| validation-classification-and-report | Severity definitions, Resolution Path, examples, output report format | p-implementation-validator |
| type-enforcement-conformance | Layer 4 audit: visibility, type strictness, enforcement layer placement, custom validators | p-implementation-validator |
| no-silent-deviations | Six-bullet test for implementation/architecture boundary | p-coder, p-diagnostics-fixer, p-implementation-validator |
| git-session-delta | File delta recovery from git for deviation detection | p-implementation-validator, p-devops |
| consistency-report-format | Disposition classification + consistency validation report format | p-consistency-validator |
| devops-report-format | Full Pipeline Mode report format (Checks, RC structure, Routing) | p-devops |
| devops-testpack-report-format | Test Pack Mode lightweight re-verification report format | p-devops |
| todowrite-discipline | Standard task-tracking pattern for multi-step agent protocols | p-coder, p-test-architect, p-devops, p-implementation-architect, p-implementation-validator, p-technical-advisor, p-release-strategy-architect, p-vision-and-architect-author, p-consistency-validator, p-documentation, p-agent-architect |

## Delegation Graph

```
p-implementation-architect
  ├── p-index-health-guard     (Step 1 — index freshness)
  ├── p-state-explorer         (Step 1 — codebase registry)
  ├── p-doc-explorer           (Step 2 — documentation context)
  ├── p-impact-analyzer        (Step 3 — blast radius)
  ├── p-contract-verifier      (Step 5 RC1 — contract saturation)
  └── p-code-structure-explorer (Step 6 — structural discovery)

p-implementation-validator
  ├── p-index-health-guard     (Step 5 — code index freshness)
  ├── p-state-explorer         (Step 1b — registry context)
  ├── p-contract-verifier      (Step 4 — contract conformance)
  └── p-code-structure-explorer (Step 5 — deviation structure)

p-consistency-validator
  ├── p-state-explorer            (Step 0 — codebase registry)
  ├── p-index-health-guard        (Step 2b — code index freshness)
  └── p-code-structure-explorer   (Step 2b — import survey)
```

## Cross-Agent Patterns

- **Brief schema** (Header + Verification + Confidence): p-code-explorer, p-doc-explorer, p-state-explorer, p-code-structure-explorer, p-contract-verifier, p-impact-analyzer, p-history-explorer
- **Skill for output format**: p-implementation-architect (implementation-plan-templates, implementation-handoff-blocks), p-implementation-validator (validation-classification-and-report, stack-truth-conformance)
- **Subagent for structured retrieval**: p-implementation-architect + p-implementation-validator + p-test-architect delegate doc/code/contract retrieval to subagents; main agents hold only file access + search tools
- **Wildcard-first permission block**: all agents use `pheidipp-codebase-context_*: deny` then explicit allows
- **Manifest model**: two files (index.yaml + phase-N-Mx.yaml), per-function validation, pytest selectors. Test Architect writes phase files. DevOps owns promotion (phase file validation + index.yaml selection groups + coverage merge)
