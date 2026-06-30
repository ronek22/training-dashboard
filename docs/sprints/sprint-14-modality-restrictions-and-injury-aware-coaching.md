# Sprint 14: Modality Restrictions And Injury-Aware Coaching

## Status

Current status:

- completed
- follows planned Sprint 13 goal progress and planning forecast work

Starting point:

- goals can influence planning and coaching, but only through broad pace and pressure math
- recovery signals exist, but they are global rather than modality-specific
- coaching can now background some run-goal pressure heuristically, but this is still inference instead of explicit user state

Dependency note:

- the next trust gap is constraint accuracy, not more generic pressure logic
- the app needs to distinguish `I am generally under-recovered` from `I am fit to train, but one modality is restricted`

## Objective

Make the app understand explicit sport-specific restrictions so coaching, planning, and goal pressure reflect what the user can actually do.

This sprint should move the app from:

- `the app infers broad recovery caution from recent signals`

to:

- `the app knows that running, riding, or strength may be temporarily restricted and adapts coaching accordingly`

## Why This Sprint

The current model is not accurate enough for injury or constraint-heavy periods.

That gap matters because:

- users can have high energy and strong fitness while still being unable to run
- broad recovery logic can suppress the wrong signals or surface the wrong pressure
- goal pressure becomes misleading if the blocked modality is not represented explicitly
- adaptive planning should react to real availability constraints, not only generic caution

## User Story

As a user managing an injury or temporary restriction, I want to declare which modalities are limited, so coaching and goals reflect what I can actually train without turning the app into a guesser.

## Sprint Scope

### In scope

- explicit modality restriction state
- coaching and goal logic that respects restriction state
- plan and dashboard visibility for current restrictions
- deterministic behavior for how restricted modalities affect pressure and session suggestions

### Out of scope

- medical diagnosis features
- treatment planning
- automated return-to-sport progression
- complex injury history modeling beyond what coaching needs immediately

## Product Outcome

After this sprint:

- users can declare that running, riding, or strength is restricted
- coaching can remain assertive in allowed modalities without pressuring blocked ones
- goal pressure becomes more honest and less frustrating during injury periods
- plan adjustments can target the blocked modality instead of collapsing into whole-system caution

## Proposed Feature Slice

### 1. Restriction model

Recommended direction:

- add current restriction state per modality such as `allowed`, `limited`, or `blocked`
- support optional reason, note, and expected end date
- keep the model lightweight and easy to edit

### 2. Coaching integration

Recommended behavior:

- blocked or limited modalities should not drive pressure the same way as available ones
- recommendation reasoning should mention active restrictions explicitly
- next-session suggestions should adapt per modality instead of only globally

### 3. Goal and planning integration

Recommended behavior:

- goals tied to restricted modalities should be shown as constrained rather than simply behind
- plans should highlight when a session supports a currently restricted goal or modality
- adaptive previews should prefer substitution or de-emphasis for blocked modalities where practical

### 4. Read surfaces

Good first surfaces:

- Dashboard restriction summary
- Goals constrained-state indicator
- Plan labels for restricted sessions or modality-aware suggestions

## Backend Deliverables

### 1. Restriction persistence

Likely targets:

- `backend/app/db.py`
- `backend/app/repositories/`
- `backend/app/services/settings.py` or a focused new service

Deliver:

- additive storage for current modality restrictions
- normalized read/write responses for UI and MCP use

### 2. Coaching and goal upgrades

Likely targets:

- `backend/app/services/coaching.py`
- `backend/app/services/goals.py`
- `backend/app/services/dashboard.py`
- `backend/app/services/plans.py`

Deliver:

- restriction-aware goal pressure
- restriction-aware coaching reasoning and next-session shaping
- explicit structured fields for constrained modalities

### 3. Coverage

Deliver:

- tests for restricted-modality coaching behavior
- at least one case where running is blocked but riding remains available
- at least one case where a goal becomes constrained instead of simply pressured

## Frontend Deliverables

### 1. Restriction controls

Likely targets:

- `frontend/src/views/Dashboard.vue`
- `frontend/src/views/Goals.vue`
- settings-oriented surface if the app prefers central editing

Deliver:

- a simple way to mark modality availability
- visible current-state summary with clear wording

### 2. Coaching and goal presentation

Likely targets:

- `frontend/src/views/Dashboard.vue`
- `frontend/src/views/Plan.vue`
- `frontend/src/views/Goals.vue`

Deliver:

- explicit constrained-goal cues
- coaching language that distinguishes general recovery from modality restriction

## Definition Of Done

Sprint 14 should be considered complete when:

- users can explicitly mark a modality as limited or blocked
- coaching and goal pressure respect those restrictions deterministically
- the app no longer confuses `globally tired` with `modality-specific restriction`

## Delivered

- added persisted modality restriction state for running, riding, and strength
- added restriction-aware coaching, goal evaluation, and next-session shaping
- surfaced constrained-goal and restricted-session cues across dashboard, goals, and plan
- added backend smoke coverage for constrained goals and restriction-aware coaching behavior
