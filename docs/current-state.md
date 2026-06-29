# Current State

This file is a compact snapshot of what is implemented now and what should happen next.

## Product Position

The app has moved beyond a simple training log, but it is not yet a full coaching workflow.

Implemented foundations:

- activity history and filtering
- Strava import
- metrics
- coach notes
- weekly plans
- plan-vs-actual comparison
- dashboard aggregation and training-load views
- MCP read/write access

## Recently Completed

### Backend modularization

The backend has already been split into routers, services, repositories, models, and DB bootstrap code.

Practical result:

- `main.py` is now a composition root
- domain logic is no longer concentrated in one oversized file

### Phase 1 adaptive planning

Phase 1 can now be treated as effectively complete.

Completed slices:

- in-app `Adjust Remaining Week` flow
- protected-day editing rules
- save-result feedback in the Plan UI
- plan revision visibility with lightweight `plan_revisions`
- clearer `moved` / `skipped` / `replaced` semantics
- small Plan UI polish pass for revision and status readability

### Sprint 3 feedback loop

Sprint 3 can now be treated as functionally implemented, even if docs and tests still need cleanup.

Completed slices:

- structured post-workout feedback attached to activities
- lightweight feedback entry from Activities and Calendar
- recovery-aware daily recommendation on the Dashboard
- recent feedback and recommendation signals exposed through MCP/context
- generic pain / niggle signal instead of heel-specific feedback
- initial goal-aware context surfaced in weekly plans

### Sprint 4 goal-aware planning

Sprint 4 can now be treated as complete for the current roadmap slice.

Completed slices:

- weekly plans include active-goal context at the week level
- plan days can expose which goals a session supports
- Goals view shows planning-relevant pacing guidance
- recent dashboard and MCP context now carry compact active-goal planning signals
- plan and goal workflows now feel more intentionally connected

### Sprint 5 planned-to-actual linking

Sprint 5 can now be treated as complete for the current roadmap slice.

Completed slices:

- weekly plan days now carry stable planned-session IDs
- activities can explicitly link back to planned sessions
- plan comparison distinguishes explicit, inferred, and unmatched execution states
- Plan UI supports lightweight on-demand review and relinking
- active plan context exposed through dashboard and MCP reads now carries linkage-aware comparison data

### Sprint 6 structured workout intent

Sprint 6 can now be treated as complete for the current roadmap slice.

Completed slices:

- planned sessions and activities now support optional structured workout intent
- Plan, Activities, Calendar, and feedback flows can surface or edit intent in lightweight ways
- inferred comparison can distinguish same-type sessions with different intended purpose
- recent dashboard and MCP context now includes compact intent-aware summaries for coaching reads

### Sprint 7 one-shot coaching

Sprint 7 can now be treated as complete for the current roadmap slice.

Completed slices:

- one-shot weekly coaching is now available through a deterministic backend service plus MCP action
- a read-only weekly coaching route exists for local inspection and testing
- coaching output includes structured execution, recovery, goal, recommendation, next-session, and preview-adjustment fields
- Dashboard now exposes the weekly coaching read in-app and can hand a preview adjustment into the Plan editor
- weekly coaching heuristics are now grounded in explicit linking, workout intent, recent subjective feedback, and lightweight goal pressure

### Sprint 8 plan diff and roadmap visibility

Sprint 8 can now be treated as complete for the current roadmap slice.

Completed slices:

- coaching-proposed weekly adjustments now expose explicit before/after diff data
- the Plan view now requires explicit approval before saving a coaching-generated adjustment
- coaching review can still hand off into the editable week flow when manual changes are needed
- roadmap and sprint progress are now visible in-app through a read-only docs-backed view
- backend planning-status parsing now reads stable markdown structure from `docs/`
- Docker-backed backend runs can access the docs mount needed for roadmap visibility

### Sprint 9 app redesign and information hierarchy

Sprint 9 can now be treated as complete for the current roadmap slice.

Completed slices:

- `Plan` now gives the current week stronger visual priority than historical weeks
- coaching approvals, revisions, changed sessions, and editable/protected distinctions are easier to scan in the planning workflow
- `Dashboard` now emphasizes today's guidance and weekly coaching more clearly than secondary analytics
- shared visual hierarchy across the shell and primary views is less flat and more directed
- `Calendar` now supports both weekly and full-month review with weekly summary context in month view
- recent execution patterns are now summarized across multiple weeks in both `Dashboard` and `Plan`
- multi-week adherence and intent-alignment trend analysis is now available through deterministic backend summaries
- weekly coaching now uses stronger deterministic heuristics across recent execution patterns, revision churn, recovery signals, and goal pressure
- weekly coaching rationale and risk reporting now expose clearer recent-pattern summaries without breaking the structured contract

### Sprint 13 goal progress and planning forecasts

Sprint 13 can now be treated as complete for the current roadmap slice.

Completed slices:

- active goals now expose deterministic forecast fields including recent pace, projected finish, projected gap, and required weekly pace
- goals now carry compact risk summaries so pace pressure is easier to inspect across API, MCP, and UI surfaces
- `Goals` now shows explicit forecast and risk cards rather than only lightweight pace guidance
- `Dashboard` now surfaces aggregate goal pressure and more visible goal-risk cues for short-horizon decisions
- `Plan` now highlights higher-pressure goal-supporting sessions more clearly in week context
- coaching and recent-context summaries now reason about goal pressure using the new forecast/risk layer
- smoke coverage now includes forecast fields and a case where a behind goal changes visible planning guidance

## Recommended Next Step

The next major sprint should be:

- Sprint 14 modality restrictions and injury-aware coaching should follow now that goal pressure and forecasts are more visible

That means moving into:

- making modality restrictions and injury signals first-class planning inputs
- teaching coaching and plan adjustment flows when to protect or avoid specific session types
- building on the goal-pressure and recovery-aware coaching surfaces now already in place

## Areas That Are Still Intentionally Lightweight

- test coverage is still smoke-level rather than deep
- weekly plans are stored as JSON blobs by week
- goal-aware planning is still lightweight rather than deeply automated
- MCP coaching still requires multiple reads rather than one opinionated weekly coaching action
- local backend test execution still depends on having the Python app dependencies installed

## Good Starting Points For Future Work

If continuing after Sprint 9:

- plan comparison and serialization: `backend/app/services/plans.py`
- activity persistence and linking: `backend/app/services/activities.py`
- activity SQL changes: `backend/app/repositories/activities.py`
- coaching summary and heuristics: `backend/app/services/coaching.py`
- coaching inspection and handoff UI: `frontend/src/views/Dashboard.vue` and `frontend/src/views/Plan.vue`
- calendar aggregation and month view: `backend/app/services/activities.py` and `frontend/src/views/Calendar.vue`
- docs-backed planning visibility: `docs/roadmap.md`, `docs/current-state.md`, and `docs/sprints/`
- sprint planning direction: `docs/sprints/sprint-10-coaching-memory-and-weekly-narrative-history.md` through `sprint-13-goal-progress-and-planning-forecasts.md`

## Working Assumption

Unless the roadmap changes, the default implementation direction should be:

1. finish lightweight coaching workflow improvements
2. build on explicit planned-to-actual linkage and approval history before adding heavier automation
3. keep logic deterministic and inspectable
4. avoid overbuilding storage or automation too early
