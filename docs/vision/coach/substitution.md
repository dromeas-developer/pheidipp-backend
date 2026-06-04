# Session Substitution, Injury & Illness Handling
*What happens when the plan meets reality*

## Workout Substitution Flow

**Initiation.** The athlete signals via a button — "I don't feel like this today" — or free text. The button lowers the activation energy required: the athlete does not need to articulate anything, just signal intent. This matters because a fatigued athlete who has to explain themselves before getting help is more likely to simply skip.

**Short conversation.** A brief branching conversation — three to four exchanges — to understand the constraint: fatigue, time pressure, motivation, injury concern. This determines what type of substitution is appropriate. The conversation is not a form — it is the coach asking sensible questions a real coach would ask.

**Resolution.** Once the constraint is understood, the system draws from the pre-built workout library rather than generating a new workout from scratch. The alternative session preserves the training intent where possible — if the athlete can still run but needs shorter duration, the substitution maintains the physiological purpose. If the constraint is injury-related, the substitution may shift to cross-training.

**Post-hoc detection.** If the athlete uploads session data that does not match the planned session structure, the system detects the mismatch and opens a conversation after the fact to understand what happened. Athletes do not need to declare upfront — the system catches it afterward.

> **Architecture:** `SkipConversationAgent` classifies the skip reason and routes to `SkipFlow`. Resolution phase queries `WorkoutLibraryEntry` via `WorkoutLibraryService.find_substitutes()`. Post-hoc detection is a separate service not owned by the skip agent.

## Rest Days

If an athlete requests a rest day, the system asks whether there is availability elsewhere in the week to redistribute the load. If yes, the plan adjusts and the session moves. If no, the rest day is logged and future load is recalculated accordingly. The framing is always about making the week work, never about a missed session. Missing a session is a normal part of training; treating it as failure achieves nothing.

> **Architecture:** `SkipConversationAgent` classifies as `fatigue` or `external_constraint` → routes to `no_redistribution` (no availability) or `offer_redistribution` (find window). Redistribution logic lives in `SessionLifecycleService`.

## Workout Library

Substitutions draw from a library of curated sessions. The library is not a marketplace — athletes do not contribute to it, cannot browse it, and have no visibility into it. It is a coaching resource, not a feature. Sessions that work well as substitutes in specific contexts surface more frequently over time as the system learns from outcomes.

> **Architecture:** `WorkoutLibraryEntry` entity. Queried by `WorkoutLibraryService.find_substitutes()` when `SkipFlow` is `offer_redistribution`. Acceptance learning maps to `acceptance_rate` sorting. Promotion from `GeneratedWorkout` runs nightly.

## Illness Flow

The coach asks how the athlete is feeling and roughly how long they expect to be affected. Short illness — one to three days — results in the plan holding and easy sessions being replaced with rest. Longer illness triggers plan restructuring designed to bring the athlete back smoothly: very easy aerobic work before any reintroduction of structure.

The return-to-training ramp is conservative. The twin treats the illness period as forced detraining, adjusting fitness and fatigue estimates accordingly before the first session back so that targets are appropriate for the athlete's actual current state.

> **Architecture:** `SkipConversationAgent` classifies as `illness` → routes to `illness_handling`. `PlanGenerationService.regenerate()` restructures the plan. Conservative return ramp enforced by post-regeneration session type constraints (`easy_aerobic`, `recovery_run` for first 3 sessions back).

## Injury Flow

More complex, because type and severity vary enormously. The coach asks enough to understand the nature of the issue: where it is, how long it has been present, and critically whether the athlete can cross-train or needs complete rest. A calf strain has very different implications to a knee niggle.

The system is not a medical tool and never frames it that way. The coach asks the questions a sensible human coach would ask. Based on the responses the plan restructures around what the athlete can do. Cross-training alternatives are suggested where appropriate to maintain aerobic fitness during the injury window.

Return to running is gradual, with the twin watching execution quality closely in the first sessions back for signs that the issue persists. Neither illness nor injury flow ever feels clinical or alarming. The coach tone is calm, practical, and focused on making the best of the situation.

> **Architecture:** `SkipConversationAgent` classifies as `injury_concern` → routes to `injury_escalation`. `PlanGenerationService.regenerate()` restructures with `{ injury_flag }`. Cross-training alternatives are non-running session prescriptions owned by a separate layer.

## Unsynced Workout Handling

When an expected workout has not appeared in the system, the coach surfaces a simple check-in: "I haven't seen your session from yesterday yet — did you get it done?" rather than making assumptions. The athlete responds with one tap.

If yes: sync or upload is prompted. Plan continues normally.
If no: the standard skip flow handles it — reschedule or let the plan adjust.
If no response: the system holds its judgement and asks again at the next app open.

When the athlete's actual data arrives, any estimates are replaced by real values throughout the model. The full post-workout analysis triggers retroactively.

> **Architecture:** Not owned by `SkipConversationAgent`. This is a distinct check-in flow triggered by missing expected data. The "if no" branch feeds into the standard skip classification pipeline. Ownership of the detection and check-in layer should be identified in the architecture.

---

## Non-Running Session Suggestions

The coach can prescribe non-running work when it serves the athlete's running goals: strength and conditioning, yoga and mobility, cross-training during injury recovery. These appear in the weekly plan as secondary sessions with type and duration only — no detailed workout targets are generated.

The athlete sees these suggestions alongside their primary running sessions. They know which sessions are primary (full workout generated) and which are secondary (suggestions). The athlete decides whether to complete the secondary sessions based on their schedule and energy.

This boundary is intentional: the coaching system owns running workout design. Non-running work is prescribed at the level of type and duration, leaving execution details to the athlete or their strength coach.

> **Architecture:** Not owned by `SkipConversationAgent` or `WorkoutLibraryEntry`. Prescription of non-running sessions is a plan generation concern — the system adds secondary session entries with type and duration only. Ownership of this prescription layer should be identified in the architecture.