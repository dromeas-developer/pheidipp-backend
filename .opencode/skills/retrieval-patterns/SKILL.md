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

## Bulk vs Targeted Retrieval

**Default: prefer bulk tools when gathering information about multiple
independent concepts.**

| Pattern | Tool | When to use |
|---|---|---|
| Discovery across multiple concepts/domains | `multi_search(searches[])` | One call per concept across domains — batch all searches |
| Cross-domain context for multiple concepts | `multi_context(concepts: ["A","B","C"])` | Full context for all named concepts in one call |
| Impact analysis before modifying an existing entity | `get_change_impact(concept)` | Returns affected entities + events + agents + vision + release features |
| Who depends on a given entity | `get_related_contracts(entity_name)` | JSON list of referencing entities |

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

| Situation | Tool |
|---|---|
| Fetch multiple entities at once | `multi_context(concepts: ["A","B","C"])` — one call for all |
| Multiple searches across domains | `multi_search(searches[])` — batch all searches, one call |
| Check what depends on an entity | `get_related_contracts(entity_name)` — JSON list |
| Check full impact of modifying an entity | `get_change_impact(concept)` — entities + events + agents + vision |
| Full spec for one entity (sections optional) | `get_entity_context(entity_name, sections?)` |
| Event producer/consumer/schema | `get_event_context(event_name)` |
| Invariants by type or enforcement layer | `search_invariants(query, invariant_type?, enforcement?)` |
| Discover entity names | `list_entities()` |
| Discover vision document names | `list_vision_entities(category?)` |
| List all release phases | `list_release_plan_phases()` |
| List features in a phase | `list_release_plan_features(phase?)` |
| Full phase spec | `get_phase_context(phase_number)` |
| Full feature spec | `get_feature_context(feature_id)` |
| Read specific files (known paths) | `get_files([paths])` — scoped, never speculative |
| Find specific function or class signatures | `search_symbols([symbols])` — batch all symbols, one call |
| Find specific patterns across known files | `grep_files(pattern, paths?)` |
| Semantic search when file location unknown | `search_codebase(query)` — last resort; targeted query only |

**Retrieval pattern:**
- Discovery and comparison → prefer bulk tools (`multi_search`, `multi_context`)
- Impact analysis → `get_change_impact`
- Verification and contract detail → prefer targeted tools (`get_entity_context`, `get_event_context`, `get_phase_context`)

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
