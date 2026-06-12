# Pheidipp — Agent Behaviour Rules

## Instruction Hierarchy

- System context stack-truth is authoritative and already part of your context
- Do NOT redefine or reinterpret architecture or rules
- Before calling any tool, verify what is already available in context

---

## Tool Pre-Validation (Mandatory)
Before calling any tool:
1. Confirm the tool name exists in your available tools
2. Confirm all required fields are present
3. Confirm argument types match the schema exactly — array ≠ string, object ≠ string
4. Construct arguments as native structures — NOT JSON-encoded strings

If any check fails → fix the arguments first, then call.
If a tool fails twice → STOP, list what is missing, ask ONE question.

---

## Batching Discipline

The purpose of bulk tools is to reduce round-trips and token consumption.
Use them when retrieving multiple independent pieces of information.

Before every tool call ask: **could this be combined with a call I am already making?**
- Identify ALL required inputs before calling any tool
- Prefer one batched call over multiple sequential calls for independent information
- Never call the same tool twice in a row for different inputs when batching is possible
- Never read the same file twice unless it was edited since the last read

Batching is a means to efficiency, not an end. A single targeted call is
always better than a large bulk call that returns mostly irrelevant results.

---

## Truncation Policy

Large file content may be truncated. This is expected — truncated content is sufficient for most tasks.
- Do NOT make follow-up calls to retrieve more of the same file
- Do NOT treat truncation as an error
- If truncation genuinely prevents task completion → note the assumption and continue

---

## Edit Discipline

- Only modify files explicitly in scope for the task
- Prefer targeted edits over full rewrites
- Read a file immediately before editing it — never edit from memory or from content retrieved earlier in the session if the file may have changed
- Do NOT create files unless the task explicitly requires it

---

## Atomic Behaviour

- Complete the task → STOP
- No unsolicited follow-up phases
- No speculative improvements outside task scope

---

## Occam's Razor

- Prefer the simplest valid solution
- Avoid new abstractions unless the task requires them

---

## Execution Rules (Non-Negotiable)

- NEVER run system commands directly if a `scripts/` wrapper exists
- ALWAYS prefer `scripts/` over raw commands
- Import/module/version errors → assume wrong runtime, retry with scripts
