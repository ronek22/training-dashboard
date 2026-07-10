# Sprint 31: Goal Readiness And What Matters Next

## Status

Current status:

- complete
- follows completed Sprint 30 readiness and fatigue foundation

Starting point:

- the app already supports richer goal families, goal forecasts, requirement mapping, conflict visibility, benchmarks, and zone-aware process goals
- users can see whether goals are on pace or behind pace, but they still get limited guidance about whether current training actually supports eventual success
- readiness signals may soon exist at the athlete level, but not yet translated into goal-specific `what matters next` guidance

Implemented outcome:

- goals now expose structured `goal_readiness` states with deterministic `what_matters_next` guidance
- event and benchmark goals now distinguish missing specificity, stale evidence, and more stable readiness cases
- process and frequency goals now surface more explicit consistency vs weak-support reads
- dashboard and goal cards now show the highest-signal readiness summary without repeating the same copy in multiple sections
- coaching goal summaries can now reference the next missing ingredient instead of only pace pressure

Dependency note:

- Sprint 16 and Sprint 17 created the richer-goal and requirement foundation
- Sprint 21 and Sprint 22 established benchmark and performance support
- Sprint 30 added the athlete-level readiness layer this sprint consumes
- the next step should connect goal-readiness gaps more directly to closed-loop adaptation decisions

## Objective

Add goal-family-specific readiness states and `what matters next` summaries so goals can explain not just pace pressure, but whether recent training is actually preparing the athlete for the target.

This sprint should move the app from:

- `goals can show progress and pressure, but not a strong readiness interpretation`

to:

- `goals can summarize readiness, key gaps, and the next most important supporting work`

## Why This Sprint

That gap matters because:

- event and benchmark goals depend on workout quality and specificity, not only volume pace
- process goals need explicit guidance when execution is inconsistent
- hybrid athletes need the app to tell the truth about which goal currently needs more specific support
- planning quality improves when the next missing ingredient is explicit

## User Story

As an athlete balancing several goals, I want each goal to tell me whether I look ready, underprepared, or stale and what type of work matters next, so I can focus on the highest-value training instead of guessing from raw totals.

## Sprint Scope

### In scope

- goal-family-specific readiness states
- explicit gap summaries and `what matters next` guidance
- dashboard, goals, and coaching visibility for the new goal-readiness layer
- conservative unavailable states where supporting evidence is too weak

### Out of scope

- fully automated periodization or race plans
- predictive race-time models built from ML or large external datasets
- free-form AI-authored goal logic that bypasses structured rules
- deep new goal families beyond the current supported set

## Product Outcome

After this sprint:

- each active goal can show a clearer readiness interpretation
- dashboard and coaching can explain which goals are progressing but under-supported
- goals can expose the next most useful work type instead of only pace math
- the product becomes more actionable for event, benchmark, process, and frequency goals

## Proposed Feature Slice

### 1. Goal-family readiness rules

Recommended first support:

- event goals: assess specificity, recent supporting work, and stale benchmark evidence
- benchmark goals: assess freshness and quality of recent benchmark-like evidence
- process goals: assess rolling consistency and recent completion pattern
- frequency goals: assess whether the habit is being maintained reliably

Recommended direction:

- keep rules narrow and explicit per family
- reuse existing requirement and benchmark context wherever possible

### 2. `What matters next` guidance

Recommended first support:

- one short structured summary per goal describing the next valuable work category
- examples such as `needs longer aerobic support`, `needs fresher threshold evidence`, or `needs one more strength exposure this week`
- clear distinction between primary gap and secondary context

Recommended direction:

- prioritize concise, deterministic guidance
- avoid broad prose that sounds smart but does not map to product logic

### 3. Surface integration

Recommended first support:

- richer goal cards in `Goals`
- compact goal-readiness highlights in `Dashboard`
- coaching references that explain which goal support is currently most important

Recommended direction:

- show only the highest-signal next step per goal
- preserve existing forecast and risk visibility rather than replacing it

## Backend Deliverables

### 1. Goal-readiness engine

Likely targets:

- `backend/app/services/goals.py`
- `backend/app/services/dashboard.py`
- `backend/app/services/coaching.py`

Deliver:

- goal-family-specific readiness summary fields
- structured `what_matters_next` fields
- explicit weak-evidence and unavailable handling

### 2. Reusable payload shaping

Likely targets:

- `backend/app/services/goals.py`

Deliver:

- normalized read shape for goals, dashboard, and MCP consumers
- compatibility with existing forecast and planning-guidance contracts where possible

### 3. Coverage

Deliver:

- at least one event goal showing underprepared or missing-specificity state
- at least one benchmark goal showing stale-evidence behavior
- at least one process or frequency goal showing consistent vs inconsistent support

## Frontend Deliverables

### 1. Goal-readiness UI

Likely targets:

- `frontend/src/views/Goals.vue`
- `frontend/src/views/Dashboard.vue`

Deliver:

- readiness label and short rationale per goal
- compact `what matters next` treatment
- explicit unavailable states when supporting evidence is thin

## UX Notes

Recommended first rules:

- do not bury the next action under a large explanation
- show readiness state and one next-step summary first
- keep family-specific reasoning visible but compact
- avoid framing every gap as failure; many should read as normal preparation needs

Recommended first copy direction:

- `Goal readiness`
- `Needs fresher benchmark evidence`
- `Mostly on track, but missing long aerobic support`
- `Not enough evidence yet`

## Definition Of Done

Sprint 31 should be considered complete when:

- active goals expose goal-family-specific readiness states
- goals, dashboard, and coaching can show `what matters next` guidance
- the logic stays deterministic and explainable
- missing-evidence cases are explicit instead of speculative
