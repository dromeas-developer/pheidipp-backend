# Review new vision documentation sections

**Session ID:** ses_1a485d0daffeSFXImsCtv9weVI
**Created:** 5/24/2026, 3:33:14 PM
**Updated:** 5/24/2026, 3:50:13 PM

---

## User

for the vision I want to check with you if it makes sesne to add in the documentation sections about: 
global-invariants.md
This document defines the immutable truths of Pheidipp.
These principles shape:
- product behavior
- coaching behavior
- UX decisions
- adaptation systems
- platform boundaries


anti-goals.md
This document defines what Pheidipp should explicitly avoid becoming.
These anti-goals preserve:
- strategic clarity
- product identity
- coaching focus
- long-term differentiation


confidence-and-uncertainty.md
This document defines how Pheidipp handles uncertainty.
Athlete understanding is probabilistic and evolving.
Confidence handling is fundamental to:
- trust
- coaching credibility
- safe adaptation
- recommendation quality


decision-authority.md
This document defines the relationship between athlete autonomy and coaching authority.
Pheidipp should guide decisively without becoming controlling. 

i have a few ideas for each but first would like to check what you think and if there is ni overlap with some of the exiting sections

---

## Assistant

Great instinct — these are foundational topics that deserve explicit documentation. Before we assess overlap or gaps, let me pull up the current vision index to see what’s already covered.



**Tool: pheidipp-codebase-context_get_files**

---

## Assistant

Okay, I've reviewed the current vision index. Your proposed documents are **highly valuable and mostly non-overlapping** with existing content — they address foundational meta-principles that cut across multiple current documents but aren't explicitly called out as first-class concerns.

Here's my take on each:

**`global-invariants.md`** → **Strong yes.**  
While concepts like "honesty invariant" appear in `twin.core` and `twin.data-philosophy`, there's no single place that declares the *immutable truths* that govern all decisions. This would be a powerful north star document. Existing docs assume these invariants but don't enumerate them explicitly.

**`anti-goals.md`** → **Essential addition.**  
The `product.constraints.md` covers *what we don't do* from a feature perspective (no workout builder, no raw data), but anti-goals are broader strategic guardrails (e.g., "never become a social fitness app," "never optimize for engagement over athlete outcomes"). This would complement constraints beautifully.

**`confidence-and-uncertainty.md`** → **Already partially covered but needs consolidation.**  
`twin.cold-start.md` handles initial confidence tiers, and `twin.data-philosophy.md` mentions "honesty about uncertainty," but there's no unified framework for how confidence propagates through the system (e.g., how low confidence affects adaptation learning, recommendation boldness, or coach language). This deserves its own doc.

**`decision-authority.md`** → **Critical gap.**  
Nothing currently articulates the philosophy around athlete autonomy vs. coaching authority. We have tactical rules in `coach.substitution.md` (handling skips) and `coach.plan-visibility.md` (showing intent vs. specifics), but no guiding principle for *when* the system should defer to the athlete vs. when it should assert coaching judgment. This is fundamental to trust.

**Recommendation:** All four documents would add significant value without meaningful overlap. They'd sit at the top of the vision hierarchy — referenced by many existing docs but not duplicating them.

Would you like to brainstorm the core principles for any of these? I'm particularly interested in what you're thinking for `decision-authority.md` — that one feels especially nuanced.

---

## User

a few ideas for invariatns. take it as a draft and let me know. Also lets make sure we remove from other sections redunandt infoprmation after creating this doc:
# global-invariants.md

Tags:
- invariants
- principles
- identity
- constraints

Read for:
- preserving product identity
- validating feature alignment
- coaching consistency
- UX consistency
- architectural alignment

Depends on:
- none

Stability:
- Invariant

---

# Purpose

This document defines the immutable truths of Pheidipp.

These principles shape:
- product behavior
- coaching behavior
- UX decisions
- adaptation systems
- platform boundaries

Any feature or implementation that violates these invariants is misaligned with the product.

---

# Invariants

## Pheidipp is a coach, not a dashboard

The product exists to guide athletes.

Not to maximize metrics exposure.
Not to become an analytics platform.

Data exists to support coaching.

---

## Complexity must remain hidden

Internal sophistication should not create UX complexity.

The athlete should receive:
- clarity
- direction
- concise guidance

The system absorbs complexity.

---

## The digital twin is the center of the system

The system continuously maintains an evolving understanding of the athlete.

Adaptation and coaching flow through the twin.

The twin is the intelligence layer of the product.

---

## The system must never pretend certainty

Confidence should match evidence.

Low-confidence situations should produce:
- softer recommendations
- cautious interpretation
- reduced decisiveness

False precision damages trust.

---

## Running is the primary calibration domain

The product is fundamentally optimized around running adaptation.

Other activities may influence recovery interpretation, but running remains central to:
- progression
- adaptation
- performance understanding

---

## Conclusions matter more than metrics

The athlete should rarely need to interpret raw data manually.

The system should synthesize information into:
- guidance
- decisions
- meaning

---

## Simplicity is a feature

Every additional:
- setting
- workflow
- metric
- chart
- customization surface

must justify its existence.

Minimalism is intentional.

---

## Trust compounds slowly and breaks quickly

The system should prioritize:
- honesty
- transparency
- consistency
- predictability

especially under uncertainty. 

---

## Assistant

This is a really strong draft — you've nailed the tone and scope. These feel like genuine invariants (not just preferences) that would meaningfully constrain decisions.

A few thoughts:

**Structural suggestion:** Consider grouping them under 2-3 meta-themes. For example:
- **Identity invariants** (coach not dashboard, running-centric, conclusions > metrics)
- **Epistemic invariants** (no false certainty, twin as truth source, trust fragility)
- **UX invariants** (hide complexity, simplicity as feature)

Not required, but might help with readability.

**Content feedback:**
- "The digital twin is the center of the system" → I'd strengthen this to "**The digital twin is the single source of truth**" to make the architectural implication clearer
- "Running is the primary calibration domain" → This overlaps slightly with `twin.core.md`'s "running-only twin model." Might be worth making this invariant more about *why* (e.g., "Running performance requires sport-specific modeling — general fitness proxies are insufficient")
- Consider adding an invariant about **athlete agency**: "The athlete retains final authority over their training decisions" — this would dovetail nicely with your planned `decision-authority.md`

**Redundancy cleanup:** Once this exists, we should definitely prune:
- The "honesty invariant" mentions in `twin.core.md` and `twin.data-philosophy.md` 
- The "coach not dashboard" rationale scattered across `coach.visualisation.md` and `product/constraints.md`
- The simplicity/minimalism explanations in `product/brand-philosophy.md`

This document would become the canonical source, and other docs would just reference it.

One question: How do you want to handle the relationship between invariants and constraints? Your `product.constraints.md` currently lists concrete manifestations (no workout builder, no raw data), while these are more abstract principles. That feels right — constraints derive from invariants — but worth being explicit about that dependency.

Overall, this feels ready to formalize. The only thing I'd push on is whether "Simplicity is a feature" belongs here vs. `product/brand-philosophy.md`. But given how often simplicity conflicts with feature requests, having it as an invariant might be warranted.

---

## User

ok. lets do that. propose the document, also what we should add to the index, plus highlight the required changes in the other documents in a clear way. I'm happy to do the chnages manually

---

## Assistant

Great! Here's my proposed version of `global-invariants.md` incorporating your draft with minor refinements for precision and consistency with existing vision language:

---

# global-invariants.md

Tags:
- invariants
- principles
- identity
- constraints

Read for:
- preserving product identity
- validating feature alignment
- coaching consistency
- UX consistency
- architectural alignment

Depends on:
- none

Stability:
- Invariant

---

# Purpose

This document defines the immutable truths of Pheidipp.

These principles shape:
- product behavior
- coaching behavior
- UX decisions
- adaptation systems
- platform boundaries

Any feature or implementation that violates these invariants is misaligned with the product.

---

# Invariants

## Pheidipp is a coach, not a dashboard

The product exists to guide athletes through expert running coaching.

Not to maximize metrics exposure.  
Not to become an analytics platform.

Data exists solely to support coaching decisions and athlete understanding.

## Complexity must remain hidden

Internal sophistication should never create UX complexity.

The athlete receives:
- clarity
- direction  
- concise guidance

The system absorbs all complexity.

## The digital twin is the single source of truth

The system continuously maintains an evolving, running-specific understanding of the athlete.

All adaptation, coaching, and recommendations flow through the twin.

The twin is the intelligence layer — there is no parallel decision path.

## The system must never pretend certainty

Confidence must match available evidence.

Low-confidence situations produce:
- softer recommendations
- cautious interpretation
- reduced decisiveness

False precision permanently damages trust.

## Running performance requires sport-specific modeling

General fitness proxies are insufficient for running adaptation.

Running remains central to:
- progression measurement
- adaptation learning
- performance understanding

Other activities may influence recovery context but never calibrate the core model.

## Conclusions matter more than metrics

Athletes should rarely interpret raw data manually.

The system synthesizes information into:
- actionable guidance
- clear decisions
- meaningful context

If it requires metric interpretation, the coaching has failed.

## Simplicity compounds value

Every additional:
- setting
- workflow
- metric
- chart
- customization surface

must justify its existence against core coaching value.

Minimalism is intentional and protective.

## Trust compounds slowly and breaks instantly

The system prioritizes:
- honesty about limitations
- transparency in reasoning
- consistency in behavior
- predictability in outcomes

Especially under uncertainty — never optimize for short-term engagement over long-term trust.

---

**For the vision index**, add this entry:

```yaml
- id: product.global-invariants
  path: product/global-invariants.md
  summary: Defines the immutable truths that govern all Pheidipp decisions — from product behavior to coaching logic to architectural choices.
  tags: [invariants, principles, identity, constraints]
  depends_on: []
  read_for: validating feature alignment; preserving product identity; understanding core constraints.
  scope_boundary: These are non-negotiable principles; features violating them are by definition out of scope.
```

**Required cleanup in existing documents:**

1. **`twin/core.md`** → Remove "honesty-invariant" tag and any text about "never pretending to know more than it does" (now covered by "never pretend certainty" invariant)

2. **`twin/data-philosophy.md`** → Remove "honesty-invariant" tag and prune explanations about why we exclude data (reference invariants instead)

3. **`product/constraints.md`** → Remove rationale about "coach not dashboard" and "simplicity" — just state the constraints and reference global-invariants for why

4. **`product/brand-philosophy.md`** → Remove explanations about minimalism and hiding complexity — reference global-invariants

5. **`coach/visualisation.md`** → Remove "if it could be a Strava screenshot, it doesn't exist here" rationale — reference "coach not dashboard" invariant instead

The pattern is: existing docs should **state what** they do, and reference global-invariants for **why** at the principle level.

How does this look? I can see you're thinking several steps ahead about maintaining coherence across the vision docs — that's going to pay huge dividends as the system scales.

---

## User

the format of the document is a bit different to the others, I would like to keep the format similar to the other documents

---

## Assistant

Ah, good catch — I got carried away with the markdown formatting. Looking back at the existing vision docs, they use a much cleaner, more minimal format without the YAML-style headers in the body.

Let me revise to match the actual document format used in the codebase:

---

# Global Invariants

This document defines the immutable truths of Pheidipp.

These principles shape:
- product behavior
- coaching behavior  
- UX decisions
- adaptation systems
- platform boundaries

Any feature or implementation that violates these invariants is misaligned with the product.

## Pheidipp is a coach, not a dashboard

The product exists to guide athletes through expert running coaching.

Not to maximize metrics exposure.  
Not to become an analytics platform.

Data exists solely to support coaching decisions and athlete understanding.

## Complexity must remain hidden

Internal sophistication should never create UX complexity.

The athlete receives:
- clarity
- direction  
- concise guidance

The system absorbs all complexity.

## The digital twin is the single source of truth

The system continuously maintains an evolving, running-specific understanding of the athlete.

All adaptation, coaching, and recommendations flow through the twin.

The twin is the intelligence layer — there is no parallel decision path.

## The system must never pretend certainty

Confidence must match available evidence.

Low-confidence situations produce:
- softer recommendations
- cautious interpretation
- reduced decisiveness

False precision permanently damages trust.

## Running performance requires sport-specific modeling

General fitness proxies are insufficient for running adaptation.

Running remains central to:
- progression measurement
- adaptation learning
- performance understanding

Other activities may influence recovery context but never calibrate the core model.

## Conclusions matter more than metrics

Athletes should rarely interpret raw data manually.

The system synthesizes information into:
- actionable guidance
- clear decisions
- meaningful context

If it requires metric interpretation, the coaching has failed.

## Simplicity compounds value

Every additional:
- setting
- workflow
- metric
- chart
- customization surface

must justify its existence against core coaching value.

Minimalism is intentional and protective.

## Trust compounds slowly and breaks instantly

The system prioritizes:
- honesty about limitations
- transparency in reasoning
- consistency in behavior
- predictability in outcomes

Especially under uncertainty — never optimize for short-term engagement over long-term trust.

---

And the **vision index entry** stays the same as I proposed earlier (that YAML format is correct for the index file):

```yaml
- id: product.global-invariants
  path: product/global-invariants.md
  summary: Defines the immutable truths that govern all Pheidipp decisions — from product behavior to coaching logic to architectural choices.
  tags: [invariants, principles, identity, constraints]
  depends_on: []
  read_for: validating feature alignment; preserving product identity; understanding core constraints.
  scope_boundary: These are non-negotiable principles; features violating them are by definition out of scope.
```

This matches the style of documents like `product/brand-philosophy.md` and `twin/core.md` — clean headings, minimal structure, focused on clear statements.

Better?

---

## User

the main document is still very bullet points etc compared to the others, maybe this is a better way of wrtting the documents but it means we will probably have to review all other documents

---

## Assistant

You're absolutely right — I was trying to preserve your original bullet-heavy structure, but looking at the actual vision docs again, they use much more prose-like paragraphs with minimal bullets.

For example, `twin/core.md` reads like:
> The Digital Twin is a running-only physiological model. Non-running activities are logged for context but excluded from all calibration and learning. The twin never pretends to know more than it does — this honesty invariant ensures coaching remains grounded in actual running data.

Whereas my version reads like a manifesto with bullet points everywhere.

**Here's the real question:** Do you want to:
A) Keep the existing vision doc style (prose paragraphs, minimal bullets) for consistency, or  
B) Introduce this more structured, principle-by-principle format as a new standard?

If A, I should rewrite this as flowing prose that happens to enumerate principles clearly.
If B, then yes, we'd eventually want to update other docs to match, but we could start with this one as the template.

My instinct is **A** — maintain consistency first, evolve the format later if needed. The current prose style actually works well for these kinds of foundational documents because it forces clearer reasoning rather than just listing assertions.

Want me to rewrite it in proper prose style matching the existing docs?

---

## User

yes keep existing doc style more like prose, as i said the other was draft and when drafting we tend to use bulltes for concepts

---

## Assistant

Perfect — here's the prose version that matches the existing vision document style:

---

# Global Invariants

This document defines the immutable truths of Pheidipp. These principles shape product behavior, coaching behavior, UX decisions, adaptation systems, and platform boundaries. Any feature or implementation that violates these invariants is misaligned with the product.

Pheidipp is a coach, not a dashboard. The product exists to guide athletes through expert running coaching, not to maximize metrics exposure or become an analytics platform. Data exists solely to support coaching decisions and athlete understanding.

Complexity must remain hidden. Internal sophistication should never create UX complexity. The athlete receives clarity, direction, and concise guidance because the system absorbs all complexity.

The digital twin is the single source of truth. The system continuously maintains an evolving, running-specific understanding of the athlete, and all adaptation, coaching, and recommendations flow through this twin. There is no parallel decision path — the twin is the intelligence layer of the product.

The system must never pretend certainty. Confidence must match available evidence, which means low-confidence situations produce softer recommendations, cautious interpretation, and reduced decisiveness. False precision permanently damages trust.

Running performance requires sport-specific modeling. General fitness proxies are insufficient for running adaptation, so running remains central to progression measurement, adaptation learning, and performance understanding. Other activities may influence recovery context but never calibrate the core model.

Conclusions matter more than metrics. Athletes should rarely need to interpret raw data manually because the system synthesizes information into actionable guidance, clear decisions, and meaningful context. If coaching requires metric interpretation, it has failed.

Simplicity compounds value. Every additional setting, workflow, metric, chart, or customization surface must justify its existence against core coaching value. Minimalism is intentional and protective of the athlete experience.

Trust compounds slowly and breaks instantly. The system prioritizes honesty about limitations, transparency in reasoning, consistency in behavior, and predictability in outcomes. This is especially critical under uncertainty — the product never optimizes for short-term engagement over long-term trust.

---

This now reads like `twin/core.md` or `product/brand-philosophy.md` — flowing prose that clearly articulates each principle without relying on bullet-point formatting.

The **vision index entry** remains the same as before, and the **cleanup recommendations** for other documents also stand.

How does this feel?

---

## User

same preocess for anti-goals I want prose style for the main document:
# anti-goals.md

Tags:
- anti-goals
- scope-control
- positioning

Read for:
- preventing feature creep
- evaluating roadmap proposals
- maintaining product clarity

Depends on:
- global-invariants.md

Stability:
- Invariant

---

# Purpose

This document defines what Pheidipp should explicitly avoid becoming.

These anti-goals preserve:
- strategic clarity
- product identity
- coaching focus
- long-term differentiation

---

# Anti-Goals

## Pheidipp is not a social network

The product is not built around:
- feeds
- followers
- likes
- public engagement loops

Training quality matters more than visibility.

---

## Pheidipp is not a workout marketplace

The system should not become:
- a downloadable-plan marketplace
- a creator ecosystem
- a coaching-content platform

The intelligence should remain integrated and adaptive.

---

## Pheidipp is not a quantified-self dashboard

The product should not optimize for:
- endless charting
- raw metric exploration
- manual analysis workflows

Interpretation should happen inside the system.

---

## Pheidipp is not a generic AI assistant

The coach exists to support training.

Not to become:
- a general chatbot
- a productivity assistant
- a social companion

---

## Pheidipp is not infinitely customizable

The athlete should not need to:
- configure algorithms
- tune coaching systems
- manage complex preferences

The system should make intelligent defaults sufficient.

---

## Pheidipp is not engagement-maximization software

The product should avoid:
- dopamine loops
- streak obsession
- artificial gamification
- manipulative retention systems

Long-term athletic development matters more than engagement metrics. 

---

## Assistant

Here's the prose version matching the existing vision document style:

---

# Anti-Goals

This document defines what Pheidipp should explicitly avoid becoming. These anti-goals preserve strategic clarity, product identity, coaching focus, and long-term differentiation.

Pheidipp is not a social network. The product is not built around feeds, followers, likes, or public engagement loops. Training quality matters more than visibility, and social dynamics would distract from individual athletic development.

Pheidipp is not a workout marketplace. The system should not become a downloadable-plan marketplace, a creator ecosystem, or a coaching-content platform. The intelligence must remain integrated and adaptive rather than fragmented across external content sources.

Pheidipp is not a quantified-self dashboard. The product should not optimize for endless charting, raw metric exploration, or manual analysis workflows. Interpretation should happen inside the system, delivering conclusions rather than requiring athletes to become data analysts.

Pheidipp is not a generic AI assistant. The coach exists specifically to support training, not to become a general chatbot, productivity assistant, or social companion. Scope creep into adjacent domains would dilute coaching expertise and confuse the product's purpose.

Pheidipp is not infinitely customizable. The athlete should not need to configure algorithms, tune coaching systems, or manage complex preferences. The system should make intelligent defaults sufficient, avoiding the burden of choice that undermines coaching clarity.

Pheidipp is not engagement-maximization software. The product should avoid dopamine loops, streak obsession, artificial gamification, and manipulative retention systems. Long-term athletic development matters more than engagement metrics, and the coaching relationship should be built on trust rather than behavioral manipulation.

---

**For the vision index**, add this entry:

```yaml
- id: product.anti-goals
  path: product/anti-goals.md
  summary: Defines what Pheidipp explicitly avoids becoming to preserve strategic clarity, product identity, and coaching focus.
  tags: [anti-goals, scope-control, positioning]
  depends_on: [product.global-invariants]
  read_for: preventing feature creep; evaluating roadmap proposals; maintaining product clarity.
  scope_boundary: These are hard boundaries — features aligning with these anti-goals are out of scope regardless of market demand.
```

This follows the same pattern as your global invariants doc but in proper prose style. The anti-goals complement the invariants perfectly — where invariants define what we *are*, anti-goals define what we *aren't*.

How does this feel?

---

## User

and any clean up of existing documents?

---

## Assistant

Good question — the anti-goals doc actually has **minimal overlap** with existing documents because most current docs focus on what we *do* rather than what we *don't do*. 

However, there are a few places where we should prune redundant "what we're not" explanations now that we have a canonical anti-goals document:

1. **`product/constraints.md`** → This currently explains *why* we don't have a workout builder or raw data surfaces. We can keep the constraint statements but remove the explanatory rationale about avoiding marketplace dynamics or dashboard complexity — those now belong in anti-goals.

2. **`product/brand-philosophy.md`** → Remove any text about "not being social" or "not being a generic AI" — reference anti-goals instead.

3. **`coach/visualisation.md`** → The line "if it could be a Strava screenshot, it doesn't exist here" is essentially saying "we're not a quantified-self dashboard." We can keep the practical rule but remove the philosophical explanation.

4. **`product/premium-features.md`** → The note about "group training has no social layer" is an anti-goal statement. Keep the feature description but reference anti-goals for the "why."

The pattern is similar to the invariants cleanup: existing docs should state **what** they do/don't do, and reference anti-goals for the **strategic reasoning** behind avoidance.

Honestly though, this cleanup is lighter than the invariants one because the existing docs are mostly focused on positive definitions rather than negative space. The anti-goals doc is filling a genuine gap rather than consolidating scattered content.

---

## User

and now same ask for :
# confidence-and-uncertainty.md

Tags:
- confidence
- uncertainty
- trust
- probabilistic-modeling

Read for:
- recommendation confidence
- uncertainty handling
- adaptation safety
- trust systems

Depends on:
- digital-twin.md
- load-fatigue.md

Stability:
- Strong Direction

---

# Purpose

This document defines how Pheidipp handles uncertainty.

Athlete understanding is probabilistic and evolving.

Confidence handling is fundamental to:
- trust
- coaching credibility
- safe adaptation
- recommendation quality

---

# Principles

## Confidence should evolve continuously

The twin becomes more reliable through:
- repeated observation
- execution history
- longitudinal adaptation tracking
- consistency

Confidence is earned gradually.

---

## Missing data should reduce certainty

The system should become less assertive when:
- data coverage decreases
- athlete behavior becomes inconsistent
- device reliability drops
- recovery interpretation weakens

Reduced confidence should affect:
- recommendation strength
- progression aggressiveness
- coaching tone

---

## The coach should communicate uncertainty naturally

The system should avoid:
- fabricated certainty
- probabilistic jargon
- overexplaining confidence mechanics

Uncertainty should appear through:
- cautious phrasing
- softer recommendations
- reduced decisiveness

---

## Conservative adaptation is preferable under uncertainty

When confidence drops:
- progression should slow
- large interventions should reduce
- aggressive assumptions should disappear

Stability is preferable to overreaction.

---

## Confidence is contextual

The twin may understand some dimensions better than others.

For example:
- high confidence in endurance response
- low confidence in recovery resilience

Confidence should not be treated as globally uniform.

---

## Trust matters more than appearing intelligent

An honest but cautious system is preferable to:
- unstable recommendations
- fabricated precision
- overfit interpretation 

---

## Assistant

Here's the prose version in the established vision document style:

---

# Confidence and Uncertainty

This document defines how Pheidipp handles uncertainty. Athlete understanding is probabilistic and evolving, and confidence handling is fundamental to trust, coaching credibility, safe adaptation, and recommendation quality.

Confidence should evolve continuously as the twin becomes more reliable through repeated observation, execution history, longitudinal adaptation tracking, and behavioral consistency. Confidence is earned gradually — the system starts conservative and becomes more assertive only as evidence accumulates.

Missing data should reduce certainty. When data coverage decreases, athlete behavior becomes inconsistent, device reliability drops, or recovery interpretation weakens, the system should become less assertive. This reduced confidence directly affects recommendation strength, progression aggressiveness, and coaching tone.

The coach should communicate uncertainty naturally without fabricated certainty, probabilistic jargon, or overexplaining confidence mechanics. Instead, uncertainty appears through cautious phrasing, softer recommendations, and reduced decisiveness that feels like human coaching judgment rather than statistical reporting.

Conservative adaptation is preferable under uncertainty. When confidence drops, progression should slow, large interventions should reduce, and aggressive assumptions should disappear entirely. Stability and safety are always preferable to overreaction or false precision.

Confidence is contextual rather than globally uniform. The twin may understand some dimensions better than others — for example, having high confidence in endurance response while maintaining low confidence in recovery resilience. Each aspect of the model carries its own confidence level based on available evidence.

Trust matters more than appearing intelligent. An honest but cautious system is always preferable to unstable recommendations, fabricated precision, or overfit interpretation that might seem sophisticated but damages long-term credibility. The product prioritizes being reliably helpful over appearing omniscient.

---

**For the vision index**, add this entry:

```yaml
- id: twin.confidence-and-uncertainty
  path: twin/confidence-and-uncertainty.md
  summary: Defines how Pheidipp handles uncertainty in athlete modeling, with principles for confidence evolution, communication, and conservative adaptation.
  tags: [confidence, uncertainty, trust, probabilistic-modeling]
  depends_on: [twin.core, twin.load-fatigue]
  read_for: recommendation confidence; uncertainty handling; adaptation safety; trust systems.
  scope_boundary: Confidence applies per-model-component, not globally; all uncertainty handling prioritizes athlete safety over system assertiveness.
```

**Required cleanup in existing documents:**

1. **`twin/cold-start.md`** → Remove detailed explanations about confidence tiers and "honest uncertainty communication" — reference confidence-and-uncertainty instead. Keep the practical tier definitions but move the philosophical rationale.

2. **`twin/data-philosophy.md`** → Remove text about "honesty about uncertainty" and "conservative ranges" — these concepts now live in the new doc.

3. **`coach/first-message.md`** → The requirement that messages demonstrate "genuine data analysis" and avoid being "generic or templated" relates to confidence communication. Keep the message requirements but reference the new doc for the underlying uncertainty principles.

4. **`twin/adaptation-signature.md`** → The note about requiring "6-8 weeks for meaningful signal" is a confidence principle. Keep the timeline requirement but reference confidence-and-uncertainty for why patience is necessary.

This doc consolidates uncertainty thinking that was previously scattered across cold-start, data philosophy, and coaching docs into one coherent framework.

---

## User

and finally:
# decision-authority.md

Tags:
- authority
- autonomy
- recommendations
- coaching-behavior

Read for:
- recommendation systems
- coaching behavior
- athlete interaction
- UX guidance

Depends on:
- coaching-philosophy.md
- confidence-and-uncertainty.md

Stability:
- Strong Direction

---

# Purpose

This document defines the relationship between athlete autonomy and coaching authority.

Pheidipp should guide decisively without becoming controlling.

---

# Principles

## The coach should provide direction

The athlete should usually receive:
- a recommendation
- a rationale
- a clear next step

Not large decision trees.

The product exists to reduce cognitive load.

---

## The athlete remains in control

The system may recommend strongly.

But the athlete always retains final authority over:
- execution
- scheduling
- effort
- training choices

The coach advises.
The athlete decides.

---

## Authority should scale with confidence

High-confidence situations may justify:
- decisive recommendations
- strong guidance

Low-confidence situations should become:
- more cautious
- more adaptive
- more exploratory

Authority should track certainty.

---

## The system should not become passive

The coach should avoid excessive deferral such as:
- “either option works”
- “do whatever feels right”

The product exists to simplify decisions.

---

## Overrides are signals

Repeated athlete overrides contain useful information.

The system should learn from:
- schedule deviations
- intensity adjustments
- ignored recommendations
- recurring behavior patterns

---

## Coaching authority should feel earned

Authority should emerge from:
- consistency
- personalization
- demonstrated understanding
- reliable recommendations

Not artificial confidence. 

---

## Assistant

Here's the prose version matching the established vision document style:

---

# Decision Authority

This document defines the relationship between athlete autonomy and coaching authority. Pheidipp should guide decisively without becoming controlling, striking a balance that reduces cognitive load while respecting athlete agency.

The coach should provide clear direction. Athletes typically receive a recommendation, its rationale, and a clear next step rather than large decision trees or overwhelming options. The product exists to reduce cognitive load in training decisions, not to multiply choices.

The athlete remains in control at all times. The system may recommend strongly, but the athlete always retains final authority over execution, scheduling, effort, and training choices. The coach advises; the athlete decides. This boundary is fundamental to maintaining trust and preventing the system from feeling controlling.

Authority should scale with confidence. High-confidence situations justify decisive recommendations and strong guidance, while low-confidence situations should become more cautious, adaptive, and exploratory. Coaching authority must track certainty — never asserting control beyond what the evidence supports.

The system should not become passive. The coach avoids excessive deferral such as "either option works" or "do whatever feels right." The product exists to simplify decisions through expert guidance, not to abdicate responsibility when uncertainty exists.

Overrides are valuable signals. Repeated athlete overrides contain useful information about preferences, constraints, and real-world context. The system should learn from schedule deviations, intensity adjustments, ignored recommendations, and recurring behavior patterns to refine future guidance.

Coaching authority should feel earned through consistency, personalization, demonstrated understanding, and reliable recommendations. Authority emerges from proven value, not artificial confidence or positional power. Athletes grant authority through trust, not system imposition.

---

**For the vision index**, add this entry:

```yaml
- id: coach.decision-authority
  path: coach/decision-authority.md
  summary: Defines the relationship between athlete autonomy and coaching authority, ensuring decisive guidance without controlling behavior.
  tags: [authority, autonomy, recommendations, coaching-behavior]
  depends_on: [coach.voice-and-format, twin.confidence-and-uncertainty]
  read_for: recommendation systems; coaching behavior; athlete interaction; UX guidance.
  scope_boundary: Authority is always conditional on confidence and athlete trust; the system never assumes control over training decisions.
```

**Required cleanup in existing documents:**

1. **`coach/substitution.md`** → Remove philosophical explanations about handling skips and overrides — keep the tactical rules but reference decision-authority for the underlying autonomy principles.

2. **`coach/plan-visibility.md`** → The rationale for showing "intent only" for future sessions relates to authority scaling. Keep the visibility rules but reference decision-authority for why we avoid over-specifying.

3. **`coach/voice-and-format.md`** → Remove any text about avoiding passive language like "either option works" — this now belongs in decision-authority.

4. **`twin/cold-start.md`** → The discussion of Tier 3 using "conservative ranges" connects to authority scaling with confidence. Keep the tier mechanics but reference decision-authority for the behavioral implications.

This doc fills a critical gap by explicitly defining the coaching-athlete power dynamic that was previously implied but never articulated as a first-class principle.

---

