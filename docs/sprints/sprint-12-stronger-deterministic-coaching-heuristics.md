# Sprint 12: Stronger Deterministic Coaching Heuristics

## Status

Current status:

- planned
- follows planned Sprint 11 multi-week execution analysis work

Starting point:

- one-shot weekly coaching already combines execution, recovery, goals, and next-session guidance
- plan approvals are explicit and inspectable
- multi-week execution context should now be available or at least more visible

Dependency note:

- recommendation quality should improve only after the app can see and explain more history
- heuristic upgrades should build on visible signals, not hidden scoring

## Objective

Improve coaching recommendation quality using richer deterministic signals while preserving transparency.

This sprint should move the app from:

- `the recommendation is reasonable for this week`

to:

- `the recommendation reflects recent patterns and remains easy to explain`

## Why This Sprint

The current coaching action is coherent, but still intentionally lightweight.

That gap matters because:

- repeated execution failures should influence guidance more explicitly
- recommendation trust depends on explainable inputs, not just better outcomes
- stronger heuristics can improve usefulness without requiring autonomous planning
- the app now has enough structure to combine recent history with current recovery and goal signals

## User Story

As a user relying on the weekly coaching read, I want the recommendation to reflect recent execution patterns and adjustment history, so the guidance feels more context-aware without becoming a black box.

## Sprint Scope

### In scope

- sharpen deterministic recommendation rules
- incorporate recent execution and revision patterns more coherently
- improve rationale and risk reporting
- keep recommendation output structured and inspectable

### Out of scope

- generative or opaque scoring models
- fully autonomous plan rewrites
- external AI service dependencies for core recommendation logic
- major MCP redesign unrelated to coaching usefulness

## Product Outcome

After this sprint:

- coaching recommendations use more real context from recent weeks
- rationale and risks become more specific and easier to trust
- the app remains deterministic even as the guidance becomes more useful

## Proposed Feature Slice

### 1. Heuristic upgrade pass

Recommended signals to combine more strongly:

- recent adherence pattern
- repeated intent mismatches
- revision frequency
- subjective recovery signals
- current goal pressure

### 2. Recommendation traceability

Recommended response improvements:

- clearer top reasons
- clearer top risks
- visible references to recent pattern summaries where relevant

### 3. MCP and UI stability

Constraint:

- keep the response contract stable enough that MCP consumers and the UI do not need a large rewrite

## Backend Deliverables

### 1. Recommendation logic upgrade

Likely targets:

- `backend/app/services/coaching.py`
- `backend/app/services/dashboard.py`

Deliver:

- sharper rule ordering and weighting
- improved rationale assembly from recent signals

### 2. Payload refinement

Deliver:

- stable structured recommendation fields
- better signal summaries without excessive free-form narrative

### 3. Coverage

Deliver:

- assertions for upgraded recommendation paths
- focused cases where recent multi-week signals change the recommendation outcome

## Frontend Deliverables

### 1. Coaching read polish

Likely target:

- `frontend/src/views/Dashboard.vue`

Deliver:

- a cleaner explanation of why the current recommendation landed where it did
- compact rendering of the strongest recent signals

## Definition Of Done

Sprint 12 should be considered complete when:

- recommendation quality improves through visible deterministic rules
- rationale and risk fields reference richer recent context
- the coaching flow remains inspectable and does not turn into autonomous planning
