# MCP Tool Catalog — 68 Tools across 8 Domains

> Condensed reference. Full retrieval patterns in `retrieval-patterns` skill.

## CORE — Codebase Navigation (10)

| Tool | What it does |
|---|---|
| `search_codebase` | Universal entry point. Auto-routes exact symbols to symbol search, strings/paths to grep, concepts to semantic. |
| `get_files` | Read file content by path. Array of paths, optional line ranges. |
| `find_files` | Glob-pattern file discovery. |
| `grep_files` | Exact regex search with context lines. Imports, constants, route names. |
| `search_symbols` | Find where a function/class/variable is defined. |
| `reindex` / `reindex_code` | Full code index rebuild. |
| `refresh_code` | Incremental code index update. |
| `check_index_health` | Per-domain staleness report (stale_files, new_files, healthy). |
| `get_index_stats` | Entity counts, FAISS size, embed model per domain. |

## ARCHITECTURE — System Design Docs (10)

| Tool | What it does |
|---|---|
| `search_architecture` | Semantic search over entity specs, events, APIs, invariants. |
| `search_invariants` | Find constraints by type (uniqueness/cardinality/behavioral/range) and enforcement (database/application/api). |
| `list_entities` | All indexed architecture entity names. |
| `get_entity_context` | Full spec: schema, events, APIs, invariants, storage, mutation rules. |
| `get_event_context` | Event definition: payload schema, producer, consumers, ordering. |
| `get_related_contracts` | Which entities reference or depend on a given entity. |
| `get_computation_pipeline` | Upstream/downstream computation dependencies. |
| `get_agent_dependencies` | Agent contract: context_budget, entity_deps, computation_deps, produces. |
| `reindex_architecture` / `refresh_architecture` | Full rebuild / incremental update. |

## VISION — Product Vision Docs (5)

| Tool | What it does |
|---|---|
| `search_vision` | Semantic search, filterable by category (coach/product/twin). |
| `list_vision_entities` | All vision documents, grouped by category. |
| `get_vision_context` | Full vision spec with sections. |
| `reindex_vision` / `refresh_vision` | Full rebuild / incremental update. |

## RELEASE PLAN — Feature Roadmap (7)

| Tool | What it does |
|---|---|
| `search_release_plan` | Search features and phases, filterable by phase number. |
| `list_release_plan_phases` | All phases with sub_phases and feature counts. |
| `list_release_plan_features` | Browse features, filterable by phase. |
| `get_phase_context` | Full phase spec with sub_phases and features. |
| `get_feature_context` | Complete feature specification. |
| `reindex_release_plan` / `refresh_release_plan` | Full rebuild / incremental update. |

## ADR — Architecture Decision Records (7)

| Tool | What it does |
|---|---|
| `search_adr` | Semantic search, filterable by status (accepted/proposed/deprecated/superseded) and tags. |
| `list_adrs` | All ADRs with id, title, status, tags. |
| `get_adr_context` | Full ADR: graph (supersedes/superseded_by/referenced) + sections. |
| `get_adrs_for_entity` | All ADRs that reference a given entity. |
| `get_related_adrs` | Supersedes/superseded-by chain for an ADR. |
| `reindex_adr` / `refresh_adr` | Full rebuild / incremental update. |

## IMPLEMENTATION — Plans & Gaps (7)

| Tool | What it does |
|---|---|
| `search_implementation` | Search batches and gap analyses, filterable by phase. |
| `list_implementation_batches` | All batches with phase, status, entities_touched. |
| `get_batch_context` | Full batch plan with scope and preconditions. |
| `get_entity_implementation_status` | Per-batch status for an entity across all batches. |
| `list_implementation_findings` | Gap analysis findings, filterable by severity. |
| `reindex_implementation` / `refresh_implementation` | Full rebuild / incremental update. |

## TESTING — Test Packs & Reports (5)

| Tool | What it does |
|---|---|
| `search_testing` | Search test packs, promotions, refactor reports. |
| `list_test_packs` | All test packs with phase, status, features, test_count. |
| `get_test_pack_context` | Full test pack content. |
| `reindex_testing` / `refresh_testing` | Full rebuild / incremental update. |

## CODE — Structure & Dependencies (12)

AST-based, no semantic search. `search_codebase` for conceptual queries.

| Tool | What it does |
|---|---|
| `list_modules` | All project modules grouped by layer (app/test/infra). |
| `list_classes` | All classes, filterable by module, base class, source_type. |
| `list_functions` | All top-level functions by module. |
| `list_imports` | Imports split internal vs external for a module. |
| `get_class_context` | Full class: bases, methods with signatures, decorators, docstring. |
| `get_function_context` | Full function: params, return_type, decorators, is_async, docstring. |
| `get_module_context` | All classes and functions in a module directory. |
| `get_module_docs` | README.md and .md files for a module. |
| `get_module_deps` | What a module imports (forward deps). |
| `get_importers` | Who imports a module (reverse deps). |
| `get_dependency_chain` | BFS shortest import chain between two modules. |
| `multi_code_query` | Batch multiple code-domain lookups (imports, deps, symbols, function/class context) in one call. Reduces round-trips when resolving multiple entities. |

## ORCHESTRATORS — Cross-Domain (5)

| Tool | What it does |
|---|---|
| `multi_search` | 2-8 parallel cross-domain searches in one call. Max 8 searches. |
| `multi_context` | Full context for multiple concepts across architecture, vision, release_plan. One call. |
| `get_change_impact` | Full blast radius: architecture + release plan + vision + implementation + testing. |
| `get_code_for_entity` | Architecture entity → code files (scored: class=3, function=2, path=1). |
| `get_arch_for_code` | Code file → architecture entities. |

## Per-Domain Summary

| Domain | Count | Identity |
|---|---|---|
| Core | 10 | Code search, files, indexing |
| Architecture | 10 | Entity specs, events, invariants, agents |
| Vision | 5 | Product vision docs |
| Release Plan | 7 | Phases and features |
| ADR | 7 | Decision records |
| Implementation | 7 | Batches, gap analysis |
| Testing | 5 | Test packs, reports |
| Code | 12 | AST structure, dependencies, batched lookups |
| Orchestrators | 5 | Cross-domain bridge |
| **Total** | **68** | |
