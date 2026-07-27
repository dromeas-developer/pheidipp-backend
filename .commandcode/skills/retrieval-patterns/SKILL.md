---
name: retrieval-patterns
description: >
  Load this when an agent queries the architecture, vision, release-plan,
  or ADR corpora via the pheidipp-codebase-context MCP tools and needs
  bulk-vs-targeted retrieval guidance, the Tool Selection Reference table,
  and section-name handling rules. Agents that do not query the
  documentation corpus should not load this skill.
---

# Retrieval Patterns

Shared retrieval guidance for all agents that query the architecture,
vision, release-plan, or ADR corpora via the `pheidipp-codebase-context`
MCP tools. Agents retain only their domain-specific retrieval notes
(e.g. "never fetch `app/` paths directly") and load this skill for
the common patterns.

---

## Delegation vs Direct Access

**When to delegate to subagents instead of using tools directly:**

| Question Type | Delegate To | Why |
|---|---|---|
| "What depends on this entity?" | `p-impact-analyzer` | Single call returns full blast radius |
| "What is the structure of this module?" | `p-code-structure-explorer` | AST-aware tools, no file reads needed |
| "What are the contracts for this entity/event?" | `p-contract-verifier` | Condenses entity/event context |
| "What exists in this domain?" | `p-state-explorer` | Registry resolution, not file content |
| "What does this file look like?" | `p-code-explorer` | Full file content retrieval |

**Delegation pattern:**
Use the `agent` tool with subagent_type set to the target agent name and
a descriptive prompt containing the concept or entity to investigate.

Use delegation when the same retrieval question would be asked by multiple
agents, or when the question is purely informational (not requiring
judgment or decision-making).

---

## Bulk vs Targeted Retrieval

**Default: prefer bulk tools when gathering information about multiple
independent concepts.**

| Pattern | Tool | When to use |
|---|---|---|
| Discovery across multiple concepts/domains | `multi_search(searches[])` | One call per concept across domains — batch all searches |
| Cross-domain context for multiple concepts | `multi_context(concepts: ["A","B","C"])` | Full context for all named concepts in one call |
| Impact analysis before modifying an existing entity | `p-impact-analyzer` (subagent) | Returns full blast radius; delegates to `get_change_impact` internally |
| Who depends on a given entity | `p-impact-analyzer` (subagent) | Delegates to `get_related_contracts` internally |

**Use targeted single-tool retrieval when:**
- investigating a specific entity in depth
- verifying a specific event contract
- retrieving a specific invariant type
- reviewing a single ownership boundary

A targeted `get_entity_context` with `sections` is better than a broad
`multi_search` when you know exactly what you need. Do not use bulk
retrieval when a bulk query would return substantially more information
than required. Optimise for retrieval relevance and efficiency — not for
maximising bulk tool usage.

---

## Tool Selection Reference

**Use this table to decide: delegate to subagent OR use tool directly.**

| Situation | Delegate To | Direct Tool (fallback) |
|---|---|---|
| Check full impact of modifying an entity | `p-impact-analyzer` | `get_change_impact(concept)` |
| Full spec for one entity (contracts) | `p-contract-verifier` | `get_entity_context(entity_name, sections?)` |
| Event producer/consumer/schema | `p-contract-verifier` | `get_event_context(event_name)` |
| Invariants by type or enforcement layer | `p-contract-verifier` | `search_invariants(query, invariant_type?, enforcement?)` |
| What depends on an entity | `p-impact-analyzer` | `get_related_contracts(entity_name)` |
| Module structure and signatures | `p-code-structure-explorer` | `get_module_context`, `get_class_context`, `get_function_context` |
| Fetch multiple entities at once | `p-doc-explorer` | `multi_context(concepts: ["A","B","C"])` |
| Multiple searches across domains | `p-doc-explorer` | `multi_search(searches[])` |
| Discover entity names | N/A (no subagent) | `list_entities()` |
| Discover vision document names | N/A (no subagent) | `list_vision_entities(category?)` |
| List all release phases | N/A (no subagent) | `list_release_plan_phases()` |
| List features in a phase | N/A (no subagent) | `list_release_plan_features(phase?)` |
| Full phase spec | N/A (no subagent) | `get_phase_context(phase_number)` |
| Full feature spec | N/A (no subagent) | `get_feature_context(feature_id)` |
| Read specific files (known paths) | N/A (no subagent) | `get_files([paths])` — scoped, never speculative |
| Find specific function or class signatures | N/A (no subagent) | `search_symbols([symbols])` — batch all symbols, one call |
| Find specific patterns across known files | N/A (no subagent) | `grep_files(pattern, paths?)` |
| Semantic search when file location unknown | N/A (no subagent) | `search_codebase(query)` — last resort; targeted query only |
| Batch multiple code-domain lookups (imports, deps, symbols, function/class context) | N/A (no subagent) | `multi_code_query(queries[])` — max 20 queries per call; split into batches if needed |

**Retrieval pattern:**
- Impact analysis → delegate to `p-impact-analyzer`
- Contract verification → delegate to `p-contract-verifier`
- Structure analysis → delegate to `p-code-structure-explorer`
- Cross-domain research → delegate to `p-doc-explorer`
- Direct file access → use `get_files` directly (no subagent needed)

---

## Unknown Section Names

When calling `get_entity_context` or `get_vision_context` without knowing
which sections exist, omit the `sections` parameter to retrieve the full
document first. Identify the relevant sections from the result before
making any follow-up filtered call. Never guess section names — an empty
result from a wrong section name wastes a retrieval call.

---

## `search_invariants` Filters

`invariant_type`: `uniqueness` | `cardinality` | `behavioral` | `range`
`enforcement`: `database` | `application` | `api`

Filter when you know the kind of constraint you're looking for. Searching
`behavioral` + `application` retrieves append-only rules and processing
boundary constraints without returning database schema invariants.

---

## `get_feature_context` Note

Feature IDs use the indexer's internal format (e.g. `1a`, `2b`) — not
sub-phase IDs like `phase-1-1` or `phase-1-2a`. To read a sub-phase
document, use the native read tool with the file path directly. Use
`list_release_plan_features(phase=1)` to discover what feature IDs exist
before calling `get_feature_context`.

---

## Index Maintenance

After writing or editing architecture, vision, or release-plan documents:
- Call `refresh_architecture()` after architecture or ADR edits
- Call `refresh_vision()` after vision edits
- Call `refresh_release_plan()` after release-plan edits

Never call `reindex_*` tools for document edits — `refresh_*` is
sufficient. `reindex_*` is reserved for structural directory changes only.
