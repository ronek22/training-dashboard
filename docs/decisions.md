# Decisions

This file records durable project decisions that should influence future work.

## 2026-08-26

### Activity Detail information hierarchy

- Subjective feedback should read as an interpreted athlete signal, not a raw row of values, while keeping the individual inputs visible and editable.
- Coach analysis belongs directly after the session overview and before detailed route, chart, segment, and zone exploration.
- Heart-rate zone summaries should link detail cards to their matching distribution-bar segments through hover and keyboard-focus feedback.
- Endurance overviews should prioritize sport-relevant metrics in scannable tiles; cycling uses distance, clock-formatted moving time, average speed, and average heart rate, deriving speed when the source omits it.

## 2026-08-25

### One-click Codex weekly planning

- The Plan view may start a non-interactive Codex CLI job through a loopback-only macOS helper; it should not require a second Send action.
- The helper reuses the installed Codex login and configured `training_dashboard` MCP server, avoiding a separate API key.
- Codex should preserve completed and past days when a current-week plan already exists, then verify the saved plan through MCP.
- The helper stays bound to `127.0.0.1`, allows only dashboard browser origins, and runs Codex from a fresh temporary workspace with auto-reviewed approvals rather than exposing the repository as its working directory.
- The same helper may generate structured single-workout analysis through the existing activity-analysis MCP tools; Activity Detail should keep that panel visible even before analysis exists.
- Activity Detail should keep subjective session feedback compact and close to the header, while presenting saved coach analysis as a high-value preview that opens into a focused full-analysis modal.
- Workout analysis should add coaching interpretation rather than restating visible metrics: explain training value, recent-pattern fit, positive signals, meaningful concerns, and the next practical implication from grounded evidence.
- Athlete-written feedback notes are first-class analysis evidence and should be included in the Codex context, especially when they explain pain, soreness, conditions, or perceived session character.

## 2026-06-25

### Documentation location

- Planning and decision documents should live under `docs/`.
- Root-level project documentation should stay minimal and point into `docs/`.

### Product direction

- The dashboard should evolve toward a lightweight coaching system.
- Near-term product work should prioritize adaptive planning, feedback loops, and clearer coaching workflows over broad new integrations.

### Planning workflow

- Future roadmaps, sprint plans, and implementation decision records should be saved in `docs/`.
- If a design or product decision is likely to affect later implementation choices, it should be added here.

### Backend architecture direction

- The backend should move away from the single-file `main.py` structure.
- Refactoring should be incremental, behavior-preserving, and organized around routers, services, repositories, models, and shared DB setup.
- Do not introduce heavy abstractions such as generic repositories or DI frameworks unless a real need appears.

### Sprint 3 product focus

- The next product sprint should prioritize the feedback loop over broader goal-planning work.
- Post-workout feedback should attach to activities directly instead of living as a separate date-only journal stream.
- Recovery guidance should start with deterministic and explainable rules before any more advanced scoring approach.

## 2026-06-26

### Sprint 4 product focus

- The next product sprint should focus on goal-aware planning rather than deeper automation.
- Weekly plans should expose which active goals they support before the app attempts stronger automatic planning behavior.
- Goal-to-plan linkage should stay explicit, lightweight, and inspectable.
- Planned-to-actual explicit linking should follow goal-aware planning rather than precede it.

### Sprint 5 product focus

- Sprint 4 is complete enough to stop expanding goal-aware planning for now.
- The next product sprint should focus on planned-to-actual explicit linking.
- Comparison behavior should prefer explicit linkage over increasingly clever heuristics.
- Manual relinking should exist before adding more advanced coaching automation on top of comparison data.

### Sprint 5 implementation outcome

- Weekly plan days should carry stable session identifiers rather than rely only on date matching.
- Activities should own the explicit link back to planned sessions through a nullable planned-session reference.
- Link review in the Plan UI should stay on-demand and lightweight instead of being permanently expanded in every day card.

### Sprint 6 product focus

- The next product sprint should focus on structured workout intent before a more opinionated coaching MCP action.
- Session purpose should become explicit in plan data before the app tries to coach more aggressively from broad activity types alone.
- The first workout-intent vocabulary should stay deliberately small, optional, and inspectable.

### Sprint 6 implementation outcome

- Workout intent should remain optional but available across planned sessions, activities, and subjective feedback flows.
- Intent should influence inferred comparison conservatively, without overriding explicit planned-to-actual links.
- Intent-aware summaries should be included in recent coaching context before building a one-shot coaching action on top.

### Sprint 7 product focus

- The next product sprint should focus on a one-shot weekly coaching action rather than deeper storage or taxonomy work.
- The first coaching action should stay deterministic, transparent, and built on existing plan, feedback, linkage, and intent context.
- Coaching output should be structured enough to support a later plan-diff confirmation flow without auto-writing changes in the same sprint.

### Sprint 7 implementation outcome

- Weekly coaching should now be available as a one-shot backend and MCP read rather than requiring several separate context calls.
- The first coaching contract should stay inspectable, deterministic, and recommendation-oriented, with preview-only plan adjustments instead of automatic writes.
- The Dashboard should expose coaching output directly and support a lightweight handoff into the existing Plan editor before a dedicated approval flow exists.

## 2026-06-29

### Sprint 8 product focus

- The next product sprint should finish the coaching workflow by adding explicit plan-diff confirmation and approval before write.
- Roadmap and sprint visibility in the UI is worth adding now only as a read-only, docs-backed slice.
- Markdown under `docs/` should remain the source of truth rather than creating a separate editable planning model in the app.
- Any roadmap visualization should depend on stable metadata or headings, not fuzzy parsing of arbitrary prose.

## 2026-06-30

### Next roadmap direction

- The next roadmap should focus on richer athlete modeling and richer goal modeling rather than broader integrations.
- The biggest product gap is now `the app understands training data better than it understands the athlete`.
- Athlete context should become explicit persisted state before deeper goal-aware automation expands further.

### Goal model direction

- Goals should expand from simple accumulation tracking into a small number of explicit goal families.
- The first goal families should include accumulation goals, event-performance goals, benchmark goals, and process or frequency goals.
- Structured goal templates should remain the canonical source of truth; free-form text can assist creation but should not replace normalized goal data.

### Athlete profile direction

- The app should store a lightweight athlete profile including focus, modality priorities, planning notes, and similar durable coaching context.
- The first athlete profile can live in settings-backed storage rather than requiring a large new profile subsystem.
- MCP and chat surfaces should consume a deterministic athlete brief derived from that stored profile.

### Planning and coaching guardrails

- Richer goals should improve planning and coaching explanations before they drive more aggressive automation.
- Goal evaluation and forecasts should stay deterministic and explainable even when they become goal-family-specific.
- Hybrid or competing goals should be surfaced as explicit tradeoffs rather than hidden behind generic pressure scores.

### Sprint 15 implementation outcome

- Athlete profile now lives in settings-backed storage as lightweight durable coaching context rather than a separate subsystem.
- The canonical stored athlete-profile payload should remain compact and raw; normalized labels and `athlete_brief` should be derived on read.
- Dashboard should treat athlete context as secondary reference information, not as a top-level daily coaching signal.

## 2026-08-29

### Dashboard role and information hierarchy

- Dashboard should answer three questions first: what to do today, why that is the call, and what comes next.
- Detailed load, strength, goal, and activity analysis should live in their dedicated views instead of being repeated in one long dashboard feed.
- Conflicting but valid signals should be reconciled into one visible guardrail, such as allowing an easy planned session while warning against extra load when short-term strain is building.
- The current seven-day plan, weekly focus, immediate goal pressure, and recent sessions are the maximum supporting context that should remain on the default dashboard surface.
- The dashboard week strip is execution-first: past days show activities actually logged on those dates, while planned workouts appear only for an unfinished today or a future date.
- Recent-session rows should not repeat the same short-horizon activity story already visible in the week strip; that dashboard space is reserved for redesigned year-to-date cycling, running, and strength trajectories.
- Year-to-date chart months expose accessible hover and keyboard detail with monthly volume, training time, session count, and cumulative progress.
- Do not keep a generic weekly-focus, goal-priority, or coming-next card row on Dashboard: those cards repeat the daily call and week strip or elevate durable restrictions as if they were new information.
- The dashboard week surface includes an aggregate of actual distance, training time, and session count; actual day cards open Activity Detail, while unfinished, future, or missing days open Plan.
- Dashboard readiness should lead with measured training load and a fresh subjective check-in as separate evidence. Consecutive training days and a long consistency streak are baseline context, not strain evidence on their own.
- Dashboard detail links must land on the matching detail surface; Training load opens a computed Metrics tab with fitness, fatigue, form, ratio, focus, and trend rather than a generic manual-metric view.
- The former Metrics page is now Trends: its job is to answer whether training is producing useful adaptation, led by training load, repeatable performance markers, supporting body/recovery signals, and plan-aware consistency.
- Trends owns longer-horizon training context: recent heart-rate zone distribution, the annual workout heatmap, and cumulative cycling, running, and strength history. The dashboard can still summarize the year, but Trends is the durable analysis home.
- Health charts are grouped into Recovery and Daily activity tabs instead of adding a primary tab for every imported measurement. Within each view, a compact metric selector controls one interactive focus chart rather than repeating multiple oversized charts; athletes can inspect individual days and switch between 14, 30, and 90-day ranges.
- Apple Health JSON ingestion is deliberately selective and idempotent. Sleep, resting HR, HRV, weight, steps, walking/running distance, and flights climbed are retained; the much larger all-day heart-rate series and duplicate workout records stay in their source exports because HealthFit and workout streams are authoritative for training analysis.
- Consecutive-day streak is no longer a primary navigation or trend signal. Consistency should measure planned sessions fulfilled, adapted, or missed so intentional recovery remains part of successful execution.
- Weight stays available as an optional manual trend, and FTP test results update the cycling threshold anchor. Resting heart rate should wait for automatic Apple Watch/health-data ingestion rather than asking for manual entry.
- Manual Z2 pace is not a trusted performance marker because route, terrain, conditions, and fatigue make isolated entries hard to compare; running threshold and derived repeatable benchmarks are preferred.
