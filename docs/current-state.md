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

### Minimum viable week

2026-10-05: `services/minimum_week.py` shrinks the rest of the current week to the smallest plan that keeps the anchor goals. This is step 2 of the "stress and life" set. It is an ordinary plan adjustment, so past and completed days are protected and every change is a plan revision.

- Targets: weekly session-count anchors (`strength_sessions`, or `activities_count` for WeightTraining or Ride) give the lift count, or 2 lifts if there's no anchor; rides are 2 easy, or more if a ride anchor asks. Anchors count even after their end date. Sessions already done this week count toward the target.
- Shape: lifts stay lifts (title "Strength", so the template rotation still assigns A/B/C/D) at 30 min, main lifts only. Rides are easy at 40 min, and every other open day rests. Travel days and sick-mode days get nothing. Lifts are spread out, avoiding back-to-back days (including next to lifts already done) and life-load days, and prefer days that already had a lift. Rides prefer untagged days that were already rides. If the days left can't fit the anchor, the summary says so.
- API: `POST /plans/weekly/{week_start}/minimum-week/preview` (proposal plus diff), `POST …/minimum-week` (apply), `POST …/minimum-week/restore` (puts back the open days from the plan saved in that revision). Plans get `minimum_week` (`active`, `summary`) from the latest such revision; a later "Restored full week" revision clears it. It ends with the week.
- Coach: `minimum_week` in `get_recent_context`, and the plan-revision prompt keeps a shrunk week small unless the feedback asks for more.
- UI: a "Minimum week" button next to "Manage week" on the current plan opens a before → after preview with a confirm. While it's on, the week shows a "Minimum viable week" pill and the button becomes "Restore full week".
- Verified with 8 unit tests and an API round-trip smoke test (432 backend, 26 helper and 27 frontend tests, plus the build). Applied and restored in the browser on a copy of the database with a seeded week: Monday (sick) and the deadline Thursday rested, lifts landed Wed/Fri/Sun as C → D → A, and restore brought back the exact original days.

### Life-load tags

2026-10-05: `services/life_load.py` lets the athlete tag days as travel, deadline, family, poor sleep or late night. Sick mode is a period about the body; these are per-day tags about time and attention, so they never add a body-risk penalty or pause the plan. This is step 1 of the "stress and life" set; a minimum viable week and a two-minute downshift will build on it.

- Storage: one row per day in `life_load_days` (tags plus an optional note). `GET /life-load?start&end` returns the tag list and tagged days; `PUT /life-load/{date}` replaces a day's tags, and an empty list clears the day. A tag added after the day is marked `tagged_after`.
- Plans get `life_load`: tags per day, plus conflicts for intervals, tempo, race-specific or 90+ min sessions on a tagged day from today on (lifts and easy sessions are fine). Each conflict suggests the nearest open day in the same week with a calm session and no hard neighbour. The Plan page lists them with a one-click swap through `/plans/weekly/swap`.
- Weekly review context has `life_load` with the week's tags and `missed_on_tagged_days` (e.g. "Missed 2 sessions, both on deadline days."). The Sunday review prompt treats those misses as life load, not motivation.
- Volume trend: a falling week with 3+ tagged days is labelled `life` automatically (sick mode still takes priority as `illness_injury`).
- Readiness: poor sleep tagged today or a late night yesterday adds a 1-point caution, but only when there is no check-in today (the check-in already rates sleep).
- Coach: `life_load` in `get_recent_context` (last 7 and next 14 days, with guidance); the weekly planning prompt keeps hard and long sessions off upcoming tagged days.
- UI: a tag picker in the calendar day popup and in the Plan session dialog; tag icons on calendar cells with a legend entry; sand `--life` chips on plan cards, outlined when they clash.
- Verified with 8 unit tests, 2 volume-trend tests and an API smoke test (423 backend, 26 helper and 27 frontend tests, plus the build). Checked in the browser against a copy of the database: tag picker, cell icons, clash banner and swap.

### Return-to-run tracker

2026-10-05: `services/return_to_run.py` runs a six-stage return to running, driven by symptom scores: run/walk 1:2 → 2:1 → 5:1 → continuous 20 min → continuous 30–40 min → back to normal. The athlete switches it on with a starting stage and the symptom to watch (default heel). It never edits the plan.

- Scores: "during" and "next morning" (0–10) per run in `run_symptom_checks` (`PUT /activities/{id}/symptoms`). The feedback form's pain score stands in for "during" when no symptom score was logged.
- Replay since the start date. Clean (≤ 2 during and the next morning): 2 in a row advance a stage, and the latest needs its morning score. Flare (≥ 4 during or ≥ 3 the next morning): one stage down. A break of 21+ days between runs, or since the last run, also costs a stage. Otherwise the stage holds.
- Next step: needs a score, needs the morning score, flare, rest day (one full day between runs at stages 1–3), ready, or graduated (3 clean full runs in a row at stage 6, meaning symptoms look resolved).
- Suggested start: the last pain-free run's duration maps to a stage, minus one after 3+ weeks off; recent pain above 2/10 starts at stage 1. On real data this suggests stage 3 (28 min at 0/10 on 9 Sep, 26 days ago).
- Easy and long runs with average HR above the run zone 2 cap (162 bpm) are marked partial in execution quality. Every run since June averaged 162–180 bpm.
- Plans get `run_guardrail` when planned run minutes rise 10%+ (and by 10+ min) over last week's actual runs and faster run sessions are added in the same week. It is shown as a banner on the Plan page. This is a warning on the saved plan, not a block.
- Coach: MCP `get_return_to_run`; `return_to_run` in `get_recent_context`. The weekly planning prompt plans run days only from the current stage and respects its next step. Run briefs show the stage, its prescription and a stop-at-3/10 rule.
- UI: a Return to run panel at the top of Recovery, with a start form and suggested stage; when active, a stage ladder, the next step and per-run scoring with HR-cap, longer-than-stage and after-a-break flags.
- Verified with 9 unit tests and `just check` (412 backend, 26 helper and 27 frontend tests, plus the build). The start form was viewed on real data without starting the program. The active panel was viewed with a state built on a database copy and injected into the browser tab only.

### One trustworthy check

2026-10-05: `just check` runs the frontend behavior tests, the frontend build, the backend suite and the four helper-script test files, stopping at the first failure. `just setup-checks` creates the backend virtualenv and runs `npm ci` for a fresh checkout. Two smoke tests depended on the weekday and are fixed without weakening their assertions:

- The zone 2 goal test logged its ride "yesterday", which is last week on a Monday. It now logs the ride today.
- The goal-tradeoff test planned only Monday–Wednesday, so from Thursday the goal it created "today" started after the plan ended. The plan now runs to Sunday, like real plans.
- Verified by running the backend suite with a patched clock on nine dates (weekdays, weekends, month and year boundaries, February). The only remaining failures under the patched clock are two sick-mode tests: their code reads SQLite's `date('now')`, which the patch cannot move, so they are an artifact of the method and pass on the real clock.

### "What worked" memory

2026-10-05: sessions can be tagged loved / fine / hated, along with what was eaten before (fasted, snack < 1 h, meal 1–3 h, meal 3 h+). Tags are stored in `session_tags`, separately from the required feedback sliders, so a one-tap rating works on its own. `services/what_worked.py` compares two outcomes across conditions the app already knows:

- Outcomes: the verdict (+1 / 0 / −1), and effort cost (post-workout RPE minus the session intent's target RPE). Effort cost uses existing feedback, so patterns can appear before any tagging.
- Conditions: time of day (local start time from Strava detail or the import reference; helpers moved to `services/activity_times.py`), indoor vs outdoor (rides), fasted vs fed, morning-check-in sleep and energy (4–5 vs 1–2), and the day after a rest day vs back-to-back days.
- Families: hard rides, easy rides, runs, strength and all sessions. A pattern is confirmed with 6+ sessions on each side and a gap of 0.5 (verdict) or 1.0 RPE (effort). With 3+ per side it is "emerging" and never presented as a rule. Sick days are excluded. Wording is descriptive: "were rated better / felt easier for the same job".
- `PUT /activities/{id}/tags`, `GET /what-worked`. The feedback POST also accepts `verdict` and `pre_fuel` (omitted means unchanged). Activity detail and activity lists carry `session_tags`.
- Coach: MCP `get_what_worked`; `what_worked` (confirmed and emerging patterns, with guidance) in `get_recent_context`. The weekly planning prompt asks Codex to place sessions where confirmed patterns say they go better. The pre-session brief adds the top confirmed pattern for that session family as a note.
- UI: Loved / Fine / Hated on the Activity Detail "How it felt" strip and on the completed Today card; the two new questions at the top of the feedback form; a collapsible "What works for you" line on the Activities page with patterns, evidence and quick rating of recent sessions.
- Verified with 5 unit tests, a smoke test of the tag round trip, the full backend suite, the planning helper tests, 27 frontend tests and the build. Against real data: 52 sessions are considered, 29 have effort data, and one emerging pattern shows (easy rides cost about 1.2 RPE more indoors, from only 3 indoor rides). The UI was viewed in the browser without saving any tags. The only backend failure, `test_performance_settings_and_zone_foundation_surface_available_and_missing_states`, also fails on the committed code (it depends on the date).

### Pre-session brief

2026-10-04: `services/session_brief.py` gives each planned session a short, coach-style brief with three parts: purpose, how it should feel (an RPE range plus a description) and when to bail. It is deterministic and never changes the plan.

- Rides: templates per workout category (recovery, endurance, tempo, sweet spot, threshold, VO2 max). Watt targets come from the structured workout and the stored FTP; heart-rate caps come from the configured zones.
- Endurance rides anchor the drift rule to the athlete's own data. `usual_hr_at_power` takes the median HR while 30 s power is within ±8% of the target, skipping the first 10 minutes, across the last 90 days (3+ rides needed). The rule is "HR more than 10 bpm above that at the same power". If the usual HR sits above zone 2, a note says to ride by HR.
- If the stored FTP is stale, a note gives the work watts at the recent FTP estimate from the records wall.
- Runs: HR cap, walk-break and pain rules. Strength: reps in reserve, load drop and joint-pain swap. Recovery-type sessions use the title to choose between a recovery ride and mobility.
- Plan guardrail sentences (stop / skip / cut / ease off, up to 180 characters) come first. The rules also cover an active recovery issue (unless the plan already does) and a low morning check-in. At most 3 bail rules are shown.
- Sick days get no brief, since guided home sessions replace the plan.
- `session_briefs` in `GET /dashboard`, plus `GET /session-brief?day=`. The Today card shows the brief in place of the old sentence-split guide, which remains as a fallback.
- Verified with 7 unit tests, the full backend suite (only the existing `test_plan_and_coaching_surface_requirement_gaps_and_goal_tradeoffs` failure), 27 frontend tests and the build. The real week's briefs were checked against a copy of the database. Today is a sick day, so the Today card was checked in the browser with an injected brief and sick mode switched off only in that tab.

### Personal best wall

2026-10-02: `services/personal_records.py` builds an all-time records wall from local data. It scans the cached streams of every ride and run, not just activities whose detail page was opened. Per-activity results are cached in `activity_record_efforts` and refreshed when the detail row's `updated_at` changes.

- Bike power: 5 s plus the existing power-profile durations (15 s–60 min), indoor and outdoor combined. 5 s is computed here so the benchmark radar is unchanged.
- Bike distance: 5K, 10K, 20K, 40K, 50K, 100K, longest ride and biggest climb. Outdoor and indoor (VirtualRide or `trainer`) are separate lists because indoor speed is simulated.
- Run: Strava's distances from 400 m to marathon, plus longest run. Distances not yet covered are listed as locked.
- Lifts: estimated 1RM (Epley, working sets of up to 12 reps), heaviest set, and most reps or added weight for bodyweight movements. Exercises need 3+ sessions.
- Streaks: current, longest and milestones at 7–365 days.
- Each record has date, activity, indoor/outdoor, average HR, time of day (where a start time is known), previous best, top 3 (ties go to the earlier date) and a progression derived chronologically.
- FTP estimate: the higher of 95% of the best 20 min and the best 60 min from the last 90 days, shown beside the stored FTP and never written to it.
- `GET /records`, `GET /records/activities`, MCP `get_personal_records`, and `personal_records` (new bests and FTP estimate) in `get_recent_context`.
- UI: a new `/records` page, a 30-day new-records strip on the Dashboard after the year charts, record chips and PR medals on Activity Detail best efforts, and a PR / Top 3 tag in the Activities list.
- Activity Detail best efforts now use the same distances and the same linear fastest-window search (`DETAIL_DERIVED_VERSION` v2). The old per-window scan took about 43 s for 12 activities; the new one takes 0.07 s with matching results.
- Verified with 13 unit tests, the full backend suite (the existing `test_plan_and_coaching_surface_requirement_gaps_and_goal_tradeoffs` failure also fails before this change), 27 frontend tests, the build, and the live Records page, Dashboard strip, Activity Detail and Activities list at 1512px. The Records page was also checked at 375px.

### Training volume trend alert

2026-09-30: `services/volume_trend.py` flags an unplanned multi-week slide in training volume (completed Monday–Sunday weeks; walks and hikes excluded). It triggers when the last three completed weeks fall twice in a row, the last week is at most 75% of the first and at least 20% below the four weeks before. A falling week counts as planned only when its plan is 15%+ lighter than the previous three plans or its title says deload, taper or recovery week — plan overview wording is ignored because it almost always mentions recovery. It needs 4+ sessions across the baseline weeks and 120+ minutes in the first week.

- `volume_trend` in `GET /dashboard`, MCP `get_recent_context` and the weekly specialist snapshot
- Dashboard Load & recovery card shows a compact alert with a three-week mini bar chart and Planned / Life / Illness-injury buttons; `POST /volume-trend/label` stores the answer per week in `volume_trend_labels`, hides the alert and keeps the label in coaching context
- Verified with 7 unit tests, an endpoint smoke test, the frontend build and the live Dashboard at 1512px (fires on real data: 726 → 457 → 341 min). The label buttons were not clicked against the real database.

### Goal intelligence (Sprint 39, complete)

2026-09-29: goals have a lifecycle (active, paused, completed, retired), anchor commitments and purposes, per-period history, outcome and cost signals, a deterministic verdict engine, season awareness (athlete profile `off_season_months`, default Oct–Mar), and evidence-based suggestions. See [Sprint 39](sprints/sprint-39-goal-intelligence.md). Step 7 added the portfolio check and the monthly review rhythm:

- `services/goal_portfolio.py` estimates the weekly hours each active goal implies (distance ÷ the athlete's average speed for that sport, sessions × median session length, zone 2 hours as-is; long-running goals use remaining work over remaining weeks) and compares the sum with hours actually trained. The comparison uses the last 8 weeks, or the same season's past weeks when the season changes within 14 days. Over 1.15× is flagged with the biggest contributors; anchor goals count but are never listed for reduction, and zone 2 or quality goals share hours with a ride-distance goal instead of adding to it.
- The check appears as `portfolio` in `GET /goals/review` and MCP `get_goal_review`, in the Goals review panel, and as a `time_budget` entry in the weekly plan's goal conflicts (`plans._build_goal_conflicts`).
- The first weekly review of a month (the week whose Sunday falls on days 1–7) gets a read-only Goals section from `GET /reviews/weekly/goals?week_start=` (also `goal_review` in the review context): goals needing a decision, the portfolio flag, the suggestion count, and a link to `/goals`. It applies nothing.
- Verified with 14 new backend tests, the goal/review test suites, live read-only endpoints and the frontend build. The over-committed and monthly Goals section layouts were not viewed against real data (the real goals fit the budget, and the latest review is not a month-first week).

### Structured cycling workouts with Zwift export

2026-09-28: added a deterministic library of nine structured cycling workouts (recovery, endurance, long endurance, tempo, sweet spot, threshold, VO2 max) in `backend/app/services/cycling_workouts.py`. Steps are FTP fractions; the app shows watt targets from the latest stored FTP and names its date and age (flagged after 56 days), while exported `.zwo` files stay FTP-relative so Zwift scales them to its own FTP.

- `GET /cycling-workouts`, `GET /cycling-workouts/{id}` and `GET /cycling-workouts/{id}/zwo`
- planned ride days accept an optional validated `cycling_workout_id`; plan diffs report changes as "Structured workout"
- Plan shows a workout pill on ride cards, a power profile, step list and `.zwo` download in the session dialog, and a picker in Adjust Remaining Week that fills intent and duration
- MCP `get_cycling_workout_library`; `set_weekly_plan`/`adjust_weekly_plan` accept `cycling_workout_id`; Codex planning prompts may assign library workouts to ride days
- Verified with 7 focused backend tests, the frontend build, live endpoints, and an in-browser check of the picker and dialog at desktop and 375px widths without saving a plan change. Execution scoring against the workout's power targets is not implemented yet.


### HEAD COACH and weekly specialists

2026-09-14 follow-up: the missing 7–13 September Sunday review was successfully generated and saved after explicit user approval to send its training context through the existing AI connection. Earlier saved reviews remain intact. Completed weeks now reads `/reviews/weekly/status`, names an overdue unsaved week, labels older content as latest available, and offers a read-only Check again action. Status follows the Warsaw Sunday 23:59 boundary; it does not imply an active generation job. Verified actual saved review in browser, synthetic missing/cleared states, 390px layout, 44 focused tests and production build. This verifies the Sunday review path, not the separate on-demand specialist review pipeline.

Implemented a snapshot-based weekly coaching team, documented in [the feature spec](specs/001-hybrid-coaching-team/spec.md):

- Running, cycling and strength reports share a complete calendar-week activity snapshot and matching-weekday comparisons across four prior weeks.
- On request, one consolidated AI call produces the three specialist summaries and HEAD COACH synthesis: verdict, tradeoff, one next-week change and an observable success check. Reports are validated, saved by week, and marked stale when inputs change. Failed generation preserves the last successful review; reports never save plan changes.
- Dashboard shows one compact Weekly review entry with the main takeaway and a recorded-time allocation chart. `/weekly-review` holds the full analysis and a clickable seven-day session grid. Completed Sunday reviews remain accessible in the same page’s Completed weeks view; the duplicate dashboard section is removed.
- Weekly HTTP/MCP coaching and historical Sunday review context share the team report. Historical reports exclude present-day recovery; existing saved Sunday reviews remain unchanged.
- Deterministic facts remain the evidence foundation. No physiological predictions or numerical confidence scores are introduced. The build, 42 focused tests and synthetic responsive/error/retry/stale/navigation checks passed. A real AI review is still unverified: automatic approval blocked sending potentially sensitive training context, and explicit user permission was requested.


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

### Recovery (simplified 2026-09-28)

2026-09-28: replaced the Sprint 38 intake/screening workflow and fixed exercise library with a chat-first injury tracker.

- An issue is a body area, optional side, and starting pain. Describing it sends the first message to the AI helper, which asks follow-up questions and returns a structured plan (exercises with dose and cues, do/avoid lists) plus a `see_professional` flag with red-flag reasons. A new plan replaces the current one.
- Daily check-ins record pain 0–10, whether the plan was done, and a note; the page shows a pain trend.
- Marking healed asks what helped. A new issue in the same body area (word match, e.g. "outside of knee" ↔ "left knee") or one started with "It came back" is linked to earlier episodes; the AI context includes those episodes' plans, check-ins and what helped, plus other healed injuries.
- All active injuries (area, pain, current avoid list, no conversation text) are included in Coach/planning context; the old per-issue sharing opt-in is gone.
- Existing issues were migrated (location/side/onset). Old intake columns remain unused in `recovery_issues`; `recovery_library.py` was removed, so `recovery-library-review.md` is historical.
- Verified with 13 recovery backend/helper tests, the frontend build and recovery-chat tests, live endpoints, and an in-browser check at desktop and 375px without saving new issues. A real AI reply with the new prompt was not run; restart the Codex helper to load it.

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
