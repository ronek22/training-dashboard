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

### Each week builds on the last one

2026-10-15: implements the `week-builds-on-last-week` idea. Inside a winter arc, the planner and Plan now see how the previous week went against its block target. Built in `services/winter_arc.py` (`last_week_review`, `block_progress`); nothing new is stored.

- Last week's review: ride hours done vs target, key (sweet-spot/VO2) rides planned / hit / missed (skipped or replaced in the plan comparison), and follow-through counts for real sessions (rest days excluded, same classifier as plan follow-through).
- Planner context: `winter_arc.this_week` and `next_week` in `get_recent_context` each carry `note`, a compact `last_week` (`ride_hours` as [done, target], key rides, follow-through), `carry_over` and `next_week_lighter`. The weekly-plan prompt in `scripts/coach_helper.py` tells the planner to build on it, not to plan the carried ride twice, and to start the overview with the note.
- Carry-over rule (`fit_week_to_arc`, on save): one missed key ride of the block's type moves into the new week once, on top of the block's own key rides, onto the earliest free easy weekday ride that is not next to another hard ride. Never in a lighter week, never on a done, past, sick, illness or mountain re-entry, or life-load day, and never a ride that was itself carried (marked by its `planning_rule_reason` "Winter arc: carried over…"). Re-saving the week does not add it again; if the planner already added the extra ride, it is only marked.
- Plan shows the one-line note under the arc pill of the current and upcoming weeks (`winter_arc.note`), e.g. "Week 2 of 4 in Sweet-spot build, last week's SS ride moved here, last week 0 of 6 h riding, lighter week next". Missed rides that cannot move say why ("not carried (lighter week)", "already moved once", "no safe day to move it"). Past weeks skip the review to keep the plan list cheap.
- Verified with `test_winter_arc_progress.py` (carry-over and its note, no second carry, lighter-week block, guarded life-load day, planner context, a week with no arc). Backend 905, coach-helper 23 and frontend 163 tests plus the build pass. Live training data was not changed; the live database has no active arc, so the note was not viewed against real weeks.

### Fitness and fatigue ahead on Plan

2026-10-15: implements the `training-load-forecast` idea. Under the week preview, Plan shows "Where fitness and fatigue are heading": one small chart (42 logged days, then the rest of this week and the 4 preview weeks) and one plain-language line. Built by code in `services/load_forecast.py` (`GET /plans/load-forecast`, `weeks` 1–26, default 4); nothing is saved.

- Past days reuse the existing CTL/ATL model (`dashboard.build_training_load_summary`, 42/7-day constants). That model now scores stream power TSS with the FTP valid on the ride's day (`stream_power_tss_on_day`): stream summaries were scored with the FTP of the day they were fetched, so a ride backfilled after an FTP change kept the wrong FTP. The stored normalized power makes the rescale exact. On the live data no stream was fetched under a different FTP, so the Trends chart is unchanged. Rides without streams already used the dated FTP.
- Estimated days (dashed lines, shaded "Estimated" area, `estimated: true` in the API). The rest of this week comes from the saved plan's sessions: library-workout rides use the workout's intensity factor, other rides use an IF for each ride type (recovery 0.55, Z2 0.68, sweet spot 0.80, VO2 0.78), runs use the athlete's own run load per minute, and lifts and other sessions use the logged duration rates. Each preview week is one weekly load spread over its days. Rides come from the winter arc block (key rides as their library workouts, the rest of the hours at Z2), else this week's plan, else the last 4 weeks. Other sessions repeat this week's plan or the last 4 weeks. Mountains days shrink rides to the days off the trip and add a trip day each: the average load on past Mountains days in the last 120 days, else a 4-hour hike. Re-entry and illness windows are not modelled.
- Ramp = fitness change from Sunday to Sunday. A week rising more than 7 CTL points is flagged as too steep (`RAMP_STEEP`, the upper end of the usual 5–8/week guidance; the live CTL sits around 75–115). The flagged week is tinted red and the line warns, with trip-aware wording for a Mountains week. In a base, sweet-spot or VO2 block, full (non-lighter) weeks averaging under +1/week (`RAMP_FLAT`) are flagged as too flat. Maintain blocks and weeks outside the arc are only checked for steep ramps. Otherwise the line reads e.g. "Fitness 75 → ~70 by Nov 15 (−1.1 a week): easing off at the planned load."
- Verified with `test_load_forecast.py` (11 tests: the dated-FTP stream rescale and average-power rides on their day's FTP; planned session and arc ride load; the projection continuing from today's CTL and marked estimated; steep, flat, maintain, Mountains trip, no-plan and no-history cases; the API). Backend 899 and frontend 163 tests plus the build pass. Viewed in the browser at 1512 px against a scratch copy of the live database. Today's plan and the Oct 19–25 Mountains week give "The mountains week of Oct 19 raises fitness by ~13, above the safe 7 a week: keep the rides around it easy." Live training data was not changed.

### Season timeline on Plan

2026-10-15: implements the `season-map-timeline` idea. Plan shows a read-only "Season" strip under the Winter arc card: about 20 weeks (2 back, at least 20 in all, stretched to the arc's end up to 26; an arc that started up to 6 weeks back sets the start) built by `services/season_timeline.py` (`GET /plans/season-timeline`) from data other pages already keep.

- Arc blocks are flat coloured bands with lighter weeks dimmed in the week row; Mountains trips (life-load runs, linking to the recap once a hike is logged) are bars, non-weekly goal target dates and goal review dates are pins (linking to Goals), the running stall block is a thin amber bar (linking to Strength), and "You are here" marks today with the current week outlined. Pins stack into up to 3 lanes so labels do not collide. Dates past the window are listed as "Later: …".
- Any subset works: with no arc the weeks are neutral and a line points to the arc planner; with nothing at all the card hides. When the timeline draws the arc, the Winter arc card hides its own strip (header and editor stay); arc edits reload the timeline.
- Clicking a week: a week with a saved plan (and the current week) opens that plan; a future week opens its row in the week preview, which now asks for more weeks when needed (`GET /plans/week-preview?weeks=` 1–26, default still 4) and highlights the row. Past weeks without a plan are not clickable. FTP retests are not shown: the app has no retest date to read yet.
- Verified with `test_season_timeline.py` (4 tests: empty season window and links, arc window/bands/lighter weeks capped at 26 weeks, trips/goal dates/stall block/later and plan vs preview links, the API and the longer preview) and `season-timeline.test.mjs` (positions, month ticks, pin lanes). Backend 888 and frontend 163 tests plus the build pass. In the browser at 1512 px and 375 px with no horizontal overflow: the live database read-only (no arc, Oct 19–25 trip, Nov 4 goal review, Jan 7 goal date, Upright Row stall block), and a scratch database with a three-block arc where clicking the week of Dec 7 expanded the preview to 8 weeks and the current week opened its plan. Live training data was not changed.

### Next four weeks on Plan

2026-10-15: implements the `four-week-plan-preview` idea. Under the current week, Plan shows "Where the next weeks are heading": one compact row for each of the next 4 weeks, built by code (`services/week_preview.py`, `GET /plans/week-preview`), never by the coach and never saved. Only the current week keeps day-by-day detail; a preview week becomes a real plan when it arrives ("Plan saved" shows if one already exists).

- A row says only what is different about that week. Without a winter arc a normal week is just "Normal week"; the weekly goals are not repeated on every row (first version did that and was reworked the same day as noise).
- Mountains trip: a full trip week reads "Hikes instead of rides · 3 short travel lifts" (no ride or quality target); a partial trip shrinks the arc hours or goal km to the days off the trip ("~55 km rides", "Hikes Fri–Sun") and lifts get a travel version on trip days.
- Re-entry after a trip (same `window_length`/`easy_days` as `mountain_reentry`, also for trips still ahead): "Easy only Mon–Tue · no intervals until Fri", lifts "legs at pre-trip loads", and the quality ride is placed on the days after the window ("1× quality ride, Fri–Sun"). An open illness return window caps effort the same way; "Sick mode on" shows on next week.
- Life-load tags show as pills by weekday with their note; no quality ride goes on them, and 3+ tagged days add "Busy week". Z2 rides are never restricted. Goal end and review dates show as pills.
- With a winter arc every row also shows the block and week number, ride hours and key rides from `winter_arc.arc_week` (matching `week_target`), "Lighter week" and "New block". The card hides when nothing is known (no arc, no events, only weekly goals). Shown only while viewing the current week; it reloads when the arc is edited. `minimum_week.anchor_session_counts` was split out of the minimum week's anchor read for the lift count.
- Verified with `test_week_preview.py` (6 tests: rows match `arc_week` incl. a lighter week and a new block; partial trip, re-entry, busy and deadline weeks with key rides placed on open days; illness window into next week; full trip and re-entry without an arc while normal weeks stay empty; partial trip shrinks goal km; hidden with only weekly goals, plus the API). Frontend 160 tests and the build pass; the backend suite passes except one `test_cycling_power_advice` failure from separate uncommitted work in `scripts/cycling_power_helper.py`. On a scratch copy of the database at 1512 px and 375 px (no horizontal overflow): Oct 19–25 trip, Oct 26–29 re-entry with the quality ride Fri–Sun, and two normal weeks. Live training data was not changed.

### Eat enough before the sessions that matter

2026-10-15: implements the `fuel-before-hard-sessions` idea. Food, the pre-session brief and Weekly Review now share one under-fuelled rule: a finished day with food logged below 85% of its target (`food_log.UNDER_SHARE`). `food_log.fuel_status_by_day` returns only judged days, so an unlogged or still-running day is unknown and never under-fuelled.

- Food → What to eat next: when tomorrow's saved plan has a hard ride or a lower-body lift (`fuelling.planned_key_session`, using the lift/ride clash rule's `is_hard_ride` and `is_lower_lift`), the card says "Leg day tomorrow, aim for the full target today" (or "Hard ride tomorrow…") with the session title. About 55% of what is left should come from carbs (`PRE_SESSION_CARB_SHARE`): each meal shows its carb grams, idea ranking adds a carb term, and "Ask Claude" passes tomorrow's session and the carb goal. The kcal target itself is unchanged.
- Pre-session brief: rides, runs, lifts and hikes get one note, "Yesterday was logged under-fuelled (X of Y kcal)…", only when the previous day had food logged and fell short. The brief also carries `under_fuelled_yesterday`.
- Weekly Review: `GET /reviews/weekly/report` has `fuelling` (`fuelling.fuel_session_comparison`): average post-session energy (1–5) and RPE for sessions after fuelled versus under-fuelled days over the last 12 weeks, walks excluded. A card "Sessions after fuelled vs under-fuelled days" appears only when each side has at least 4 logged days behind a rated session.
- Verified with `test_fuel_before_sessions.py` (7 tests: leg day and hard ride named, easy ride and upper lift ignored, carb-leaning ideas, brief note only after a logged short day, unlogged days unknown, comparison hidden at 4 vs 3 days and shown at 4 vs 4); backend 876 and frontend 160 tests plus the build pass. Not checked in the browser; live training data was not changed.

### Winter arc for cycling

2026-10-15: Plan opens with a Winter arc strip: a few dated blocks (Base, Sweet-spot build, VO2 touch, Maintain), each with weekly ride hours, a target ride mix (Z2, sweet spot and VO2 rides per week) and an optional lighter week every 3–5 weeks. The arc only shapes rides; lifts, anchors and minimum weeks are never changed.

- Storage and API: `winter_arc_blocks` (`services/winter_arc.py`). `GET /plans/winter-arc` returns the blocks, the current week's target, status (none, upcoming, active, gap, finished) and recent weekly ride hours; `PUT` replaces the whole arc (blocks run Monday to Sunday and cannot overlap); `DELETE` clears it. Saved weekly plans are not touched by editing or clearing.
- Strip: one horizontal bar per block, sized by weeks, with lighter weeks dimmed, "You are here" and the current block, week number and weeks left. "Edit arc" opens a back-to-back block editor; an empty arc offers a November–February template (base, sweet-spot build, VO2 touch) sized from recent ride hours. Each week card shows a pill such as "Sweet-spot build · wk 2/6 · lighter", which turns amber with "1 sweet spot short" when the saved week misses a key ride.
- Planner: the coach's recent context has `winter_arc` with `this_week` and `next_week` (block, week number, lighter flag, `ride_hours`, `ride_mix`, `key_types`), and the weekly-plan prompt tells the coach to plan rides to that block. When a new week is saved (`upsert_weekly_plan_data`), `fit_week_to_arc` converts open easy rides into any missing key ride (Sweet spot 3 × 10 or VO2 5 × 3 from the workout library, weekdays and away from other quality rides first, never the long ride) and, in a lighter week, trims easy rides to about 60% of the block's hours (30 minutes minimum). Days that are past, done, sick, in an illness or mountain re-entry window or tagged in life load never get a quality ride. The lift/ride clash rule runs afterwards. Adjustments and minimum weeks are not refitted; the week's `winter_arc` status reports any shortfall instead.
- A lighter week keeps one of each key ride and one fewer Z2 ride.
- Verified with `test_winter_arc.py` (8 tests: create/edit/clear, validation, strip position, coaching context, key rides added, tagged days skipped, lighter-week trim with lifts kept, weeks outside the arc untouched); backend 858, scripts 59 and frontend 160 tests plus the build pass. On a scratch copy of the database at 1512 px and 375 px: created, edited (strip rescaled), cleared, and saved the template. Live training data was not changed and no arc was created there.

### Stall blocks shape later suggestions

2026-10-14: A running stall block now shows outside Strength, and finished blocks steer the next stall suggestion for the same lift.

- Dashboard: the Load & recovery card shows "Dumbbell Upright Row stall block, week 2 of 3" (or that the weeks are done and the block should be finished), linking to Strength. The payload is `stall_block` from `stall_blocks.current_block`; the coach's recent context gets the same key.
- Pre-session brief: a strength day whose saved workout includes the block's lift gets a note with the week and the block's change (`session_brief._session_block_notes`).
- Suggestions: `stall_blocks.block_results` scores each finished multi-week block (kept or reverted) by the original lift's best estimated 1RM from the block's start until the next block for that lift (or today), against the stall it answered. `find_plateaus` then chooses between a rep scheme and a variation/tempo: it repeats a kind that added 1 kg or more, and when the default kind last added less and the other kind is untried, it tries the other one. A micro-deload (lift sliding back) is never overridden. The reason is in `suggestion.history.text` ("Last rep scheme block (12 Oct) added 2.6 kg to the estimated 1RM."), shown in the brief's stalled lifts, their hover text and the workout's stall note. Starting a block applies the reranked suggestion.
- Lifts with no finished block get exactly the old suggestion and no `history`. Only the same lift's own blocks count; similar lifts are not pooled yet.

### Data-quality inbox

2026-10-14: Data & Sync opens with a small inbox of gaps from the last 30 days, and the Data & Sync nav item shows a count badge (9+ above nine) only while items are open. `services/data_inbox.py` detects four kinds:

- Missing feedback: activities without `activity_feedback`. Walks are skipped, and so are lifts recorded in Workout Studio (a completed `strength_workout_sessions` row already holds per-set effort taps). Fix: "Add feedback" opens the usual feedback dialog.
- Unmatched planned session: past plan days whose plan-vs-actual status is `skipped` (rest days never count). Fix: link one of the plan's own `link_candidates` (±2 days) through `POST /activities/{id}/link-plan`. Activities linked elsewhere, or already fulfilling another planned session, are not offered, so a link never unmatches another day; one done on a rest day stays on offer. "Skipped, that's right" dismisses it.
- Missing heart-rate stream: Strava runs and rides with no cached streams, or whose streams lack the heart rate Strava reported (`avg_hr` set, `has_heartrate` 0). Manual entries the history backfill marked `no_streams` are skipped. Fix: "Re-fetch streams" (`POST /data-inbox/streams/{id}/refetch`) fetches that one activity and stores streams plus the stream summary; if Strava has no heart rate the item stays and says so.
- Stale benchmark: the working FTP once `working_ftp` calls it stale (a logged or typed FTP older than 56 days; the training estimate never goes stale). Not limited to 30 days. Fix: "Update FTP" goes to the Athlete page; "Still holds" dismisses it. The key carries the FTP's date, so a newer FTP that later goes stale shows again.

Every item can be marked as fine (`POST /data-inbox/dismiss {key}`, stored in `data_inbox_dismissals`); only keys currently open are accepted, and dismissed keys never come back. Resolved items disappear by themselves because detection reads the data. `GET /data-inbox` returns `count`, per-kind `counts` and the items. The nav badge loads on start, follows the inbox as it changes, and recounts on navigation at most once a minute.

- Verified with `test_data_inbox.py` (6 tests: detection for each kind, the 30-day window, candidate filtering, dismissals and self-resolving items) and `data-inbox.test.mjs`; backend 841 and frontend 158 tests plus the build pass. On a scratch copy of the database at 1512 px: dismiss, add feedback and link each removed their item after reload and the badge followed; the real data has 6 open items, all missing feedback. Live training data was not changed.

### Lift and hard-ride clash rule

2026-10-14: A leg lift no longer lands the day before or after a hard ride without a word. `services/lift_ride_clash.py` defines the rule: a hard ride is a ride with tempo, interval or race-specific intent, or a Tempo / Sweet spot / Threshold / VO2 max library workout; a leg lift is a lift that trains legs (`strength_lower`, or a whole-body saved workout with leg exercises, via `session_brief._trains_legs`). Upper-body lifts, mobility and easy, long, Z2 or recovery rides never clash. Plans hold one session per day, so the same-day case does not arise.

- Generation: `upsert_weekly_plan_data` (coach `set_weekly_plan` and the plan API) swaps days until no clash is left or no swap helps (up to 3 swaps; past days and days with a recorded activity never move). The lift moves first, then the ride; a moved lift carries a `planning_rule_reason`, and the response lists `clash_swaps`.
- Manual moves are never blocked. `POST /plans/weekly/swap` returns `clashes` for the moved days, each with a `suggested_swap` that leaves the session the athlete just placed where it is. Calendar shows it in the move toast ("Legs (Tue) is the day before Sweet spot (Wed)…") with a "Swap … instead" button next to Undo.
- Plan page: every serialized plan carries `lift_ride_clashes`; open clashes show as a one-line banner with the swap button, or "No clean day left this week".
- Coach adjustments (`adjust_weekly_plan_data`) are not reshuffled automatically; a clash they create shows in the banner.
- Verified with `test_lift_ride_clash.py` (11 tests: detection, exemptions, swap choice with locked and pinned days, resolve, generation and a warned move with its swap) and `lift-ride-clash.test.mjs`; backend 835 and frontend 155 tests plus the build pass. The last three real plans serialize with no clash; live training data was not changed.

### Automatic database backups

2026-10-14: `data/training.db` is no longer a single point of failure. `services/backups.py` takes snapshots with SQLite's online backup API into `data/backups/` and verifies each with `PRAGMA integrity_check` (a failed copy is discarded and the failure recorded in `backup-status.json`).

- When: an hourly check in the backend lifespan takes one copy a day; `init_db` takes one before migrations at startup (skipped for new/empty databases and when a copy is under an hour old; the first copy of a day counts as the daily one). `just backup` or Data & Sync → "Back up now" takes a manual copy.
- Retention: newest copy of each of the last 7 days and the 4 weeks before them, plus the last 2 startup copies. Only `training-YYYYMMDD-HHMMSS-<kind>.db` files are pruned.
- Data & Sync → Database backups: last good backup, Up to date / Overdue (no good copy for 36 h) / Failed with the message, and the saved copies.
- `just restore <file>`: integrity-checks the backup, stops the stack, keeps the replaced database as `training.db.replaced-<time>`, puts the backup in place and restarts what was running.
- Verified with `test_backups.py` (backup of a live WAL database and restore with matching row counts, integrity failure status, retention, startup rules, `init_db` hook, CLI); backend 824 and frontend tests plus the build pass. The running app took its first copies (482 MB each, integrity ok) and the panel was checked at 1512 px. `just restore` was dry-run only; no restore was performed on live data.

### Backup restore drill

2026-10-15: backups are now proven to restore, not just to pass `PRAGMA integrity_check`. `backups.restore_drill` copies the newest backup into a temporary `restore-drill-*` directory beside the backups (cleared at the start of the next drill if a restart killed one mid-copy), runs `init_db(snapshot=False)` on that copy in a child process (`TRAINING_DB_PATH` points at the copy, so the running app's `db.DB_PATH` is never swapped and no extra snapshot is taken), integrity-checks the migrated copy and runs smoke queries (activity count, latest activity date, `weekly_plans` count; zero activities fails). The result (OK or the reason, e.g. `Migrations failed: …`) is saved in `data/backups/restore-drill.json` and returned as `restore_drill` by `GET /backups`.

- When: weekly from the backup loop (`restore_drill_due`, 7 days since the last drill), `just restore-drill`, or Data & Sync → "Test restore" (`POST /backups/drill`).
- Data & Sync → Database backups: "Last restore drill: OK, 2 days ago — <file> migrated with N activities (latest …) and N plan weeks", or the failure and its reason.
- Real restore steps are in the README (Backups → Restoring for real).
- Verified with `RestoreDrillTests` in `test_backups.py` (fixture backup built by the real migrations; live file and backup unchanged, scratch copy and a stale killed-drill copy removed, no extra backup; migration failure, smoke failure, no backup, CLI). Backend 863 and frontend 160 tests plus the build pass. No drill was run against the live data/backups in this change.

### Fixed-step adjustable dumbbells

2026-10-14: Home gym → Dumbbells has "Adjusts in" (Auto / 1 / 2 / 2.5 kg), stored as `dumbbell_step_kg` in the athlete profile. Auto (null) keeps the old rule: +1 kg under 10 kg, then +2 kg. With a step set, every dumbbell load suggested lands on a setting the dumbbells can make (e.g. 2–24 kg in 2 kg steps):

- Progression (`strength_progression._heavier`): the next setting above the top load, so 6 → 8 kg and an older odd 7 kg → 8 kg. The heaviest-dumbbell cap still switches to reps.
- Plateau suggestions: lighter and heavier loads use the setting below / two settings above.
- Set coach in the runner: "add" goes to the next setting, drops round down to one. The runner's −/+ load buttons move by the step on dumbbell lifts.
- Dumbbell detection in the frontend now uses the same name hints as the backend (Hammer Curls, lateral and rear-delt raises, goblet squats), so those lifts get dumbbell steps in the set coach too.
- Verified with progression, plateau, profile and set-coach tests; backend 818 and frontend 153 tests plus the build pass. Barbell lifts are unchanged.

### Plates per side and suggested warm-ups

2026-10-14: the workout runner does the barbell plate maths. `frontend/src/coach/plates.mjs` holds the logic and `components/PlateStack.vue` draws the plates.

- Barbell lifts (named "Barbell …" or classic bar lifts such as Back Squat and Romanian Deadlift; not dumbbell, machine, cable, Smith, trap-bar or bodyweight) show the plates per side under the target, as a small coloured stack plus text, e.g. "25 + 1.25 per side". A target at or below the bar shows "Empty bar". When a target cannot be loaded exactly, it adds "nearest 62.5 kg"; ties go to the lighter load. The stored target and progression are never changed.
- Breakdown: the nearest loadable weight with the fewest plates, using only the plates owned. Each side needs one, so a size loads in pairs (3 × 20 kg gives one per side and a spare). Not greedy, so a 15 kg bar with 15/10 plates loads 55 kg as 10 + 10.
- Athlete page → **Home gym** card: a barbell preview loaded with everything you own, heaviest load and smallest jump, a bar picker (20/15/10 or any weight), and a plate rack with a count per size, add/remove sizes. Adjustable dumbbells ("up to 24 kg each", the existing `max_dumbbell_kg`) moved here from Profile; plates are for the bar only. Stored in the athlete profile as `bar_weight_kg` and `plates` (`[{kg, count}]`, total plates owned). Defaults: a 20 kg bar and 2 each of 25/20/15/10/5/2.5/1.25.
- "Suggest warm-ups" (barbell lifts with no warm-ups yet): adds up to 3 ordinary warm-up sets at about 50% × 8, 70% × 5 and 85% × 3 of the first working set, each rounded to a loadable weight and kept below it. They use the existing warm-up endpoint, can be removed, and never count as working sets.
- Verified with 7 frontend plate tests (incl. targets below the bar, unloadable targets, limited plate counts), 2 profile normalization tests and the profile persistence smoke test. Backend 816 tests, frontend 152 tests and the build pass. The Home gym card was checked in the local app at 1512 px (counts update the preview; the test edit was discarded). The runner was not opened on a live session, so no workout data was created.

### Detailed streams for the whole Strava history

2026-10-13: after importing Strava history back to 2013, 2,109 older runs and rides had only summary numbers, so their fastest-distance records, season bests, charts and maps were missing. The existing "Fetch next 12" backfill skips runs without heart rate, which is most of them before 2022.

- `services/strava_history_backfill.py` fetches full streams in the background: runs first, newest first, in batches of up to 60 about every 16 minutes. It stops a batch while 35% of Strava's 15-minute or daily limit is still free, so syncing and activity pages keep working; at the default 1,000 requests a day that is about 3 days for the whole history.
- Each activity is tried once and recorded in `strava_history_backfill` (fetched, no_streams for manual entries, or failed with up to 3 attempts). A rate-limit error or a network problem pauses the batch without marking anything. Progress is committed after every activity.
- Streams are cached like detail-page fetches (`activity_details.streams_json`). A training-load stream summary is stored only when the streams carry heart rate or power; without either it would count the whole session as easy aerobic time.
- Switched on and off from Data & Sync ("Detailed history" card with progress and what happens next: "Fetching a batch of up to 60 now", "Next batch of up to 60 about 15:41", or the pause reason; between batches the count holds still on purpose), or `POST /integrations/strava/history-backfill {"enabled": true}`; `GET` gives the status. It switches itself off when nothing is left. The loop runs in the backend (`STRAVA_HISTORY_BACKFILL=false` disables it).
- Full streams take about 150 KB per run and 300 KB per ride: the database grows from about 226 MB to about 600 MB.
- Faster path from a Strava bulk export: `services/strava_export_import.py` reads the export's original files (FIT, TCX, GPX, gzipped or not) through `activities.csv` (Activity ID to file) and converts them to Strava-shaped streams: equal-length `time`, `distance` (the device's, or measured along the track for GPX), `latlng` (last fix carried through dropouts), `altitude`, `heartrate`, `watts`, `cadence`, `velocity_smooth`. It fills only runs and rides that have no streams, marks them done for the API backfill, and stores a training-load summary only with heart rate or power. XML with a DOCTYPE or entity declarations is refused, and only files inside the export folder are read. `POST /integrations/strava/export-import {"dry_run": true|false}` reads `STRAVA_EXPORT_DIR` (default `/data/strava-export`, i.e. `data/strava-export` on the host), so the import runs inside the backend container that owns the database.
- Checked against 40 activities the API had already fetched (all four formats): total distance differs by a median 0.0% (max 0.26%), fastest-window times by at most 0.7 s. On 2026-10-13 the export filled 1,182 activities in 58 s (0 unreadable); the API had fetched 834 before that, and the remaining 55 activities without an export file are left to the API backfill.
- With streams for the whole history the first Records read computes efforts once (about 9 s); after that Records takes about 0.4 s. The database grew from 226 MB to 481 MB.
- Tests: `backend/tests/test_strava_history_backfill.py`, `backend/tests/test_strava_export_import.py`.

### Ready for full Strava history

2026-10-13: preparing to import Strava history back to 2013 (about 2,300 runs and rides against 468 activities today). A simulated import of 2,657 older activities on a copy of the database took the Dashboard from 0.2 s to 5.3 s and the coaching context from 0.45 s to 2 s. Both are back to about 0.5 s.

- `build_training_load_summary` warmed its CTL/ATL model from the first activity ever, re-estimating thresholds for every day without stream data. It now warms up from at most `TRAINING_LOAD_WARMUP_DAYS` (365) before the chart. It starts on that cap date, so the first-day seed fades too. With the 42-day constant, older training weighs under 0.02%: on the real data the chart is identical, and on the simulated history it differs by at most a 0.1 rounding step.
- `estimate_thresholds` took the all-time max HR, so a reading from years ago would have lifted today's zones and load scores. Max HR now counts only the last `MAX_HR_LOOKBACK_DAYS` (730) before the day being scored.
- The Sync page's Strava import request now allows 10 minutes instead of the default 8 seconds, so a multi-year date range is not reported as failed while it is still running.
- Tests: `backend/tests/test_training_load_history.py`.

### Season in review

2026-10-13: implements the `season-in-review` idea. `/season/:year` pulls one calendar year onto one page. It adds no tracking and, like the monthly letter, calls no LLM.

- `services/season_review.py`. Each section reuses the code behind the page it links to, so the numbers match. Totals by sport use the Dashboard year-chart query (Ride + VirtualRide, Run, WeightTraining, Hike, Walk and Other), plus all-session hours and active days. They are compared with the previous year only when that year has any activity. The longest streak inside the year counts activities and finished guided sessions, like the Records wall. Records set come from Records-wall progressions: a best that beat an earlier best, or the year's first attempt when the record is new that year. A first ever attempt alone does not count. Each record is linked to its activity. Lifts that progressed most are the top 5 lift records improved in the year, with loaded lifts before bodyweight reps. Mountains shows trail first walked and summits first reached in the year, inside the national parks, like the Mountains "new trail by year" figure. The best month is the one with the most training hours, walks excluded. Goals lists those completed in the year and active weekly goals as weeks kept out of full weeks since each goal started.
- Empty sections are `null` or `[]` and the page hides them; a sport with no sessions is left out.
- Every year with activity is available, the running year included and shown "so far" (browser date). `GET /season-review?day=` lists years and when the running year's coach paragraph opens, `GET /season-review/{year}?day=` returns the review (404 for a year with no activity) with `coach_opens_on`, and `POST /season-review/{year}/coach?day=` writes the closing paragraph (409 before it opens). The running year's paragraph waits for 1 December because it is saved once and never rewritten. The Dashboard year charts link to "Your {year} so far" all year ("in review" in December).
- The coach paragraph is deterministic. It is built from the year's facts and that year's saved monthly letters (the most common win kind, and the last letter's focus). It is written only on request and saved in `season_reviews` (year primary key). A repeat request returns it unchanged. The rest of the page is computed live, so it stays in step with the source pages.
- `months` (12 buckets of hours and sessions, with per-sport hours/km/sessions) and `days` (each active day's minutes and main sport) feed the page's charts; they are the same activity rows as the totals.
- UI: `views/SeasonReview.vue` is a celebratory, flat, animated year story. A giant year with count-up totals and pills against last year; the whole year as a day grid coloured by each day's main sport (streak days underlined); "The year in sport" as one composition: a split bar of the year's hours by sport, a ranked sport list (biggest first, Other last; count-up km, or hours for strength and other; change against last year; a share-of-hours line), and one hours-by-month chart stacked by sport, where hovering or focusing a sport highlights it; the longest streak with a year timeline and best month with an hours-by-month chart; trophy cards for the six biggest improvements, then the rest on request; lift bars that grow from the old best to the new one; a summit skyline per mountain range (tallest in the middle, snow caps; well-spaced summits are labelled, and every summit shows a tooltip with its name, height and first-reached date on hover, keyboard focus or tap) beside new trail km and a park coverage ring; goal check badges and kept-weeks rings; and the coach paragraph as a closing quote. Sections slide in as they scroll into view; reduced-motion users get static content. Links: "Season in review" on the Records hero, and "Your {year} so far" on the Dashboard year charts.
- Career context (2026-10-13, after the Strava history import back to 2013): `career.years` gives every year from the first activity to the last (gaps included) with hours by sport, sessions, active days, ride/run km and strength sessions; `available` marks which reviews open. `career.badges` ranks the year against all years: "Most X of any year" (with the previous best), "Most X up to then" (a record later beaten, naming the year that beat it), "Most X since YYYY" (3+ years back), or "#N of M years" for a top three. "Since" and top-three badges need at least 25% of the best year's value, so a quiet year is not praised for 2 sessions; up to 4 badges, records first. `career.milestones` lists lifetime totals (km of running, km of riding, activities, hours) that crossed a round number during the year, with the activity that crossed it.
- UI: the year chips became a story strip, one stacked bar per year (hours by sport, the selected year highlighted, empty gap years dimmed), which scrolls inside itself on phones. Badges sit under the hero numbers; "Lifetime milestones" cards (count-up value, date, linked activity) follow "The year in sport".
- Fair comparisons while the year runs: the running year's totals, sport changes and pills compare with the same dates last year (`totals.compared_until`, "vs 2025 by 13 Oct"), and `totals.pace` sets hours to date against the biggest other year at the same date ("160 h ahead of 2017's pace"). Finished years still compare full year with full year.
- Season bests: `_rank` in `personal_records.py` now also keeps each year's best (`yearly`) and `higher_is_better`; `build_personal_records` strips `yearly` from the API unless `include_yearly=True`, so the Records payload does not grow. `season_bests` frames the year's best in each run, bike-distance and power record against every season: "Best of any season", "Best season yet, until 2024", "Best since 2019" (2+ years back) or "#2 of 9 seasons"; at least 3 seasons with the effort are needed, and records already listed as new bests are not repeated. Pre-2022 runs and rides only have longest and biggest-climb bests until their streams are fetched.
- The coach paragraph adds career context: biggest year since the first one, a comeback from the latest low point in the last six years (4× its sessions), a record year for riding or running, the biggest lifetime milestone, and a "best since" season best. "Rewrite" (confirmed, `POST .../coach?rewrite=true`) replaces a saved paragraph with one from today's numbers and keeps the replaced text as `previous`, shown under "Previous version".
- Not included: the illness and heel comeback. No existing service summarises it per year, so the page does not invent one.
- Verified with 10 unit tests (`backend/tests/test_season_review.py`), the full backend suite, the frontend tests and build, and in the browser against a copy of the database (2024 and a simulated December 2026, dark theme, at 1512px and 390px widths).

### Roadmap page shows open threads and what shipped

2026-10-13: the Roadmap page still pointed at Sprint 33 from July, while the work since then came from the Ideas board. Roadmap V3 is closed and archived, and the page now reads what is actually current.

- `docs/roadmap.md` says `Active roadmap: none` and lists the open threads. `planning_status.py` returns `open_threads`, `archived` roadmaps, and `shipped`: dated entries from this section, newest first, each with its first useful sentence.
- Phase status is read from a `Status: complete` line under a phase heading. The old hardcoded text matching on this file is gone.
- Sprint statuses fixed: 33 and 38 superseded, 34 complete, 35 partially implemented (the data-quality inbox is still open), 36 complete (it was missing from the page).
- UI: open threads and a "Where planning lives" card linking to Ideas, a "Recently shipped" list grouped by month (12 shown, then "Show all"), and an archive with the roadmaps and a collapsed sprint list.
- Verified with the updated planning smoke test, `just check`, and in the browser at 1512 px and 375 px (dark).

### Polish meal names: Dinner = obiad, Supper = kolacja

2026-10-13: the Food page follows the Polish day. The stored meal keys are unchanged (`breakfast`, `lunch`, `dinner`, `snack`), so no data moved. `lunch` is now labelled **Dinner** (obiad, the main cooked meal) and `dinner` is labelled **Supper** (kolacja).

- The dinner planner plans obiad: `dinner_plan.PLANNED_MEAL = "lunch"`. "Log as eaten" prefills that meal, the planner's ✓ Logged mark checks it, and meal ideas stop subtracting the planned dish once it is logged.
- Copy says "today's planned" instead of "tonight's"; meal-time windows (`defaultMeal`, `MEAL_ENDS`) are unchanged.

### Shopping list from planned dinners

2026-10-13: implements the `dinner-plan-shopping-list` idea. Food → Dinner plan has a **Shopping list** button that opens a panel under the week table.

- Day chips pick the dates within the displayed week (opening it selects the planned days from today on, or every planned day for a past week). No days selected shows "Pick the days you are shopping for"; days without dinners say so.
- `GET /nutrition/dinners/shopping-list?dates=YYYY-MM-DD,...` (`dinner_plan.shopping_list`, at most 14 days) scales each recipe ingredient's grams by planned servings ÷ recipe servings and sums them. Items merge only on the same `product_id`, otherwise only on the same name after lower-casing and collapsing spaces and edge punctuation (no plural, synonym or diacritic matching). Every item keeps its contributing dinners and grams.
- Ingredients without grams, recipes without ingredients and free-text dinners are listed under **Needs review** with their original amount text and source dinner; no amount is guessed or converted.
- Items can be ticked as already at home; **Copy list** copies the remaining items with quantities, the selected dates and the review items. If the clipboard is unavailable, the text appears in a selectable box.
- The preview refetches when the selected days, the week or a dinner (portions, recipe) change. It is read-only: it never writes dinner plans, recipes or food logs. "At home" ticks live only in the open page.
- Verified with 4 backend tests (300 g for two servings gives 150 g for one, sums across dinners, distinct products and unlinked names kept apart, review items, read-only and portion changes), 3 frontend tests for the copied text and gram formatting, the full backend (753) and frontend (133) suites, and the frontend build. Checked in the browser at 1512 px against a throwaway backend on a copy of the database (live data unchanged).

### Compact coaching context for MCP

2026-10-08: MCP `get_recent_context` returned about 200k characters, which coach sessions could not read in one go. It now returns a compact view by default (about 42k characters, minified). `services/recent_context_view.py` builds it from the unchanged `build_recent_context` bundle.

- Every section stays. Plan days lose link candidates; goals appear once as summaries instead of three full copies; the training-load chart keeps only the last 7 days; cycling power keeps levels and records; strength sessions keep totals and major lifts. Null and empty values are dropped, but null top-level sections such as `sick_mode` stay explicit.
- `detail_tools` names the tool to call for each section's detail. `workout_template_settings` is left out.
- `detail: "full"` returns the original bundle. `GET /context/recent` and the internal callers (coaching, recovery, team analysis) are unchanged. The stdio server in `mcp/server.py` now calls the backend MCP tool, so both servers return the same output.
- Verified with 3 unit tests, an MCP smoke test, the full backend and script suites, and the live server: 42,221 characters compact against 202,643 full.

### Monthly letter from your coach

2026-10-07: implements the `monthly-coach-letter` idea. A short letter looks back at one finished calendar month: up to three wins, one pattern and one focus for the next month. It is deterministic (no LLM) and written only when the athlete presses the button; nothing generates it automatically.

- `services/monthly_letters.py`. Wins, each citing its numbers with links: all-time bests set that month (a progression step that beat an earlier best; a first ever attempt doesn't count), cited with the old best and linked to the activity and the Records wall; a streak milestone reached for the first time, otherwise the month's longest run of active days (7+) with the full streak length; a weekly goal kept in 3+ of the month's full weeks or a monthly goal met; and training time against the average of the three months before (or active on at least half the days). The pattern is the strongest of: sleep (month average against the median of the 60 nights before, and days at 3+ h of 7-night sleep debt), life load (tagged days and missed planned sessions on them), or the top confirmed "what worked" pattern. The focus is a goal missed that month (anchor first), a thin-month restart, a sleep or life-load habit, the last weekly review's change, a what-worked pattern, or "repeat the rhythm".
- A thin month (fewer than 4 training sessions and fewer than 6 active days) gets a short, honest letter: no consistency win, only real records or milestones, and a restart focus. An empty month says nothing was logged.
- Saved in `monthly_letters` (month primary key, JSON snapshot). A saved letter is returned unchanged on a repeat request, so later syncs never rewrite it. Only finished months can be written.
- `GET /reviews/monthly-letters?day=` lists saved letters (newest first) and the status: last month's letter is offered on days 1–7 of a month until written. `POST /reviews/monthly-letters/{YYYY-MM}?day=` writes one (`day` is the browser's date; the container clock is UTC).
- UI: `weekly-review/MonthlyLetters.vue` at the top of Weekly Review. During the offer window it shows "Write the September letter" as the primary action; after day 7 an unwritten last month still has a quiet button. Past letters are month pills; a letter written for last month stays open during the first days of the month.
- Verified with 9 backend tests (empty and thin months, a beaten record with its old best and link, first-ever attempts ignored, goal/streak/consistency wins, a streak carried in from the previous month, a missed anchor goal as the focus, short sleep as the pattern, immutability and finished-months-only, the offer window), the related suites and the frontend build. On a copy of the real database (live data unchanged): September 2026 gives 11 new all-time bests, Ride 100 km weekly kept in 3 of 3 full weeks, 45 h (+18% on the 3 months before), "sleep held up", and "Protect Lift three times per week" (kept in 2 of 3 full weeks) as the focus. Checked in the browser at 1512 px and 375 px.

### Hike activity page: map first

2026-10-07: hikes, walks and trail runs that were synced as mountain tracks get their own Activity Detail presentation (`HikeAnalysis.vue`), led by the mountain map right under the title, above feedback and the streak card. `GET /activities/{id}` now carries `mountain_region` (set when the activity is in `mountain_tracks`), and `activityPresentation(type, mountainRegion)` picks the map-first page only for Hike/Walk/TrailRun with a region; the same sports elsewhere keep the usual layout. Wording follows the type (Hike / Walk / Trail run overview, "Reached on this walk"), and trail runs also show average pace.

- `GET /trails/activity/{id}` (`services/hike_detail.py`) returns the hike's mountain context when the activity is a synced mountain track: the detailed GPS track with altitude (10 m), trail sections around it (walked ones flagged, and whether this was the first time), places around it (reached here / first time), valley labels, and totals (marked trail km, new trail km, summits, first-time summits). ~80 KB gzipped. Mountain hikes and walks older than the activity history (2016–2024, 74 of them) are added to `activities` during "Sync hikes" with the regular Strava import code (`_add_missing_to_history`, one request each, resumes after a rate limit), so they get detail pages; their streams load on first open. Mountain runs are left out so old runs don't land on the personal best wall; year charts only use the current year. Not a mountain activity → `{"region": null}` (the page doesn't ask in that case; endurance layouts are titled "Hike overview" / "Walk overview").
- Map: the same grey relief, labels and place icons as the Mountains page (shared `trails/map.css`, `trails/baseMap.js`); walked trails bold in their colours, first-time ones with a green glow, the GPS track in violet, other trails faint, S/F pins, region and park chip linking to `/mountains/{region}`. Wheel zoom only after clicking the map, so the page scrolls past it.
- Elevation profile under the map, built from the track by distance, with reached summits/passes marked (first time in green). Hovering moves a marker on the map. Then the overview (distance, moving and elapsed time, ascent/descent, highest point, marked trail and summits with first-time counts, HR) and two lists: summits & places reached and trails walked (merged by name, new km tagged).
- API responses are now gzipped (`GZipMiddleware`): the Tatras map payload went from 2.5 MB to 670 KB.
- Verified with a backend test for the hike context and 5 frontend tests (profile, stats with a dead band, chart geometry, trails merged by name, places ordering), the full suites (551 backend, 78 frontend) and the build. In the browser at 1512 px on the 6 Mar 2026 Karkonosze hike: Vysoká pláň headline, 16.5 km of marked trail (0.3 km new), 3 summits (Sowiniec first time), profile hover following the map.

### Mountains: trail coverage, summits and places

2026-10-07: a Mountains page (`/mountains/:region`) shows which marked trails in the Tatras and Karkonosze the athlete has walked, plus the summits, passes, caves and huts reached.

- Trails come from OpenStreetMap hiking relations with standard PTTK/KST/KČT marks (`osmc:symbol` `<colour>:white:<colour>_bar`), split into junction-to-junction sections and kept inside the national parks (TPN/TANAP, KPN/KRNAP). A section that runs along the state border (half of it within 40 m of both parks' boundaries, e.g. Kasprowy – Kopa Kondracka, the Polish-Czech Friendship trail) belongs to both parks (`trail_sections.parks_json`): 22 km in the Tatras, 16 km in Karkonosze. Trails and places outside the parks but within 8 km of a park boundary (Szklarska Poręba, Piechowice, Karpacz, Zakopane, Kościelisko) are assigned to the nearest park and flagged `around`: always drawn on the map, but counted in the figures (%, km, sections, summits & places, new km per hike) only with the "Include trails around the park" switch (off by default, remembered per browser). Range tabs always use the parks only. For KPN only (`REGIONS[...]['bike_parks']`), OSM bicycle/MTB routes count too as a muted mauve "Bike" trail colour (names in grey) (walked in winter around Szklarska Poręba), only where no marked hiking trail runs on the same path: 247 km, 11 km of it inside the park. KPN: 125 km in the park, 665 km with the area around it. Adding the cycle routes splits more trails at junctions (Karkonosze has 1740 sections now). One Overpass request per range also brings park boundaries and named places (`POST /trails/{region}/import`, `services/trail_coverage.py`). Overpass is slow at times (a Tatras import took 3.7 min with retries; Karkonosze 6 s).
- GPS comes straight from Strava into `mountain_tracks` (`POST /trails/sync-hikes`), separate from `activities`, so hikes back to 2016 don't change other stats. Only foot activities starting or ending inside a range are fetched; a cursor (`trail_tracks_synced_until`) makes later syncs incremental.
- Coverage: 10 m samples along each section; a sample counts when a track passes within 30 m; 80% of samples = done, 25% = partly. Track jumps over 200 m (lifts, lost signal) never count. A second pass handles drifting GPS (forests, valleys): a section not done yet still counts when a track runs within 150 m of it along 85% of its length, this section is the nearest marked trail wherever the track is (so a parallel trail doesn't get the credit), and the track gets within 150 m of both ends (Piechowice – Pod Wielkim Szyszakiem: 145 m drift, now done; Za Zmarzłym Stawem – Zadni Granat: turned back 208 m short, stays partial). It flipped 17 sections (8 km) in Karkonosze and 2 (2.3 km) in the Tatras.
- Places: summits within 80 m of a marked trail, passes within 40 m, caves within 30 m (the trail goes to them), huts within 150 m. A place is reached when a track gets as close as the trail does plus 30 m (min 50–80 m by kind); summits and passes with a height: walking within 25 m of the marker always counts (Mały Kościelec's marker sits on the trail); a near miss beyond that also needs the track's altitude within 35 m of the summit height, so turning back below a top doesn't count (Świnica: 61 m away, 75 m below). Strava altitude, barometric or terrain-corrected, matched pass and hut heights within ±25 m on hikes from 2016 to 2026. Tracks without any altitude need a 50 m pass. Sync backfills altitude for older tracks (92 in 46 s). Border places belong to every park whose boundary lies within 60 m; cave entrance/exit pairs are merged.
- UI: grey/dark Esri relief (Mapy.com outdoor in grey when `MAPY_API_KEY` is set). Done sections are bold in their trail colour; shared trails show their colours side by side like Mapy.cz (a pixel-offset polyline, sections oriented west→east so the order holds at junctions); partly walked are dashed, the rest thin grey dots. Choosing a park fades the other one and is remembered per range. Mapy.cz-style labels (`trails/labelLayer.js`, toggle "Labels"): summit names with heights (Polish name for border summits), hut/pass/cave names, valley names letter-spaced along the valley (OSM `natural=valley`, stored in `map_labels`), and section names along trails in their colour from zoom 13.5. Rebuilt on every move/zoom; placed in priority order (summits by height, each claiming its icon too, then long valleys, huts, passes, short valleys, caves, trail names) and skipped when they would overlap. Side panel: % and km, by colour, new trail by year, summits & places with reached/not yet filters, longest sections to do, hikes with new km.
- Route ideas (`?view=routes`, `services/route_ideas.py`, `GET /trails/{region}/routes?park=&length=half|day|long&around=`): day hikes from a trailhead (OSM bus stop or public car park within 300 m of a trail junction, stop codes stripped) that pick up the most not-yet-walked trail in 4, 7 or 10 h. Walking time is Naismith with descent (5 km/h + 1 h per 600 m up + 1 h per 1000 m down), checked against TPN signposts. Ascent per section from OpenTopoData EU-DEM 25 m, sampled every 100 m and cached in `elevation_cache` (public API: 100 points per request, 1 request/s; Open-Meteo counts each point as a request, 600/min, too few). The planner merges missing sections into chains (stopping at junctions and trailheads), then from every trailhead greedily inserts the chain with the most new metres per extra hour (cheapest insertion for the orienteering problem), as loops and as one-way routes that must finish at a bus stop (so there is a way back; scored at 75% so loops win unless the one-way is clearly better); each summit/pass not reached yet on a missing section counts as 1 km extra. Routes under 40% of the budget, with under 1 km or 20% new trail, or mostly overlapping a better one are dropped; best 8 shown. Cached in memory per data state (0.1 s Tatras, 1.2 s Karkonosze). The view dims the coverage map and draws the selected route (new trail green, walked white, S/F pins). Each route carries a `track` of [lat, lon, ele] every 100 m read from `elevation_cache` only (sampled the same way as at import, so no API calls); the map shows it as an elevation profile panel (shared `components/trails/ElevationProfile.vue`, also used on the hike page) with summits/passes not reached yet in green and a hover marker on the map. The panel's GPX button exports the route client-side (`routeGpx` in `trails/routes.mjs`): GPX 1.1 track with the full trail geometry, heights interpolated from the 100 m track, and waypoints for start/finish, huts and summits/passes (higher one kept within 300 m), for Mapy.com, OsmAnd, Garmin Connect courses or Strava.
- Route planner (`?view=plan`, `services/route_planner.py`, `POST /trails/{region}/plan` with `points: [[lat, lon, snap_m?]]`, `simplify`): click points on the map and the route between them follows the marked trails (multi-source Dijkstra on the route-ideas `TrailGraph` by walking time, entering/leaving the clicked sections at either end; partial sections are cut at the clicked offset). A click snaps to the nearest trail within ~30 screen px (at least 200 m, stored per point); further out it stays put and is joined with a dashed straight off-trail line (timed as flat walking). Answer: snapped waypoints named after the nearest summit/pass/hut (150 m) or trailhead (300 m), segments split by new trail / walked / off trail, a [lat, lon, ele] track with heights interpolated from the cached 100 m samples, distance, Naismith time, ascent/descent, highest point, new-trail metres and places on the way; ~40 ms per request, network cached per data state. UI: drag a point to move it, right-click to remove, click the line to insert (`legAt`), click a summit/hut marker to add it, click the start to close a loop, Undo (also Ctrl/Cmd+Z), Back to start, Reverse, Clear; double-click zoom is off while planning. Trails are drawn as a thin colour backdrop (dashed when not walked). The draft is kept per range in localStorage (`mountains.plan.<region>`). The shared profile panel (collapsible, remembered) shows the live profile, and GPX exports through `trackGpx`. Route ideas have "Edit in planner": start, the midpoint of every walked section and the finish, then `simplify` drops points the route passes anyway (24 km Kozi Wierch loop → 6 points, same route). A Full screen button on the map (every view) puts the map and its side panel over the whole window (teleported to `<body>`, since the page's entrance animation leaves a transform that traps `position: fixed`) and also asks the browser for real full screen where allowed; Esc or the button exits, and a ResizeObserver keeps Leaflet's size right. In full screen the side panel slides away; hovering the edge tab (or the panel) slides it back over the map, clicking the tab pins it.
- Saved routes (`saved_routes` table; `GET/POST /trails/{region}/saved-routes`, `PUT/DELETE /trails/saved-routes/{id}`): the planner saves the clicked points (not the geometry) with a name and an optional collection (free text; a case-only variant joins the existing spelling). The list re-plans every route so distance, time and "new trail" follow the trails walked since saving ("all walked" once nothing is new). In the planner: Save route (name defaults to the route title, collection picked from existing or typed), an open saved route shows "Saved as …" with unsaved-changes state, Save changes / Save as new; the Saved routes card groups by collection (A–Z, uncollected last) with open, rename/move and delete (inline confirm). Opening goes through undo history; the link between the draft and its saved route survives a reload (`mountains.planRoute.<region>`); the saved name titles the profile panel and the GPX. It does not know one-way rules (Orla Perć Zawrat → Kozi Wierch) or closures.
- On real data: 55 Tatras and 37 Karkonosze activities; TPN 179 of 264 km (68%), 45 of 96 summits, all 8 huts.
- Verified with 14 backend tests (sections, coverage, places, Strava sync with rate limit) and 12 frontend tests, the full suites (515 backend, 60 frontend) and the build. Checked in the browser at 1512 px in dark mode.

### Coach drawer: check-ins, unread replies, groups and suggestions

2026-10-07: the last coach-moments step. The coach drawer leads with what the coach has to say and keeps chats sorted by what they are about.

- "From your coach" (`services/coach_moments.py`, `GET /notes/chat/moments?day=`): the latest training session's win for two days, and the week's "3 wins, 1 focus" on Sunday (this week) and Monday (last week), each until its linked chat exists. Session wins come from the week wins cache (`session_wins_for_week`). Opening one creates the chat with the coach's opener, which retires it. Refreshed when the drawer opens, after any linked chat changes, and every 10 minutes.
- Unread: `coach_chat_conversations.last_read_message_id` (existing chats migrate as read); conversations list `unread_count` (coach messages after it), and `POST /notes/chat/conversations/{id}/read` marks one read. A reply that finishes while the drawer is closed stays unread; the drawer opens on the first unread chat.
- The Coach launcher gets a dot when there is a moment or an unread reply.
- The list is grouped Sessions / Days / Weeks / General, groups ordered by their newest chat.
- An empty chat suggests three questions based on the page the drawer was opened from (Activity Detail, Today, Plan, Weekly Review, Strength, Recovery, or a default set).
- While Codex works, the thinking bubble shows the stage and elapsed time; the timing and debug panel sit behind "Details" (and still open on their own for the idle warning).
- Verified with 3 backend tests (unread until read, a session moment until its chat exists and its expiry, Monday's last-week moment), 3 frontend tests (grouping, page suggestions, moment requests) and `just check` (501 backend, 27 helper and 48 frontend tests, plus the build). In the browser at 1512 px on real data: the launcher dot, the 6 Oct lift as a moment, page suggestions, and opening the moment (the chat it created was deleted again). The thinking bubble was not seen live because no Codex message was sent.

### Three wins, one focus

2026-10-07: the third coach moment. Each week gets up to three wins and one focus, built from the athlete's own data, so it shows instantly on any day.

- `services/week_wins.py` (`GET /reviews/weekly/wins?week_start=&day=`): wins are the strongest session wins of the week (the same picker as the Activity Detail card, score 40+, one per session; walks are left out), weekly goals met (an anchor goal scores highest), every or most planned sessions done (from the plan comparison), and moving every day (3+ days so far). If nothing qualifies but something was logged, a "N min of movement in the bank" fallback. The focus is the saved Sunday review's proposed change when there is one; mid-week, the first open weekly goal (anchor first) with the days left; otherwise the most important "next time" from the week's flagged session reads; otherwise "Keep the rhythm".
- Results are cached in memory, keyed on everything they depend on (the week's activities, feedback and detail, plan, saved review, goals and logged strength sets). A full week takes about 0.25 s to build.
- The Sunday AI review's context now carries `week_wins`, and its prompt asks it to lead "improved" with the most meaningful of them, never adding wins the data doesn't show.
- UI: `WeekWinsCard.vue` at the top of Weekly Review → This week, with a This week / Last week switch (it opens on last week on Monday and Tuesday), and on the Dashboard on Sunday (this week) and Monday (last week). Wins link to their session; "Talk it through" opens a chat linked to the week (`context_kind: "week"`, its Monday), and the helper tells Codex to help turn the focus into sessions.
- Verified with 5 tests on a real schema (anchor goal and review focus, mid-week goal focus and moving every day, the fallback, at most three wins one per session, the cache noticing a new session), a week-chat test, helper and frontend tests, and `just check`. On real data: 28 Sep week shows the lift anchor kept (4 against 3), 7 of 7 planned sessions done and 1 of 5 lifts up, with the Sunday review's change as the focus; this week so far shows 73 min in the bank and "Lift three times per week: 2 to go". Checked at 1512 px and 375 px.

### "Feeling flat" / "Short on time" on Today

2026-10-07: the second coach moment. A planned Today card has a "Going in" row with two chips; each one opens two or three ready-made versions of today's session instead of a blank chat.

- Options (`services/today_options.py`, `GET /plans/today/options?reason=flat|short&day=`): flat gives an easy version (60% of the time, min 30 min, Zone 2; "Lighter version" when it is already easy) or, for a lift, the same lifts with 2 working sets and no new loads; a move to a later day that makes today lighter (a rest day, or an easy ride in place of a lift, never a tagged day, and a lift never next to another lift); and rest, never offered on a lift day because lifting three times a week is an anchor. Short gives a 30-min version (25 min for a lift: main lifts only, still counts), the move, and "Shrink the whole week" (the existing minimum week, previewed then applied) unless it is already on. Nothing is offered on a rest day or once a non-walk activity is recorded.
- Applying (`POST /plans/today/options/apply`) is an ordinary plan adjustment or swap, so it is a plan revision with a reason like "Feeling flat: rest today". The card shows what changed with an Undo (`POST /plans/today/options/undo`), which puts the session back. A walk doesn't lock the day here: `adjust_weekly_plan_data` and `swap_weekly_plan_days_data` take `unprotected_dates` for days whose only activity doesn't complete the planned session.
- The browser sends its local date, because the backend container runs on UTC and "today" differs around midnight.
- "Talk it through" opens a chat linked to the day (`context_kind: "day"`), whose opener lists the options. The helper tells Codex the chat is about that day's plan and to recommend one change the card can apply.
- A completed Today card shows the session win with "Talk this through".
- Verified with 6 tests on a real schema (options per session type, the lift move, apply and undo with a walk logged, a move and its undo, nothing to change), a day-chat test, a helper test, a frontend test and `just check` (493 backend, 27 helper and 44 frontend tests, plus the build). On real data at 1512 px and 375 px both panels open for today's easy ride; nothing was applied to the real plan.

### Session win and session-linked coach chats

2026-10-07: the first step of "coach moments". The coach now speaks first after a session, and the in-app Codex chat stays, attached to what it is about.

- Win: `services/session_win.py` picks the single most encouraging fact about a session. Candidates: wins collected by the session read (`wins` on each read: a power best, heart rate lower at the same power, least drift of recent steady rides, pace faster at the same heart rate, a clean or stage-up return-to-run run, lifts up or a new best, the weekly strength goal done, easy kept easy), all-time top-3 places from the record wall, "showed up on a tough day" (going-in tile from check-in or life-load tags), a sick-mode session, done as planned, the streak, and a fallback "Nth session of the week in the bank", so there is always one. Streak milestones (7…365, then every 100) are a big win; other streak days are a fallback that counts down to the next milestone. The detail payload carries it as `win` (`kind`, `headline`, `detail`, up to two `also` lines, and `opener`).
- UI: `SessionWinCard.vue` sits under "How it felt" on Activity Detail, with "Talk this through" (or "Continue the chat" with a message count) when the coach drawer is available.
- Linked chats: `coach_chat_conversations` gains `context_kind` / `context_id` (only `activity` for now). `POST /notes/chat/conversations/open` returns the latest chat for that context or creates one whose first message is the coach's opener; `GET /notes/chat/conversations` filters by context. Linked chats keep their title, show a "Session" tag in the drawer and an "About this session" link back. Pages open the drawer through `coach/chat-bus.js`.
- Codex: the drawer sends `context: {kind: "activity", id}` to `/coach-chat`; the helper validates it and tells Codex to read `get_activity_analysis_context` for that activity first and lead with what went well when the evidence supports it. The helper advertises a `coach_chat_context` capability, so an older running helper must be restarted.
- A question typed in the session read's box now goes to the session's chat (when the drawer is available); "Get coach read" without a question still runs the one-shot analysis.
- Verified with 7 unit tests (wins, streak, linked conversations), a helper test, 3 frontend tests and `just check` (485 backend, 27 helper and 43 frontend tests, plus the build). On real data at 1512 px and 375 px: the 29 Sep ride shows "Showed up on a tough day"; "Talk this through" created the linked chat with the opener (deleted again afterwards). No Codex message was sent.

### Session read replaces the coach analysis

2026-10-06: the old Activity Detail coach card mostly summarised the session, so it is replaced by `services/session_read.py`: a rule-based read that compares the session with your own earlier sessions (never later ones), shown below the charts in `SessionReadPanel.vue`.

- Ride: heart-rate drift ranked against the last 6 steady rides (closest to zero wins), heart rate at the same power against the earliest comparable ride (both from `aerobic_decoupling`, same environment, 12 weeks), power bests for hard rides, and time above Zone 2 for easy rides without a power meter. Next time: +5–10 W when drift stays under 3.5%, hold under 5%, drop 10 W (or fix fuelling after a bonk) above it.
- Run: return-to-run stage and symptom outcome, average heart rate against the easy cap, and pace against runs of similar duration at an average heart rate within 5 bpm (6 months). Next time comes from the return-to-run next step.
- Strength: the two main lifts (compound lifts first) with their per-session e1RM series, lifts up/same/down on last time, and the weekly strength goal. A main lift with no increase in 4+ sessions sets the verdict, and its double-progression hint becomes the next-time line; fixed-load accessories are shown but never flagged.
- Shared: planned vs done, and a "going in" tile from the day's check-in and life-load tags; one "watch" item (pain, a bonk, RPE 9+ with soreness, a hard session on a busy day, HR over the easy cap).
- Asking: the panel has a question box. The app saves the question on the analysis request (`activity_analysis_requests.question`; omitting it keeps a pending one, `""` asks for a general read), then starts Codex as before. The analysis context carries `question`, `session_read` and question-aware instructions, and the saved analysis keeps the question. The full-analysis modal is gone.
- Verified with 7 unit tests, a question round-trip smoke test, `just check`, and in the browser on a database copy at 1512 px (dark and light) and 375 px.

### Aerobic fitness without a test

2026-10-05: `services/aerobic_decoupling.py` tracks heart-rate drift (Pw:HR decoupling) and power per heartbeat (W/bpm) on steady rides, so winter base fitness shows up from ordinary Zone 2 rides with no FTP test. It reads the cached power and heart-rate streams through the `power_trends` segment parser; nothing is estimated or written as FTP.

- Qualifying: Ride/VirtualRide of 45+ min with measured power (same `device_watts` / VirtualRide-backfill rule as the power profile), not planned as tempo, intervals or race-specific. The first 10 min and last 5 min are trimmed; power and heart rate must cover 90% of the rest, zero watts at most 10%, normalized/average power at most 1.10, and average power at most 80% of the latest stored FTP (skipped with no FTP). Every other ride in the window is listed with its reason.
- Per ride: efficiency over the trimmed window, and decoupling = efficiency drop from the first to the second half (under 5% is steady).
- Trend, per environment (indoor = VirtualRide or Strava `trainer`; outdoor otherwise): needs 3 qualifying rides, else `unavailable`. Direction comes from heart rate at the same power, a least-squares fit of `avg_hr ~ avg_watts + day` once there are 5+ rides with a 10 W spread, because raw W/bpm also rises on harder rides; with fewer it falls back to the efficiency slope (±2%). A same-power comparison (latest ride against the earliest within ±7% power) gives the coach line, e.g. "Same power, 7 bpm lower than on 4 Sep".
- API: `GET /metrics/aerobic-decoupling?weeks=8..26` (default 12). Coach: `aerobic_fitness` in `get_recent_context` (trends, last 5 rides, rules), and MCP `get_aerobic_fitness_trend` on both servers.
- UI: "05 / Your aerobic base", the last section on Trends → Cycling power. A two-line heading ("Same power. Lower heart rate."), a hero verdict (bpm change at the same power, with direction pill and three mini stats), a "then and now" pair of rides at similar power, two single-axis charts (power per heartbeat with a dashed trend line; drift with the steady zone under 5% shaded), a ride table with half-by-half heart rate and drift chips, and the excluded rides with reasons. Indoor/outdoor and 8/12/26-week toggles sit top right.
- Real data (12 weeks to 2026-10-05): 7 indoor rides qualify, about 4.6 bpm lower at the same power over 17 days. No outdoor ride qualifies yet because outdoor rides have no power meter.
- Verified with 10 unit tests and an endpoint/MCP smoke test (`just check`: backend, helper and frontend tests plus the build), and in the browser at 1512 px and 375 px.

### Two-minute downshift

2026-10-05: `services/downshift.py` offers a guided breathing or mobility block on a high-stress day: today's check-in stress 4–5/5, or today tagged deadline or late night. It is never offered in sick mode. This is step 3 of the "stress and life" set.

- Guided engine: `services/guided_sessions.py` now holds the session catalog, time estimates, finished-session records (still in `sick_session_completions`) and watch-workout matching, all moved from `sick_mode.py`. Each session has a `context`: `sick` (offered by severity, names an Apple Watch workout, matched to the synced activity) or `stress`. `sick_mode.py` keeps periods, severities, the manual log and the sick-mode state.
- Sessions: "Two-minute downshift" (1 min physiological sighs, 1 min box breathing, no gap between them via `transition_seconds: 0`) and "Desk mobility" (about 7 min). Neither names a watch workout.
- Streak: days with a finished guided session count toward the daily streak and the records-wall streaks, so a downshift keeps the streak without creating an activity (no fake training volume). Downshift sessions are never matched to a synced activity, so a real ride near the same time is never relabelled as mobility.
- API: `GET /guided-sessions/{key}` and `POST /guided-sessions/complete` replace the old `/sick-mode/sessions/…` and `/sick-mode/complete`; `GET /downshift`; `downshift` in the dashboard payload and in `get_recent_context`.
- UI: a compact Downshift card under the Today card when offered, showing the reasons, both sessions and its done state. The follow-along page is now `GuidedSession.vue` at `/guided/:key` (old `/sick-mode/:key` links redirect). It takes its label from the context, skips the watch step when a session has no watch workout, and offers the manual log only for sick sessions.
- Verified with 8 unit tests and an API smoke test (441 backend, 26 helper and 27 frontend tests, plus the build). In the browser on a database copy with sick mode ended and a stress-5 check-in: the card appeared, the two-minute session ran without a watch step and saved, and the streak went from 275 to 276 days with no new activity.
- 2026-10-13: also offered on a planned Rest or Recovery day while nothing is recorded yet (reason "planned rest day" / "planned recovery day", `rest_day: true`), so resting never costs the streak. The card and coach guidance then say it keeps the streak and still counts as rest.

### Recovery days

2026-10-13: `services/recovery_day.py` defines a deterministic cap for a light day that keeps the daily streak and still counts as rest.

- Cap: every activity that day is a walk ≤60 min, a mobility block ≤30 min (Yoga, Pilates, Stretching, PhysicalTherapy, Mobility, Recovery, or any session tagged `mobility`), or an easy spin (Ride/VirtualRide) ≤45 min with average HR below the start of riding zone 2 from the Athlete page (140 bpm default; without HR only a ride tagged `recovery` fits); together ≤60 min; no hard or strength intent. Unknown types do not qualify.
- Streak: unchanged. Any activity keeps it, so going over the cap never breaks it.
- Readiness: days under the cap are left out of "Training days in 7d" (`active_days_7d`, risk at 6+) and counted in a new `recovery_days_7d` factor and metric.
- Plan: planned Rest and Recovery days carry `recovery_cap` (limits plus a one-line summary shown on the Plan day card). Their comparison carries `recovery_check` (`within_cap`, `total_min`, `over` reasons). A walk or mobility block under the cap now matches a planned Recovery day; a Recovery match over the cap is labelled "Matched · over cap"; a Rest day with only light activity reads "Light day · counts as rest" and is not counted as changed in the week summary; otherwise the over-cap reasons are shown in the day's status detail.
- Not done: the planner does not propose recovery days by itself; "Feeling flat" on the Today card covers that.
- Verified with 10 unit tests (`backend/tests/test_recovery_day.py`), the full backend suite (763 tests) and the frontend build.

### Minimum viable week

2026-10-05: `services/minimum_week.py` shrinks the rest of the current week to the smallest plan that keeps the anchor goals. This is step 2 of the "stress and life" set. It is an ordinary plan adjustment, so past and completed days are protected and every change is a plan revision.

- Targets: weekly session-count anchors (`strength_sessions`, or `activities_count` for WeightTraining or Ride) give the lift count, or 2 lifts if there's no anchor; rides are 2 easy, or more if a ride anchor asks. Anchors count even after their end date. Sessions already done this week count toward the target.
- Shape: lifts stay lifts (title "Strength", so the template rotation still assigns A/B/C/D) at 30 min, main lifts only. Rides are easy at 40 min, and every other open day rests. Travel days and sick-mode days get nothing. Lifts are spread out, avoiding back-to-back days (including next to lifts already done) and life-load days, and prefer days that already had a lift. Rides prefer untagged days that were already rides. If the days left can't fit the anchor, the summary says so.
- API: `POST /plans/weekly/{week_start}/minimum-week/preview` (proposal plus diff), `POST …/minimum-week` (apply), `POST …/minimum-week/restore` (puts back the open days from the plan saved in that revision). Plans get `minimum_week` (`active`, `summary`) from the latest such revision; a later "Restored full week" revision clears it. It ends with the week.
- Coach: `minimum_week` in `get_recent_context`, and the plan-revision prompt keeps a shrunk week small unless the feedback asks for more. MCP `preview_minimum_week` shows the proposal without changing anything; `set_minimum_week` with `active: true` shrinks the week and `active: false` restores it. Both default to the current week.
- UI: a "Minimum week" button next to "Manage week" on the current plan opens a before → after preview with a confirm. While it's on, the week shows a "Minimum viable week" pill and the button becomes "Restore full week".
- Verified with 8 unit tests and an API round-trip smoke test (432 backend, 26 helper and 27 frontend tests, plus the build). Applied and restored in the browser on a copy of the database with a seeded week: Monday (sick) and the deadline Thursday rested, lifts landed Wed/Fri/Sun as C → D → A, and restore brought back the exact original days.

### Life-load tags

2026-10-05: `services/life_load.py` lets the athlete tag days as travel, deadline, family, poor sleep or late night. Sick mode is a period about the body; these are per-day tags about time and attention, so they never add a body-risk penalty or pause the plan. This is step 1 of the "stress and life" set; a minimum viable week and a two-minute downshift will build on it.

- Storage: one row per day in `life_load_days` (tags plus an optional note). `GET /life-load?start&end` returns the tag list and tagged days; `PUT /life-load/{date}` replaces a day's tags, and an empty list clears the day. A tag added after the day is marked `tagged_after`.
- Plans get `life_load`: tags per day, plus conflicts for intervals, tempo, race-specific or 90+ min sessions on a tagged day from today on (lifts and easy sessions are fine). Each conflict suggests the nearest open day in the same week with a calm session and no hard neighbour. The Plan page lists them with a one-click swap through `/plans/weekly/swap`.
- Weekly review context has `life_load` with the week's tags and `missed_on_tagged_days` (e.g. "Missed 2 sessions, both on deadline days."). The Sunday review prompt treats those misses as life load, not motivation.
- Volume trend: a falling week with 3+ tagged days is labelled `life` automatically (sick mode still takes priority as `illness_injury`).
- Readiness: poor sleep tagged today or a late night yesterday adds a 1-point caution, but only when there is no check-in today (the check-in already rates sleep).
- Coach: `life_load` in `get_recent_context` (last 7 and next 14 days, with guidance); the weekly planning prompt keeps hard and long sessions off upcoming tagged days. MCP `get_life_load` reads tags; `set_life_load_day` replaces one day's tags (an empty list clears it), so the athlete can say "I'm travelling Thursday" in chat.
- UI: a tag picker in the calendar day popup and in the Plan session dialog; tag icons on calendar cells with a legend entry; sand `--life` chips on plan cards, outlined when they clash.
- Verified with 8 unit tests, 2 volume-trend tests and an API smoke test (423 backend, 26 helper and 27 frontend tests, plus the build). Checked in the browser against a copy of the database: tag picker, cell icons, clash banner and swap.

### Mountain trip days

2026-10-09: a `mountains` life-load tag (▲) for trips where a hike is the day's session. It is the one tag that is also about the body.

- Plans: a hike on a Mountains day is never a life-load conflict, even when it is long; rides on those days still are.
- Lift volume (`services/strength_volume.py`): no accessory sets on Mountains days, and with 2+ Mountains days in the week legs show "hiking" instead of a shortfall, so no leg sets are added.
- Travel kit (`services/guided_sessions.py`, context `travel`): `travel_upper` (push-ups, pike push-ups, backpack rows, chair dips, backpack curls, about 23 min) and `travel_core`. The Apple Watch workout syncs as WeightTraining, so these count toward lifting 3× a week. They have no template, so the A/B/C/D rotation waits until you are home.
- Briefs: hike days get a hike brief (fuel, water, a descent and knee bail rule, "counts as leg work"). Strength days titled "Travel kit" get a bodyweight brief, and Today's main button opens the guided session.
- Coach: `life_load.mountains_guidance` in `get_recent_context` when a trip is ahead. The planning prompt tells the coach to plan one hike a day, no rides or runs, and Travel kit lifts.

### Back from the mountains

2026-10-14: `services/mountain_reentry.py` opens a re-entry window when a run of 3+ consecutive Mountains days ends. The window starts the day after the last one and lasts about half the trip: 3–4 days → 2, 5–6 → 3, 7+ → 4 (cap). Shorter runs open none. The first day (or the first 2 in a 3–4 day window) is "easy only" (RPE ≤4, easy rides). The rest is "moderate" (RPE ≤6), still with no intervals.

- Briefs: rides, runs and hikes are capped at the window's RPE; quality rides get "ride it as endurance" as the first bail rule. Lower-body lifts (intent `strength_lower`, or legs in the saved workout) get 2+ reps in reserve and a "pre-trip loads" note. Upper-body and Travel kit lifts are untouched. With an illness-return window open too, the lower RPE cap wins.
- Loads (`services/progression_guard.py`, rule 5): inside the window, a leg lift last logged before the trip ends stays at that load. Once it has been done after the trip, it progresses as usual.
- Lift volume: no leg accessory sets on window days. Other groups still get their top-up, and no lift session is removed or shortened.
- Readiness: a "Back from the mountains" factor (caution, 1 point) and a hint in the readiness panel.
- Coach: `mountain_reentry` is in the dashboard payload and `get_recent_context`. The planning prompt keeps sessions within `rpe_cap` until `window_ends_on`, with no extra leg sets and the first leg lift at pre-trip loads.
- Verified with 9 re-entry tests (trip lengths, a trip ending on a Sunday, overlap with return from illness), plus 1 progression-guard and 1 lift-volume test. `just check`: 814 backend, 59 helper and 145 frontend tests, plus the build. Not checked against live data.

### Mountain trip recap

2026-10-14: `services/mountain_trips.py` turns each run of consecutive Mountains-tagged days into a trip. A run counts once it has a Hike, Walk or TrailRun on one of its days. Each trip has a recap at `/mountains/trips/<first day>` (`GET /trails/trips/{date}`; any day of the trip finds it). `GET /trails/trips` lists past trips newest first, plus tagged runs still ahead with no hikes yet.

- Recap (`views/TripRecap.vue`): count-up totals for distance, ascent (activity elevation) and hours. New trail km, summits and the highest point show when the data exists. New trail and first summits come from the trail coverage, as on the hike page: a section or place counts as new when a trip activity was the first to walk or reach it. A bar shows the trip's share of the calendar year's ascent across all sports.
- Map: every GPS track of the trip on one relief map, one colour per day. Tracks come from the trail sync (`mountain_tracks`), or from the activity's streams for hikes outside a mapped range. Hovering a day card or a legend chip highlights that day's routes.
- Day cards: one per trip day, rest days included. Each shows the day's highlight (highest summit, else highest pass or hut, else the longest outing's name, with a "first time" tag), an elevation profile chaining the day's outings (`trails/trip.mjs`), stats and links to the activities.
- Links: a Trips card on Mountains (coverage view), "Trip recap" on the Dashboard re-entry hint, and a Mountain trips block in Season in review (`mountain_trips` in the review payload).
- Verified with 5 backend tests (trip detection, upcoming runs, coverage and season share, streams fallback, API and season review) and 2 frontend helper tests. 850 backend and 160 frontend tests pass, and the build passes. Checked in the browser at 1512 px against a scratch copy of the database, with the March Karkonosze hikes tagged as a trip. Live data has no past tagged trip yet; the 19–25 Oct trip is listed as upcoming.

### Return from illness

2026-10-09: `services/illness_return.py` covers the days after sick mode ends. The window lasts as long as the sickness did (3–7 days). It stretches to 3 days after the last feedback or check-in note that mentions symptoms (English or Polish), up to 14 days. The first half is "easy only" (RPE ≤5, lifts at 3+ reps in reserve). Any day with symptoms noted in the last 2 days is also easy only. The rest of the window is "moderate" (RPE ≤7, no intervals or max lifts). Sessions rated RPE 8+ inside the window are named.

- Readiness: a "Back from illness" factor, 1 point, or 2 while symptoms are still in the notes.
- Briefs: the cap overrides the session's effort target and reps in reserve, adds a headache or chest stop rule, and leads the notes.
- Lift volume: no accessory sets on days in the window.
- Today: a hint in the readiness panel. `illness_return` is in the dashboard payload and in `get_recent_context`, and the planning prompt keeps every session within `rpe_cap` until `window_ends_on`.
- Verified with 8 illness-return, 2 life-load, 2 lift-volume and 3 brief tests (683 backend tests in total). Checked in the browser against a copy of the database: on day 3 of 6, Saturday's leg top-up was gone, and the travel kit guided page loaded.

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

There is no active roadmap. Pick the next piece of work from the Ideas board or from the open threads in `docs/roadmap.md`, and record it under "Recently Completed" above when it ships.

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
- docs-backed planning visibility: `docs/roadmap.md` (open threads), `docs/current-state.md` (shipped log), `docs/sprints/` (archive), and `backend/app/services/planning_status.py`

## Working Assumption

Unless the athlete decides otherwise, new work should:

1. keep logic deterministic and inspectable
2. prefer structured templates over vague free-form modeling
3. keep plan changes approval-based
