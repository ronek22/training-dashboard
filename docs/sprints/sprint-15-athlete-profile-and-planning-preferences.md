# Sprint 15: Athlete Profile And Planning Preferences

## Status

Current status:

- complete
- followed completed Sprint 14 modality restrictions and injury-aware coaching work

Starting point:

- the app can now coach around execution, restrictions, and goal pressure
- goals are visible and useful, but they still mostly describe `how much` rather than `what kind of target`
- MCP and chat can read useful context, but they still do not get one durable athlete brief

Dependency note:

- the next product gap is not another coaching surface
- the app needs clearer athlete context before richer goals and deeper goal-aware planning will stay coherent

## Objective

Make the app understand the athlete more explicitly so planning, coaching, and MCP context stop relying on guesswork.

This sprint should move the app from:

- `the app infers the athlete mostly from recent activities and active goals`

to:

- `the app has an explicit athlete profile that informs planning and coaching`

## Why This Sprint

The current workflow is useful, but too much context is still implicit.

That gap matters because:

- hybrid, endurance, and strength-focused athletes need different coaching emphasis even with similar recent logs
- richer goal types will be harder to add cleanly without stable athlete context
- MCP and chat recommendations become more reliable when profile, priorities, and planning notes are stored explicitly
- user trust improves when the app reflects declared priorities rather than inferred ones

## User Story

As an athlete using the dashboard for ongoing coaching, I want to declare my focus, priorities, and planning context, so the app and MCP guidance understand what kind of training I am actually trying to do.

## Sprint Scope

### In scope

- lightweight persisted athlete profile
- planning-preference fields that affect interpretation and coaching context
- compact read surfaces in app and MCP
- deterministic use of profile context in coaching explanations

### Out of scope

- a full social or demographic profile system
- automatic personality or preference inference
- deeply automated plan generation based only on profile
- broad redesign of settings beyond what the profile needs immediately

## Product Outcome

After this sprint:

- users can persist a compact athlete profile
- coaching reads can reference athlete focus and planning notes explicitly
- MCP context becomes easier to use because profile state is packaged deterministically
- the product is better prepared for richer goal families in the next sprint

Implemented outcome:

- athlete profile persistence now lives in settings-backed storage with normalized defaults
- dashboard, recent context, coaching reads, and MCP expose a compact `athlete_brief`
- `Goals` owns compact athlete-profile editing and summary visibility
- `Dashboard` now shows athlete context as secondary reference beside recent coaching history
- readback tolerates previously normalized profile data and stores a stable raw payload shape

## Proposed Feature Slice

### 1. Athlete profile model

Recommended direction:

- add fields such as:
  - primary focus like `endurance`, `hybrid`, `strength`, or `general_fitness`
  - preferred modalities or modality priority order
  - current emphasis block or season
  - preferred long-session days or weekly availability notes
  - free-form planning notes
- keep the first version lightweight and easy to edit

### 2. Profile-aware coaching context

Recommended behavior:

- dashboard and MCP context should expose the stored athlete profile
- coaching rationale can reference focus or planning notes where relevant
- profile should guide interpretation before it starts driving heavy automation

### 3. Read surfaces

Good first surfaces:

- a compact athlete profile card or modal in `Goals`
- dashboard visibility for the current focus
- MCP or recent-context payload exposure for chat workflows

## Backend Deliverables

### 1. Profile persistence

Likely targets:

- `backend/app/services/settings.py`
- `backend/app/repositories/settings.py`
- `backend/app/models/settings.py`
- `backend/app/routers/settings.py`

Deliver:

- additive athlete-profile storage
- normalized read and write responses
- simple defaults when no profile exists yet

### 2. Coaching and context integration

Likely targets:

- `backend/app/services/dashboard.py`
- `backend/app/services/coaching.py`
- `backend/app/services/mcp.py`

Deliver:

- athlete profile exposure in dashboard and MCP reads
- compact structured athlete brief for downstream chat use
- initial coaching rationale support for profile-aware wording

### 3. Coverage

Deliver:

- smoke assertions for reading and writing the athlete profile
- at least one case where stored profile context appears in coaching or dashboard output

## Frontend Deliverables

### 1. Athlete profile editing

Likely targets:

- `frontend/src/views/Goals.vue`
- settings-adjacent surface only if it stays small

Deliver:

- a compact way to edit athlete focus and planning preferences
- clear wording that explains what the profile is used for

### 2. Profile visibility

Likely targets:

- `frontend/src/views/Goals.vue`
- `frontend/src/views/Dashboard.vue`

Deliver:

- visible athlete-focus summary
- clear distinction between durable athlete context and temporary training restrictions

## Definition Of Done

Sprint 15 should be considered complete when:

- users can persist and edit an athlete profile
- dashboard and MCP reads expose that profile in a compact structured form
- coaching can reference athlete focus or planning notes without relying only on reconstructed prompt context

Status:

- complete for the current roadmap slice
