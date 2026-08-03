---
name: retrieval-patterns
description: >
  Load this when an agent queries the architecture, vision, release-plan,
  or ADR corpora via the pheidipp-codebase-context MCP tools and needs
  section-name handling, search_invariants filter documentation,
  get_feature_context usage notes, and index maintenance rules.
  Delegation patterns live in each agent's own prompt.
---

# Retrieval Patterns

Shared reference for agents querying the documentation corpus. Each agent
encodes its own delegation-to-subagent patterns and retrieval rules; this
skill covers cross-cutting reference material only.

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
