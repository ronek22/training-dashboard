# Sprint 24: Strength Workout Enrichment Via Manual Fitbod Import

## Status

Current status:

- planned
- follows planned Sprint 23 activity detail view and on-demand Strava caching

Starting point:

- the app already imports lightweight activity summaries from Strava
- `WeightTraining` activities can be stored, reviewed, and linked to planned strength sessions
- Strava public API does not expose the richer Fitbod-style strength payload visible in the Strava mobile app
- the athlete can manually export workout data from Fitbod on iOS
- the observed Fitbod export is a CSV where each row represents an exercise entry or performed set-like record, not a whole workout
- the same export can include non-strength rows such as `Cycling` and likely other Strava-synced endurance activities that should be ignored by the strength enrichment flow

Dependency note:

- the app should not block on Strava or Fitbod offering a public structured strength API
- a manual enrichment pipeline is the pragmatic next step because it can attach richer strength detail to already imported Strava activities
- the feature needs conservative matching and explicit user confirmation because imported Fitbod workouts and imported Strava activities are separate data sources

## Objective

Introduce a manual Fitbod import and enrichment workflow so imported Strava strength activities can be linked to richer exercise-level strength detail after the fact.

This sprint should move the app from:

- `strength activities exist, but the app only knows summary-level Strava rows`

to:

- `the app can ingest Fitbod export data, match it to existing strength activities, and surface richer exercise, set, rep, and volume detail in activity review`

The first implementation should assume:

- rows sharing the same workout timestamp belong to one logical Fitbod workout session
- repeated exercise names inside that timestamp group represent multiple performed sets for the same exercise
- strength enrichment should filter out obvious non-strength modalities before workout-session reconstruction

## Why This Sprint

That gap matters because:

- strength sessions are currently second-class compared with run and ride review
- the athlete already has richer workout structure in Fitbod, but that detail dies when only Strava summary rows are imported
- planned strength templates become more useful when completed activities can show what was actually performed
- a manual monthly or weekly import is acceptable if it gives the app durable richer strength history

## User Story

As an athlete who tracks strength sessions in Fitbod and syncs them to Strava, I want to import exported Fitbod CSV data and link reconstructed strength workouts to already imported Strava strength activities, so my strength review in the app includes exercises, sets, reps, and volume instead of only generic summary rows.

## Sprint Scope

### In scope

- manual Fitbod CSV export ingestion
- storage for imported strength workout detail
- deterministic grouping of row-level CSV records into logical workout sessions
- filtering of non-strength activity rows before strength-session creation
- conservative linking between reconstructed Fitbod workout sessions and existing Strava `WeightTraining` activities
- athlete-facing enriched strength detail in the activity review surface
- import review states for matched, unmatched, and ambiguous sessions

### Out of scope

- automatic Fitbod sync
- reverse-syncing enriched data back to Strava
- automatic OCR or screenshot parsing
- advanced exercise analytics such as progression scoring, estimated 1RM modeling, or fatigue modeling
- full exercise library normalization across all naming variants in the first sprint

## Product Outcome

After this sprint:

- the athlete can import Fitbod export data into the app manually
- the app can reconstruct logical Fitbod workout sessions from row-level CSV exports
- the app can ignore non-strength rows that do not belong in weight-training enrichment
- the app can match or help link reconstructed Fitbod workout sessions to existing Strava strength activities
- matched strength activities can show richer detail such as exercise list, sets, reps, and volume
- the import process is explicit and auditable instead of silently guessing

## Proposed Feature Slice

### 1. Manual Fitbod CSV import pipeline

Recommended first support:

- upload a Fitbod CSV export into the app
- parse the first supported CSV format conservatively
- preserve raw imported rows exactly as exported
- group rows into logical workout sessions using shared workout timestamp and deterministic grouping rules
- filter out non-strength rows such as `Cycling` before session creation
- persist both raw rows and normalized workout-session summaries
- surface an import batch summary showing successful parses, ignored non-strength rows, reconstructed sessions, and rejects

Recommended direction:

- keep the first supported CSV format narrow and explicit
- preserve raw import payloads for debugging or future parser upgrades
- treat parsing and grouping as deterministic and versioned where possible
- make ignored-row reasons visible so the athlete can understand why endurance rows were skipped

### 2. Strength activity matching and enrichment

Recommended first support:

- suggest links between reconstructed Fitbod workout sessions and Strava `WeightTraining` activities using date, start time, title similarity, and duration proximity
- require user confirmation when the match is ambiguous
- allow manual linking from an unmatched reconstructed session to an existing activity
- once linked, enrich the activity detail contract with exercise-level strength data

Recommended direction:

- prefer false negatives over bad automatic matches
- store linkage provenance such as `matched_automatically`, `matched_manually`, or `parser_confidence`
- make re-import idempotent where possible

### 3. Strength detail review surface

Recommended first support:

- enriched strength summary block showing total volume, sets, reps, elapsed time, and calories when available
- exercise list with exercise name, set count, rep count, and optional load summary
- optional per-exercise set breakdown when enough row detail is available
- optional compact muscle-group read when the export contains enough structured signal

Recommended direction:

- integrate this into the existing activity detail view rather than inventing a separate strength page first
- gracefully degrade when some workouts only include partial export detail

## Backend Deliverables

### 1. Import storage and parsing

Likely targets:

- `backend/app/db.py`
- new repository/service files for Fitbod imports
- `backend/app/services/activities.py`

Deliver:

- tables for import batches, imported Fitbod rows, reconstructed Fitbod workout sessions, imported exercises or set rows, and workout-to-activity links
- parser support for the first accepted Fitbod CSV export format
- deterministic grouping logic that converts row-level CSV entries into workout sessions
- normalized stored shape for session-level, exercise-level, and set-level detail

### 2. Matching and enrichment contract

Likely targets:

- `backend/app/services/activities.py`
- new Fitbod import or matching service

Deliver:

- match suggestion logic using conservative heuristics
- explicit endpoints or service methods for confirming or overriding a match
- activity detail payload support for enriched strength details when linked
- explicit separation between ignored non-strength rows and importable strength-session rows

### 3. Coverage

Deliver:

- smoke assertions for importing at least one Fitbod CSV file with mixed modality rows
- at least one case where `Cycling` rows are ignored during strength import
- at least one case where several rows sharing one timestamp reconstruct into a single Fitbod workout session
- at least one case where a reconstructed Fitbod workout session links to an existing `WeightTraining` activity
- at least one case where ambiguity keeps the import unmatched until manually resolved
- at least one case where linked strength detail appears in the activity detail contract

## Frontend Deliverables

### 1. Import workflow

Likely targets:

- new import UI or settings/import surface
- `frontend/src/views/Activities.vue`
- `frontend/src/views/ActivityDetail.vue`

Deliver:

- manual Fitbod import entry point
- import result summary with matched sessions, unmatched sessions, ignored non-strength rows, and failed rows
- manual linking UI for unresolved reconstructed strength workouts

### 2. Enriched strength activity detail

Likely targets:

- `frontend/src/views/ActivityDetail.vue`

Deliver:

- strength summary cards for volume, sets, reps, elapsed time, and calories when available
- exercise list rendering for linked Fitbod workouts
- optional set table beneath each exercise when enough row detail is available
- clear fallback state when a strength activity is not yet enriched

## Data And Matching Notes

Observed CSV columns in the first export sample:

- `Date`
- `Exercise`
- `Reps`
- `Weight(kg)`
- `Duration(s)`
- `Distance(m)`
- `Incline`
- `Resistance`
- `isWarmup`
- `Note`
- `multiplier`

Recommended first reconstruction rules:

- treat rows with the same `Date` timestamp as one logical Fitbod workout session
- within a session, group repeated `Exercise` names into one exercise summary with multiple performed sets or entries
- derive session totals such as set count, rep count, and volume from the grouped rows
- preserve `isWarmup` so warmup sets can remain distinct from work sets later
- keep duration, distance, incline, resistance, note, and multiplier fields available even if the first UI uses only a subset

Recommended first filtering rules:

- ignore rows whose `Exercise` clearly maps to endurance modalities such as `Cycling`
- do not create a strength session from a timestamp group if all rows in that group are filtered non-strength entries
- record why a row or timestamp group was ignored so imports remain auditable

Recommended first matching signals:

- activity date
- approximate start timestamp
- elapsed or moving duration proximity
- workout title similarity when a useful label can be derived from grouped exercises
- existing planned-session template linkage when relevant

Recommended storage notes:

- preserve raw imported CSV rows per batch
- store reconstructed workout sessions separately from raw rows
- store parser version
- store grouping version
- store match confidence and manual override flags
- keep import batches repeat-safe so the same CSV does not duplicate reconstructed sessions silently

## Risks

Key risks:

- Fitbod export format may change or vary across versions
- the same export may mix true strength data with Strava-imported endurance activity rows
- rows may not always share a perfectly unique timestamp for one logical workout
- timestamps may not align cleanly with Strava-imported activities
- exercise naming may be inconsistent across exports
- incorrect auto-linking would silently corrupt the training history if matching is too aggressive

Risk response:

- parser and grouping rules should be narrow and explicit in first release
- non-strength filtering should be conservative and auditable
- ambiguous matches should require confirmation
- all links should be reversible

## Definition Of Done

Sprint 24 should be considered complete when:

- the app can ingest at least one supported Fitbod CSV export format manually
- row-level CSV data can be reconstructed into logical strength workout sessions
- non-strength rows such as `Cycling` are ignored and reported clearly
- reconstructed Fitbod workout sessions can be matched or manually linked to existing `WeightTraining` activities
- linked activities surface richer strength detail in the activity detail view
- unmatched or ambiguous imports are visible and resolvable by the athlete
- smoke coverage includes filtering, reconstruction, match, unmatched handling, and enriched activity detail behavior
