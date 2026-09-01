# Current State

This file is a compact snapshot of what is implemented now and what should happen next.

## Product Position

The app has moved beyond a simple training log, but it is not yet a full coaching workflow.

Implemented foundations:

- activity history and filtering
- Strava import
- metrics
- coach notes
- a global floating Coach drawer available from every page, with separate persistent conversations, new-chat, switching, deletion, local Codex CLI replies, and read-only live training context
- weekly plans
- plan-vs-actual comparison
- dashboard aggregation and training-load views
- MCP read/write access
- one-click, non-interactive Codex planning that creates or updates the current week through MCP
- optional pre-generation Codex planning briefs for schedule constraints, recovery feedback, and week-specific preferences
- post-generation Codex plan feedback that revises eligible remaining days and records the plan change
- always-visible workout analysis on Activity Detail with one-click Codex generation through MCP

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
- a later dashboard simplification replaces the long analytics feed with a daily decision surface: today’s call, readiness and check-in context, the current week, three priorities, recent sessions, and explicit routes into deeper views

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

### Sprint 14 modality restrictions and injury-aware coaching

Sprint 14 can now be treated as complete for the current roadmap slice.

Completed slices:

- users can persist modality restrictions for running, riding, and strength
- coaching now adapts next-session suggestions and rationale to active restrictions
- goals can become explicitly constrained instead of only looking behind pace
- `Dashboard`, `Goals`, and `Plan` now surface restriction-aware cues and constrained states
- smoke coverage includes restriction-aware goal and coaching behavior

### Sprint 15 athlete profile and planning preferences

Sprint 15 can now be treated as complete for the current roadmap slice.

Completed slices:

- users can persist a lightweight athlete profile with focus, modality priorities, long-session days, and planning notes
- dashboard and recent-context reads now expose a deterministic `athlete_brief` instead of relying only on inferred athlete context
- weekly coaching rationale can reference athlete focus, current block, long-session preferences, and planning notes
- `Goals` now provides compact athlete-profile editing alongside restriction management
- `Dashboard` now surfaces athlete context as secondary reference context near coaching history instead of treating it like a top-level daily signal
- smoke coverage now includes athlete-profile persistence and readback expectations

### Sprint 16 richer goal families

Sprint 16 can now be treated as complete for the current roadmap slice.

Completed slices:

- goals now support explicit accumulation, process, event-performance, and benchmark families
- richer goal reads are normalized across API, dashboard context, coaching context, and UI surfaces
- `Goals` now supports family-aware creation with type-specific fields and lightweight in-form guidance
- goal cards, dashboard goal visibility, and plan goal context now show clearer structured goal meaning instead of treating every target like pure volume
- recurring weekly, monthly, and yearly goal windows now float with the active calendar period instead of staying pinned to stale stored dates
- count-based goal presentation now treats sessions and activity counts as discrete values rather than fractional pacing noise
- smoke coverage now includes richer goal-family creation plus current-window regression checks for recurring goals

### Sprint 17 goal-aware session requirements and conflicts

Sprint 17 can now be treated as complete for the current roadmap slice.

Completed slices:

- active goals now expose deterministic weekly requirement summaries and normalized requirement types
- plan goal context now shows requirement-aware support, unsupported goals, and weaker-support gaps instead of only generic goal matching
- dashboard and weekly coaching now surface compact conflict, tradeoff, and deprioritization signals when goals compete
- `Goals`, `Plan`, and `Dashboard` now show requirement-focused cues so it is clearer why a session matters and what is still missing
- smoke coverage now includes multiple goal-family requirement mappings plus cases for unsupported goals and visible goal tradeoffs

### Sprint 18 rule-based workout templates and rotation state

Sprint 18 can now be treated as complete for the current roadmap slice.

Completed slices:

- settings now persist reusable strength workout templates plus explicit rotation state and skip behavior
- generic strength plan days are normalized into named templates like `Workout A` instead of staying generic
- completing a linked template-backed strength session advances the persisted next-workout pointer
- missed strength sessions stay pending so later weekly plan generation postpones them instead of silently skipping ahead
- restriction-aware template assignment can delay lower-body strength while running is limited or blocked
- `Goals`, `Plan`, and `Dashboard` now expose the current strength rotation and next programmed workout

### Sprint 28 heart-rate zones in activity detail and dashboard

Sprint 28 can now be treated as complete for the current roadmap slice.

Completed slices:

- activity detail now shows compact heart-rate zone summaries from cached Strava heart-rate and time streams
- dashboard now summarizes recent heart-rate zone accumulation with explicit zone-2 emphasis and coverage state
- Strava stream backfill now populates cached stream detail needed for zone review on previously imported activities
- heart-rate zone boundaries now follow the documented explicit running and cycling HR ranges
- UI treatment now makes zone distribution more compact, color-coded, and easier to scan in both dashboard and activity detail

### Sprint 29 LLM workout analysis via MCP for activity detail

Sprint 29 can now be treated as complete for the current roadmap slice.

Completed slices:

- activity detail now exposes a dedicated AI workout-analysis block with compact preview and modal detail
- MCP now exposes single-workout analysis reads and writes through `get_activity_analysis_context`, `save_activity_analysis`, and related analysis request state
- ChatGPT-facing prompt flow now guides the client toward the deterministic analysis context and away from legacy notes writes
- saved workout analyses are persisted back into the app with stale, unavailable, pending, and failure states
- activity-detail charts now share hover state across panels and project the hovered point back onto the route map

### Sprint 30 readiness and fatigue foundation

Sprint 30 can now be treated as complete for the current roadmap slice.

Completed slices:

- dashboard now surfaces a compact readiness read next to daily guidance with explicit short-horizon state
- coaching now consumes a shared readiness summary with state, reasons, limitations, and next-48-hour guidance
- recent-context and MCP-facing reads now expose the same deterministic readiness payload instead of requiring downstream reconstruction
- readiness now distinguishes `ready`, `watch`, `strained`, and `insufficient_data` while staying conservative about missing evidence
- readiness now leads with modeled fitness, short-term fatigue, form, and the latest subjective check-in; ordinary consistency, long easy sessions, and missing Zone 2 flags no longer create a strain state by themselves
- frontend dashboard cleanup removed duplicated athlete-context and strength-rotation reference blocks so the readiness layer stays closer to the main decision flow

### Sprint 32 planned-vs-actual workout quality

Sprint 32 can now be treated as complete for the current roadmap slice.

Completed slices:

- linked completed sessions now receive conservative, intent-aware execution-quality reads when evidence supports them
- easy, long, tempo, interval, race-specific, and enriched strength intents have a narrow first-pass evaluator
- results preserve explicit matched, partial, drifted, limited-evidence, and unavailable states with inspectable reasons and limitations
- activity detail and plan review surface execution quality without treating missing evidence as poor execution
- weekly coaching and multi-week execution summaries distinguish workout-quality misses from simple non-completion

### Phase 5 coaching workflow and analysis

Phase 5 can now be treated as complete for the current roadmap slice.

Completed slices:

- one-shot weekly coaching is available through MCP and backend reads
- coaching-generated plan changes expose reviewable diff and approval flow
- roadmap, sprint, coaching-history, revision-timeline, and multi-week analysis reads are now visible in-app
- deterministic coaching heuristics, goal forecasts, and modality restrictions now work together as a coherent coaching layer

### Sprint 21 performance foundations

Sprint 21 can now be treated as complete for the current roadmap slice.

Completed slices:

- manual performance anchors now persist running threshold pace and cycling threshold power settings
- zone definitions are explicit and reusable instead of being guessed implicitly in goal reads
- compact derived reads now expose recent 5k and 10k run benchmarks plus best recent 10-minute power
- zone-dependent goal logic now stays explicitly unavailable when threshold anchors are missing
- `Goals` now exposes lightweight performance-foundation editing and visibility for benchmark and zone-based goal support
- `Trends` now replaces the generic Metrics presentation with training load, threshold anchors, derived run/ride benchmarks, automatic Apple Health resting HR, optional weight and FTP history, four-week plan-aware consistency, recent workout heart-rate distribution, a full-year workout heatmap, and year-to-date cycling/running/strength charts
- focused Trends tabs group athlete-facing charts by purpose: Recovery contains sleep, resting HR, and HRV; Daily activity contains steps, walking/running distance, and flights climbed. Compact metric selectors drive one focused interactive chart with 14/30/90-day ranges, hover/tap/keyboard day inspection, prior-day comparison, and a rolling seven-day personal average without treating one reading as a readiness verdict
- consecutive-day streak and manual Z2/resting-HR entry no longer occupy the primary Trends interface; rest days are part of the plan and Apple Watch recovery signals come from Health Data Export instead of manual entry
- `Data & Sync` can stream raw Health Data Export JSON from a read-only iCloud Drive mount; imports run automatically on backend startup and every 15 minutes by default, remain manually triggerable, and are idempotent across a large initial backfill and overlapping daily files
- Health Data Export supplies sleep stages, resting HR, HRV, weight, steps, walking/running distance, and flights climbed; HealthFit remains authoritative for workouts, and raw all-day heart rate is intentionally left out of SQLite

## Recommended Next Step

Sprint 32 is complete. The next roadmap slice is ready for execution.

Current recommendation:

- Sprint 33 closed-loop weekly adaptation should use readiness, goal gaps, and execution-quality evidence to improve reviewable plan-adjustment guidance

## Areas That Are Still Intentionally Lightweight

- test coverage is still smoke-level rather than deep
- weekly plans are stored as JSON blobs by week
- goal-aware planning is still lightweight rather than deeply automated
- richer goal families now exist, but deeper family-specific progress and readiness modeling is still intentionally lightweight
- local backend test execution still depends on having the Python app dependencies installed

## Good Starting Points For Future Work

If continuing into the next roadmap:

- plan comparison and serialization: `backend/app/services/plans.py`
- activity persistence and linking: `backend/app/services/activities.py`
- activity SQL changes: `backend/app/repositories/activities.py`
- coaching summary and heuristics: `backend/app/services/coaching.py`
- coaching inspection and handoff UI: `frontend/src/views/Dashboard.vue` and `frontend/src/views/Plan.vue`
- goal schema and progress logic: `backend/app/models/goals.py`, `backend/app/repositories/goals.py`, and `backend/app/services/goals.py`
- settings-backed athlete context: `backend/app/services/settings.py` and `backend/app/repositories/settings.py`
- athlete-facing goal and profile UI: `frontend/src/views/Goals.vue`
- calendar aggregation and month view: `backend/app/services/activities.py` and `frontend/src/views/Calendar.vue`
- docs-backed planning visibility: `docs/roadmap.md`, `docs/roadmaps/`, `docs/current-state.md`, and `docs/sprints/`
- sprint planning direction: Phase 8 should now focus on context packaging and explanation quality before Phase 9 deepens performance data foundations

## Working Assumption

Unless the roadmap changes, the default implementation direction should be:

1. make athlete profile explicit before deeper goal automation
2. add richer goal families before trying to make coaching more autonomous
3. keep logic deterministic and inspectable
4. prefer structured templates over vague free-form modeling
