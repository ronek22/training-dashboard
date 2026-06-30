# Training Dashboard Roadmap

## Purpose

This roadmap is the working product and engineering plan for evolving the dashboard from a training log into a lightweight coaching system.

It is intentionally pragmatic:

- prioritize features that improve day-to-day usefulness
- keep changes aligned with the current FastAPI + SQLite + Vue architecture
- prefer small, compounding product improvements over large speculative rewrites

## Current State

The app already supports:

- activity history and filtering
- Strava import
- personal metrics
- coach notes
- weekly plans
- plan vs completed comparison
- MCP read/write access for ChatGPT and Claude
- partial weekly plan adjustment through `adjust_weekly_plan`

Current implementation status:

- the in-app `Adjust Remaining Week` flow is now at least partially implemented
- the backend modularization track is structurally complete
- the Sprint 9 through Sprint 14 coaching workflow sequence is now complete
- modality-specific restriction handling is now implemented, including restriction-aware goals and coaching
- the roadmap should therefore be read as an implemented sequence plus a record of product priorities, not as a claim that major listed items remain untouched

The main gap is that the app still acts more like a dashboard than a coaching workflow. The next phases should reduce manual interpretation and make planning, feedback, and adaptation first-class features.

## Product Direction

Target outcome:

1. store training context cleanly
2. understand what actually happened
3. recommend what to do next
4. let the user confirm or edit that recommendation quickly

That implies four product pillars:

- planning
- feedback
- analysis
- coaching workflow

## Priority Order

## Phase 1: Make Adaptive Planning Usable In-App

Goal: remove the dependency on chat for common replanning actions.

### 1. In-app "Adjust Remaining Week" flow

Why:

- the backend already supports partial adjustment
- the missing piece is user-facing control
- this gives immediate value with limited backend work

Scope:

- add an action on the Plan page
- show the current week and protected days
- let the user edit only open days
- submit to `/plans/weekly/adjust`
- display changed vs preserved dates after save

Implementation notes:

- frontend form or modal on [frontend/src/views/Plan.vue](../frontend/src/views/Plan.vue)
- API helper for `POST /plans/weekly/adjust` in [frontend/src/stores/api.js](../frontend/src/stores/api.js)
- reuse current plan data shape instead of inventing a new editor model

### 2. Clearer status semantics

Why:

- current statuses are useful but still coarse
- users need to tell the difference between skipped, moved, replaced, and intentionally changed

Scope:

- expand comparison states beyond `matched`, `partially_matched`, `different`, `rest_day_changed`
- detect when a planned session appears on a nearby day
- show `moved`, `skipped`, or `replaced` in the Plan UI

Implementation notes:

- likely centered in [backend/app/main.py](../backend/app/main.py)
- should remain conservative to avoid false positives

### 3. Plan revision visibility

Why:

- once plans become adaptive, silent overwrites are not enough
- users need to see how the week changed

Scope:

- store revision metadata or snapshot history
- show when a week was adjusted and why
- expose the latest revision in dashboard context

Implementation options:

- minimal: add `plan_revisions` table with snapshots
- later: render revision timeline in the UI

## Phase 2: Add the Feedback Loop

Goal: make future recommendations depend on how workouts actually felt, not just what was logged.

### 4. Post-workout feedback

Why:

- load-only logic misses fatigue, soreness, and pain
- subjective feedback is the highest-value missing data source

Scope:

- quick entry after workout:
  - `rpe`
  - `energy`
  - `muscle soreness`
  - `pain / niggle`
  - optional note

Implementation notes:

- new table, likely separate from `activities`
- lightweight form attached to recent activities
- include latest feedback in MCP context

### 5. Recovery-aware planning signals

Why:

- current load panels say whether load is balanced
- the app should also say whether a hard session is a good idea today

Scope:

- combine recent load, streak, feedback, and planned session type
- generate a daily recommendation:
  - push
  - keep planned session
  - reduce intensity
  - recover

Implementation notes:

- can start as deterministic rules
- no need for a heavy ML or scoring system

## Phase 3: Link Goals to Planning

Goal: make plans reflect goals instead of existing as a separate layer.

### 6. Goal-aware weekly plans

Why:

- goals exist already but are not driving plan generation strongly enough
- planning quality improves if the app knows the current target

Scope:

- tie weekly plans to active goals
- include goal context in MCP plan generation prompts
- show which sessions support which goal

Implementation notes:

- extend planning context in [backend/app/main.py](../backend/app/main.py)
- keep goal linkage simple at first

### 7. Goal progress forecast

Why:

- `how am I doing?` should be visible without manual calculation

Scope:

- project monthly or weekly target completion
- show pace-to-go and risk of missing target

Implementation notes:

- fits naturally in Goals and Dashboard views
- should stay interpretable, not overly statistical

## Phase 4: Improve Data Quality And Structure

Goal: reduce ambiguity in how planned and completed sessions relate.

### 8. Planned-to-actual linking

Why:

- date matching is a good start but not enough once sessions move around

Scope:

- attach an activity to a planned workout explicitly
- allow manual relinking in the UI
- use linkage to improve comparison accuracy

Implementation notes:

- simplest version is a nullable `planned_date` or `planned_session_id` reference on activities

Status:

- complete as a first explicit-linking slice

### 9. Structured workout intent

Why:

- `Run` or `Ride` is too broad for coaching logic

Scope:

- support workout intent values like:
  - easy
  - long
  - interval
  - tempo
  - recovery
  - strength lower
  - strength upper

Implementation notes:

- add optional structured fields without breaking current plans
- use this for better matching and better recommendations

Status:

- complete as a first structured-intent slice

## Phase 5: Make Coaching Easier Through MCP

Goal: reduce prompt overhead and make chat interactions more reliable.

### 10. One-shot coaching MCP action

Why:

- today chat has to compose several reads and then write an adjustment
- a more opinionated tool would improve consistency

Scope:

- add something like `coach_this_week`
- return:
  - summary of current training context
  - recommended next sessions
  - optional plan patch

Implementation notes:

- start deterministic and transparent
- let the model still explain reasoning in natural language

Status:

- complete as [docs/sprints/sprint-7-one-shot-coaching.md](sprints/sprint-7-one-shot-coaching.md)

### 11. Plan-diff confirmation flow

Why:

- chat should not silently rewrite your week without a clear before/after

Scope:

- generate diff
- show changed days
- require explicit user approval before save in the UI flow

Implementation notes:

- build directly on the Sprint 7 coaching payload rather than inventing a separate adjustment path
- likely spans `backend/app/services/coaching.py`, `backend/app/services/plans.py`, and `frontend/src/views/Plan.vue`

Recommended Sprint 8 role:

- this is the primary sprint goal

Status:

- complete as [docs/sprints/sprint-8-plan-diff-and-roadmap-visibility.md](sprints/sprint-8-plan-diff-and-roadmap-visibility.md)

### 12. Read-only roadmap and sprint visibility

Why:

- roadmap and sprint status already exists in markdown, but it is invisible unless someone reads the repo directly
- users can benefit from lightweight visual progress without turning docs into an editable in-app system

Scope:

- expose roadmap phase and sprint status in-app
- keep markdown under `docs/` as the single source of truth
- use deterministic metadata or stable headings instead of parsing arbitrary prose

Implementation notes:

- likely requires a small docs metadata reader plus a read-only API shape
- UI should favor compact cards, timelines, and progress indicators over free-form markdown rendering

Recommended Sprint 8 role:

- this is a secondary slice only if it stays lightweight and docs-backed

Status:

- complete as [docs/sprints/sprint-8-plan-diff-and-roadmap-visibility.md](sprints/sprint-8-plan-diff-and-roadmap-visibility.md)

### 13. App redesign and information hierarchy

Why:

- the current UI is clean and usable, but it can feel visually flat
- important states often carry too little visual emphasis compared with historical or secondary information
- current and old plan weeks should not feel equally important in the interface

Scope:

- improve hierarchy, emphasis, and scanning across the key app surfaces
- make current, active, and historical states more visually distinct
- redesign Plan and Dashboard presentation so important information stands out more clearly

Implementation notes:

- likely centered in `frontend/src/views/Plan.vue`, `frontend/src/views/Dashboard.vue`, `frontend/src/style.css`, and shared app layout components

Recommended Sprint 9 role:

- this is the next primary sprint goal

Status:

- complete as [docs/sprints/sprint-9-app-redesign-and-information-hierarchy.md](sprints/sprint-9-app-redesign-and-information-hierarchy.md)

### 14. Coaching history and revision timeline

Why:

- explicit approval is now in place, but users still lack a clear view of how coaching and plan changes evolved over time
- history visibility should improve before heavier trend analysis or heuristic expansion

Scope:

- expose recent coaching history in a compact read-only form
- show richer multi-entry plan revision timeline data
- connect recommendation, approval, and saved changes where practical

Implementation notes:

- likely spans `backend/app/services/coaching.py`, `backend/app/services/plans.py`, `frontend/src/views/Dashboard.vue`, and `frontend/src/views/Plan.vue`

Recommended Sprint 10 role:

- this should follow the redesign pass once hierarchy and emphasis are stronger

Status:

- complete as [docs/sprints/sprint-10-coaching-history-and-revision-timeline.md](sprints/sprint-10-coaching-history-and-revision-timeline.md)

### 15. Multi-week execution analysis

Why:

- single-week comparison is now solid, but repeated patterns matter more than isolated misses
- richer analysis should build on visible history instead of replacing it

Scope:

- summarize adherence trends across several weeks
- show recurring moved, skipped, replaced, and partial patterns
- surface intent-alignment trends conservatively

Implementation notes:

- likely spans `backend/app/services/plans.py`, `backend/app/services/coaching.py`, and Dashboard or Plan summary views

Recommended Sprint 11 role:

- this should follow Sprint 10 once history visibility is in place

Status:

- complete as [docs/sprints/sprint-11-multi-week-execution-analysis.md](sprints/sprint-11-multi-week-execution-analysis.md)

### 16. Stronger deterministic coaching heuristics

Why:

- recommendation quality can improve now that approval and trend visibility are becoming stronger
- the app should get smarter without becoming opaque

Scope:

- upgrade deterministic recommendation rules using recent execution, revision, recovery, and goal signals
- improve rationale and risk reporting without destabilizing the contract

Implementation notes:

- likely centered in `backend/app/services/coaching.py`

Recommended Sprint 12 role:

- this is the heuristic upgrade sprint after history and trend work

Status:

- complete as [docs/sprints/sprint-12-stronger-deterministic-coaching-heuristics.md](sprints/sprint-12-stronger-deterministic-coaching-heuristics.md)

### 17. Goal progress and planning forecasts

Why:

- goals exist and influence planning lightly, but pace-to-go and planning risk can still become more actionable
- the app should connect short-term coaching and longer-term targets more intentionally

Scope:

- refine goal forecasting and planning pressure signals
- show clearer goal risk states in Goals, Dashboard, and planning context
- keep forecasting lightweight and interpretable

Implementation notes:

- likely spans `backend/app/services/goals.py`, `backend/app/services/plans.py`, `backend/app/services/coaching.py`, and `frontend/src/views/Goals.vue`

Recommended Sprint 13 role:

- this should follow the stronger coaching and multi-week context work

Status:

- complete as [docs/sprints/sprint-13-goal-progress-and-planning-forecasts.md](sprints/sprint-13-goal-progress-and-planning-forecasts.md)

### 18. Modality restrictions and injury-aware coaching

Why:

- generic recovery logic is not enough when one modality is temporarily limited
- coaching and goal pressure should reflect what the user can actually do

Scope:

- add explicit modality restriction state
- make goals, plan context, and coaching respect active restrictions
- surface constrained states clearly in the app

Implementation notes:

- likely spans `backend/app/services/settings.py`, `backend/app/services/goals.py`, `backend/app/services/coaching.py`, and `frontend/src/views/Goals.vue`

Recommended Sprint 14 role:

- this should follow goal forecasting once coaching pressure is already more visible

Status:

- complete as [docs/sprints/sprint-14-modality-restrictions-and-injury-aware-coaching.md](sprints/sprint-14-modality-restrictions-and-injury-aware-coaching.md)

## Cross-Cutting Engineering Track

Goal: keep the codebase maintainable enough to support the product roadmap.

### 19. Backend modularization

Why:

- the backend has accumulated too much logic in a single file
- feature velocity will drop if extraction keeps getting delayed
- future planning and coaching features need cleaner boundaries

Scope:

- split `backend/app/main.py` into routers, services, repositories, models, and DB bootstrap modules
- preserve existing API behavior
- extract plans first, then other major domains

Implementation notes:

- see [docs/sprints/sprint-2-backend-modularization.md](sprints/sprint-2-backend-modularization.md)

## Suggested Build Sequence

This is the recommended implementation order:

1. In-app "Adjust Remaining Week" flow
2. API helper + UX polish for plan adjustments
3. Backend modularization
4. Plan revision history
5. Post-workout feedback model and form
6. Daily recommendation card
7. Goal-aware planning context
8. Planned-to-actual linkage
9. Goal forecasting
10. Structured workout intent
11. One-shot coaching MCP tool

## Recommended Next Sprint

The current roadmap sequence is complete.

### Sprint Goal

Draft a new roadmap slice only after deciding what the next product gap actually is.

### Scope

- preserve the current deterministic, inspectable coaching model
- harden tests and cleanup around the implemented workflow
- avoid pretending the Sprint 9 through Sprint 14 sequence is still pending

Current interpretation:

- the one-shot coaching, approval, history, trend, goal-forecast, and restriction-aware slices now exist end-to-end
- roadmap visibility is already in place, so future work should avoid turning docs into a parallel editable system
- the next decision is not `which listed sprint is next`, but `what belongs on the next roadmap`

### Definition of done

- the current roadmap is treated as complete in docs and status views
- any new major work starts from a fresh roadmap or sprint definition

## Risks And Constraints

- SQLite is fine for this stage; no storage migration is needed beyond additive tables
- over-automation is a product risk; recommendations should stay inspectable
- matching workouts too aggressively can create misleading coaching signals
- MCP write access is powerful, so plan changes should become more explicit over time

## Out Of Scope For Now

These ideas are reasonable but should wait:

- social features
- public sharing
- advanced mobile app packaging
- wearable integrations beyond Strava
- ML-heavy performance prediction
- fully autonomous training plans with no user review

## Working Principle

When choosing between features, prefer the one that:

1. reduces manual interpretation
2. improves planning decisions this week
3. fits the current architecture with minimal complexity
4. keeps the user in control of training changes
