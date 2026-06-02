# Workout Visualisation
*What Pheidipp shows — and what it deliberately does not*

## The Core Test

Every visualisation in Pheidipp must pass a single test: does this require the twin's context to produce? If it could be shown by Garmin Connect, Strava, or intervals.icu, it does not belong here.

Athletes already have access to raw data charts — HR over time, pace over time, power curves, cadence graphs. Those platforms do this well. Duplicating them inside Pheidipp would produce an inferior version of something the athlete already has, and would pull the product toward the dashboard experience it is deliberately designed to avoid.

Pheidipp does not compete with those platforms on raw data display. Its role is coaching intelligence derived from that data.

## What Pheidipp Shows

**Comparative session overlay.** A simplified shape comparison of this session against the most recent comparable one — same session type, similar phase of training, similar target intensity. Not raw data plotted twice: an abstracted view of execution shape. Did the athlete hold pace better through the back half? Did effort distribute more evenly across reps? Where did the fade begin versus last time?

This requires the twin to identify which previous session is actually comparable — not just any previous threshold session, but one in similar training context and at a similar fitness level. That identification is what makes this view impossible for Garmin to show.

**Session shape classification.** Rather than an HR or pace chart, a single visual summarising how the session unfolded: even execution, progressive fade, positive split, W-shape blowup, strong finish. The same pattern the coach describes in words, rendered as a visual shape. Derived from the raw signal but not the raw signal itself.

**Zone compliance in context.** Not a time-in-zone pie chart — that exists in Garmin already. Instead: a simple view of whether the athlete landed where they were meant to for this specific session intent. A threshold session where 40% of time was spent in Zone 2 tells a different story to an easy aerobic run with the same distribution. The context that makes the number meaningful comes from the twin's understanding of what the session was for.

**Fitness and fatigue trend with session marked.** The rolling twin state over the last six to eight weeks — a single line representing the athlete's form arc — with today's session placed on it. Shows the athlete where this session sits in the block: early build, mid-block accumulation, pre-race sharpening. This perspective requires weeks of data and is invisible in any single-session view.

## The Principle

Raw data belongs in the athlete's existing tools. Pheidipp shows only what requires coaching intelligence to produce — comparisons that need the twin to identify what is actually comparable, abstractions that need the twin to know what the session was for, trends that need the twin's longitudinal model to be meaningful.

If it could be a screenshot from Strava, it should not exist in Pheidipp.