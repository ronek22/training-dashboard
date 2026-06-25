# Sprint 3: Feedback Loop And Daily Guidance

## Status

Current status:

- planned, not started as a sprint
- this is the next major product sprint after the remaining Phase 1 adaptive-planning cleanup

Dependency note:

- do not read `Sprint 3` as meaning it must happen immediately after `Sprint 2`
- [sprint-2-backend-modularization.md](sprint-2-backend-modularization.md) is already structurally complete
- [phase-1-adaptive-planning.md](phase-1-adaptive-planning.md) is the active product sprint and still has open follow-up items

Recommended trigger to start this sprint:

- start once the team decides the remaining Phase 1 items are either complete or intentionally postponed

## Objective

Make the app react to how training actually felt, not only to what was completed.

This sprint should turn the dashboard from a passive log plus plan viewer into a more useful coaching workflow:

1. capture post-workout feedback quickly
2. surface that feedback in the app context
3. use it to shape a simple daily recommendation

## Why This Sprint

The current product already has:

- activities
- weekly plans
- notes
- metrics
- training load
- MCP access for chat-based coaching

What is still missing is the shortest path between `I did the workout` and `the plan should adapt to how I feel now`.

That gap matters because:

- load-only logic misses fatigue, soreness, pain, and poor recovery
- the dashboard still requires too much manual interpretation
- adaptive planning becomes more useful when it can rely on subjective inputs
- MCP coaching context is weaker without a structured record of how sessions felt

This sprint should create the first full feedback loop in the product.

## User Story

As a user who completed a workout, I want to record how it felt in under a minute and see that feedback influence today’s recommendation, so the app behaves more like a coach than a static tracker.

## Sprint Scope

### In scope

- add structured post-workout feedback storage
- add a lightweight feedback entry flow in the Activities view
- show recent feedback in app context
- compute a simple recovery-aware daily recommendation
- display that recommendation clearly on the Dashboard
- expose recent feedback and recommendation context through MCP

### Out of scope

- long-form journaling or standalone diary UX
- notifications or reminders to enter feedback
- ML-based readiness scoring
- automatic plan rewrites based only on feedback
- wearable integrations beyond the current Strava flow

## Product Outcome

After this sprint:

- each recent activity can have structured subjective feedback
- the user can see whether recent feedback suggests `push`, `keep`, `reduce`, or `recover`
- Dashboard guidance becomes more explainable
- chat-based coaching gets access to the same structured recovery signals

## Proposed Feature Slice

### 1. Post-workout feedback model

Capture a small set of fields per activity:

- `rpe` from 1-10
- `energy` from 1-5
- `muscle_soreness` from 1-5
- `heel_pain` from 0-10
- optional note

Recommended shape:

- one feedback record per activity
- nullable until entered
- editable if the user wants to revise it later

Why this shape:

- feedback stays attached to a real workout
- it avoids duplicate date-only records
- it becomes easier to use in plan comparison and coaching context later

### 2. Feedback entry UX in Activities

Primary placement:

- add a compact `Log Feedback` or `Edit Feedback` action in [frontend/src/views/Activities.vue](../../frontend/src/views/Activities.vue)

Recommended UX:

- only show the action on recent activities first
- open a lightweight inline panel or modal
- keep all inputs visible at once
- make save friction low

The workflow should feel closer to checking in than filling a form.

### 3. Recovery-aware daily recommendation

Use recent load plus recent feedback to compute a simple daily status:

- `push`
- `keep`
- `reduce`
- `recover`

Recommended first-pass rule inputs:

- recent training load state
- whether there was a hard session recently
- latest `energy`
- latest `muscle_soreness`
- latest `heel_pain`
- recent streak context
- today’s planned session type

Important constraint:

- start with deterministic and explainable rules
- always show why the status was chosen

### 4. Dashboard recommendation upgrade

Extend [frontend/src/views/Dashboard.vue](../../frontend/src/views/Dashboard.vue) so the top recommendation card explains:

- what is planned today
- current recommendation state
- the key signals driving it
- a short suggested action

Example outputs:

- `Keep the planned easy run.`
- `Reduce intensity today because soreness is elevated after two harder days.`
- `Recover today because heel pain is high.`

### 5. MCP context upgrade

Add recent feedback and daily guidance signals to the context already exposed for coaching flows.

Minimum target:

- recent activity feedback
- latest subjective state summary
- current daily recommendation
- simple reasoning fields behind that recommendation

That keeps app guidance and chat guidance aligned.

## Backend Deliverables

### 1. Feedback persistence

Add a new domain for activity feedback.

Recommended data fields:

- `activity_id`
- `rpe`
- `energy`
- `muscle_soreness`
- `heel_pain`
- `note`
- `created_at`
- `updated_at`

Likely module targets:

- `backend/app/models/activity_feedback.py`
- `backend/app/repositories/activity_feedback.py`
- `backend/app/services/activity_feedback.py`
- `backend/app/routers/activity_feedback.py`

### 2. Feedback API

Recommended endpoints:

- `POST /activities/{activity_id}/feedback`
- `GET /activities/{activity_id}/feedback`
- optional later: include feedback directly in activity list responses

Preferred product behavior:

- create or replace feedback with one endpoint
- keep the contract simple

### 3. Recommendation service

Add a service that derives a daily recommendation from:

- training load summary
- recent context
- latest feedback
- current plan day

Likely target:

- `backend/app/services/recommendations.py`

### 4. MCP integration

Extend MCP read context so coaching tools can access:

- recent feedback entries
- recommendation status
- recommendation reasoning

This can likely live in the existing MCP adapter/service path without a protocol redesign.

## Frontend Deliverables

### 1. Activities feedback entry

Update [frontend/src/views/Activities.vue](../../frontend/src/views/Activities.vue):

- add feedback action per recent activity
- add feedback form state
- save through new API methods
- show whether feedback is missing or already logged

### 2. API helpers

Update [frontend/src/stores/api.js](../../frontend/src/stores/api.js) with feedback endpoints.

### 3. Dashboard guidance card

Update [frontend/src/views/Dashboard.vue](../../frontend/src/views/Dashboard.vue):

- show current recommendation state
- show short rationale
- distinguish plan content from recovery guidance

## Suggested Implementation Order

1. add feedback table and backend modules
2. add feedback API endpoints
3. include feedback in recent context responses
4. add recommendation service with deterministic rules
5. expose recommendation in dashboard backend response
6. add Activities feedback UI
7. add Dashboard recommendation UI
8. extend MCP context with feedback and recommendation signals
9. add smoke coverage for feedback flow

## Risks

- too many subjective fields could make logging feel heavy
- naive recommendation logic could feel arbitrary if reasoning is hidden
- feedback that is not attached to activities cleanly could become noisy fast
- heel pain should remain high-signal and not get buried inside generic soreness logic

## Design Constraints

- keep feedback logging under one minute
- preserve current app simplicity
- do not turn the Dashboard into a medical readiness score
- prefer explicit rule explanations over opaque scoring

## Definition Of Done

- user can log feedback for a recent activity in the app
- saved feedback persists and can be edited
- dashboard shows a recovery-aware daily recommendation
- recommendation includes human-readable reasoning
- recent feedback is available in MCP coaching context
- basic backend tests cover the new flow

## Follow-up After This Sprint

Once this sprint is complete, the next best product follow-ups are:

1. goal-aware planning and goal-linked sessions
2. plan revision visibility
3. planned-to-actual explicit linking
