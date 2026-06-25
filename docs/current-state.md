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

## Recommended Next Step

The next major sprint should be:

- [docs/sprints/sprint-3-feedback-loop.md](sprints/sprint-3-feedback-loop.md)

That means moving into:

- post-workout feedback capture
- recovery-aware daily recommendation logic
- dashboard guidance based on subjective recovery signals
- MCP context updates for feedback and recommendation signals

## Areas That Are Still Intentionally Lightweight

- test coverage is still smoke-level rather than deep
- weekly plans are stored as JSON blobs by week
- feedback capture does not exist yet
- goal-aware planning is still shallow
- plan-to-activity explicit linking does not exist yet

## Good Starting Points For Future Work

If starting Sprint 3:

- backend persistence shape: `backend/app/db.py` plus a new feedback domain
- dashboard recommendation logic: `backend/app/services/dashboard.py` or a new recommendation service
- activities feedback entry UI: `frontend/src/views/Activities.vue`
- dashboard guidance UI: `frontend/src/views/Dashboard.vue`

## Working Assumption

Unless the roadmap changes, the default implementation direction should be:

1. finish lightweight coaching workflow improvements
2. keep logic deterministic and inspectable
3. avoid overbuilding storage or automation too early
