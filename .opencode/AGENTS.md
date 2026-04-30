# Pheidipp — Agent Behaviour Rules

## Instruction Hierarchy
- System context (Stack Truth + Dynamic Context) is authoritative
- Do NOT redefine or reinterpret architecture or rules

## Always Batch — Never Sequential
- Identify ALL required inputs before calling a tool
- Call MCP tools ONCE with full input set
- NEVER call tools in loops
- NEVER perform sequential reads

## Tool Selection
- **Need file contents** (source files, plans, any path): `pheidipp-codebase-context_get_files` (ALL paths in one call — never use read)
- **Need symbols (functions/classes)**: `pheidipp-codebase-context_search_symbols`
- **Need conceptual/semantic search**: `pheidipp-codebase-context_search_codebase`
- **Need architecture overview**: `pheidipp-codebase-context_get_architecture_context` (use sparingly)
- **Need to rebuild the index**: `pheidipp-codebase-context_reindex`
There is no read, find_files, or grep_files tool. Do NOT attempt to call them.

## Tool Discipline
- If answer can be derived from context → DO NOT call tools
- Prefer reasoning over tool usage
- Never re-fetch known information

## Edit Discipline
- Only modify files explicitly in scope
- Prefer targeted edits over full rewrites
- Do NOT create files unless specified

## Two-Strike Rule
- If a tool fails twice → STOP
- List missing context
- Ask ONE question
- Do NOT guess

## Atomic Behaviour
- Complete the task → STOP
- No follow-ups, no extra phases

## Occam's Razor
- Prefer the simplest valid solution
- Avoid new abstractions unless required
