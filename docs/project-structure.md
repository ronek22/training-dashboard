# Project Structure

This is a practical map of the repository for day-to-day development.

## Top Level

- `backend/` — FastAPI app and tests
- `frontend/` — Vue app
- `mcp/` — local MCP server bridge
- `docs/` — roadmap index, roadmap archives, sprint plans, decisions, and durable repo context
- `docker-compose.yml` — local multi-service startup
- `justfile` — common developer commands
- `README.md` — setup and operator-facing instructions
- `CODEX.md` — repo-specific guidance for coding agents

## Backend

Root:

- `backend/app/main.py` — app composition root
- `backend/app/db.py` — SQLite path resolution and schema init
- `backend/tests/test_smoke_*.py` — backend smoke tests by area (activities, strength, goals, plans, context), sharing setup from `smoke_base.py`

### Models

- `models/activities.py` — activity payload shape
- `models/goals.py` — goal payload shape
- `models/integrations.py` — Strava request/response models
- `models/metrics.py` — metric payload shape
- `models/notes.py` — note payload shape
- `models/plans.py` — weekly plans, adjustments, revisions
- `models/settings.py` — modality restrictions and athlete-profile payload shape
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
- `services/ache_followups.py` — next-morning "better, same or worse?" threads for mild aches named in notes; optional expiring lift protection
- `services/dashboard.py` — dashboard aggregation, recent context, training load
- `services/goals.py` — goal creation and listing
- `services/kit.py` — kit wear (shoes, bikes with fitted parts, trainer): per-activity assignment by sport default, Strava gear, parent bike or manual choice; service log (wax, lube...) and replacement history; nearly-due status
- `services/meal_protein.py` — protein per meal on the Food day (threshold, light meals, top-ups) and the per-meal spread for the muscle-gain check
- `services/mcp.py` — MCP tool definitions and dispatch
- `services/metrics.py` — metric history and writes
- `services/notes.py` — note creation and listing
- `services/power_estimate.py` — physics power estimate for outdoor rides without a meter (load and ride type only) and its calibration check
- `services/plans.py` — plan serialization, adjustment, comparison semantics
- `services/run_dynamics.py` — Apple Watch running dynamics from HealthFit FIT files (`run_dynamics` table), matched to runs from any source
- `services/running_fitness.py` — Running page: VDOT (efforts, heart rate, resting HR), race predictions, training paces, comeback curve, form, power, build-up guard
- `services/settings.py` — app settings reads/writes including modality restrictions and athlete profile normalization
- `services/strava.py` — Strava import and stream backfill logic
- `services/weekly_summary.py` — weekly summary writes/reads

### Routers

- `routers/activities.py` — `/activities`, `/activities/stats`, `/calendar/weeks`
- `routers/dashboard.py` — `/dashboard`, `/training-load`, `/context/recent`
- `routers/goals.py` — `/goals`
- `routers/integrations.py` — Strava routes
- `routers/kit.py` — `/kit` (incl. replace, events, Strava gear), `/activities/{id}/kit`
- `routers/mcp.py` — `/mcp`
- `routers/metrics.py` — `/metrics`
- `routers/notes.py` — `/notes`
- `routers/plans.py` — `/plans/weekly`, `/plans/weekly/adjust`
- `routers/running.py` — `/running/fitness`, `/running/dynamics/scan`
- `routers/settings.py` — settings-backed athlete profile and modality restriction routes
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
- `views/Plan.vue` — weekly plans, plan-vs-actual view, in-app adjustment flow. It keeps page state and wiring; the rest lives in `plan/`:
  - components, each with its own scoped sheet next to it: `PlanDayGrid` (day cards), `PlanWeekEditor` (adjust remaining week, drag/move swaps), `PlanCoachingDiff` (coaching draft approval), `PlanWeekNotes` (reasoning, plan changes, goal alignment), `PlannedSessionDialog` (workout brief and planned-to-actual link), `CoachPromptDialog` (plan brief and plan feedback), `MinimumWeekDialog`
  - composables: `usePlanCoach` (coach planning/revision jobs), `useMinimumWeek`, `usePlanLinks`
  - pure modules (tested): `plan-helpers.mjs` (labels, formatting, plan/day predicates), `plan-editor.mjs` (editor state and swaps), `plan-week.mjs` (day match status, week metrics, strength rotation); `plan-storage.mjs` holds the weather location, coaching draft and request timeout
  - page styles in `plan/Plan.css`; the coaching-context section is `components/PlanInsights.vue`
- `views/Calendar.vue` — weekly training calendar
- `views/Goals.vue` — goal management and visibility; its goal card (`goals/GoalCard.vue`), add/edit dialog (`goals/GoalEditDialog.vue`), pure helpers (`goals/goal-helpers.mjs`, tested) and styles (`goals/*.css`) live in `goals/`
- `views/Activities.vue` — imported/manual activities
- `views/Notes.vue` — coach notes
- `views/Metrics.vue` — metric history and trends
- `views/Running.vue` — running fitness page; its charts and panels (`RunFitnessHero`, `RunRaceSimulator`, `RunTrainingPaces`, `RunComebackChart`, `RunPaceTrend`, `RunFormPanel`, `RunnerFigure`, `RunPowerPanel`) with the gait model `runner-gait.mjs` and tested helpers (`running-helpers.mjs`) live in `running/`

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
- `frontend/src/views/Dashboard.vue`
- `frontend/src/views/Mountains.vue`, `Athlete.vue`, `Strength.vue`, `StrengthWorkoutSession.vue` (over 1,500 lines each)
