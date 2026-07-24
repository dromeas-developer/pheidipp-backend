# Ecosystem Review — Subagent Inconsistencies, Overlaps & Rationalization

**Date:** 2026-07-22  
**Scope:** All 10 subagents + all orchestrators that invoke them  
**Mode:** Ecosystem Review (subagent-focused)

---

## Executive Summary

The subagent ecosystem is architecturally sound in its core design — the hierarchy of state→structure→content explorers, the delegation of retrieval to specialized agents, and the Brief schema consistency are well-executed. However, the review uncovered **4 critical permission gaps** where prompts instruct task delegation but the permission block denies it (runtime failures), **3 dead-or-aspirational description mismatches** where subagent descriptions claim invokers that don't actually call them, and **1 dead subagent** (p-history-explorer) with zero callers. Several tool overlaps between subagents also warrant rationalization.

---

## Overall Assessment

| Dimension | Rating |
|---|---|
| Architecture | ✅ Strong — clear specialization hierarchy |
| Brief Schema Consistency | ✅ All 7 explorers follow the same Header+Verification+Confidence pattern |
| Tool Permission Patterns | ⚠️ 2 agents have gaps (p-consistency-validator, p-release-strategy-architect) |
| Description Accuracy | ❌ 5 subagents have inaccurate claim lists |
| Dead Agents | ❌ p-history-explorer has zero active invokers |
| Tool Overlap | ⚠️ 3 cross-agent overlaps need rationalization |
| REGISTRY Accuracy | ⚠️ 2 skill-consumer mismatches |

---

## Detailed Findings

### CRITICAL — Must Fix

#### F1. p-consistency-validator: Missing task permission for p-state-explorer

**Evidence:**
- `p-consistency-validator.md` lines 118-131 and 222-235: prompt explicitly says "Invoke `p-state-explorer` via the `task` tool" with full task template
- Permission block line 6-8: `task: "*": deny` then only `p-index-health-guard: allow`
- `p-state-explorer` is NOT in the task allow list

**Impact:** Runtime failure — the `task` call to `p-state-explorer` will be rejected at the permission layer. The consistency validator cannot fulfill its Step 0 "Load State" protocol.

**Fix:** Add `p-state-explorer: allow` to the task permissions block in `p-consistency-validator.md`.

---

#### F2. p-release-strategy-architect: Missing task permission for p-doc-explorer

**Evidence:**
- `p-release-strategy-architect.md` lines 360-375: prompt says "Invoke `p-doc-explorer` via the `task` tool" with full task template
- Permission block line 6-8: `task: "*": deny` then only `p-index-health-guard: allow`
- `p-doc-explorer` is NOT in the task allow list

**Impact:** Runtime failure — the Retrieval section's primary instruction cannot execute. The release strategy architect would need to fall back to direct tool calls, which the prompt's delegation model is designed to avoid.

**Fix:** Add `p-doc-explorer: allow` to the task permissions block. Alternatively, if the intent is for p-release-strategy-architect to use direct retrieval (it has `search_architecture`, `search_vision`, etc.), remove the delegation instruction from the prompt.

---

#### F3. p-vision-and-architect-author: Task delegation instruction with no task permission

**Evidence:**
- `p-vision-and-architect-author.md` lines 167-183: prompt says "Invoke `p-doc-explorer` via the `task` tool" with full task template
- Permission block line 12-13: `task: "*": deny` (no exceptions — no subagent delegation allowed at all)

**Impact:** Runtime failure — the Step 3 delegation to p-doc-explorer cannot execute. However, this agent holds direct retrieval tools (`search_architecture`, `get_entity_context`, etc.) and `get_change_impact`, so it can retrieve context directly. The delegation instruction appears to be a copy-paste artifact from agents that follow the delegation pattern (p-technical-advisor, p-implementation-architect) but was placed in an agent that does not delegate.

**Fix:** Either (a) remove the p-doc-explorer delegation instruction and replace with direct tool guidance, or (b) add `p-doc-explorer: allow` to task permissions. Given this agent is itself a `mode: subagent`, option (a) is preferred — subagents should not nest further subagents unless there's a clear architectural reason. The agent already has the tools to do its own retrieval.

---

#### F4. p-diagnostics-fixer: Prompt-only restriction on bash commands is fragile

**Evidence:** `p-diagnostics-fixer.md` lines 348-365 defines a detailed "Permitted bash commands" list (6 allowed patterns, 7 forbidden patterns) enforced only by prompt text. The permission block simply says `bash: allow`.

**Impact:** Any model drift or prompt truncation could allow the agent to run forbidden commands. The guardrail is prompt-level, not permission-level. This is a known finding carried from prior reviews (FINDINGS.md line 10: "risk of model drift escaping the guard").

**Fix:** This is a platform limitation — the current permission system cannot express per-command restrictions. Document as an accepted risk. If the platform gains finer-grained bash permissions, restrict to `scripts/typecheck.sh`, `scripts/lint.sh`, and `scripts/format.sh` only.

---

### MUST FIX — Description & REGISTRY Mismatches

#### F5. p-impact-analyzer description claims 6 invokers; only 2 actually invoke it

**Description says:** "Invoked via Task by p-coder, p-implementation-architect, p-test-architect, p-implementation-validator, p-consistency-validator, or p-devops"

**Actual invokers:**
| Agent | Invokes p-impact-analyzer? | Evidence |
|---|---|---|
| p-coder | ✅ Yes | Has task template, `p-impact-analyzer: allow` |
| p-implementation-architect | ✅ Yes | Has task template, `p-impact-analyzer: allow` |
| p-test-architect | ❌ No | Uses p-code-explorer + p-contract-verifier; impact analysis lives in p-implementation-architect's roasting |
| p-implementation-validator | ❌ No | Uses p-contract-verifier + p-code-structure-explorer; no impact-analyzer invocation |
| p-consistency-validator | ❌ No | Uses p-state-explorer; no impact-analyzer invocation |
| p-devops | ❌ No | Uses only p-index-health-guard |

**Fix:** Update description to: "Invoked via Task by p-coder and p-implementation-architect."

---

#### F6. p-code-structure-explorer description claims 6 invokers; only 3 actually invoke it

**Description says:** "Invoked via Task by p-coder, p-implementation-architect, p-test-architect, p-implementation-validator, p-consistency-validator, or p-devops"

**Actual invokers:**
| Agent | Invokes? | Evidence |
|---|---|---|
| p-coder | ✅ Yes | Has task template |
| p-implementation-architect | ✅ Yes | Has task template |
| p-implementation-validator | ✅ Yes | Has task template (Step 5 deviation detection) |
| p-test-architect | ❌ No | Uses p-code-explorer exclusively |
| p-consistency-validator | ❌ No | Uses p-state-explorer |
| p-devops | ❌ No | Uses only p-index-health-guard |

**Fix:** Update description to: "Invoked via Task by p-coder, p-implementation-architect, and p-implementation-validator."

---

#### F7. p-contract-verifier description missing p-implementation-validator

**Description says:** "Invoked via Task by p-coder, p-implementation-architect, p-test-architect, or p-implementation-validator"

**Actually:** p-implementation-validator IS in the description. But p-test-architect also invokes p-contract-verifier (Step 3). Let me re-check...

Wait — p-test-architect DOES invoke p-contract-verifier in Step 3:
```
"subagent_type": "p-contract-verifier",
"prompt": "Entity: <entity_name>"
```
And its task permissions DO include `p-contract-verifier: allow`. So p-test-architect is a valid invoker.

**Revised check:** Description says "p-coder, p-implementation-architect, p-test-architect, or p-implementation-validator" — all 4 are correct. ✅

**However**, the REGISTRY line says "Invoked via Task by p-coder, p-implementation-architect, p-test-architect, or p-implementation-validator." — also correct. ✅

This is actually consistent. Strike F7 — it's fine.

---

#### F8. p-history-explorer is a dead subagent — zero active invokers

**Description says:** "invoked only via Task by p-test-architect, p-coder, or p-implementation-architect"

**Actual invokers:** None. No agent in the ecosystem has `p-history-explorer: allow` in its task permissions. No agent's prompt contains a task template for p-history-explorer.

**Value proposition:** p-history-explorer scans prior validation reports, DevOps reports, diagnostics reports, implementation plans, and manifests for excerpts relevant to a caller's task. This is genuinely useful — it would help p-implementation-architect (knowing what failed before), p-coder (knowing what diagnostics patterns recur), p-test-architect (knowing prior test failures), and p-consistency-validator (scanning cross-phase history).

**Fix options:**
1. **Remove it** — if no one needs it, dead code is dead code. Remove the agent file and REGISTRY entry.
2. **Wire it in** — add `p-history-explorer: allow` and invocation templates to p-implementation-architect (Step 1 or a new cross-phase-awareness step), p-coder (Fix Mode pre-flight), or p-consistency-validator.
3. **Update description** — if the intent is to keep it available as an on-demand tool, change description to "Available for on-demand invocation by any agent needing historical report context. Currently not wired into any standard pipeline."

**Recommendation:** Option 3 (update description) as a stopgap; plan option 2 for p-implementation-architect Step 1 context gathering.

---

### MUST FIX — REGISTRY.md Skill Consumer Mismatches

#### F9. no-silent-deviations skill: REGISTRY missing p-coder

**REGISTRY.md line 42:** `no-silent-deviations | ... | p-implementation-validator, p-diagnostics-fixer`
**Actual consumers:** p-coder, p-diagnostics-fixer, p-implementation-validator (via validation-classification-and-report)

The REGISTRY's skill section omits p-coder. FINDINGS.md line 61 correctly lists all three.

**Fix:** Add p-coder to the Loaded By column for no-silent-deviations in REGISTRY.md line 42.

---

#### F10. retrieval-patterns skill: REGISTRY missing p-history-explorer

**REGISTRY.md line 35:** `retrieval-patterns | ... | p-implementation-architect, p-doc-explorer, p-state-explorer`
**Actual consumers:** p-implementation-architect, p-doc-explorer, p-state-explorer, **p-history-explorer** (line 72 of its prompt)

**Fix:** Add p-history-explorer to the Loaded By column for retrieval-patterns in REGISTRY.md line 35.

---

### SHOULD FIX — Tool Overlaps

#### O1. `get_change_impact` held by both p-doc-explorer and p-impact-analyzer

**Current state:**
- p-doc-explorer: Uses `get_change_impact` in Phase 1 ("Also call `get_change_impact(concept)` for each existing entity the task modifies")
- p-impact-analyzer: Primary owner — its whole role is impact analysis via `get_change_impact`

**Analysis:** p-doc-explorer's use of `get_change_impact` is an optimization — it pre-fetches blast-radius data during Phase 1 bulk context. But this creates ambiguity: orchestrators that want impact analysis can go through either p-doc-explorer OR p-impact-analyzer. p-implementation-architect already delegates to p-impact-analyzer for blast radius (Step 3) and to p-doc-explorer for documentation (Step 2). Having `get_change_impact` in both creates a boundary question.

**Recommendation:** Remove `get_change_impact` from p-doc-explorer. Orchestrators that need blast-radius analysis should delegate to p-impact-analyzer explicitly. p-doc-explorer's Phase 1 already returns architecture entities; the orchestrator can then delegate impact questions to p-impact-analyzer in a targeted way. This keeps the single-responsibility boundary clean: doc-explorer owns documentation retrieval, impact-analyzer owns blast-radius analysis.

**Token impact:** Negligible — removes 1 tool permission line from p-doc-explorer, no prompt changes needed to Phase 1 (just skip that sentence).

---

#### O2. `get_module_deps` and `get_importers` held by both p-impact-analyzer and p-code-structure-explorer

**Current state:**
- p-impact-analyzer: Uses these for code-level dependency tracing as part of impact analysis
- p-code-structure-explorer: Uses these for module structure reporting

**Analysis:** Both agents use these tools for different purposes: p-impact-analyzer uses them transitively (what depends on what), p-code-structure-explorer uses them structurally (what does this module contain). There is a valid case for both. However, p-impact-analyzer could delegate code-level dependency questions to p-code-structure-explorer instead of holding the tools directly, keeping its toolset focused on `get_change_impact` and `get_related_contracts` (architecture-level impact).

**Recommendation:** This is a judgment call. The overlap is not harmful — both agents use the tools for genuinely different things. Keep as-is unless delegation latency becomes a concern. Note: if p-code-structure-explorer is invoked for every module in an impact chain, the orchestrator pays N+1 subagent invocations. Direct tool access in p-impact-analyzer avoids that cost. **Keep both.**

---

#### O3. `get_related_contracts` held by p-doc-explorer, p-impact-analyzer, and p-contract-verifier

**Current state:** Three agents hold this tool:
- p-doc-explorer: Phase 3 deep-fetch
- p-impact-analyzer: Blast radius analysis
- p-contract-verifier: Contract verification

**Analysis:** This is the correct distribution. Each agent uses `get_related_contracts` for a different purpose aligned with its role. No rationalization needed.

---

### SHOULD FIX — Model & Pattern Consistency

#### C1. p-doc-explorer uses `opencode-go/deepseek-v4-flash` (paid) while all other explorers use `opencode/deepseek-v4-flash-free`

**Current state:** 8 explorers use `flash-free`; only p-doc-explorer and p-diagnostics-fixer use the paid `flash` model. (p-documentation also uses paid `flash`, but it writes files — it's not purely an explorer.)

**Analysis:** p-doc-explorer has the most complex retrieval pipeline (Phase 1-3 with multi_context, multi_search, ADR chain traversal, and deep-fetch). It needs to synthesize results across 4 domains. This likely justifies the more capable model. p-diagnostics-fixer's paid model is justified by its code-editing responsibilities.

**Recommendation:** Keep as-is. The model choice is deliberate and justified by task complexity.

---

#### C2. p-release-strategy-architect has `p-index-health-guard` in task permissions but never invokes it

**Evidence:** Permission block allows `p-index-health-guard`, but the prompt contains no task template or invocation instruction for it.

**Impact:** Dead permission — no runtime harm, but it implies intent that was never implemented.

**Fix:** Either remove `p-index-health-guard: allow` from task permissions, or add an invocation step (pre-flight index freshness check before retrieval).

---

### NICE TO HAVE — Documentation & Naming

#### N1. "Explorer" naming convention is slightly overloaded

Seven agents carry "explorer" in their name, but three serve fundamentally different roles:
- **True explorers** (return Briefs): p-state-explorer, p-doc-explorer, p-code-explorer, p-history-explorer
- **Verifiers** (return structured verification reports): p-contract-verifier
- **Analyzers** (return analysis reports): p-impact-analyzer
- **Structure resolvers** (return AST-based reports): p-code-structure-explorer

The term "explorer" is used loosely. p-contract-verifier and p-impact-analyzer don't "explore" in the same sense — they verify and analyze respectively. The current naming works in practice but could be more precise.

**Recommendation:** No rename needed now — renaming introduces cascading changes across all orchestrator prompts. If the ecosystem ever undergoes a naming pass, consider aligning names more tightly to the Brief-vs-Report distinction.

---

#### N2. p-index-health-guard description says "Invoked via Task by any agent at session start"

**Reality:** 4 orchestrators invoke it (p-coder, p-implementation-architect, p-implementation-validator, p-test-architect). 2 agents have the permission but no invocation (p-release-strategy-architect, p-technical-advisor). p-devops invokes it in Pre-Flight 2.

**Fix:** The description is approximately correct but aspirational. Update to: "Invoked via Task by implementation-pipeline agents at session start (p-coder, p-implementation-architect, p-implementation-validator, p-test-architect, p-devops)."

---

## Delegation Graph (Verified)

```
p-implementation-architect
  ├── p-index-health-guard     ✅ Step 1
  ├── p-state-explorer         ✅ Step 1
  ├── p-doc-explorer           ✅ Step 2
  ├── p-impact-analyzer        ✅ Step 3
  ├── p-contract-verifier      ✅ Step 5 RC1
  └── p-code-structure-explorer ✅ Step 6

p-implementation-validator
  ├── p-index-health-guard     ✅ Step 5
  ├── p-state-explorer         ✅ Step 1b
  ├── p-contract-verifier      ✅ Step 4
  └── p-code-structure-explorer ✅ Step 5

p-coder
  ├── p-index-health-guard     ✅ Pre-flight
  ├── p-impact-analyzer        ✅ Subagent Delegation
  ├── p-code-structure-explorer ✅ Subagent Delegation
  ├── p-contract-verifier      ✅ Pre-flight Step 4
  ├── p-diagnostics-fixer      ✅ Completion Verification
  └── p-documentation          ✅ Completion Verification

p-test-architect
  ├── p-index-health-guard     ✅ Step 1
  ├── p-code-explorer          ✅ Step 6 (all stages)
  ├── p-contract-verifier      ✅ Step 3
  ├── p-diagnostics-fixer      ✅ Step 9 / Fix Mode
  └── p-documentation          ✅ Step 9

p-technical-advisor
  ├── p-doc-explorer           ✅ Retrieval Protocol
  ├── p-index-health-guard     ⚠️ Permission exists, no invocation
  └── p-vision-and-architect-author ✅ Architecture Handoff Mode

p-release-strategy-architect
  ├── p-index-health-guard     ⚠️ Permission exists, no invocation
  └── p-doc-explorer           ❌ Prompt says to, permission missing (F2)

p-vision-and-architect-author
  └── p-doc-explorer           ❌ Prompt says to, task denied entirely (F3)

p-consistency-validator
  ├── p-index-health-guard     ✅ Permission exists
  └── p-state-explorer         ❌ Prompt says to, permission missing (F1)

p-devops
  └── p-index-health-guard     ✅ Pre-Flight 2
```

---

## Cross-Subagent Tool Overlap Map

| Tool | p-state | p-doc | p-impact | p-code-struct | p-contract | p-code | p-history | p-diag | p-doc-writer | p-index |
|---|---|---|---|---|---|---|---|---|---|---|
| search_symbols | ✅ | | ✅ | ✅ | ✅ | ✅ | | ✅ | ✅ | |
| get_entity_context | | ✅ | | | ✅ | ✅ | | | | |
| get_event_context | | ✅ | | | ✅ | | | | | |
| get_related_contracts | | ✅ | ✅ | | ✅ | | | | | |
| get_change_impact | | ⚠️ | ✅ | | | | | | | |
| get_module_deps | | | ⚠️ | ⚠️ | | | | | | |
| get_importers | | | ⚠️ | ⚠️ | | | | | | |
| get_files | ✅ | | | | | ✅ | ✅ | | ✅ | |
| find_files | ✅ | | | | | ✅ | ✅ | | ✅ | |
| grep_files | ✅ | | | | | ✅ | ✅ | | ✅ | |
| search_codebase | ✅ | | | | | ✅ | | | ✅ | |
| get_code_for_entity | ✅ | | | | | | | | | |

**Key:** ✅ = correct for role | ⚠️ = overlap, may need rationalization | (blank) = not held

**Top overlap candidates for rationalization:**
1. `get_change_impact` in p-doc-explorer → remove (O1)
2. `get_module_deps` / `get_importers` in both p-impact and p-code-struct → keep (O2)
3. `search_symbols` across 7 agents → fundamental tool, keep

---

## Prioritized Recommendations

### Immediate (Must Fix — Blocking)

| # | Finding | Agent | Action |
|---|---|---|---|
| F1 | Missing task permission for p-state-explorer | p-consistency-validator | Add `p-state-explorer: allow` to task permissions |
| F2 | Missing task permission for p-doc-explorer | p-release-strategy-architect | Add `p-doc-explorer: allow` to task permissions OR remove delegation instruction |
| F3 | Task delegation instruction with no task permission | p-vision-and-architect-author | Remove p-doc-explorer delegation instruction; agent does direct retrieval |
| F5 | Description claims 6 invokers, only 2 active | p-impact-analyzer | Update description to "p-coder and p-implementation-architect" |
| F6 | Description claims 6 invokers, only 3 active | p-code-structure-explorer | Update description to "p-coder, p-implementation-architect, p-implementation-validator" |
| F8 | Dead subagent — zero invokers | p-history-explorer | Update description to reflect actual state; plan wiring into p-implementation-architect |
| F9 | REGISTRY missing p-coder in no-silent-deviations consumers | REGISTRY.md | Add p-coder |
| F10 | REGISTRY missing p-history-explorer in retrieval-patterns consumers | REGISTRY.md | Add p-history-explorer |

### Short-term (Should Fix)

| # | Finding | Agent | Action |
|---|---|---|---|
| O1 | get_change_impact overlap | p-doc-explorer | Remove tool; orchestrators use p-impact-analyzer for blast radius |
| C2 | Dead permission (p-index-health-guard) | p-release-strategy-architect | Remove from task permissions or add invocation step |
| N2 | Aspirational description | p-index-health-guard | Update to list actual verified invokers |

### Long-term (Nice to Have)

| # | Finding | Action |
|---|---|---|
| N1 | "Explorer" naming overload | Consider rename pass in future |
| F4 | Bash prompt-only restriction | Document as accepted platform limitation |

---

## Expected Impact

**Addressing the 8 Must-Fix items:**
- 3 agents that currently fail at runtime (p-consistency-validator, p-release-strategy-architect, p-vision-and-architect-author) will function correctly when their delegation instructions execute
- 3 subagent descriptions will accurately reflect their actual invocation patterns, preventing orchestrator confusion
- 2 REGISTRY entries will match reality, preventing ecosystem-wide discovery gaps
- 1 dead agent will be clearly labeled as such, preventing wasted investigation

**Addressing the Should-Fix items:**
- p-doc-explorer / p-impact-analyzer boundary will be cleaner (remove get_change_impact from p-doc-explorer)
- No dead permissions will remain

**Token impact:** Minimal — description updates are 1-line changes. Permission changes are 1-line additions/removals.

---

## Risks

1. **F3 fix (p-vision-and-architect-author):** If the delegation instruction is removed, the agent must be confirmed to have sufficient direct tools for its retrieval needs. Current toolset includes `search_architecture`, `get_entity_context`, `get_event_context`, `get_related_contracts`, `get_change_impact` — this is sufficient. No risk.

2. **F2 fix (p-release-strategy-architect):** If p-doc-explorer delegation is enabled, this changes the retrieval model for this agent from direct-tool to subagent-based. The agent's prompt already has the delegation pattern written; only the permission is missing. Low risk.

3. **O1 fix (remove get_change_impact from p-doc-explorer):** Orchestrators that currently rely on p-doc-explorer's Phase 1 including blast-radius data will need to delegate separately to p-impact-analyzer. p-implementation-architect already does this in Step 3 — no change needed for the primary consumer. Other consumers (p-technical-advisor, p-vision-and-architect-author) use doc-explorer for documentation context, not blast radius. Low risk.

4. **F8 (p-history-explorer):** If the description is updated to "available for on-demand invocation" rather than "invoked by," no runtime behavior changes. If wiring into p-implementation-architect, adds one subagent call to Step 1 — negligible overhead.

---

## Final Recommendation

Apply the 8 Must-Fix items immediately. They are all small, targeted changes (permission lines, description text, REGISTRY entries) with no blast radius beyond the affected agent. The 3 Should-Fix items can follow in the next review cycle.

The subagent ecosystem's architecture — state→structure→content hierarchy, Brief schema consistency, and delegation pattern — is sound. The issues found are maintenance debt (stale descriptions, permission gaps from copy-paste artifacts) rather than design flaws. Addressing them restores the ecosystem to full consistency.

---

## Appendix: Agent Model Summary

| Subagent | Model | Cost Tier |
|---|---|---|
| p-state-explorer | opencode/deepseek-v4-flash-free | Free |
| p-doc-explorer | opencode-go/deepseek-v4-flash | Paid |
| p-impact-analyzer | opencode/deepseek-v4-flash-free | Free |
| p-code-structure-explorer | opencode/deepseek-v4-flash-free | Free |
| p-contract-verifier | opencode/deepseek-v4-flash-free | Free |
| p-code-explorer | opencode/deepseek-v4-flash-free | Free |
| p-history-explorer | opencode/deepseek-v4-flash-free | Free |
| p-index-health-guard | opencode/deepseek-v4-flash-free | Free |
| p-diagnostics-fixer | opencode-go/deepseek-v4-flash | Paid |
| p-documentation | opencode-go/deepseek-v4-flash | Paid |

9 out of 10 subagents use the cheaper `flash-free` model. Only p-doc-explorer and the two write/edit subagents use the paid tier — justified by task complexity.
