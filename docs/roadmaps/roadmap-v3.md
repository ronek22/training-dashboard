# Training Dashboard Roadmap V3

## Purpose

This roadmap is the active product and engineering plan for the next stage of the dashboard.

It keeps the same product stance:

- prioritize features that materially improve coaching usefulness and training decisions
- keep behavior deterministic, inspectable, and grounded in stored app data
- prefer small reusable product systems over broad speculative automation

## Current State

The app already supports:

- structured athlete profile, goals, and modality restrictions
- weekly planning, plan approval, and plan-vs-actual review
- deterministic weekly coaching and roadmap visibility in-app
- activity detail with cached Strava detail, heart-rate zone review, and AI workout analysis
- Fitbod-enriched strength history, trends, and MCP exposure
- MCP reads and writes for both ChatGPT and Claude

Current implementation status:

- the app is now strong at `plan -> execute -> review`
- richer goals, performance anchors, benchmark views, and workout detail all exist
- single-workout interpretation is now available through an MCP-backed LLM workflow
- the product still feels lighter on readiness, execution quality, and closed-loop progression than on planning visibility

The main gap is that the app can describe training history well, but still does not consistently answer:

- `how ready am I?`
- `did I execute this session the way it was meant to be done?`
- `what matters next if I want this goal to improve?`

## Product Direction

Target outcome:

1. turn recent training data into clear readiness and risk signals
2. judge workout execution quality against intent, not just completion
3. connect goal progress to practical `what matters next` guidance
4. make hybrid endurance and strength progression more closed-loop
5. improve trust through better coverage, data hygiene, and explicit uncertainty states

That implies four product pillars for this roadmap generation:

- readiness and recovery context
- intent-aware execution quality
- progression and adaptation loops
- trust, setup, and data hygiene

## Priority Order

## Phase 10: Build Readiness And Execution Intelligence

Goal: move beyond static review so the app can explain whether the athlete is absorbing work well and whether key sessions were executed as intended.

### 30. Readiness and fatigue foundation

Why:

- the app already tracks recent load, feedback, restrictions, benchmark context, and heart-rate zones, but does not yet convert them into one compact readiness layer
- users need a conservative answer to `push, maintain, or back off?`
- later adaptation and goal-readiness features need one shared readiness contract instead of ad hoc heuristics

Scope:

- add deterministic readiness inputs such as recent load balance, hard-session density, feedback burden, and recovery friction
- expose compact readiness states like `ready`, `watch`, `strained`, or `insufficient data`
- surface clear limitations when inputs are missing or mixed across modalities

Implementation notes:

- likely centered in `backend/app/services/dashboard.py`, `backend/app/services/coaching.py`, and `backend/app/services/activities.py`
- keep the first version rule-based and conservative
- avoid pretending to provide physiological precision from incomplete data

Recommended Sprint 30 role:

- first readiness foundation sprint

### 31. Goal readiness and `what matters next`

Why:

- progress alone is not enough for event and benchmark goals
- athletes need explicit guidance about whether their current training pattern supports their target
- readiness signals become more useful when translated into goal-specific next steps

Scope:

- add goal-family-specific readiness states and gap summaries
- support examples like:
  - event goal underprepared because long-session or specificity work is missing
  - benchmark goal stale because recent test evidence is weak
  - process goal at risk because recent execution is inconsistent
- expose a compact `what matters next` summary per goal

Implementation notes:

- likely centered in `backend/app/services/goals.py` with shared signals from readiness and planning services
- reuse existing planning-guidance fields where possible
- keep explanations short and deterministic

Recommended Sprint 31 role:

- second readiness sprint that turns generic signals into goal-specific guidance

### 32. Planned-vs-actual workout quality

Why:

- a session can be completed but still miss its intended effect
- the app already stores workout intent, explicit links, and some zone-aware context, so the next step is judging execution quality conservatively
- coaching quality improves when it knows whether easy work stayed easy or key work drifted off target

Scope:

- score session execution against planned intent where enough evidence exists
- support first-pass cases such as:
  - easy session drifted too hard
  - quality session lacked enough work in the intended intensity band
  - long aerobic work accumulated less zone-2 time than intended
  - strength session completed but with weaker-than-usual lift output or reduced prescription coverage
- expose matched, partial, and unavailable states clearly

Implementation notes:

- likely spans `backend/app/services/activities.py`, `backend/app/services/plans.py`, and `backend/app/services/strength.py`
- start with a narrow rule set tied to explicit intent types
- do not invent quality judgments when the plan intent or activity detail is too weak

Recommended Sprint 32 role:

- execution-quality sprint built on plan linkage, intent, and activity detail

## Phase 11: Close The Adaptation And Progression Loop

Goal: use readiness and execution-quality context to improve weekly decisions and progression logic without introducing opaque automation.

### 33. Closed-loop weekly adaptation

Why:

- weekly coaching already proposes adjustments, but it still reasons more about completion and broad pressure than about readiness and session quality
- once readiness and execution-quality data exist, the app should make more realistic tradeoffs
- the user should understand the cost of dropping, moving, or protecting a session

Scope:

- improve coaching and plan-adjustment previews using readiness, goal gaps, and recent workout-quality evidence
- explain which sessions are being protected, reduced, postponed, or replaced and why
- show the likely effect of a change on specific goals or readiness pressure

Implementation notes:

- likely centered in `backend/app/services/coaching.py` and `backend/app/services/plans.py`
- keep all plan changes approval-based
- emphasize recommendation quality and explanation quality over autonomy

Recommended Sprint 33 role:

- adaptation sprint that closes the loop from review to next-week decisions

### 34. Strength progression and stall detection

Why:

- strength history is visible, but progression guidance is still shallow
- hybrid athletes need the same `what matters next` clarity for lifting that endurance goals already receive
- the app should recognize when a lift is progressing, stalling, or being under-dosed because of broader weekly tradeoffs

Scope:

- add deterministic progression reads for key lifts and template-backed sessions
- support signals such as recent best load trend, repeat exposure count, stall risk, and suggested next action like `advance`, `repeat`, or `deload`
- connect progression state back to template rotation where relevant

Implementation notes:

- likely centered in `backend/app/services/strength.py`, `backend/app/services/activities.py`, and strength-facing frontend surfaces
- keep exercise grouping conservative and explicit
- avoid estimated 1RM-heavy modeling in the first slice

Recommended Sprint 34 role:

- progression sprint for the strength side of the product

## Phase 12: Improve Trust, Review Loops, And Setup Quality

Goal: make the system easier to trust and easier to keep complete as product logic becomes more specialized.

### 35. Weekly and block retrospectives plus data-quality inbox

Why:

- Sprint 29 solved single-workout interpretation, but the product still lacks a compact weekly or 4-week retrospective
- users also need a practical way to clean up missing feedback, unmatched links, stale benchmarks, and missing detail
- trust improves when the app is explicit about what is missing and what should be reviewed next

Scope:

- add retrospective summaries for the last week and recent block
- surface themes such as load pattern, intensity distribution, adherence, strength continuity, and notable wins or misses
- add a compact data-quality or review inbox for items like:
  - missing workout feedback
  - unmatched planned sessions
  - missing heart-rate streams
  - stale benchmark evidence
  - incomplete strength linkage

Implementation notes:

- likely spans `backend/app/services/dashboard.py`, `backend/app/services/activities.py`, `backend/app/services/mcp.py`, and `frontend/src/views/Dashboard.vue`
- keep the first retrospective compact and evidence-based
- the inbox should prioritize trust-building cleanup, not generic notifications

Recommended Sprint 35 role:

- review-loop and trust sprint that packages recent progress into a practical weekly workflow

## Cross-Cutting Engineering Track

Goal: keep product logic evolvable as readiness, goal-readiness, and progression rules become more specialized.

### 36. Deeper coverage for readiness, execution quality, and progression contracts

Why:

- the product is moving into denser rule systems with more branching than simple CRUD or summary views
- smoke tests alone will not be enough once readiness and session-quality rules begin driving coaching and progression reads

Scope:

- add targeted service-level coverage for readiness, goal-readiness, execution quality, adaptation tradeoffs, and strength progression
- lock down structured API and MCP contracts that the frontend and chat clients depend on
- prioritize edge cases around missing data, mixed-modality weeks, and partial evidence

Implementation notes:

- likely starts in `backend/tests/test_app_smoke.py` and should expand into more focused service-level tests where helpful

## Suggested Build Sequence

This is the recommended implementation order:

1. Readiness and fatigue foundation
2. Goal readiness and `what matters next`
3. Planned-vs-actual workout quality
4. Closed-loop weekly adaptation
5. Strength progression and stall detection
6. Weekly and block retrospectives plus data-quality inbox

## Recommended Next Sprint

If only one sprint is available, do this:

### Sprint Goal

Start with Sprint 30 readiness and fatigue foundation.

### Scope

- establish one conservative readiness contract built from recent load, workout density, and recovery signals
- expose readiness in dashboard, coaching, and MCP reads
- keep the first version inspectable enough that later goal and adaptation logic can safely depend on it

Current interpretation:

- the next highest-value gap is not another new analysis surface, but a reusable readiness layer
- once readiness exists, both goal guidance and weekly adaptation can become materially better without guessing
- this is the cleanest way to make the app feel more like a real coaching system rather than only a planning and review tool

### Definition of done

- the app can expose a compact readiness summary with explicit supporting factors and limitations
- dashboard and coaching surfaces can reference readiness without falling back to vague prose
- missing or weak data produces calm unavailable states instead of false precision

## Risks And Constraints

- do not present readiness as medical or biometric truth
- avoid broad quality scores that hide the real reasons behind them
- keep execution-quality rules tied to explicit workout intent and available evidence
- preserve approval-based plan edits even as coaching becomes more context-aware
- avoid building a heavyweight sports-science engine before the product proves which signals matter most

## Out Of Scope For Now

These ideas are reasonable but should wait:

- live wearable streaming or real-time coaching
- automatic threshold detection as the default source of truth
- generalized AI coaching chat that bypasses deterministic app context
- social features, leaderboards, or public sharing
- aggressive predictive injury modeling

## Working Principle

When choosing between features, prefer the one that:

1. improves the quality of the next training decision
2. makes uncertainty or missing evidence more explicit
3. reuses structured context across dashboard, coaching, frontend, and MCP
4. strengthens trust without over-automating the product
