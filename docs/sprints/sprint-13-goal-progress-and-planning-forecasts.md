# Sprint 13: Goal Progress And Planning Forecasts

## Status

Current status:

- complete
- follows completed Sprint 12 stronger deterministic coaching heuristics work

Starting point:

- goals already exist and weekly plans can expose lightweight goal context
- goals view already includes planning-relevant pacing guidance
- coaching now has a clearer approval loop and should be gaining better historical context

Dependency note:

- stronger forecasting should come after coaching and execution context are more mature
- the app should stay interpretable rather than sliding into speculative prediction

## Objective

Make goal progress and near-term planning forecasts more actionable and visible.

This sprint should move the app from:

- `goals exist and influence planning lightly`

to:

- `goals visibly shape pace-to-go, planning risk, and short-horizon decisions`

## Why This Sprint

Goals are present, but they still feel looser than the rest of the planning workflow.

That gap matters because:

- users should see whether current execution is putting goals at risk
- plan quality improves when next-week decisions reflect pace-to-go clearly
- coaching becomes more valuable when it can explain tradeoffs against real targets
- the app should connect reactive adjustment and long-horizon direction more intentionally

## User Story

As a user training toward a goal, I want clearer forecasting and risk visibility, so I can tell whether my current plan is keeping me on pace or quietly falling behind.

## Sprint Scope

### In scope

- stronger pace-to-go forecasting
- clearer risk visibility for active goals
- tighter goal context in planning and coaching reads
- lightweight interpretable visuals for forecast and risk status

### Out of scope

- complex predictive modeling
- event-specific periodization engines
- automatic goal creation or autonomous long-term plan generation
- speculative probability estimates that are hard to explain

## Product Outcome

After this sprint:

- goals feel more connected to daily and weekly planning
- users can see whether they are ahead, on pace, or under pressure more clearly
- coaching can explain short-term recommendations against longer-term targets

## Proposed Feature Slice

### 1. Forecast refinement

Recommended capabilities:

- stronger required-per-day or required-per-week guidance
- clearer current pace and projected finish indicators
- visible under-pressure flags when recent execution makes the target harder

### 2. Planning integration

Recommended behavior:

- show which upcoming sessions matter most for active goals
- make goal pressure visible in planning and coaching summaries
- keep linkages simple and interpretable

### 3. Goal risk surfaces

Good first surfaces:

- Goals page forecast cards
- Dashboard risk summary
- compact plan annotations for high-value supporting sessions

## Backend Deliverables

### 1. Forecast logic upgrade

Likely targets:

- `backend/app/services/goals.py`
- `backend/app/services/plans.py`
- `backend/app/services/coaching.py`

Deliver:

- refined forecasting and risk summaries for active goals
- compact structured fields suitable for UI and MCP use

### 2. Context upgrades

Deliver:

- stronger goal-planning summaries in recent context and coaching reads
- better mapping between sessions and high-priority goals where practical

### 3. Coverage

Deliver:

- assertions for forecast outputs and pressure states
- at least one case where falling behind changes visible planning guidance

## Frontend Deliverables

### 1. Goals forecast UI

Likely target:

- `frontend/src/views/Goals.vue`

Deliver:

- clearer forecast cards and risk indicators
- lightweight visuals consistent with existing goal context panels

### 2. Dashboard and Plan integration

Likely targets:

- `frontend/src/views/Dashboard.vue`
- `frontend/src/views/Plan.vue`

Deliver:

- compact goal-risk cues where they help the user make planning decisions quickly

## Definition Of Done

Sprint 13 should be considered complete when:

- active goals expose clearer pace-to-go and risk visibility
- planning and coaching surfaces reference goal pressure more intentionally
- forecasting remains lightweight, deterministic, and easy to explain
