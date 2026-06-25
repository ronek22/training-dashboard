# Architecture

This document is a durable orientation guide for the current system shape.

It is not intended to describe every implementation detail. It should answer:

- what the main runtime pieces are
- where core responsibilities live
- how data flows through the app
- where to make changes for common feature work

## System Overview

The app has three main surfaces:

1. FastAPI backend
2. Vue 3 frontend
3. MCP interface for chat-based read/write access

Current stack:

- backend: FastAPI + SQLite
- frontend: Vue 3 + Vite
- integration transport: HTTP API plus MCP JSON-RPC endpoint

## Backend Shape

The backend is intentionally modular but still lightweight.

Main entrypoint:

- [backend/app/main.py](../backend/app/main.py)

Responsibilities:

- create the FastAPI app
- register CORS
- include domain routers
- initialize SQLite schema
- register the MCP router

Domain structure:

- `models/` — Pydantic request/response and domain models
- `repositories/` — thin SQL access helpers
- `services/` — business logic and aggregation
- `routers/` — HTTP endpoints and request wiring
- `adapters/` — integration glue, currently MCP-related

Database bootstrap:

- [backend/app/db.py](../backend/app/db.py)

This file owns:

- `TRAINING_DB_PATH` resolution
- `get_db()`
- `init_db()`
- additive SQLite schema creation

## Frontend Shape

The frontend is a small routed SPA.

Main files:

- [frontend/src/main.js](../frontend/src/main.js)
- [frontend/src/App.vue](../frontend/src/App.vue)
- [frontend/src/router.js](../frontend/src/router.js)
- [frontend/src/stores/api.js](../frontend/src/stores/api.js)

Responsibilities:

- `router.js` maps top-level pages
- `stores/api.js` is the shared HTTP client wrapper
- `views/` contains page-level features
- `components/` contains reusable UI pieces

The frontend is currently view-driven rather than heavily componentized. Most feature logic still lives close to the page that uses it.

## Core Product Flows

### Activities

Primary flow:

- activities are created directly or imported from Strava
- activities feed dashboard summaries, calendar views, and plan comparison

Relevant backend areas:

- `routers/activities.py`
- `services/activities.py`
- `repositories/activities.py`

Relevant frontend area:

- [frontend/src/views/Activities.vue](../frontend/src/views/Activities.vue)

### Weekly Plans

Primary flow:

- a weekly plan is stored as one row per week with `days_json`
- the Plan page reads weekly plans through `/plans/weekly`
- the backend enriches each day with plan-vs-actual comparison data
- the Plan page can partially adjust open days through `/plans/weekly/adjust`
- adjustments now also create entries in `plan_revisions`

Relevant backend areas:

- `routers/plans.py`
- `services/plans.py`
- `repositories/plans.py`
- `models/plans.py`

Relevant frontend area:

- [frontend/src/views/Plan.vue](../frontend/src/views/Plan.vue)

### Dashboard and Context

Primary flow:

- dashboard responses aggregate multiple domains into one coaching-oriented payload
- training-load summaries and recent context are separate backend reads
- the Dashboard view renders the current plan and training-load interpretation

Relevant backend areas:

- `routers/dashboard.py`
- `services/dashboard.py`

Relevant frontend area:

- [frontend/src/views/Dashboard.vue](../frontend/src/views/Dashboard.vue)

### Goals

Goals are stored independently today and are visible in the UI, but they are not yet deeply coupled to weekly planning logic.

Relevant backend areas:

- `routers/goals.py`
- `services/goals.py`
- `repositories/goals.py`

Relevant frontend area:

- [frontend/src/views/Goals.vue](../frontend/src/views/Goals.vue)

### Notes and Metrics

These are supporting coaching/context domains.

Notes:

- coach observations and day-level qualitative context

Metrics:

- longitudinal scalar data such as weight, resting HR, FTP, or custom numeric values

### Strava Integration

The backend owns import and stream backfill behavior. The frontend mostly triggers it and shows status.

Relevant backend areas:

- `routers/integrations.py`
- `services/strava.py`
- `services/settings.py`

## MCP Surface

The app exposes the same training data and plan-writing capabilities through MCP.

Relevant files:

- [backend/app/routers/mcp.py](../backend/app/routers/mcp.py)
- [backend/app/services/mcp.py](../backend/app/services/mcp.py)
- [backend/app/adapters/mcp.py](../backend/app/adapters/mcp.py)
- [mcp/server.py](../mcp/server.py)

Current shape:

- local `stdio` MCP server for Claude Desktop still exists in `mcp/server.py`
- backend also exposes remote MCP over HTTP at `/mcp`

## Design Intent

Important current architectural choices:

- stay with SQLite for now
- keep repositories thin and explicit
- keep most business rules in services, not routers
- preserve inspectable and deterministic planning behavior over opaque automation
- add features incrementally instead of rewriting storage or app structure

## Where To Change Things

If you need to:

- add or change an API endpoint: start in `routers/`
- change data validation or payload shape: start in `models/`
- change business behavior: start in `services/`
- change SQL reads/writes: start in `repositories/`
- change a page workflow: start in `frontend/src/views/`
- change shared API calls: start in `frontend/src/stores/api.js`

## Known Architectural Limits

These are acceptable for the current repo size, but worth keeping in mind:

- weekly plans are still stored as `days_json` blobs rather than fully normalized tables
- frontend view files are fairly large, especially `Plan.vue` and `Dashboard.vue`
- there is only light automated test coverage today
- MCP write access is powerful and still lightly guarded
