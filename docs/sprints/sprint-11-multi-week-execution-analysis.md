# Sprint 11: Multi-Week Execution Analysis

## Status

Current status:

- complete
- follows completed Sprint 10 coaching history and revision timeline work

Starting point:

- plan comparison already distinguishes matched, linked, moved, skipped, replaced, and partial states
- structured workout intent and explicit linkage now improve single-week interpretation
- weekly coaching can summarize the current week, but trend visibility is still shallow

Dependency note:

- historical traceability should come before heavier trend analysis
- once revision and coaching history are visible, the next high-value step is pattern detection across multiple weeks

## Objective

Make execution quality visible across several weeks instead of only the current one.

This sprint should move the app from:

- `I can inspect this week`

to:

- `I can understand recurring execution patterns across recent weeks`

## Why This Sprint

Single-week coaching is useful, but trends matter more than isolated snapshots.

That gap matters because:

- repeated skipped or moved sessions are more meaningful than one-off misses
- adherence quality should be visible without manually reading several weeks of plans
- intent-alignment patterns can reveal whether the plan is realistic or being regularly diluted
- stronger recommendation heuristics depend on visible multi-week execution context

## User Story

As a user reviewing my training consistency, I want to see execution patterns across several weeks, so I can understand whether I am following the plan reliably or repeating the same failures.

## Sprint Scope

### In scope

- multi-week adherence summaries
- trend views for matched, skipped, moved, replaced, and partial sessions
- intent-alignment trend visibility where the data is available
- conservative interpretation that stays explainable

### Out of scope

- machine-learned scoring
- deep statistical forecasting
- complex custom charting that depends on free-form manual data entry
- autonomous plan changes driven by trend analysis alone

## Product Outcome

After this sprint:

- users can see execution patterns across recent weeks
- coaching gains a clearer view of consistency instead of only isolated sessions
- the product becomes better at explaining whether the current plan structure is actually sustainable

## Proposed Feature Slice

### 1. Multi-week comparison summary

Recommended response shape:

- recent weeks considered
- adherence counts by comparison state
- streaks or recurring misses where easy to define
- compact observations built from deterministic rules

### 2. Intent trend summary

Recommended behavior:

- show whether planned intensity or intent distribution is being preserved
- highlight repeated mismatches conservatively
- avoid strong claims when intent data is sparse

### 3. Read surfaces

Good first surfaces:

- Dashboard trend card
- Plan summary over recent weeks
- lightweight tables, bars, or stacked summaries derived directly from known statuses

## Backend Deliverables

### 1. Trend builder

Likely targets:

- `backend/app/services/plans.py`
- `backend/app/services/coaching.py`
- `backend/app/services/dashboard.py`

Deliver:

- a deterministic multi-week execution summary
- aggregation of comparison states and intent alignment over time

### 2. API exposure

Deliver:

- a stable route or dashboard payload extension for frontend consumption
- compact shapes optimized for read-only UI rendering

### 3. Coverage

Deliver:

- assertions for trend aggregation behavior
- at least one case covering recurring skipped or moved sessions

## Frontend Deliverables

### 1. Dashboard trend view

Likely target:

- `frontend/src/views/Dashboard.vue`

Deliver:

- a compact multi-week execution panel
- visuals built from deterministic status counts rather than prose

### 2. Plan trend summary

Likely target:

- `frontend/src/views/Plan.vue`

Deliver:

- a supporting recent-weeks summary that complements day-level weekly detail

## Definition Of Done

Sprint 11 should be considered complete when:

- recent execution patterns are visible across multiple weeks
- adherence and intent trends are inspectable without reading raw week data manually
- the analysis remains conservative, deterministic, and easy to explain
