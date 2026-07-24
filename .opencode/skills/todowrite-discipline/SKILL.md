---
name: todowrite-discipline
description: >
  Standard task-tracking pattern for multi-step agent protocols. Every
  agent with a multi-step protocol loads this skill. The agent's own
  prompt supplies its protocol source and surfaced-work examples as a
  short annotation — this skill supplies the pattern, not the specifics.
---

# Todo List Discipline

At the start of every invocation, create a `todowrite` tasklist from the
protocol steps for the mode you are entering. Each step becomes one task
item. Mark each `[x]` as it completes. When a step surfaces new work, add
those as nestable task items. Update the tasklist at the end of every step.

**Agent annotation:** the agent's own prompt states which protocol steps
initialize the tasklist and what kind of surfaced work to expect. This
skill defines the pattern only — each agent supplies its own protocol
source and work-type examples inline.
