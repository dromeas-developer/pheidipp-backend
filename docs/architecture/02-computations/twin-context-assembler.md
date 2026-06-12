# Twin Context Assembler

**Domain:** Translation Layer (Twin → Coaching)  
**Purpose:** Translates raw `TwinState` physiological data into coaching-ready language and targets, calibrated to confidence level and data tier.

## Purpose

The `TwinContextAssemblerService` sits at the boundary between the **Twin Layer** (physiological truth) and the **Coaching Layer** (athlete-facing communication). It is responsible for:

1.  **Confidence-Aware Translation:** Converting numerical threshold estimates into language that reflects certainty (effort descriptions vs. ranges vs. point estimates).
2.  **Data Tier Filtering:** Selecting the appropriate target modality (Power, GAP, or Effort) based on available sensor data.
3.  **Readiness Synthesis:** Combining form scores and wellness modifiers into a single `form_descriptor`, `readiness_level`, and `recovery_modifier_reason`.
4.  **Intent Range Computation:** Deriving target ranges from uncertainty values for intermediate consumers (e.g., Workout Generation).

**Why This Exists:**  
Raw physiological data (e.g., "LT2 = 172 bpm, uncertainty = 8.0") is useless to an athlete and dangerous if misinterpreted by an agent. This service ensures the twin's "voice" is consistent, honest about uncertainty, and actionable.

## Input Contract

```typescript
type TwinContextAssemblerInput = {
  twin_state: TwinState
  recovery_modifier?: RecoveryModifier  // Optional: if available, overrides twin_state.readiness_level
}

// TwinState provides:
// - fitness, fatigue, form (scores)
// - lt1_hr, lt2_hr, lt1_pace, lt2_pace, lt1_power, lt2_power, cp (estimates)
// - metric_confidence (per-metric confidence levels)
// - confidence_level (coarse global signal)
// - data_tier (1-6)
```

## Output Contract

**Note:** This schema matches the existing `TwinContextSummary` defined in `01-entities/twin-state.md` to ensure compatibility with `ContextBudgetService` and agents.

```typescript
type TwinContextSummary = {
  // Readiness
  form_descriptor: string            // Plain language form summary
  readiness_level: RecoveryModifierLevel  // GREEN | AMBER | RED
  recovery_modifier_reason: string | null // Plain language explanation (e.g., "Sleep 1.5h below baseline")

  // Threshold Targets (Language)
  threshold_target_description: string  // Plain language summary (may combine HR + Pace)

  // Threshold Targets (Numerical, Confidence-Calibrated)
  // Each field is null if the specific metric's confidence is LOW
  lt2_pace_sec_per_km: number | null   // Point estimate (if HIGH) or mid-range (if MEDIUM)
  lt2_power_watts: number | null
  cp_watts: number | null              // Critical Power
  
  // Note: lt1_hr_bpm is typically not surfaced directly; lt2 is the primary anchor

  // Intent Ranges (For Workout Generation)
  // Structured as an object for explicit access by metric
  intent_ranges: {
    lt1: IntentRange | null
    lt2: IntentRange | null
    cp: IntentRange | null
  }

  // Modality Selection
  data_tier: DataTier
  target_type: 'power' | 'gap' | 'effort_description'  // Primary modality for this athlete
  metric_confidence: TwinMetricConfidence  // Passed through for granular consumers
  confidence_level: TwinConfidenceLevel    // Passed through for coarse consumers
}

type IntentRange = {
  signal_type: 'power' | 'gap' | 'hr'
  min: number | null
  max: number | null
  unit: string
  uncertainty: number  // Raw uncertainty value driving the range width
}
```

## Assembly Algorithm

The assembly process is deterministic and follows this sequence:

### 1. Readiness Synthesis
```python
def synthesize_readiness(twin_state, recovery_modifier=None):
    if recovery_modifier:
        level = recovery_modifier.level
        reason = recovery_modifier.reason  # e.g., "Sleep debt", "HRV suppression"
    else:
        level = twin_state.readiness_level
        reason = None
    
    descriptor = form_to_descriptor(twin_state.form)
    
    return {
        'form_descriptor': descriptor,
        'readiness_level': level,
        'recovery_modifier_reason': reason
    }
```
*Source:* `form_to_descriptor` logic imported from `02-computations/banister-update.md`.

### 2. Confidence-to-Language Mapping (Multi-Signal)
Converts numerical thresholds into confidence-appropriate language. **Composes HR + Pace** when both are available and ≥ MEDIUM confidence.

| Confidence Level | Language Pattern | Example |
|---|---|---|
| **LOW** | Effort descriptions only. No numbers. | "Comfortably hard effort" |
| **MEDIUM** | Ranges with uncertainty context. | "5:30–5:50/km at threshold, roughly 165–170 bpm" |
| **HIGH** | Point estimates. Precise numbers. | "5:38/km at threshold, 168 bpm" |

```python
def compose_threshold_description(twin_state):
    lt2_pace = twin_state.lt2_pace
    lt2_hr = twin_state.lt2_hr
    pace_conf = twin_state.metric_confidence.lt2_pace
    hr_conf = twin_state.metric_confidence.lt2_hr
    
    pace_str = None
    hr_str = None
    
    # Format Pace
    if pace_conf != 'LOW' and lt2_pace:
        if pace_conf == 'HIGH':
            pace_str = f"{lt2_pace.mean} sec/km"
        else:  # MEDIUM
            width = compute_range_width(lt2_pace.uncertainty, 'gap')
            pace_str = f"{lt2_pace.mean - width}–{lt2_pace.mean + width} sec/km"
    
    # Format HR
    if hr_conf != 'LOW' and lt2_hr:
        if hr_conf == 'HIGH':
            hr_str = f"{lt2_hr.mean} bpm"
        else:  # MEDIUM
            width = compute_range_width(lt2_hr.uncertainty, 'hr')
            hr_str = f"{lt2_hr.mean - width}–{lt2_hr.mean + width} bpm"
    
    # Compose
    if pace_str and hr_str:
        return f"{pace_str} at threshold, roughly {hr_str}"
    elif pace_str:
        return f"{pace_str} at threshold"
    elif hr_str:
        return f"{hr_str} at threshold"
    else:
        return "threshold effort"  # LOW confidence fallback
```

### 3. Intent Range Computation
Computes numerical ranges for workout targets based on uncertainty.

```python
def compute_intent_range(parameter_mean, uncertainty, signal_type, confidence):
    if confidence == 'LOW':
        return None  # No numerical range at low confidence
    
    # Range width scales with uncertainty
    # Formula: ± (uncertainty * scaling_factor)
    # scaling_factor is tuned per signal type (HR narrower than Pace)
    # NOTE: Values below are provisional placeholders pending data science validation.
    scaling_factors = {
        'hr': 1.0,    # ±1 bpm per unit uncertainty
        'gap': 1.5,   # ±1.5 sec/km per unit uncertainty
        'power': 2.0  # ±2 watts per unit uncertainty
    }
    
    width = uncertainty * scaling_factors.get(signal_type, 1.0)
    
    return IntentRange(
        signal_type=signal_type,
        min=parameter_mean - width,
        max=parameter_mean + width,
        unit='bpm' if signal_type == 'hr' else ('sec/km' if signal_type == 'gap' else 'watts'),
        uncertainty=uncertainty
    )
```

**Scaling Factors Status:**  
*These values are architectural placeholders. They must be calibrated against:
1.  Bayesian posterior uncertainty distributions from `threshold-detection.md`.
2.  Real-world execution variance data.
3.  Athlete perception of "tight" vs "loose" targets.*

### 4. Data Tier → Target Type Mapping
Selects the primary target modality based on available sensors.

| Data Tier | Primary Target | Secondary Target | Rationale |
|---|---|---|---|
| **1** (Power + HR + Pulse Ox) | Power | GAP | Power is most reliable |
| **2** (Power + HR) | Power | GAP | Power preferred |
| **3** (HR + Pulse Ox) | GAP | HR | No power; GAP from HR |
| **4** (HR Only) | GAP | HR | GAP estimated from HR |
| **5** (Pace Only) | Effort Description | None | No physiological signal |
| **6** (None) | Effort Description | None | Effort only |

```python
def select_target_type(data_tier):
    mapping = {
        1: 'power', 2: 'power',
        3: 'gap', 4: 'gap',
        5: 'effort_description', 6: 'effort_description'
    }
    return mapping[data_tier]
```

### 5. Assembly
```python
def assemble(twin_state, recovery_modifier=None) -> TwinContextSummary:
    # 1. Readiness
    readiness = synthesize_readiness(twin_state, recovery_modifier)
    
    # 2. Threshold Language (Multi-signal)
    threshold_desc = compose_threshold_description(twin_state)
    
    # 3. Intent Ranges (Per-metric confidence gating)
    intent_ranges = {
        'lt1': compute_intent_range(
            twin_state.lt1_hr.mean, 
            twin_state.lt1_hr.uncertainty, 
            'hr',
            twin_state.metric_confidence.lt1_hr
        ),
        'lt2': compute_intent_range(
            twin_state.lt2_pace.mean if twin_state.metric_confidence.lt2_pace != 'LOW' else None,
            twin_state.lt2_pace.uncertainty,
            'gap',
            twin_state.metric_confidence.lt2_pace
        ) if twin_state.metric_confidence.lt2_pace != 'LOW' else None,
        'cp': compute_intent_range(
            twin_state.cp.mean,
            twin_state.cp.uncertainty,
            'power',
            twin_state.metric_confidence.cp
        ) if twin_state.metric_confidence.cp != 'LOW' else None
    }
    
    # 4. Target Type
    target_type = select_target_type(twin_state.data_tier)
    
    # 5. Numerical Targets (Gated by per-metric confidence)
    lt2_pace_val = twin_state.lt2_pace.mean if twin_state.metric_confidence.lt2_pace != 'LOW' else None
    lt2_power_val = twin_state.lt2_power.mean if twin_state.metric_confidence.lt2_power != 'LOW' else None
    cp_val = twin_state.cp.mean if twin_state.metric_confidence.cp != 'LOW' else None
    
    return TwinContextSummary(
        form_descriptor=readiness.form_descriptor,
        readiness_level=readiness.readiness_level,
        recovery_modifier_reason=readiness.recovery_modifier_reason,
        threshold_target_description=threshold_desc,
        lt2_pace_sec_per_km=lt2_pace_val,
        lt2_power_watts=lt2_power_val,
        cp_watts=cp_val,
        intent_ranges=intent_ranges,
        data_tier=twin_state.data_tier,
        target_type=target_type,
        metric_confidence=twin_state.metric_confidence,
        confidence_level=twin_state.confidence_level
    )
```

## Cross-References

-   **TwinState Schema:** `01-entities/twin-state.md` (input structure, output contract match)
-   **Confidence Model:** `00-foundations/confidence-model.md` (confidence level definitions)
-   **Form Descriptor Logic:** `02-computations/banister-update.md` (form → language mapping)
-   **Data Tier Definitions:** `01-entities/data-tiers.md` (tier criteria)
-   **Usage:** `04-platform/context-budget-service.md` (calls `assemble()`), `03-agents/workout-generation-agent.md` (consumes `TwinContextSummary`)
-   **Threshold Detection:** `02-computations/threshold-detection.md` (Bayesian uncertainty source for scaling factors)