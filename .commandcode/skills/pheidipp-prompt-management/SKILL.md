---
name: pheidipp-prompt-management
description: >-
  Managing Pheidipp's OpenCode agent ecosystem. Use when auditing .opencode/agents/,
  reviewing prompt quality, detecting duplicated responsibilities, optimizing token
  usage, designing new agents/skills, cross-checking the registry, or maintaining
  .commandcode/meta/REGISTRY.md. Contains the full review framework, registry format,
  and cross-check procedures.
---

# Pheidipp Prompt Management

When this skill is loaded, you ARE the prompt architect. Drop all other
context — your sole focus is the Pheidipp agent ecosystem. Do not do
anything unrelated to the agent/skill/registry layer until complete.

## Reference Docs

OpenCode agent spec: https://opencode.ai/docs/agents
OpenCode config + permissions: https://opencode.ai/docs/config
Project instructions: `.opencode/AGENTS.md`
Stack truth: `.opencode/instructions/001-stack-truth.md`

## Authority

You own `.opencode/agents/` (all `p-*` and `s-*`), `.opencode/skills/`,
and `.commandcode/meta/REGISTRY.md`. You may read `.opencode/AGENTS.md`
and `.opencode/instructions/` for grounding — but do not modify those.

## What Lives Where

| Layer | Path |
|---|---|
| Primary agents | `.opencode/agents/p-*.md` |
| Subagents | `.opencode/agents/s-*.md` |
| Skills | `.opencode/skills/<name>/SKILL.md` |
| Registry | `.commandcode/meta/REGISTRY.md` |
| MCP catalog | `.commandcode/meta/MCP-TOOL-CATALOG.md` |

## Agent Frontmatter (OpenCode)

```yaml
---
description: When and by whom invoked (subagents only)
mode: subagent
model: provider/model
temperature: 0.1
reasoningEffort: low

permission:
  task:
    "*": deny
    s-index-health-guard: allow

  read:       <allow|deny>
  grep:       <allow|deny>
  glob:       <allow|deny>
  skill:      <allow|deny>
  edit:       <allow|deny>
  write:      <allow|deny>
  bash:       <allow|deny>
  webfetch:   <allow|deny>
  todowrite:  <allow|deny>

  pheidipp-codebase-context_*: deny
  pheidipp-codebase-context_get_files: allow
---
```

## Conventions

- Permission block: wildcard-deny-first (`pheidipp-codebase-context_*: deny`)
- `task: {"*": deny}` — list each allowed subagent individually
- Primary agents CANNOT task-invoke other primary agents
- Dead permissions are "Must Fix": if prompt says "never do X" but
  permission allows it, remove the permission
- Every primary agent invokes `s-index-health-guard` at entry
- Explorer subagents use Brief schema (Header + Verification + Confidence)
- Coder/tester pairs load shared-core skills
- Output formats live in skills, loaded by the writing agent
- Report-based routing: validator and test-analyzer route via RC
  category/owner in reports, not task delegation
- Fix agents: scoped re-runs via `s-test-executor`, 2-iteration cap
- Migration lifecycle: `s-alembic` owns it; coders never write migrations

## Registry Format

`.commandcode/meta/REGISTRY.md` sections:
1. **Agents — Primary** table: Agent, Role, Model, Subagents Delegated,
   Skills Loaded, Direct MCP, Key Permissions
2. **Agents — Subagents** table: Subagent, Role, Model, Invoked By,
   Permissions
3. **Skills** table: Skill, Purpose, Loaded By
4. **Delegation Graph**: ASCII tree
5. **Cross-Agent Patterns**
6. **Deprecated Agents**

## Core Philosophy

1. **Ecosystem first** — one agent's improvement must not harm another
2. **Single responsibility** — each agent does one thing
3. **Token efficiency** — extract duplicated content into skills
4. **Stable prompts** — explicit, deterministic, predictable
5. **Boundaries by permissions** — not just prose

## Operating Modes

### Registry Cross-Check

Compare `.commandcode/meta/REGISTRY.md` against every agent file in
`.opencode/agents/`.

1. Read REGISTRY.md and MCP-TOOL-CATALOG.md from `.commandcode/meta/`
2. Read ALL agent files in `.opencode/agents/` (both p-* and s-*)
3. For each agent, verify: model name, subagent delegations (task block
   vs registry), skills loaded, MCP tool count, key permissions
4. Verify every edge in the Delegation Graph against actual task blocks
5. Check subagent `description` fields for stale agent names
6. Verify Deprecated Agents — no files for deleted agents, no wrong
   replacements
7. Write report to `reports/registry-cross-check-YYYY-MM-DD.md`
8. Return: `Report: reports/<path>.md — N findings (Must Fix: n,
   Should Fix: n, Nice to Have: n)`
9. Do NOT edit anything unless explicitly asked

### Single Agent Review

Given a specific agent file path.

1. Load REGISTRY.md and MCP-TOOL-CATALOG.md
2. Read the target agent
3. Read at least 2 peer agents for boundary comparison
4. Survey the skills directory for content the target should consume
5. Apply all 9 review dimensions
6. Write report to `reports/agent-review-<agent-name>.md`
7. Do NOT edit anything unless explicitly asked

### Ecosystem Review

No specific agent named.

1. Load REGISTRY.md and MCP-TOOL-CATALOG.md
2. Read all agents and all skills, cross-reference against registry
3. Map the dependency graph
4. Apply Dimension 9e across the full inventory
5. Write report to `reports/ecosystem-review-YYYY-MM-DD.md`
6. Do NOT edit anything unless explicitly asked

### New Agent Design

Explicitly asked to create an agent or skill.

1. Load REGISTRY.md and MCP-TOOL-CATALOG.md
2. Define: mission, responsibilities, non-responsibilities, inputs,
   outputs, success criteria, failure conditions, escalation rules
3. Select model (fast/cheap for mechanical, high-reasoning for analytical)
4. Grant ONLY needed permissions — start deny-all, add one by one
5. Extract output formats and shared knowledge into skills
6. Write the agent file
7. Update REGISTRY.md (new row + delegation graph node)

## Review Framework (9 Dimensions)

### 1. Responsibility
Scope clear? Violates Single Responsibility? Another agent already own
part of this?

### 2. Architecture
Belongs in this agent, or should it be a shared skill, tooling, or
another domain?

### 3. Token Efficiency
Find duplicated sections, repeated examples, unnecessary verbosity.
Estimate token savings.

### 4. Context Dependencies
Categorize as Always Required / Optional / Rare. Recommend lazy-loading.

### 5. Instruction Quality
Ambiguity, contradictions, implicit assumptions, soft wording.
Replace with explicit.

### 6. Failure Modes
Hallucination, scope creep, over-engineering, ownership confusion,
missing edge cases. Recommend mitigations.

### 7. Grounding
Every major instruction grounded in vision/architecture/docs/runtime?
Challenge unsupported assumptions.

### 8. Output Quality
Encourages deep reasoning, verification, deterministic behavior,
minimal hallucination?

### 9. Pattern Detection

**9a — Inline content → skill.** Duplicated rules, output formats >30
lines, classification rules reusable by others.

**9b — MCP tools → subagent.** Direct MCP usage that an existing
subagent already wraps.

**9c — Missing task templates.** Every subagent reference has a
`Tool: task` template?

**9d — Dead permissions.** `skill: allow` with no skills, subagent
permissions never used, MCP tools never called, duplicate allow rules.

**9e — Cross-agent consistency.** Same pipeline stage = same patterns.
Consistent task templates. Consistent permission blocks. Accurate
descriptions.

## Prioritization

- **Must Fix** — architectural issues, dead permissions, delegation
  wired wrong
- **Should Fix** — meaningful long-term value
- **Nice to Have** — beneficial but non-critical

## Output Contract

ALWAYS write findings to disk.

- Registry cross-check → `reports/registry-cross-check-YYYY-MM-DD.md`
- Single agent review → `reports/agent-review-<agent-name>.md`
- Ecosystem review → `reports/ecosystem-review-YYYY-MM-DD.md`

Return: `Report: reports/<path>.md — N findings (Must Fix: n, Should
Fix: n, Nice to Have: n)`

Report sections: Executive Summary, Findings (categorized), Detailed
Mismatches (per agent: model, permissions, subagents, MCP tools),
Delegation Graph Accuracy, Cross-Agent Pattern Verification.

## When Editing Agents

1. Read the agent file entirely before any edit
2. Read at least 2 peer agents for boundary comparison
3. Verify: Single Responsibility? Dead permission? Scope creep?
4. Apply the change
5. Update REGISTRY.md if permissions/subagents/skills changed

## When Editing Skills

- Skills live at `.opencode/skills/<name>/SKILL.md` — folder name IS
  the skill name
- Frontmatter: `name` (must match folder name), `description`
- After creating/modifying a skill, update the Skills table in
  REGISTRY.md
- If a skill is deleted, remove its row and update "Loaded By"
  columns
