# Sprint 36: First-Party Strength Workout Tracking

## Status

- completed
- follows the retrospective Fitbod strength import and analytics foundation

## Objective

Let the athlete define reusable strength workouts, perform them set by set in TrainLog, and attach a separately recorded Apple Watch activity after HealthFit imports it.

## Delivered

- Activity Detail now resolves an explicitly linked TrainLog session before falling back to Fitbod enrichment, so completed first-party sets, repetitions, and loads appear alongside Apple Watch heart-rate and calorie data.

- reusable workout templates with ordered exercises
- per-exercise targets for sets, repetitions, weight, rest duration, and notes
- a live session runner that snapshots the template so later template edits do not rewrite history
- actual repetition and load capture per set
- rest countdowns based on durable timestamps
- manual switching between exercises and sets without discarding incomplete work
- prevention of multiple simultaneous active strength sessions
- completed and abandoned session history
- post-workout candidate matching to imported `WeightTraining` and `Workout` activities within two days
- explicit Apple Watch activity attachment and unlinking
- linked activity summaries for duration, average heart rate, maximum heart rate, and calories
- exercise autocomplete across imported Fitbod and first-party TrainLog history
- opt-in set, rep, and weight targets derived from the latest recorded work sets
- live session exercise additions with the same history search and target suggestions
- an optional two-tone audible cue when a rest countdown finishes
- a responsive Workout Studio redesign with a focused workout library, compact session log, and quieter template management actions

## Data Boundary

The first-party session owns exercise structure and performed sets. The imported Apple Watch/HealthFit activity remains the source of truth for physiological and device-recorded data. Linking connects the two records without copying heart-rate streams or creating a second activity.

## Deliberate Follow-Ups

- automatic match suggestions using start-time and duration confidence once imported activity timestamps are normalized consistently
- direct watch companion controls and mirrored rest timers
- per-set RPE, warm-up sets, supersets, and exercise substitutions
- inclusion of first-party sessions in the cross-session progression analytics currently based on Fitbod history
- richer linked heart-rate charts inside the completed session review

## Live workout design overhaul — September 2026

Implemented a focused live session layout with a compact progress header, persistent ready/recovery panel, prominent reps and load controls, and an amber Log set action above set history. The quieter exercise lineup includes per-set progress markers; phone layouts keep reps and load side by side and allow horizontal scrolling within set history. Added an explicit all-sets-recorded state and an Update set label when revisiting recorded sets. Existing workout APIs, durable rest timing, warm-up insertion, exercise addition, and Apple Watch linking are retained.

Validation: production frontend build; browser checks with isolated sample data for desktop, 390px and 320px layouts, repetition changes, set logging, recovery, exercise switching, expanded history, all-sets-recorded state, and completed review. No live workout data was changed by these checks.

## Strength activity muscle map — September 2026

Implemented an original SVG front/back body silhouette in enriched strength activity details, shared by linked TrainLog sessions and Fitbod imports. Pink marks estimated primary muscles; muted pink marks supporting muscles. Whole-workout and selected-exercise views use recorded non-warm-up sets, including bodyweight work. Selecting a muscle highlights it and opens the relevant body view. Unmapped exercises remain visible in a disclosure and do not produce highlights.

Mappings are conservative exercise-name heuristics in `frontend/src/activity-detail/muscles.mjs`, using muscle terminology and movement examples from the [NASM exercise library](https://www.nasm.org/workout-exercise-guidance) and [ACE exercise library](https://www.acefitness.org/resources/everyone/exercise-library/). They are not measurements of activation, fatigue, or recovery. A set may contribute to multiple muscle groups. Specific variants are matched before broader names; unknown and composite movements are left unmapped. The existing broad muscle-focus summary now uses the same classifier, avoiding leg curl/leg press categorization collisions.

Validation: frontend production build, four Node test cases covering mapping precedence, unknown names, warm-up/pending-set exclusions, bodyweight inclusion, and aggregation; isolated browser checks for front/back switching, muscle selection, exercise selection synchronization, unmapped state, and 390px/320px layouts. Visually inspected desktop and mobile previews.

## Workout Studio muscle explorer — September 2026

Implemented a muscle-based exercise browser in Workout Studio using the shared front/back silhouette and classifier. Athletes can click the body or use the keyboard-accessible muscle-group buttons, search matching names, and optionally include supporting-muscle matches. A starter library covers all 15 muscle groups and merges exercises from saved workout templates, retaining personal set/load/rest targets. Primary matches appear before supporting matches. Unknown movements remain available through normal template editing but are not assigned speculative muscle matches.

Adding a result creates a draft if needed, fills an empty exercise row or appends a movement, and prevents duplicate additions through the browser. Existing draft content is retained. Starter exercises use the editor's existing defaults; personal template exercises retain their targets. Saving remains an explicit editor action.

Validation: production build; seven Node tests across muscle mapping and library filtering; isolated browser checks for body/group selection, primary/supporting filtering, search and empty states, draft creation, duplicate prevention, retained personal targets, save payload, and 390px/320px layouts. Desktop and mobile previews visually inspected.

## Live draft muscle map — September 2026

Implemented a reactive muscle map inside the Workout Studio editor for both new and existing templates. The shared map has a planned-set mode, clearly labeled Draft muscle map, and updates from exercise names and set counts as rows are added, edited, or removed. It includes front/back views, primary/supporting involvement, unmapped names, and a disclosure of groups without mapped involvement. Empty names and invalid set counts are excluded. Removing or renaming the highlighted movement clears a stale muscle selection. Planned coverage does not alter completed-session aggregation or persist anything before Save workout.

Validation: production build; eight Node tests, including planned-set aggregation and invalid draft inputs; mocked browser checks for changing names/counts, adding/removing rows, stale highlight reset, unmapped state, save payload, and 390px/320px layout. Desktop preview visually inspected.

## Automatic exercise history — September 2026

Implemented automatic latest-session history beside every named exercise in the Workout Studio editor, including exercises added from the muscle browser and existing templates. Displays the last date/source and individual recorded sets, reps, and load. Use last targets explicitly applies the latest-session set count, modal reps, and median positive recorded load while retaining rest and notes. Loading, no-history, and retry states are included; renaming immediately clears stale history and late responses are ignored. Exact normalized-name matches are ranked before partial matches in the existing suggestions endpoint. Added last_sets and last_source to its response and label warm-up-only history accurately. Fixed narrow mobile target fields so all four targets remain readable.

Validation: production build; backend strength-workout tests verify both Fitbod and TrainLog history fields; isolated browser checks cover automatic lookup, recorded-set display, explicit application, retained rest, unknown names, stale responses, retry, and mobile layout. No actual workout records changed during checks.

## Edit an active workout's structure — September 2026

Implemented Add set, Remove selected set, and Remove exercise in the live runner. Added working sets inherit the last working set's planned reps/load/rest and remain pending. Warm-up addition remains available. Removing recorded sets or an entire exercise requires confirmation in the UI. Keep at least one working set per exercise and one exercise per session; the existing exercise removal/discard actions handle larger reductions. Working sets are capped at 20 per exercise.

New session-scoped POST/DELETE endpoints validate active status and membership, update ordering transactionally, preserve the current set by identity when it survives, and select a valid remaining set otherwise. Progress is recalculated from the remaining sets. Template definitions remain unchanged. Live structure changes serialize through a busy state and surface recoverable errors.

Validation: production frontend build; three backend test cases including add/remove structure, completed-set removal, ordering/selection repair, warm-up removal, limits, closed-session rejection, and template preservation. Mocked browser checks cover add/remove actions, failure recovery, confirmation cancellation/acceptance, last-item guards, and mobile layout.

## One-time workouts from recommendations — September 2026

Implemented a **Create one-time workout** action for today's planned strength session. It opens an editable Workout Studio draft. The explicit reduced lower-body prescription (two easy sets of squat/leg press, Romanian deadlift, split squat/leg curl, then calves/core) maps to matching saved Workout D movements. Matching movements retain template reps/rest; an explicit 70% load instruction scales saved loads down, rounded down to 0.5 kg. Missing movements use disclosed editable defaults. Calf/core set counts are also labeled as defaults. Alternative exercises remain editable, and the complete original prescription, duration and execution guidance travel with the session.

Unrecognized prose opens a reviewable draft, optionally copied from an exactly matching template, without guessing reductions. This is a deterministic conversion of the supported prescription, not a general natural-language workout generator. Saved workouts also expose **Use once with changes**. Starting calls a validated one-time session endpoint that snapshots exercises and notes without creating or changing reusable templates. Session notes persist through reload and completion and appear in the runner. The existing active-session guard applies.

Validation: four backend strength-workout tests pass, covering one-time creation, instruction persistence, recording/completion, unchanged library, validation and duplicate-start rejection; three draft-conversion Node tests pass; production frontend build passes. Browser-verified the live dashboard action and populated reduced Workout D draft, including two sets, template-derived reps/rest and 70% loads. No actual workout was started during browser verification.
