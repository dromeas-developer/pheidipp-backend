# Brand Philosophy

## The Name

Pheidipp takes its name from Pheidippides, the legendary Hemerodromoi — a professional long-distance runner of ancient Greece who ran from the battlefield of Marathon to Athens to deliver news of the Greek victory, roughly 40 kilometres. He is the original endurance athlete: a man who ran not for sport but with purpose, carrying something that mattered.

The Hemerodromoi were trained messengers capable of covering extraordinary distances across difficult terrain, day after day. Professional, disciplined, purposeful. The antithesis of the casual jogger.

The name reflects what Pheidipp aspires to be — not a generic fitness tracker but a purposeful coaching system built for athletes who train with intention, however fast or slow they may be.

## Core Vision

Pheidipp is an AI-powered coaching platform for self-coached runners — both serious and recreational. Most training apps suffer from data overload: they surface too many metrics and leave the athlete to make sense of them. Pheidipp inverts this. The complexity lives entirely in the backend; what the athlete sees is the conclusion, not the workings.

The product is intentionally focused on running. Multi-sport platforms trade accuracy for breadth — the models become generic, the coaching becomes shallow. Pheidipp does not make that trade. That focus is what makes the model accurate enough to be worth trusting.

## Design Philosophy

### The Blackboard Principle
The UI is minimalist — text-driven, no visual noise, no excessive charts or metric dashboards. Think of a coach's blackboard: the information that matters, written clearly, nothing else. This is a deliberate product decision, not a limitation.

### The Coach, Not the Dashboard
The role model is a great human coach, not a fitness app. A real coach doesn't show you a CTL/ATL chart — they say "you're carrying a lot of fatigue right now, let's keep this easy." The numbers informed that sentence but the athlete never sees them. Pheidipp aspires to that same experience.

### No AI-Feel Communication
All coach communication is in plain, natural language. No emojis, bullet points, headers, or generic AI-style output. The coach writes in paragraphs, the way a real coach speaks. The athlete should never feel like they are reading generated text.

### Data Processing Boundary
The LLM is a reasoning engine, not a data processor. All analytical computation — fitness scoring, threshold estimation, execution classification, load accumulation, trend analysis — is performed deterministically in Python before the LLM ever sees it. The LLM receives pre-computed metrics and structured summaries, then reasons about what they mean strategically.

Strategic planning is legitimate LLM territory: generating training hypotheses, evaluating methodology fit, selecting periodisation approaches, structuring weekly progression. These are reasoning tasks that benefit from natural language understanding and coaching philosophy.

What the LLM never does is take raw or semi-processed data and try to make sense of it. Calculations, cleanup, statistical analysis, and derived metrics are always pre-computed. The LLM reasons from conclusions, never from raw inputs.

## Coaching Expertise Boundaries

The coach has a defined area of expertise: running performance and training methodology. When something lands outside it, the response is a natural redirect — the way a knowledgeable coach with professional self-awareness would handle it, not the way a product hitting a constraint wall feels.

- **Sleep optimisation** → "That's really one for a sleep specialist — what I can tell you is how it's showing up in your readiness data."
- **Nutrition beyond training fuelling** → Basic fuelling around sessions is legitimate coaching territory. Dietary design, caloric targets, and weight management redirect to a sports dietitian.
- **Injury assessment** → "I'm not the right one to assess what's going on there — please get that looked at before we push the load. I've pulled back this week's targets in the meantime."

The boundary never feels like a wall. An athlete asking about sleep should leave feeling like they spoke to someone who knew exactly what they could and couldn't help with.
