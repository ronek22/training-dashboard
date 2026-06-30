# Sprint 16: Richer Goal Families

## Status

Current status:

- planned
- follows completed Sprint 15 athlete profile and planning preferences work

Starting point:

- the app now has explicit athlete context and a durable athlete brief
- goals are forecasted and useful, but they are still mostly accumulation-based
- coaching can reason about pressure, restrictions, and athlete priorities, but it still cannot reason about different kinds of goals very well

Dependency note:

- richer planning quality now depends more on richer goal modeling than on another dashboard surface
- the app needs explicit goal families before goal-aware coaching can become more truthful about tradeoffs

## Objective

Expand the goal model from simple accumulation tracking into a small set of structured goal families that better match how athletes actually train.

This sprint should move the app from:

- `goals mostly describe how much volume to do`

to:

- `goals can describe distinct target types with structured fields and clearer meaning`

## Why This Sprint

The current goal system is useful, but too narrow.

That gap matters because:

- many athlete targets are event, benchmark, or process-based rather than pure totals
- coaching explanations become weak when every target gets reduced to generic pace pressure
- richer athlete context from Sprint 15 is only fully useful once the goal model can express more realistic intent
- future planning upgrades need goal types that map to different session requirements

## User Story

As an athlete using the dashboard for ongoing coaching, I want to define different kinds of goals in a structured way, so progress, planning, and coaching reflect what I am actually trying to achieve.

## Sprint Scope

### In scope

- structured richer goal families
- normalized storage and read contracts for those goal families
- lightweight UI support for selecting goal type and entering the right fields
- compact goal-family visibility in dashboard, goals, and coaching context

### Out of scope

- deep automatic plan generation from goal types alone
- broad event-specific periodization engines
- free-form natural-language goals as the canonical storage model
- advanced probability or readiness modeling

## Product Outcome

After this sprint:

- users can create more than one kind of goal in a structured way
- the app can distinguish accumulation, event, benchmark, and process-style targets
- dashboard and MCP context can expose clearer goal meaning instead of only generic totals
- the codebase is better prepared for goal-specific progress engines in the following sprint

## Proposed Feature Slice

### 1. Goal-family model

Recommended first families:

- accumulation goals such as total distance, total time, or activity count
- event-performance goals such as `run 10k under 40 minutes`
- benchmark goals such as `hold 300W for 10 minutes`
- process or frequency goals such as `lift twice per week` or `6 hours of Z2`

Recommended direction:

- keep a small explicit vocabulary rather than a generic schema free-for-all
- make goal family and structured target fields the source of truth
- preserve existing accumulation goals without breaking current reads

### 2. Read and context integration

Recommended behavior:

- goals should expose a visible family/type label
- dashboard and MCP context should include compact structured goal meaning
- coaching should start referencing goal family where it changes interpretation, even before deeper family-specific forecasting exists

### 3. UI entry and visibility

Good first surfaces:

- `Goals` goal-creation flow
- compact family labels and summary fields in `Goals`
- lightweight dashboard visibility only where it helps decisions

## Backend Deliverables

### 1. Goal schema expansion

Likely targets:

- `backend/app/models/goals.py`
- `backend/app/repositories/goals.py`
- `backend/app/services/goals.py`
- `backend/app/routers/goals.py`

Deliver:

- additive support for richer goal families
- normalized read and write responses
- backward-compatible handling for existing accumulation goals

### 2. Context and coaching integration

Likely targets:

- `backend/app/services/dashboard.py`
- `backend/app/services/coaching.py`
- `backend/app/services/mcp.py`

Deliver:

- goal-family visibility in dashboard and MCP reads
- compact structured goal summaries for downstream chat use
- first-pass coaching wording that can distinguish goal types where relevant

### 3. Coverage

Deliver:

- smoke assertions for creating and reading at least two goal families
- at least one case where goal-family metadata appears in dashboard, coaching, or MCP output

## Frontend Deliverables

### 1. Goal creation flow

Likely target:

- `frontend/src/views/Goals.vue`

Deliver:

- a compact goal-family selector
- type-specific form fields with clear wording
- sensible defaults that preserve today’s simpler experience

### 2. Goal visibility

Likely targets:

- `frontend/src/views/Goals.vue`
- `frontend/src/views/Dashboard.vue`

Deliver:

- visible goal-family labels and structured summaries
- clear separation between goal kind and progress state

## Definition Of Done

Sprint 16 should be considered complete when:

- users can create and persist more than one structured goal family
- dashboard and MCP reads expose compact goal-family context
- coaching can distinguish goal type where it materially changes interpretation
- existing accumulation goals continue to work without migration pain
