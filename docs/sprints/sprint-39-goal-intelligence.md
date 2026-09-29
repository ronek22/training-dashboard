# Sprint 39: Goal Intelligence — Lifecycle, Verdicts And Suggestions

## Status

Current status:

- complete — Steps 1–7, including 5b (season awareness), done (2026-09-29)
- builds on Sprint 13 (goal forecasts), Sprint 16 (goal families), Sprint 17 (requirements and conflicts), Sprint 31 (goal readiness)

Starting point:

- goals can only be created and listed: there is no edit, pause, complete, or retire path (`routers/goals.py`, `repositories/goals.py`)
- every goal answers "am I on pace?" (forecast, risk, readiness) but none answers "is this goal still worth chasing?"
- process goals (volume, frequency) are not linked to the outcomes they are supposed to improve
- there is no `test_goals.py`; goal logic (2.2k lines in `services/goals.py`) is untested

## Objective

Move goals from:

- `user-defined targets that are tracked forever`

to:

- `goals with a lifecycle, an honest monthly verdict on whether they still pay off, and calibrated suggestions for what to do next`

## Guiding Principles

1. **Deterministic first.** Verdicts and suggestions come from explicit rules and thresholds, like the other coaching heuristics. Claude via MCP can explain and discuss them, but the app works without a model.
2. **Evidence or silence.** When data is sparse (for example, only 49 of 146 rides have verified power, with no power data April–July), the verdict is `insufficient_evidence`, not a guess.
3. **The athlete decides.** The system recommends; nothing changes a goal without an explicit click. Recommendations can be snoozed.
4. **Anchor goals are respected.** A goal marked `anchor` is a deliberate standard (for example, "Lift 3×/week to maintain muscle alongside heavy cardio"). The system never recommends lowering or retiring it. It evaluates whether the goal's *purpose* is being served and helps fit it into the week.

## Acceptance Fixtures (real goals, 2026-09-28)

These four goals are the reference scenario for tests and manual verification:

| Goal | Data | Expected verdict | Expected action |
|---|---|---|---|
| Ride 3500 km in 2026 | ~4,875 km YTD | `done` | Complete and suggest a 2027 version |
| Run 1000 km in 2026 | ~258 km YTD, <10 km/month since May | `out_of_reach` | Retire, or lower to a realistic target (flexible goal) |
| Ride 100 km weekly | Hit ~14 of the last 15 weeks, median ~180 km | `too_easy` (volume margin ≥1.4×) | Change to a quality goal, or raise it and give it a season end date |
| Lift 3× per week (**anchor**) | 3+ in ~5 of the last 15 weeks, averaging ~2 per week | `anchor_under_pressure` | Show whether the purpose is served (strength held?) and suggest how to fit sessions in; **never** lower it |

---

## Step 1 — Goal Lifecycle And Editing ✅

The foundation. Every later step needs goals that can end.

Backend:

- Migration in `db.py` (same `PRAGMA table_info` pattern as `goal_family`), adding goal columns:
  - `lifecycle_status TEXT DEFAULT 'active'` — `active | paused | completed | retired` (named `lifecycle_status` because serialized goals already use `status` for pace)
  - `status_reason TEXT`, `status_changed_at TEXT`, `updated_at TEXT`
  - `purpose TEXT` — why the goal exists ("maintain muscle")
  - `commitment TEXT DEFAULT 'flexible'` — `flexible | anchor`
  - `review_on TEXT` — optional date for the next deliberate review
  - `season_end TEXT` — optional date for when a recurring goal stops applying (for example, the end of the off season)
  - `outcome_signal TEXT` — optional override of the default outcome link (Step 3)
- Backfill `status` from `is_active`. Keep `is_active` in sync (`status == 'active'`) so `plans.goal_applies_to_plan` and the dashboard keep working unchanged.
- Recurring goals with `season_end` in the past are treated as paused by `goal_applies_to_plan`.
- Repository: `update_goal`, `set_goal_status`, `get_goal_row`.
- Service: `update_goal_data` (reuses `_validate_goal_payload`), `set_goal_status_data` (validates transitions and stamps a reason and timestamp).
- Routes:
  - `PATCH /goals/{id}` — edit fields
  - `POST /goals/{id}/status` — `{status, reason}`
  - `GET /goals?status=` — lifecycle filter; `active_only` still works and also excludes ended seasons
- MCP: `get_goals`, `update_goal` and `set_goal_status` tools in `services/mcp.py` (backend `/mcp`) and the `mcp/server.py` stdio proxy.

Frontend (`Goals.vue`, `stores/api.js`):

- Edit drawer that reuses the create form, plus fields for purpose, commitment (an "Anchor goal" toggle with a short explanation), review date and season end.
- Card actions: Pause, Complete, Retire (each asks for an optional reason).
- A collapsed "Past goals" section showing status, reason and final progress.
- Anchor badge on anchor goals.

Tests (new `backend/tests/test_goals.py`):

- migration backfill, edit validation, status transitions, `is_active` sync, season-end exclusion from planning.

Done when: you can mark "Ride 3500 km" completed, retire "Run 1000 km" with a reason, and mark "Lift 3×" as an anchor with a purpose.

---

## Step 2 — Goal Period History ✅

A pure, testable history of every goal against its own target. Verdicts and target calibration both depend on it.

- New module `services/goal_history.py`:
  - `build_goal_period_history(conn, goal, periods=12)`:
    - weekly goals: the last N completed weeks as `{period_start, value, target, hit}`
    - monthly goals: the last N months
    - yearly goals: cumulative monthly values against a pro-rata target, plus the required rate to finish
  - summary stats: `hit_rate`, `median`, `p75`, `best_4_period_rate`, `current_streak`, `trend_slope`, `margin` (median / target), `required_rate_ratio` (required rate / recent rate)
- Reuse `goal_value_for_window` for each period so the numbers match the existing progress bars exactly.
- History operates on serialized goals and is opt-in (`GET /goals?include_history=true`) so planning and the dashboard don't pay for it; `GET /goals/{id}/history?periods=N` (max 52). MCP `get_goals` takes `include_history` and returns stats only.
- Periods before the first synced activity are dropped (they would read as misses); periods before the goal existed are flagged `before_goal` but still counted, since pre-goal behaviour is evidence for "too easy" verdicts.
- Goals page: a sparkline of per-period values with the target line on each card.

Tests: synthetic activity fixtures for weekly, monthly and yearly goals, including partial current periods (excluded) and empty periods.

---

## Step 3 — Outcome And Cost Signals ✅

Answers "does hitting this goal actually improve anything?" and "what is it costing?".

- New module `services/goal_outcomes.py` with a registry of signals. Each returns
  `{key, label, series: [{month, value}], trend: improving|flat|declining|insufficient, delta, evidence_count, confidence, note}`.
- Outcome signals:
  - `cycling_power_20m`, `cycling_power_5m`, `cycling_power_60m` — monthly bests from `power_trends.get_cycling_power_trends_data()["monthly"]`; mark months without verified power as gaps, not zeros
  - `cycling_efficiency` — watts per heartbeat (avg_watts / avg_hr) on steady rides with power, monthly median
  - `run_efficiency` — speed / HR on easy runs, monthly median
  - `strength_maintenance` — Epley e1RM (non-warmup sets, ≤ 12 reps) for the 5 most-trained weighted lifts. Per lift, the median session best of the last 6 weeks is compared with the median before it; the signal is the median change across lifts (±3% = holding). Monthly *bests* were tried first and rejected: one-off peak days and coarse dumbbell jumps made a steady lifter look −8% to −10%
- Cost signals (from `health_metric_samples` and `readiness`):
  - `hrv_trend` (7-day vs 28-day baseline), `resting_hr_trend`, `sleep_trend`
- Default links from goal to outcome (overridable with `outcome_signal`):
  - `ride_km`, `zone2_hours` → `cycling_efficiency`, `cycling_power_20m`
  - `run_km` → `run_efficiency`
  - `strength_sessions` → `strength_maintenance`
  - `benchmark_*` / `event_*` → the benchmark itself (already tracked)
- Trend rules: at least 3 months with data and at least 6 evidence points, otherwise `insufficient`; "flat" means within ±2% change.
- Endpoints: `GET /goals/{id}/outcomes` (linked outcomes + costs), `GET /goals/signals` (all signals), `GET /goals?include_outcomes=true`. MCP tool `get_goal_signals` (optional `goal_id`; series omitted).
- Cost signals compare the 7 days up to the latest sample with the 28 days before it, and flag `stale` when the latest sample is more than 4 days old. The health module is imported lazily so goal signals don't depend on the importer's streaming-JSON package.
- Goal cards show one line per linked outcome ("→ Holding ±0% · Top-lift strength"), with the evidence note as a tooltip.

Tests: signal trend classification, gap handling (the April–July power gap), insufficient-evidence cases.

---

## Step 4 — Goal Verdict Engine ✅

The core of "is this goal still worth doing?".

- New module `services/goal_review.py`:
  - `build_goal_verdict(goal, history, outcomes, costs, active_goals) -> {verdict, confidence, headline, evidence[], recommended_actions[]}`
- Verdicts, in priority order (thresholds are named constants):

| Verdict | Rule (initial) |
|---|---|
| `done` | Accumulation total ≥ target before the period ends |
| `review_due` | `review_on` or `season_end` has passed |
| `out_of_reach` | Yearly: required rate > 1.5× best 4-period rate. Recurring: hit rate < 25% over ≥ 8 periods |
| `too_easy` | Hit rate ≥ 90% over ≥ 8 periods and margin ≥ 1.4 |
| `crowding_out` | This goal's volume trend is up while another active goal's hit rate fell by ≥ 30 points, or cost signals worsen alongside it |
| `plateaued` | Hit rate ≥ 70% and the linked outcome is flat or declining with enough evidence |
| `productive` | Hit rate ≥ 60% and the linked outcome is improving |
| `inconsistent` | Added during build: hit rate 25–60% (recurring), or a yearly goal that is reachable only above recent pace |
| `on_track_unproven` | Being hit, but the outcome has `insufficient` evidence |
| `insufficient_evidence` | Fewer than 4 periods of history |

- Anchor overrides:
  - `out_of_reach` and `too_easy` become `anchor_under_pressure` or `anchor_steady`
  - allowed actions: `keep`, `plan_support` (suggest week slots or a minimum-effective 30-minute session format), `set_review`
  - the headline speaks to the purpose, for example: "Averaging 2 lifts/week; top lifts held within 3% over 12 weeks, so muscle maintenance is on track. 3× stays your standard."
- Action types (each carries a ready-to-apply payload for the Step 1 endpoints):
  `keep`, `raise_target`, `lower_target`, `set_season`, `convert_to_quality` (with a draft), `pause`, `retire`, `complete_and_replace` (with a draft).
  Target values are calibrated from history: `p75 × 1.05`, rounded with `rounded_goal_value`.
- Snooze and decisions: a new `goal_review_decisions` table `{goal_id, verdict, decision: applied|snoozed|kept, until, created_at}`. A snoozed verdict stays hidden until its `until` date, or until the verdict changes.
- Endpoints: `GET /goals/review` (all active goals, sorted by urgency) and `POST /goals/{id}/review-decision` (`snoozed` 28 days, `kept` 56 days by default, `applied`).
- Maintenance purposes: when a goal's purpose mentions maintaining, keeping, holding, preserving or retaining, a *holding* outcome counts as success (productive / purpose served), not a plateau.
- `review_due` overrides every verdict except `done` and `out_of_reach`; its Keep action clears `review_on` and `season_end`.
- MCP `get_goal_review` shipped here rather than in Step 7 so Claude can discuss verdicts as soon as they exist.
- A `review` block goes on each serialized goal. The dashboard summary counts goals that need attention.

Tests: one test per verdict, anchor overrides, snooze expiry, and all four acceptance fixtures.

---

## Step 5 — Review UI ✅

- Goals page:
  - a "Goal review" panel at the top: "N goals need attention", each with its verdict chip, headline, 2–3 evidence lines, and buttons for the recommended action, Keep as is, and Snooze 4 weeks
  - a verdict chip on every goal card, with the outcome sparkline next to the progress sparkline
  - applying a recommendation shows a before/after confirmation and then calls the Step 1 endpoints
- Dashboard: the Goals link in "Go a little deeper" reads "N goals need a review" (the dashboard has no goal risk area to extend).
- Overview stats: "Need attention" renamed "Behind pace" (it counts pace status) next to a new "To review" count, so the two ideas no longer share a word.
- Non-attention verdicts show their headline on the card (e.g. the anchor's "purpose is served" line).
- Next-period goals: "Start next year's goal" opens the goal editor pre-filled. A goal starting in the future is saved paused with `review_on` = its start date; the review lists paused goals whose date has arrived as `review_due` with *Start it now*, and reactivating a goal clears a past `review_on`. (Yearly accumulation goals always track the current calendar year, so creating the 2027 goal active in 2026 would have counted 2026 riding.)
- Desktop-first: verify at about 1512px wide, then check phone width.

---

## Step 5b — Season Awareness ✅

Added after the first real review: the verdict engine called "Ride 100 km weekly" *too easy* and proposed 220 km/week, calibrated from July–September outdoor riding, at the start of a Polish autumn. Last winter (Dec 2025–Mar 2026, all indoor) the same goal was hit 8 of 13 weeks with a median of ~101 km.

- Athlete profile: `off_season_months` (default Oct–Mar, editable as a month range in the profile dialog; an empty list disables seasons). It appears in the athlete brief for coaching context.
- `services/seasons.py`: season of a date, season label, end of the current/next off season, next season change.
- History (`ride_km`, `run_km`, `zone2_hours` only): when the season 14 days ahead differs from the majority season of the recent periods, `history.season.reference` holds the same-season periods from the past year (up to 26 weeks / 6 months) with hit rate, median, p75 and margin.
- Yearly projection uses each season's own weekly pace for the rest of the year (`projection_basis: seasonal`): the 2026 ride projection moved from ~7,300 km to ~6,300 km.
- Verdicts judge recurring goals by the reference when the season is changing, calibrate target changes from it, and return the new non-urgent `season_change` verdict (review 4 weeks into the new season) when there is no reference. "Limit to the off season" uses the profile's season end (31 Mar) instead of a fixed 28 Feb.
- Yearly `inconsistent` now compares the season-aware projection with the target instead of the recent weekly pace.

---

## Step 6 — Goal Suggestions ✅

- New module `services/goal_suggestions.py` with generators. Each returns `{key, title, rationale, evidence[], draft: Goal payload, source}`:
  - `replace_completed` — a completed accumulation goal gets a next-period version (for example, "Ride N km in 2027", with N from this year's projected total × 1.05)
  - `plateau_to_quality` — a plateaued or too-easy volume goal becomes a quality goal (for example, "2 structured quality rides per week, Nov–Feb"). This needs a new `quality_sessions` metric type:
    - count activities with `workout_intent` in {tempo, interval, sweet_spot, race_specific}
    - intent is mostly missing today (124 of 152 activities since June), so fall back to power-based detection: at least 20 minutes at ≥ 88% of FTP, from streams
    - links to the `.zwo` cycling workouts, which can supply the sessions
  - `profile_weakness` — the weakest `category_levels` entry in the power profile (currently Climb, Aspiring) becomes a benchmark goal measured from ride data, with no dedicated FTP test
  - `season_template` — near a season boundary, a small set of off-season or build-season goals
  - `neglected_modality` — a sport dropped for 8+ weeks after regular use gets an optional small maintenance goal, only if modality restrictions allow it
- Rules: at most 3 suggestions shown; never duplicate an active goal's metric and period; respect modality restrictions and anchors.
- Persistence: a `goal_suggestion_decisions` table (same pattern as `project_idea_decisions`) for accepted or dismissed-until.
- Endpoints: `GET /goals/suggestions`, `POST /goals/suggestions/{key}/decision`. MCP tool `get_goal_suggestions`.
- UI: a "Suggested goals" section; Accept opens the existing draft-confirm form pre-filled.

Tests: each generator against date-pinned fixtures, de-duplication, restriction and anchor protection, API/MCP reads, persisted decisions and expiry, and quality-session counting.

Implementation details and deviations:

- `on_track_unproven` also qualifies for a quality draft. All five generators return editable drafts; accepting a draft records the decision only after the goal saves. Cancelling the editor keeps the suggestion available. Future goals save paused with a review date at their start.
- Near a boundary (within 21 days), quality and seasonal templates use completed weeks from the upcoming season in the past year. At least four reference weeks are required; missing same-season evidence produces no template. A zero quality-session p75 starts at one session through the count calibration minimum.
- Power profile suggestions require three recent monthly bests for the weakest category's limiting duration. Targets use p75 × 1.05, and already-achieved targets are suppressed. Suggested benchmarks opt into `target_config.measurement = power_stream`, measuring exact-duration efforts within normal rides; legacy average-power benchmarks retain their behavior.
- Power fallback uses the FTP recorded on or before the activity, verified cached power only, and the power-profile parser's maximum two-second sample gaps. At least 20 qualifying minutes must be backed by one continuous run of valid samples; explicit non-quality intent takes precedence. No streams are fetched while reading suggestions.
- Neglected means eight weeks without the sport after use in at least six of eight weeks. Maintenance targets are capped at one session for a four-week restart. Cycling frequency includes both outdoor and virtual rides.
- Both blocked and limited modalities are excluded. Paused goals also reserve their metric/period pair so scheduled drafts are not offered twice. Completed anchor goals do not generate replacement suggestions.
- Verified at 1512px and 390px. Save and Dismiss were checked with browser API writes mocked; the athlete's goals and profile were not modified. The requested focused unittest command and Vite build passed.

---

## Step 7 — Portfolio Check And Review Rhythm ✅

- Time budget (`services/goal_portfolio.py`): estimates the weekly hours each active goal implies and compares the sum with the hours trained per week. Flags over-commitment above 1.15× with a plain explanation and the biggest contributors.
  - Distance goals: km per week ÷ the athlete's average speed for that sport; session goals: sessions × median session length; zone 2 goals: hours as-is. Weekly and monthly goals use the period target; longer goals use remaining work over remaining weeks, so a reached goal costs nothing.
  - Anchor goals count towards the budget but are never listed as reduction candidates.
  - Zone 2 and quality-session goals share riding time with a ride-distance goal (only the largest adds hours), to avoid double counting.
  - Season-aware: the trailing 8 weeks, or the same season's past weeks (up to 26) when the season changes within 14 days. It needs at least 4 completed weeks and 1 h/week of training, otherwise the status is `insufficient_evidence`.
- It extends `plans._build_goal_conflicts` with a `time_budget` conflict in the existing format and is also returned as a `portfolio` block by `GET /goals/review`, MCP `get_goal_review`, and the Goals review panel.
- Review rhythm: the first weekly review of each month (the week whose Sunday falls on days 1–7) gets a read-only "Goals" section from `GET /reviews/weekly/goals?week_start=` (goals needing a decision, portfolio flag, suggestion count, link to `/goals`). The same digest is `goal_review` in the weekly review context. It never applies anything.
- MCP `get_goal_review` already shipped in Step 4; Step 7 only adds the portfolio block to its output.
- Docs: `docs/current-state.md` and this sprint's status updated; the roadmap has no goal-intelligence entry to change.

Tests: `backend/tests/test_goal_portfolio.py` covers over-commitment, anchor protection, overlap, yearly remaining work, inactive goals, sparse data, off-season history, the conflict format, the month-first rule, the API/MCP portfolio block and the read-only Goals section.

---

## Delivery Order

| Step | Depends on | Size | Ships something visible? |
|---|---|---|---|
| 1 Lifecycle | — | M | Yes: edit, complete, retire, anchor |
| 2 History | 1 | S | Yes: sparklines |
| 3 Signals | — (parallel with 2) | M | Partly: outcome sparkline |
| 4 Verdicts | 1, 2, 3 | L | Via Step 5 |
| 5 Review UI | 4 | M | Yes: the main feature |
| 6 Suggestions | 2, 4 | L | Yes |
| 7 Portfolio and rhythm ✅ | 4, 6 | S–M | Yes |

## Out Of Scope

- Model-generated verdicts inside the app (Claude discusses them through MCP instead)
- Automatic goal changes without confirmation
- Scheduling FTP tests (power benchmarks are measured from normal ride data)
