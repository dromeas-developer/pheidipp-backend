# Integrations  
*How Pheidipp connects to the athlete's existing training ecosystem*

## Core Philosophy: Raw Data Only

Pheidipp ingests raw sensor data exclusively — never processed metrics from third-party platforms. Training stress scores, heart rate zones, pace calculations, and other derived metrics vary significantly between platforms due to different algorithms and assumptions. Accepting these processed outputs would silently corrupt the Digital Twin's internal consistency.

By processing all data through Pheidipp's own pipeline, every comparison — session to session, week to week — uses identical definitions and calculations. This isn't a technical preference; it's fundamental to model trustworthiness.

## Integration Tiers

### Tier 1: Native Platform APIs  
**Direct connections to device manufacturers** (Garmin Connect, COROS, Polar, Suunto) enable automated sync while preserving access to raw sensor streams. These integrations balance user convenience with data integrity, though each platform presents unique challenges in data completeness and API reliability. All must provide sufficient raw signal data to meet Pheidipp's processing requirements.

### Tier 2: Aggregator Platforms  
**Training data aggregators** (intervals.icu, with potential future support for others) serve athletes who already consolidate their training history across multiple devices. intervals.icu is prioritized because it maintains raw FIT files and attracts serious athletes who value data integrity. These platforms act as bridges rather than data processors — Pheidipp still performs all metric calculations internally.

### Tier 3: Direct File Ingestion
**Manual FIT file upload** provides immediate onboarding for any athlete regardless of their current ecosystem. This represents the highest data fidelity path — pure raw sensor streams without intermediary processing or API transformations. While requiring manual effort, it establishes the baseline standard for what constitutes complete training data.

## Wellness Data Integration

**Recovery context providers** (Garmin, Whoop, Oura, Polar) feed sleep, HRV, and resting heart rate data to the External Modifiers layer. Unlike training integrations, these don't calibrate the core twin but provide essential recovery context. Single-night anomalies are ignored in favor of trend-based analysis, and data quality thresholds ensure only meaningful signals influence coaching decisions.

## What Pheidipp Does Not Replace

Pheidipp doesn't compete with existing data browsing tools. Athletes continue using Garmin Connect, Strava, or intervals.icu for raw data inspection — pace charts, HR curves, lap analysis. These platforms excel at data display.

Pheidipp's role is coaching intelligence derived from that data, not raw data visualization. Integrations exist solely to bring data in, not to become another dashboard.