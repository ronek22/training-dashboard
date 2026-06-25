# Sprint 2: Backend Modularization

## Objective

Refactor the backend so new feature work does not continue accumulating inside a single oversized `main.py`.

The goal is not a rewrite. The goal is to preserve behavior while introducing a modular structure that is easier to navigate, test, and extend.

## Why This Sprint

Right now too many concerns live in [backend/app/main.py](/Users/jakubronkiewicz/Projekty/training-dashboard/backend/app/main.py:1):

- FastAPI app bootstrap
- database initialization
- Pydantic models
- request handlers
- Strava integration
- dashboard aggregation
- planning logic
- MCP tool definitions
- business rules

That creates several problems:

- hard to find the correct place to change behavior
- high risk of accidental regressions
- weak separation between HTTP layer and domain logic
- difficult testing strategy
- growing cost for each new feature

This sprint should create the structure needed for the next phases in the roadmap, especially feedback capture, richer planning, and goal-aware coaching logic.

## Desired Outcome

After this sprint:

- routes are separated by domain
- business logic lives outside route handlers
- database access is isolated behind small, explicit functions
- shared models are easier to find
- `main.py` becomes a composition entrypoint, not the entire backend

## Refactor Principles

- preserve existing API behavior unless explicitly improved
- prefer incremental extraction over rewrite
- keep SQLite and FastAPI
- avoid introducing unnecessary abstraction layers
- introduce structure only where it reduces future complexity

## Target Structure

Recommended backend layout:

```text
backend/app/
  main.py
  db.py
  models/
    activities.py
    metrics.py
    plans.py
    goals.py
    notes.py
    integrations.py
  routers/
    activities.py
    metrics.py
    plans.py
    goals.py
    notes.py
    dashboard.py
    integrations.py
    mcp.py
  services/
    activities.py
    metrics.py
    plans.py
    goals.py
    dashboard.py
    training_load.py
    strava.py
    mcp.py
  repositories/
    activities.py
    metrics.py
    plans.py
    goals.py
    notes.py
    settings.py
```

This is a target shape, not a rigid requirement. The main architectural intent is:

- `routers/` own HTTP concerns
- `services/` own business logic
- `repositories/` own SQL access
- `models/` own request/response/domain models

## Scope

### In scope

- split `main.py` into coherent modules
- extract route groups into router files
- extract planning logic into a plans service
- extract dashboard/training-load aggregation into service modules
- extract Strava integration logic into a dedicated service
- centralize database connection and initialization
- preserve current API endpoints
- leave the app in a state where further extraction is straightforward

### Out of scope

- full ORM adoption
- replacing SQLite
- auth redesign
- rewriting the MCP feature set
- major schema redesign
- full test suite buildout beyond minimal smoke coverage

## Current Status

Completed extractions so far:

- `db.py` now owns DB connection and initialization
- `plans` domain moved into `models/`, `repositories/`, `services/`, and `routers/`
- dashboard aggregation and training-load logic moved into `services/dashboard.py`
- Strava integration logic moved into `models/integrations.py` and `services/strava.py`
- MCP transport and tool dispatch moved into `routers/mcp.py` and `services/mcp.py`
- `notes` and `metrics` now have dedicated models, repositories, services, and routers
- `goals` now have dedicated models, repositories, services, and routers
- `activities` and calendar-week aggregation now live in dedicated models, repositories, services, and routers
- `weekly summary` and shared `app_settings` persistence now live in dedicated modules
- dashboard, recent-context, training-load, and Strava HTTP routes now live in dedicated routers
- MCP callback glue now lives in a dedicated adapter module instead of `main.py`

Still remaining in `main.py`:

- FastAPI app assembly, MCP router registration, and health endpoint

Recommended next slice:

- Sprint 2 can be considered structurally complete; next work should shift to tests, small cleanup passes, or product features

## Suggested Architecture Decisions

### 1. App composition

Keep [backend/app/main.py](/Users/jakubronkiewicz/Projekty/training-dashboard/backend/app/main.py:1) minimal:

- create FastAPI app
- register middleware
- include routers
- run startup initialization

### 2. Database access

Create a single `db.py` that owns:

- `DB_PATH`
- `get_db()`
- `init_db()`
- small shared DB helpers

### 3. Models

Move Pydantic models into domain-oriented modules instead of leaving them in the main entry file.

Example:

- weekly plans and adjustment payloads in `models/plans.py`
- Strava request/response models in `models/integrations.py`

### 4. Services

Business logic to extract first:

- `adjust_weekly_plan_data`
- plan comparison logic
- recent context and dashboard aggregation
- training load summary logic
- Strava import and stream enrichment

### 5. Repositories

Do not introduce a heavy repository pattern. Keep it thin:

- SQL queries grouped by domain
- explicit functions
- no generic base repository abstraction

That is a better fit for the current project size.

## Implementation Order

### Step 1. Establish module boundaries

- add `db.py`
- add `routers/`, `services/`, `repositories/`, and `models/`
- move only foundational utilities first

### Step 2. Extract plans domain

Start with plans because it already contains real domain behavior:

- plan models
- plan persistence
- plan comparison
- adjustment logic
- weekly plan routes

This is the best first slice because it is cohesive and already actively evolving.

### Step 3. Extract dashboard and training load logic

Move:

- dashboard aggregation
- recent context
- training load summaries

into service modules with route wrappers.

### Step 4. Extract Strava integration

Move:

- token handling
- import range resolution
- activity mapping
- stream backfill

into a dedicated integration service.

### Step 5. Extract remaining CRUD domains

Move:

- activities
- notes
- metrics
- goals
- weekly summary

into domain routers and repositories.

### Step 6. Extract MCP layer

Move MCP tool definitions and dispatch into a dedicated module so the API app and MCP transport are not tangled with general backend logic.

## Recommended Patterns

Use these patterns selectively:

- `Router + Service + Repository`
- `Composition root` in `main.py`
- `Pure helper functions` for aggregation/comparison logic
- `Domain-oriented modules` rather than technical dumping grounds

Avoid these for now:

- generic CRUD base classes
- dependency injection frameworks
- full DDD ceremony
- ORM migration just for architecture aesthetics

## Deliverables

### 1. New backend module structure

A coherent package layout under `backend/app/`.

### 2. Smaller `main.py`

Target: `main.py` should mainly bootstrap the app and include routers.

### 3. Plans domain extracted first

This should be the first completed vertical slice.

### 4. No endpoint regressions

Existing frontend and MCP flows should continue to work.

### 5. Basic verification path

At minimum:

- app imports cleanly
- backend starts
- core endpoints respond
- adaptive plan adjustment still works

## Risks

- moving too much at once can create subtle import/runtime breakage
- route extraction without service extraction only relocates complexity
- over-engineering abstractions would slow the project down

## Definition Of Done

- `main.py` is no longer the primary home for all backend logic
- plans are extracted into dedicated modules
- at least one more major domain is extracted after plans
- app startup remains simple
- endpoint behavior is preserved
- the resulting structure is easier to extend for the next roadmap phases

## Recommended First Slice

If we want the safest starting point, begin with:

1. `db.py`
2. `models/plans.py`
3. `repositories/plans.py`
4. `services/plans.py`
5. `routers/plans.py`

Then wire those modules back into the app before touching other domains.

## Follow-up After This Sprint

Once modularization is in place, the next backend-heavy features become much safer:

1. plan revision history
2. post-workout feedback storage
3. clearer moved/skipped/replaced plan semantics
