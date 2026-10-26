# Current State

This file is a compact snapshot of what is implemented now and what should happen next.

## Product Position

The app has moved beyond a simple training log, but it is not yet a full coaching workflow.

Implemented foundations:

- activity history and filtering
- Strava import
- metrics
- coach notes
- a global floating Coach drawer available from every page, with separate persistent conversations, new-chat, switching, deletion, local Codex CLI replies, and read-only live training context; conversations can be linked to an activity and opened from its win card
- weekly plans
- plan-vs-actual comparison
- dashboard aggregation and training-load views
- MCP read/write access
- one-click, non-interactive Codex planning that creates or updates the current week through MCP
- optional pre-generation Codex planning briefs for schedule constraints, recovery feedback, and week-specific preferences
- post-generation Codex plan feedback that revises eligible remaining days and records the plan change
- a rule-based session read on Activity Detail (comparisons with your own past sessions), plus questions answered by Codex through MCP

## Recently Completed

One line per shipped feature, newest first. The full entry (what shipped, API, UI, what was not done, how it was verified) lives in the month's file under `docs/shipped/`; open only the one you need. Undated sprint and phase records are in `shipped/earlier.md`.

When a feature ships: add its full entry at the top of `docs/shipped/YYYY-MM.md` (create the file for a new month, same shape: `### Title`, a blank line, then `YYYY-MM-DD: summary...`), and add its line at the top of this list.

- 2026-10-26 — Kit wear: shoes, chain and tyres (`shipped/2026-10.md`)
- 2026-10-26 — Follow-up on aches you mention (`shipped/2026-10.md`)
- 2026-10-26 — Sleep payback plan (`shipped/2026-10.md`)
- 2026-10-26 — Estimated power for outdoor rides (`shipped/2026-10.md`)
- 2026-10-26 — Heart-rate load on the TSS scale (`shipped/2026-10.md`)
- 2026-10-26 — Planned-day brief on the dashboard week (`shipped/2026-10.md`)
- 2026-10-26 — Hikes apart from walks (`shipped/2026-10.md`)
- 2026-10-26 — Lift records by body area (`shipped/2026-10.md`)
- 2026-10-26 — Structured workout briefs (`shipped/2026-10.md`)
- 2026-10-26 — Tick off the rehab routine (`shipped/2026-10.md`)
- 2026-10-26 — Injury-aware weekly planning (`shipped/2026-10.md`)
- 2026-10-25 — Strava photos on the trip recap (`shipped/2026-10.md`)
- 2026-10-25 — Ideas when nothing is planned (`shipped/2026-10.md`)
- 2026-10-15 — Milestone celebrations (`shipped/2026-10.md`)
- 2026-10-15 — Gentle strength phases (`shipped/2026-10.md`)
- 2026-10-15 — Food targets follow the planned week (`shipped/2026-10.md`)
- 2026-10-15 — Block recap at the end of every arc block (`shipped/2026-10.md`)
- 2026-10-15 — Winter arc adapts to lost weeks (`shipped/2026-10.md`)
- 2026-10-15 — Sunday planning flow (`shipped/2026-10.md`)
- 2026-10-15 — Each week builds on the last one (`shipped/2026-10.md`)
- 2026-10-15 — Fitness and fatigue ahead on Plan (`shipped/2026-10.md`)
- 2026-10-15 — Season timeline on Plan (`shipped/2026-10.md`)
- 2026-10-15 — Next four weeks on Plan (`shipped/2026-10.md`)
- 2026-10-15 — Eat enough before the sessions that matter (`shipped/2026-10.md`)
- 2026-10-15 — Winter arc for cycling (`shipped/2026-10.md`)
- 2026-10-15 — Backup restore drill (`shipped/2026-10.md`)
- 2026-10-14 — Stall blocks shape later suggestions (`shipped/2026-10.md`)
- 2026-10-14 — Data-quality inbox (`shipped/2026-10.md`)
- 2026-10-14 — Lift and hard-ride clash rule (`shipped/2026-10.md`)
- 2026-10-14 — Automatic database backups (`shipped/2026-10.md`)
- 2026-10-14 — Fixed-step adjustable dumbbells (`shipped/2026-10.md`)
- 2026-10-14 — Plates per side and suggested warm-ups (`shipped/2026-10.md`)
- 2026-10-14 — Back from the mountains (`shipped/2026-10.md`)
- 2026-10-14 — Mountain trip recap (`shipped/2026-10.md`)
- 2026-10-13 — Detailed streams for the whole Strava history (`shipped/2026-10.md`)
- 2026-10-13 — Ready for full Strava history (`shipped/2026-10.md`)
- 2026-10-13 — Season in review (`shipped/2026-10.md`)
- 2026-10-13 — Roadmap page shows open threads and what shipped (`shipped/2026-10.md`)
- 2026-10-13 — Polish meal names: Dinner = obiad, Supper = kolacja (`shipped/2026-10.md`)
- 2026-10-13 — Shopping list from planned dinners (`shipped/2026-10.md`)
- 2026-10-13 — Recovery days (`shipped/2026-10.md`)
- 2026-10-09 — Mountain trip days (`shipped/2026-10.md`)
- 2026-10-09 — Return from illness (`shipped/2026-10.md`)
- 2026-10-08 — Compact coaching context for MCP (`shipped/2026-10.md`)
- 2026-10-07 — Monthly letter from your coach (`shipped/2026-10.md`)
- 2026-10-07 — Hike activity page: map first (`shipped/2026-10.md`)
- 2026-10-07 — Mountains: trail coverage, summits and places (`shipped/2026-10.md`)
- 2026-10-07 — Coach drawer: check-ins, unread replies, groups and suggestions (`shipped/2026-10.md`)
- 2026-10-07 — Three wins, one focus (`shipped/2026-10.md`)
- 2026-10-07 — "Feeling flat" / "Short on time" on Today (`shipped/2026-10.md`)
- 2026-10-07 — Session win and session-linked coach chats (`shipped/2026-10.md`)
- 2026-10-06 — Session read replaces the coach analysis (`shipped/2026-10.md`)
- 2026-10-05 — Aerobic fitness without a test (`shipped/2026-10.md`)
- 2026-10-05 — Two-minute downshift (`shipped/2026-10.md`)
- 2026-10-05 — Minimum viable week (`shipped/2026-10.md`)
- 2026-10-05 — Life-load tags (`shipped/2026-10.md`)
- 2026-10-05 — Return-to-run tracker (`shipped/2026-10.md`)
- 2026-10-05 — One trustworthy check (`shipped/2026-10.md`)
- 2026-10-05 — "What worked" memory (`shipped/2026-10.md`)
- 2026-10-04 — Pre-session brief (`shipped/2026-10.md`)
- 2026-10-02 — Personal best wall (`shipped/2026-10.md`)
- 2026-09-30 — Training volume trend alert (`shipped/2026-09.md`)
- 2026-09-29 — Goal intelligence (Sprint 39, complete) (`shipped/2026-09.md`)
- 2026-09-28 — Structured cycling workouts with Zwift export (`shipped/2026-09.md`)
- 2026-09-28 — Recovery (simplified 2026-09-28) (`shipped/2026-09.md`)
- 2026-09-14 — HEAD COACH and weekly specialists (`shipped/2026-09.md`)

## Recommended Next Step

There is no active roadmap. Pick the next piece of work from the Ideas board or from the open threads in `docs/roadmap.md`, and record it when it ships (see "Recently Completed" above).

## Areas That Are Still Intentionally Lightweight

- test coverage is still smoke-level rather than deep
- weekly plans are stored as JSON blobs by week
- goal-aware planning is still lightweight rather than deeply automated
- richer goal families now exist, but deeper family-specific progress and readiness modeling is still intentionally lightweight
- local backend test execution still depends on having the Python app dependencies installed

## Good Starting Points For Future Work

Where to start in the code:

- plan comparison and serialization: `backend/app/services/plans.py`
- activity persistence and linking: `backend/app/services/activities.py`
- activity SQL changes: `backend/app/repositories/activities.py`
- coaching summary and heuristics: `backend/app/services/coaching.py`
- coaching inspection and handoff UI: `frontend/src/views/Dashboard.vue` and `frontend/src/views/Plan.vue`
- goal schema and progress logic: `backend/app/models/goals.py`, `backend/app/repositories/goals.py`, and `backend/app/services/goals.py`
- settings-backed athlete context: `backend/app/services/settings.py` and `backend/app/repositories/settings.py`
- athlete-facing goal and profile UI: `frontend/src/views/Goals.vue` and `frontend/src/views/Athlete.vue`
- calendar aggregation and month view: `backend/app/services/activities.py` and `frontend/src/views/Calendar.vue`
- docs-backed planning visibility: `docs/roadmap.md` (open threads), `docs/current-state.md` (shipped index) with `docs/shipped/` (full entries), `docs/sprints/` (archive), and `backend/app/services/planning_status.py`

## Working Assumption

Unless the athlete decides otherwise, new work should:

1. keep logic deterministic and inspectable
2. prefer structured templates over vague free-form modeling
3. keep plan changes approval-based
