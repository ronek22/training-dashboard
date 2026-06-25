# Project Structure

This is a practical map of the repository for day-to-day development.

## Top Level

- `backend/` — FastAPI app and tests
- `frontend/` — Vue app
- `mcp/` — local MCP server bridge
- `docs/` — roadmap, sprint plans, decisions, and durable repo context
- `docker-compose.yml` — local multi-service startup
- `Makefile` — common developer commands
- `README.md` — setup and operator-facing instructions
- `CODEX.md` — repo-specific guidance for coding agents

## Backend

Root:

- `backend/app/main.py` — app composition root
- `backend/app/db.py` — SQLite path resolution and schema init
- `backend/tests/test_app_smoke.py` — lightweight backend smoke tests

### Models

- `models/activities.py` — activity payload shape
- `models/goals.py` — goal payload shape
- `models/integrations.py` — Strava request/response models
- `models/metrics.py` — metric payload shape
- `models/notes.py` — note payload shape
- `models/plans.py` — weekly plans, adjustments, revisions
- `models/weekly_summary.py` — stored weekly summary shape

### Repositories

- `repositories/activities.py` — activity SQL reads/writes
- `repositories/goals.py` — goal SQL
- `repositories/metrics.py` — metric SQL
- `repositories/notes.py` — note SQL
- `repositories/plans.py` — weekly plan and plan revision SQL
- `repositories/settings.py` — app settings persistence
- `repositories/weekly_summary.py` — weekly summary SQL

### Services

- `services/activities.py` — activity CRUD and calendar-week aggregation
- `services/dashboard.py` — dashboard aggregation, recent context, training load
- `services/goals.py` — goal creation and listing
- `services/mcp.py` — MCP tool definitions and dispatch
- `services/metrics.py` — metric history and writes
- `services/notes.py` — note creation and listing
- `services/plans.py` — plan serialization, adjustment, comparison semantics
- `services/settings.py` — app settings reads/writes
- `services/strava.py` — Strava import and stream backfill logic
- `services/weekly_summary.py` — weekly summary writes/reads

### Routers

- `routers/activities.py` — `/activities`, `/activities/stats`, `/calendar/weeks`
- `routers/dashboard.py` — `/dashboard`, `/training-load`, `/context/recent`
- `routers/goals.py` — `/goals`
- `routers/integrations.py` — Strava routes
- `routers/mcp.py` — `/mcp`
- `routers/metrics.py` — `/metrics`
- `routers/notes.py` — `/notes`
- `routers/plans.py` — `/plans/weekly`, `/plans/weekly/adjust`
- `routers/weekly_summary.py` — `/weekly`

### Adapters

- `adapters/mcp.py` — dependency wiring for the MCP route

## Frontend

Root:

- `frontend/src/main.js` — app bootstrap
- `frontend/src/App.vue` — top-level shell and navigation
- `frontend/src/router.js` — route table
- `frontend/src/stores/api.js` — Axios wrapper for backend endpoints
- `frontend/src/style.css` — global styles

### Views

- `views/Dashboard.vue` — main coaching/dashboard surface
- `views/Plan.vue` — weekly plans, plan-vs-actual view, in-app adjustment flow
- `views/Calendar.vue` — weekly training calendar
- `views/Goals.vue` — goal management and visibility
- `views/Activities.vue` — imported/manual activities
- `views/Notes.vue` — coach notes
- `views/Metrics.vue` — metric history and trends

### Components

- `components/ActivityIcon.vue` — activity/session icon rendering
- `components/TrainingLoadPanel.vue` — load analysis and planning signal UI

## MCP

- `mcp/server.py` — local stdio MCP bridge
- `mcp/requirements.txt` — MCP dependencies
- `mcp/claude_desktop_config.json` — example Claude Desktop config

## Useful Change Paths

For common tasks:

- adaptive planning behavior: `backend/app/services/plans.py` and `frontend/src/views/Plan.vue`
- dashboard interpretation: `backend/app/services/dashboard.py` and `frontend/src/views/Dashboard.vue`
- Strava behavior: `backend/app/services/strava.py`
- API contract updates: `backend/app/models/*`, `backend/app/routers/*`, `frontend/src/stores/api.js`
- new persistent domain: `models/` + `repositories/` + `services/` + `routers/`

## Current Heavy Files

These are not problems by themselves, but they are the files most likely to need careful reading before changes:

- `backend/app/services/dashboard.py`
- `backend/app/services/plans.py`
- `frontend/src/views/Plan.vue`
- `frontend/src/views/Dashboard.vue`
