# Pheidipp — Agent Behaviour Rules

## Instruction Hierarchy
- System context (stack-thruth + dynamic-context) is authoritative and already part of your context 
- Do NOT redefine or reinterpret architecture or rules
- Before calling any tool, verify what is already available

---

## Context Check (Run This First — Always)
The following is injected into your system prompt before this conversation:
- Full file tree with all current modules and files
- Database schema with all tables, columns, and relationships
- Active ARQ jobs and LangGraph agents
- Stack architecture and layer rules

Ask yourself before calling any tool:
1. Do I know which files are affected? → file tree is in context
2. Do I know the current schema? → schema is in context
3. Do I know existing patterns? → stack-truth is in context
4. What specific information is MISSING that I cannot derive?

If the answer to question 4 is "nothing" → produce output immediately.
Only call tools to fill genuine gaps that cannot be inferred from context.

---

## Tool Selection

**Need file contents** (source files, plans, any path):
→ `pheidipp-codebase-context_get_files` — ALL paths in one call

**Need symbols (functions/classes/signatures)**:
→ `pheidipp-codebase-context_search_symbols` — cheaper than reading full files

**Need to find files by name or pattern**:
→ `pheidipp-codebase-context_find_files`

**Need exact string/regex match in file contents**:
→ `pheidipp-codebase-context_grep_files`

**Need conceptual/semantic search across code**:
→ `pheidipp-codebase-context_search_codebase`

**Need to rebuild the index**:
→ `pheidipp-codebase-context_reindex`

**`pheidipp-codebase-context_get_architecture_context`**:
→ AVOID — dynamic.md already provides structure and patterns.
→ Only call if dynamic.md is missing and no other tool suffices.
→ NEVER set both include_structure=true AND include_patterns=true.

**Forbidden native tools** — do NOT call these:
→ `read`, `grep`, `glob` — use MCP tools above instead

---

## Tool Usage — Batch and Justify

Use as many tool calls as the task genuinely requires — no artificial cap.
The constraint is discipline, not count.

Before every tool call, ask: **could this be batched into a call I'm already making?**

- Identify ALL required inputs before calling any tool
- Call MCP tools ONCE per type with the full input set
- NEVER call tools in loops or sequentially when batching is possible

Examples of correct batching:
- `get_files` with 8 paths = 1 call ✅
- `search_symbols` with 5 symbols = 1 call ✅
- Four sequential `find_files` calls for paths already listed in context = ❌

Planning agents (p-architect, p-prompt-engineer, p-technical-advisor):
→ Prefer zero tool calls — context usually contains everything needed.
→ 3–4 calls is the expected ceiling for a planning task.

Implementation agents (p-coder):
→ Tool calls are expected — reading files, verifying edits, running scripts.
→ Still batch aggressively; never read the same file twice unless it was just edited.

---

## Always Batch — Never Sequential

- Identify ALL required inputs before calling a tool
- Call MCP tools ONCE with full input set
- NEVER call tools in loops
- NEVER perform sequential reads

---

## Truncation Policy

File content returned by `get_files` may be truncated for large files.
This is expected behaviour — truncated content is sufficient for planning.

- Do NOT make follow-up search calls to retrieve more of the same file
- Do NOT treat truncation as an error or failure
- For exact signatures, use `search_symbols` instead of reading full files
- If truncation prevents completing the task → note the assumption and continue

---

## Tool Pre-Validation (Mandatory)

Before calling any tool:
1. Validate tool name exists in available tools
2. Validate ALL required fields are present
3. Validate argument types match schema exactly
   - array ≠ string
   - object ≠ string
4. Construct arguments as a native structure — NOT a JSON string

If any check fails → fix arguments first, then call

---

## Edit Discipline

- Only modify files explicitly in scope
- Prefer targeted edits over full rewrites
- Do NOT create files unless specified

---

## Two-Strike Rule

- If a tool fails twice → STOP
- List missing context
- Ask ONE question
- Do NOT guess

---

## Atomic Behaviour

- Complete the task → STOP
- No follow-ups, no extra phases

---

## Occam's Razor

- Prefer the simplest valid solution
- Avoid new abstractions unless required

---

## Execution Rules (Non-Negotiable)

- NEVER run system commands directly if a `scripts/` wrapper exists
- ALWAYS prefer `scripts/` over raw commands
- Import/module/version errors → assume wrong runtime, retry with scripts
