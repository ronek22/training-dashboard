# Sprint 22: Benchmark Sessions And Test-Result Visibility

## Status

Current status:

- planned
- follows Sprint 21 derived performance metrics and zones foundation

Starting point:

- the app has richer performance-oriented goals
- Sprint 21 is expected to provide the first reusable benchmark and zone data foundations
- plans and activities still do not treat benchmark or test sessions as explicit first-class planning artifacts

Dependency note:

- once derived performance reads and thresholds exist, the app should become more intentional about benchmark sessions themselves
- the next step is visibility and lightweight planning support, not full periodization automation

## Objective

Make benchmark or test sessions visible across planning, activity review, and goal progress so performance-oriented goals can anchor to explicit test efforts instead of only passive history.

This sprint should move the app from:

- `performance goals exist, but test efforts are still implicit`

to:

- `the app can tag, review, and connect benchmark sessions back to benchmark-oriented goals`

## Why This Sprint

That gap matters because:

- athletes need to see whether benchmark work is actually happening
- performance goals become more trustworthy when specific test efforts can be reviewed directly
- benchmark visibility is a useful bridge between lightweight planning and stronger future readiness modeling

## User Story

As an athlete with a benchmark or event-performance goal, I want benchmark sessions to be visible and connected to goal progress, so I can tell whether the work and the results are moving in the right direction.

## Sprint Scope

### In scope

- benchmark or test-session tagging
- benchmark history visibility
- lightweight plan/activity linkage back to performance-oriented goals

### Out of scope

- full test-protocol authoring
- automatic race-detection heuristics beyond conservative support
- autonomous periodization logic

## Product Outcome

After this sprint:

- planned sessions and completed activities can expose benchmark intent more clearly
- users can review benchmark history and recent changes over time
- benchmark and event goals can reference visible test efforts instead of only generic progress reads

## Proposed Feature Slice

### 1. Benchmark session identity

Recommended first support:

- explicit benchmark or test-session tagging on planned sessions
- visible benchmark markers on matched activities
- compact benchmark labels in Plan and Activities

### 2. Benchmark history and goal connection

Recommended first support:

- recent benchmark timeline or history panel
- compact benchmark delta summary
- visible linkage between benchmark-oriented goals and relevant benchmark efforts

## Backend Deliverables

### 1. Planning and activity support

Likely targets:

- `backend/app/services/plans.py`
- `backend/app/services/activities.py`
- `backend/app/services/goals.py`

Deliver:

- planned-session benchmark tagging
- activity read support for benchmark-tagged efforts
- compact goal-facing benchmark history summaries

### 2. Coverage

Deliver:

- smoke assertions for saving or reading benchmark-tagged sessions
- at least one case where a benchmark-oriented goal surfaces recent benchmark history in a visible contract

## Frontend Deliverables

### 1. Benchmark visibility

Likely targets:

- `frontend/src/views/Plan.vue`
- `frontend/src/views/Activities.vue`
- `frontend/src/views/Goals.vue`

Deliver:

- benchmark session labeling in plan and activity review
- compact history or delta visibility for benchmark-oriented goals

## Definition Of Done

Sprint 22 should be considered complete when:

- benchmark or test sessions can be tagged and read back visibly
- benchmark history is available in at least one athlete-facing surface
- benchmark-oriented goals can reference recent benchmark efforts more directly
- smoke coverage includes the new benchmark visibility behavior
