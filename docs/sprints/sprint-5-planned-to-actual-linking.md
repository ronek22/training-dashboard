# Sprint 5: Planned-To-Actual Linking

## Status

Current status:

- complete
- follows completed Sprint 4 goal-aware planning work

Completed so far:

- stable `session_id` values are assigned to weekly plan days on write and exposed in plan responses
- activities now support nullable `linked_planned_session_id` persistence
- weekly plan comparison now distinguishes explicit vs inferred matching and prefers explicit links
- a manual linking endpoint exists for linking an activity to a planned session
- the Plan view includes an inline planned-to-actual relink control
- the Plan view received a first visual polish pass to reduce status-color bleed and make linking controls less heavy
- the linking UI is now on-demand instead of always visible, with review/relink actions shown only where needed
- smoke coverage was added for session IDs, explicit-link precedence, and recent-context visibility

Dependency note:

- weekly plans now expose goal context and per-day support mapping
- comparison logic still relies mostly on date and loose matching rules
- explicit activity-to-plan linkage is the next structural step before deeper coaching automation

## Objective

Make plan comparison dependable when sessions move, get replaced, or need manual clarification.

This sprint should move the app from:

- `the app guesses what matched`

to:

- `the app knows which activity fulfilled which planned session`

## Why This Sprint

The product already has:

- weekly plans
- adaptive plan adjustments
- plan-vs-actual comparison
- feedback attached to completed activities
- goal-aware plan context

What is still missing is a durable connection between a planned session and the activity that actually satisfied it.

That gap matters because:

- date-based comparison becomes noisy once sessions move across days
- coaching logic is weaker when completed work is only inferred
- feedback and future recommendations cannot cleanly attach back to the original plan
- later workout-intent and automation work will be harder without explicit linkage

## User Story

As a user adjusting my training week in real life, I want to tell the app which activity fulfilled which planned session, so the comparison stays accurate even when the schedule shifts.

## Sprint Scope

### In scope

- introduce explicit planned-to-actual linkage in the data model
- expose linkage state in plan comparison responses
- support manual relinking from the UI where the match is unclear
- preserve conservative automatic matching as a starting convenience
- make linkage available to MCP/coaching context

### Out of scope

- fully automatic matching confidence models
- broad workout taxonomy redesign beyond fields needed for linking
- complete coaching rewrite based on linkage
- large historical cleanup tooling beyond basic migration behavior

## Product Outcome

After this sprint:

- planned sessions can be explicitly fulfilled by activities
- moved workouts no longer depend only on date proximity
- users can correct ambiguous matches without editing raw data
- future coaching flows can reason about plan execution with less guesswork

## Proposed Feature Slice

### 1. Durable link field

Add an explicit way to associate an activity with a planned session.

Recommended direction:

- introduce a stable planned-session identifier in weekly plan data
- store the linked planned-session identifier on activities

Important constraint:

- the first version should stay simple and migration-friendly
- avoid redesigning the full plan storage model unless the current JSON shape forces it

### 2. Comparison upgrade

Update plan comparison so it prefers explicit links over inference.

Behavior target:

- explicit link wins
- otherwise fall back to current conservative matching
- clearly surface linked, inferred, and unmatched states

### 3. Manual relinking UX

Add a small UI flow so the user can link or relink a completed activity to a planned session when the automatic result is wrong or missing.

Recommended UX:

- keep it lightweight and local to existing Plan or Calendar workflows
- prefer click-to-link over a heavy editor

### 4. Context upgrade

Expose linkage in recent context and plan analysis payloads so later coaching logic can understand:

- what was planned
- what fulfilled it
- what stayed unmatched

## Backend Deliverables

### 1. Planned session identity

Likely target:

- `backend/app/services/plans.py`
- `backend/app/repositories/plans.py`

Deliver:

- stable planned-session IDs in serialized weekly plans
- migration-safe persistence for those IDs in stored plan JSON

### 2. Activity linkage persistence

Likely target:

- `backend/app/repositories/activities.py`
- `backend/app/services/activities.py`

Deliver:

- nullable linked planned-session field on activities
- write path for manual linking or relinking

### 3. Comparison and context updates

Likely targets:

- `backend/app/services/plans.py`
- `backend/app/services/dashboard.py`
- `backend/app/services/mcp.py`

Deliver:

- comparison paths that prefer explicit linkage
- linkage state available in recent context and coaching reads

## Frontend Deliverables

### 1. Link-aware plan comparison

Update `frontend/src/views/Plan.vue`:

- show when a planned session is explicitly fulfilled
- distinguish linked vs inferred vs unmatched states

### 2. Manual linking flow

Update the most appropriate existing workflow, likely:

- `frontend/src/views/Plan.vue`
- `frontend/src/views/Calendar.vue`
- possibly `frontend/src/views/Activities.vue`

Deliver:

- a small relink interaction
- enough context that the user can see both the planned session and candidate activities

## Suggested Implementation Order

1. define stable planned-session identity in plan serialization
2. add activity linkage persistence and migration
3. upgrade comparison logic to prefer explicit links
4. expose a manual linking API
5. wire a lightweight frontend relink flow
6. add smoke coverage around linked vs inferred matching

## Risks

- stored weekly plan JSON may make stable IDs awkward if old data is inconsistent
- a poor manual-linking UI could feel heavier than the problem it solves
- relinking rules must avoid silently breaking prior comparison assumptions

## Design Constraints

- prefer explicit, inspectable linkage over hidden heuristics
- preserve current plan readability
- keep migration and backward compatibility simple
- avoid forcing a full plan editor redesign in this sprint

## Definition Of Done

- planned sessions have stable IDs in plan responses
- activities can explicitly link to a planned session
- comparison prefers explicit links over date-only inference
- users can correct ambiguous matches from the UI
- linkage is available to backend context used for coaching and MCP

## Completion Notes

What this implementation covers:

- explicit planned-session identity without redesigning weekly plan storage
- backward-compatible activity linkage storage via a nullable activity field
- explicit-link-first comparison behavior with fallback inference still intact
- lightweight inline relinking in the existing Plan view
- linkage visibility in serialized active-plan context used by dashboard and MCP reads

Validation status:

- Python compile checks passed for the changed backend modules
- targeted smoke assertions were added for linking and recent context
- full backend test execution still depends on local FastAPI test dependencies
- frontend production build still depends on local Vite installation

## Follow-up After This Sprint

Once this sprint is complete, the next best product follow-ups are:

1. structured workout intent
2. one-shot coaching MCP action for weekly analysis and adjustment
3. deeper history-aware comparison and execution insights
