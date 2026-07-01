# Sprint 23: Activity Detail View And On-Demand Strava Caching

## Status

Current status:

- planned
- follows completed Sprint 22 benchmark sessions and test-result visibility

Starting point:

- the app already imports and stores activity summaries from Strava
- activities are visible in list and planning contexts, but there is no dedicated detail view
- richer detail such as route geometry, charts, laps, or stream-derived visuals are not yet available as athlete-facing review surfaces

Dependency note:

- benchmark and feedback visibility are now stronger, so activity review is the next obvious surface to deepen
- the next step should add richer single-activity inspection without turning the regular Strava sync into a heavy full-detail backfill

## Objective

Introduce an activity detail view with richer visuals and stats, while fetching and caching Strava detail data only when the athlete opens a specific activity.

This sprint should move the app from:

- `activity summaries exist, but detailed review still depends on leaving the app`

to:

- `the app can open one activity, fetch its richer Strava detail once, cache it locally, and render a meaningful review view`

## Why This Sprint

That gap matters because:

- athletes need a better way to review one session in context instead of scanning only list rows
- post-workout feedback becomes more useful when it sits next to route, effort, and elevation detail
- automatic full-detail sync would add cost and latency that are unnecessary for most activities
- an on-demand cache is a pragmatic bridge between lightweight sync and richer training analysis

## User Story

As an athlete reviewing a completed workout, I want to open one activity and see maps, charts, stats, and my own feedback in one place, so I can inspect what actually happened without going back to Strava.

## Sprint Scope

### In scope

- dedicated activity detail screen or dialog
- on-demand Strava detail fetch for a single activity when opened
- local caching of fetched detail so later opens do not re-fetch unnecessarily
- map, core charts, summary stats, and feedback visibility for one activity

### Out of scope

- full bulk backfill of detailed activity payloads during normal sync
- advanced cross-activity analytics built from detailed streams
- segment analysis, power curve engine, or route editing
- manual GPX handling outside Strava-backed activities

## Product Outcome

After this sprint:

- athletes can open an activity detail view from the app
- the first open can fetch richer Strava detail and store it locally
- later opens should use cached detail unless an explicit refresh path is added later
- subjective feedback and key workout stats are visible together in one review surface

## Proposed Feature Slice

### 1. Activity detail surface

Recommended first support:

- open-from-list activity detail entry point
- route map when route or polyline data exists
- basic effort charts such as speed or pace, heart rate, elevation, and optionally power
- compact stats block with duration, distance, pace or speed, heart rate, elevation, watts, and similar available fields
- visible feedback block for RPE, energy, soreness, pain, and note when provided

Recommended direction:

- keep the first version focused on one useful inspection screen, not a full analysis suite
- gracefully degrade when an activity lacks certain stream types such as heart rate or power

### 2. On-demand Strava detail caching

Recommended first support:

- regular activity sync continues to import lightweight summary rows only
- opening an activity detail view checks whether richer local detail already exists
- if missing, the backend fetches activity detail from Strava for that activity only
- fetched detail and streams are normalized and cached in app storage for future reads

Recommended direction:

- treat detailed Strava reads as a read-through cache
- keep cache keys explicit per activity and track fetched timestamps or versions conservatively

## Backend Deliverables

### 1. Cached activity detail contract

Likely targets:

- `backend/app/services/activities.py`
- `backend/app/services/strava.py`
- `backend/app/db.py`

Deliver:

- one activity-detail read endpoint
- storage for cached detailed activity payloads or normalized detail fields
- storage for route or stream detail needed by charts and map rendering
- backend logic that fetches from Strava only when detail is missing locally

### 2. Detail shaping for frontend use

Likely targets:

- `backend/app/services/activities.py`

Deliver:

- normalized activity detail payload with summary stats, chart-ready series, feedback, and fetch status
- clear missing-data behavior for route, heart rate, power, cadence, or elevation gaps
- conservative cache metadata such as `fetched_at` or `source_status`

### 3. Coverage

Deliver:

- smoke assertions for reading cached detail after first fetch
- at least one case where first read fetches and later read reuses cached data
- at least one case where feedback appears in the detail contract when present

## Frontend Deliverables

### 1. Activity detail view

Likely targets:

- `frontend/src/views/Activities.vue`
- `frontend/src/router.js`
- new activity detail component or view if needed

Deliver:

- activity detail navigation from the activities list
- map rendering for route data when available
- chart sections for speed or pace, heart rate, elevation, and other available streams
- visible summary stats and athlete feedback block

### 2. Loading and cache-aware states

Deliver:

- first-open loading state while Strava detail is fetched
- empty or partial states when route or streams are unavailable
- clear indication that detail has been loaded or cached without over-explaining the backend

## Definition Of Done

Sprint 23 should be considered complete when:

- an activity can be opened in a dedicated detail view
- the first open can fetch richer Strava detail for that activity only
- fetched detail is cached locally and reused on later reads
- the detail view shows at least map, core charts, summary stats, and feedback when available
- smoke coverage includes the on-demand fetch and cache reuse behavior
