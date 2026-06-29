# Sprint 6: Structured Workout Intent

## Status

Current status:

- complete
- follows completed Sprint 5 planned-to-actual linking work

Completed so far:

- optional `workout_intent` support was added to planned sessions and activities
- weekly plan responses expose normalized intent labels alongside plan days
- comparison exposes conservative intent-alignment information without overriding explicit links
- the Plan view shows and edits lightweight structured intent
- Activities have a lightweight activity-intent update path
- Calendar shows activity intent labels where present
- feedback flows can capture intent from Calendar and Activities
- recent coaching context includes a compact workout-intent summary
- smoke coverage was extended for intent serialization, intent updates, comparison behavior, and recent-context intent summaries

Dependency note:

- planned sessions now have stable IDs
- activities can explicitly link back to planned sessions
- comparison is more dependable, but session meaning is still too broad
- `Run`, `Ride`, and `WeightTraining` are not specific enough for higher-quality matching or coaching

## Objective

Make planned and completed sessions describe intended purpose, not just activity type.

This sprint should move the app from:

- `this was a run`

to:

- `this was an easy run`
- `this was a tempo ride`
- `this was lower-body strength`

## Why This Sprint

The product already has:

- weekly plans
- adaptive replanning
- goal-aware plan context
- explicit planned-to-actual linking
- basic comparison and manual correction

What is still missing is a structured description of what a session was for.

That gap matters because:

- matching logic is still coarse when two sessions share the same activity type
- coaching context cannot distinguish easy work from intensity or long work cleanly
- future recommendation quality will stay shallow if the app only knows broad categories
- plan evaluation is limited when `Ride` could mean recovery, endurance, tempo, or long

## User Story

As a user following a structured training week, I want planned sessions to describe workout intent clearly, so the app can compare, review, and coach based on what the session was meant to accomplish.

## Sprint Scope

### In scope

- add optional structured workout-intent fields to planned sessions
- add optional structured intent fields to activities where practical
- expose intent in plan responses and comparison payloads
- improve comparison to use intent conservatively when present
- surface intent in the Plan UI without making planning heavy
- include intent in recent context for later coaching and MCP actions

### Out of scope

- full workout builder or interval authoring
- advanced automatic intent classification from free text or streams
- broad sports taxonomy redesign across every part of the app
- complete coaching rewrite based on intent

## Product Outcome

After this sprint:

- planned sessions can say what kind of run, ride, or strength session they are
- plan comparison can use intent in addition to type and explicit linkage
- users can inspect the week with more clarity about session purpose
- future coaching flows can reason about easy vs hard vs long vs recovery work much better

## Proposed Feature Slice

### 1. Intent vocabulary

Define a small, explicit intent vocabulary that fits the current product.

Recommended starting direction:

- endurance intents:
  - `recovery`
  - `easy`
  - `long`
  - `tempo`
  - `interval`
  - `race_specific`
- strength intents:
  - `strength_general`
  - `strength_lower`
  - `strength_upper`
  - `mobility`

Important constraint:

- keep the first vocabulary deliberately small
- prefer practical usefulness over theoretical completeness

### 2. Plan data upgrade

Add structured intent to planned sessions without breaking existing weekly plan JSON.

Behavior target:

- intent is optional
- old plans remain valid
- new plans can store intent explicitly

### 3. Comparison upgrade

Use intent as a conservative quality signal when evaluating whether a completed activity matches the planned session.

Behavior target:

- explicit link still wins
- intent helps distinguish better or worse inferred matches
- absence of intent should not break comparison

### 4. UI upgrade

Show session intent in the Plan page in a compact way.

Recommended UX:

- keep it lighter than a full workout editor
- use small intent pills or labels near the planned session
- if editing is exposed now, keep it to a simple select field rather than free-form taxonomy editing

### 5. Context upgrade

Include structured intent in recent context and active plan payloads for future MCP/coaching flows.

That should make later coaching work able to answer:

- what type of work was planned
- what kind of work actually happened
- whether intensity distribution looks sensible

## Backend Deliverables

### 1. Planned-session intent support

Likely targets:

- `backend/app/models/plans.py`
- `backend/app/services/plans.py`
- `backend/app/repositories/plans.py`

Deliver:

- optional intent field on weekly plan days
- persistence-safe serialization for stored plan JSON

### 2. Activity intent support

Likely targets:

- `backend/app/models/activities.py`
- `backend/app/repositories/activities.py`
- `backend/app/services/activities.py`

Deliver:

- optional workout-intent field or equivalent annotation on activities
- migration-safe persistence if stored directly on activities

### 3. Comparison and context upgrades

Likely targets:

- `backend/app/services/plans.py`
- `backend/app/services/dashboard.py`
- `backend/app/services/mcp.py`

Deliver:

- comparison logic that can use intent conservatively
- intent included in active plan and recent context reads

## Frontend Deliverables

### 1. Intent-aware Plan view

Update `frontend/src/views/Plan.vue`:

- show planned session intent clearly
- show linked or inferred activity intent where available
- preserve current readability

### 2. Lightweight intent editing

If intent editing is added in this sprint, likely targets:

- `frontend/src/views/Plan.vue`
- possibly `frontend/src/views/Activities.vue`

Deliver:

- a small select-based workflow
- no heavyweight workout editor

## Suggested Implementation Order

1. define the initial intent vocabulary
2. add optional intent field to planned sessions
3. add optional intent support to activities if needed for comparison
4. expose intent in weekly plan responses and recent context
5. update comparison to use intent conservatively
6. surface intent in the Plan UI
7. add smoke coverage for serialization and intent-aware comparison behavior

## Risks

- an overly broad vocabulary could create noise instead of clarity
- intent rules may feel arbitrary if they silently override simpler matching behavior
- too much UI around intent could push the app toward a heavy plan editor too early

## Design Constraints

- prefer a small, inspectable taxonomy
- keep all intent fields optional in the first version
- explicit linkage still has priority over inferred intent-based matching
- preserve current plan readability and low editing overhead

## Definition Of Done

- planned sessions can carry structured workout intent
- plan responses expose intent in a backward-compatible way
- comparison can use intent conservatively when present
- Plan UI surfaces intent clearly
- recent coaching/MCP context includes intent-aware active plan data

## Completion Notes

What this implementation covers:

- optional structured workout intent for planned sessions and activities
- normalized intent labels in plan, activity, calendar, and context payloads
- lightweight intent editing across Plan, Activities, Calendar, and feedback flows
- inferred comparison that can distinguish type match with intent mismatch
- recent context with compact activity-intent and active-plan-intent summaries for later coaching work

Validation status:

- Python compile checks passed for the changed backend modules
- targeted smoke assertions were extended for intent-aware serialization and comparison semantics
- full backend test execution still depends on local FastAPI test dependencies
- frontend production build still depends on local Vite installation

## Follow-up After This Sprint

Once this sprint is complete, the next best product follow-ups are:

1. one-shot coaching MCP action for weekly analysis and adjustment
2. deeper history-aware execution insights using explicit link plus intent
3. better automatic inference or suggestion of workout intent from existing activity data
