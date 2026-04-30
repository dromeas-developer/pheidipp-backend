# Pheidipp Running App - Product Vision

## What Is Pheidipp
Pheidipp is an AI-powered running coach — a backend API, background worker, and web frontend that:
- Ingests FIT files from GPS running watches via direct upload or Garmin/COROS API sync
- Computes training load metrics (CTL, ATL, TSB) from the full activity history
- Maintains a per-athlete physiological model (thresholds, zones, calibration state)
- Maintains a Digital Twin — a living simulation of the athlete's physiology that can forecast fitness, predict race times, and model training block outcomes
- Generates AI-coached training plans and individual workouts via a multi-agent LLM pipeline
- Analyses completed workouts for execution quality and trend detection

## Core Principles
- Running only — all agents refuse off-topic requests. No general-purpose chatbot behaviour
- Privacy first — no raw PII ever reaches an LLM API. All prompts are scrubbed by PromptSanitiser before dispatch
- Science-backed — zone frameworks, threshold models, and calibration methods are grounded in published exercise physiology research (Seiler, Friel, Daniels, Vance, 80/20 Running)
