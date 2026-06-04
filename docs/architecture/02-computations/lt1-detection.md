# LT1 Detection

LT1 detection is harder than LT2 detection because LT1 is a subtle physiological transition. The system uses a multi-method approach: passive inference from natural training plus optional active tests.

## Detection Methods

### 1. MAF Test (Constant Intensity Validation)

**Protocol**: Run at constant intensity at MAF HR (180 - age) for 20-30 minutes. Measure pace.

**Purpose**: Validate LT1 HR estimate. If the athlete can maintain MAF HR with consistent pace, the LT1 estimate is likely accurate.

**Requirements**:
- HR data (Tier 1-4)
- 20+ minutes at steady MAF HR
- Consistent pace (±5% variation)

**Output**: `training_hr_deflection` observation with weight 1.0

**Note**: This is NOT a progressive intensity test. It is a constant intensity validation. The MAF Test is named after Phil Maffetone's method, not because it detects LT1 directly.

### 2. Controlled Progression Test (Progressive Inflection Detection)

**Protocol**: Progressive intensity steps (e.g., 5 min at each: 120, 130, 140, 150, 160 bpm). Detect HR deflection and RR inflection points.

**Purpose**: Direct LT1 and LT2 detection from structured intensity variation.

**Requirements**:
- HR data (Tier 1-4)
- RR intervals for RR inflection (Tier 1-3)
- ≥3 distinct intensity steps
- ≥8 minutes at each intensity level

**Output**:
- `training_hr_deflection` observation (weight 1.0)
- `training_rr_inflection` observation (weight 2.5) if RR data available

**Note**: This is the most reliable field test for LT1 detection. The progressive intensity profile provides clear inflection points.

### 3. Natural Training Analysis (Passive Inference)

**Protocol**: Analyse easy runs for HR ceiling patterns. If the athlete consistently runs easy at a specific HR ceiling, that ceiling likely approximates LT1.

**Purpose**: Build LT1 confidence passively from the 80% of training that occurs around aerobic intensity.

**Requirements**:
- HR data (Tier 1-4)
- ≥3 easy runs with consistent HR patterns
- Easy runs should be truly easy (below LT1)

**Output**: `training_hr_deflection` observation with weight 0.5 (lower confidence than active tests)

**Algorithm**:
1. Identify easy runs (session_type = 'easy_run' or 'recovery_run')
2. Compute mean HR for each easy run
3. If mean HR is consistent (±5 bpm across 3+ runs), use that HR as LT1 estimate
4. The consistency itself is evidence of a physiological threshold

### 4. HR Drift (Stability in Steady-State)

**Protocol**: During steady-state running at constant intensity, measure HR drift over time. Significant HR drift (>5 bpm over 30 minutes) suggests the intensity is above LT1.

**Purpose**: Detect whether a given intensity is above or below LT1.

**Requirements**:
- HR data (Tier 1-4)
- Steady-state running (≥20 minutes at constant intensity)
- Consistent pace (±5% variation)

**Output**: `training_hr_deflection` observation with weight 1.0

**Algorithm**:
1. Identify steady-state segments (constant pace, constant grade)
2. Compute HR at start (first 5 min) and end (last 5 min) of segment
3. If HR drift > 5 bpm, intensity is likely above LT1
4. If HR drift < 2 bpm, intensity is likely below LT1

### 5. HR Recovery (Recovery Speed After Stopping)

**Protocol**: After hard effort, measure HR recovery speed. Faster recovery suggests lower LT1 (better aerobic fitness). Slower recovery suggests higher LT1.

**Purpose**: Supplementary LT1 evidence from recovery kinetics.

**Requirements**:
- HR data (Tier 1-4)
- Hard effort (above LT2) followed by easy running or walking
- ≥2 minutes of recovery data

**Output**: `training_hr_deflection` observation with weight 0.5 (supplementary evidence)

**Algorithm**:
1. Identify hard efforts (above LT2 or near max HR)
2. Compute HR at cessation of hard effort
3. Compute HR at 2 minutes into recovery
4. HR recovery = HR_start - HR_2min
5. Faster recovery (>30 bpm in 2 min) suggests lower LT1
6. Slower recovery (<20 bpm in 2 min) suggests higher LT1

## Evidence Accumulation

LT1 confidence accumulates from multiple methods:

| Method | Weight | Conditions |
|---|---|---|
| MAF Test | 1.0 | 20+ min at MAF HR, consistent pace |
| Controlled Progression | 1.0 (HR) / 2.5 (RR) | ≥3 intensity steps, ≥8 min each |
| Natural Training | 0.5 | ≥3 easy runs with consistent HR |
| HR Drift | 1.0 | ≥20 min steady-state, consistent pace |
| HR Recovery | 0.5 | Hard effort + 2 min recovery |

**Transition thresholds** (same as LT2):
- LOW → MEDIUM: evidence weight ≥ 4.0
- MEDIUM → HIGH: evidence weight ≥ 8.0

## Cross-References

- Confidence model: `00-foundations/confidence-model.md`
- Evidence weights: `02-computations/physiology-update.md`
- Threshold detection: `02-computations/threshold-detection.md`
- Data tiers: `00-foundations/data-tiers.md`
