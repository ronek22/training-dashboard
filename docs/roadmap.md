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

- frontend form or modal on [frontend/src/views/Plan.vue](/Users/jakubronkiewicz/Projekty/training-dashboard/frontend/src/views/Plan.vue:1)
- API helper for `POST /plans/weekly/adjust` in [frontend/src/stores/api.js](/Users/jakubronkiewicz/Projekty/training-dashboard/frontend/src/stores/api.js:1)
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

- likely centered in [backend/app/main.py](/Users/jakubronkiewicz/Projekty/training-dashboard/backend/app/main.py:1685)
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
  - `heel pain`
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

- extend planning context in [backend/app/main.py](/Users/jakubronkiewicz/Projekty/training-dashboard/backend/app/main.py:2679)
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

### 11. Plan-diff confirmation flow

Why:

- chat should not silently rewrite your week without a clear before/after

Scope:

- generate diff
- show changed days
- require explicit user approval before save in the UI flow

## Suggested Build Sequence

This is the recommended implementation order:

1. In-app "Adjust Remaining Week" flow
2. API helper + UX polish for plan adjustments
3. Plan revision history
4. Post-workout feedback model and form
5. Daily recommendation card
6. Goal-aware planning context
7. Planned-to-actual linkage
8. Goal forecasting
9. Structured workout intent
10. One-shot coaching MCP tool

## Recommended Next Sprint

If only one sprint is available, do this:

### Sprint Goal

Make adaptive planning visible, safe, and easy to use without chat.

### Scope

- add `adjust weekly plan` UI
- add adjustment result messaging
- add revision notes or snapshots
- improve plan status labels

### Definition of done

- user can adjust remaining days from the app
- completed days cannot be overwritten
- the app shows what changed
- the user can understand why the plan now differs from the original week

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
