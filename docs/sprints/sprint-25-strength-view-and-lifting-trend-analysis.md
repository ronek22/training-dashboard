# Sprint 25: Strength View And Lifting Trend Analysis

## Status

Current status:

- planned
- follows completed Sprint 24 strength workout enrichment via manual Fitbod import

Starting point:

- the app can now import Fitbod CSV exports and reconstruct logical strength workout sessions
- linked `WeightTraining` activities can show exercise-level detail, set breakdowns, reps, and total volume inside activity review
- strength detail is now materially richer, but it remains trapped inside single-activity review
- there is no dedicated strength analytics surface comparable to the existing cross-activity visibility for endurance work

Dependency note:

- Sprint 24 established the data foundation needed for strength-specific analysis
- the next step should convert that stored exercise-level history into athlete-facing insights instead of only richer one-off detail pages
- the first strength analytics view should stay deterministic and interpretable rather than trying to jump straight to advanced coaching models

## Objective

Introduce a dedicated strength view that turns Fitbod-enriched `WeightTraining` history into usable workout analysis, progression reads, and trend visibility.

This sprint should move the app from:

- `strength workouts are enriched one activity at a time, but there is no strength-specific analytics surface`

to:

- `the app has a dedicated strength view with session trends, exercise progression, and practical volume or frequency analysis`

## Why This Sprint

That gap matters because:

- strength is still under-served compared with run and ride review even after enrichment landed
- exercise-level history is much more valuable when the athlete can inspect trends across weeks instead of opening sessions one by one
- the imported Fitbod detail now makes it realistic to answer questions like `am I progressing`, `which lifts are moving`, and `how much upper vs lower work am I doing`
- a dedicated strength surface can become the foundation for later coaching or planning features around gym work

## User Story

As an athlete who now has Fitbod-enriched strength history in the app, I want a dedicated strength view with workout trends and lift-level analysis, so I can understand how my gym work is evolving over time instead of reviewing one workout in isolation.

## Sprint Scope

### In scope

- dedicated strength analytics view in the frontend
- backend contract(s) for strength-specific summaries and trends
- session-level and exercise-level trend aggregation from linked Fitbod-enriched activities
- deterministic views of volume, sets, reps, exercise frequency, and recent progression
- practical filtering such as time range and optional body-part or exercise focus

### Out of scope

- estimated 1RM modeling that depends on aggressive assumptions
- automatic technique scoring or rep-quality scoring
- fully normalized commercial exercise taxonomy
- advanced fatigue or recovery modeling based on muscle maps
- coaching recommendations generated directly from strength trends in the first version

## Product Outcome

After this sprint:

- the athlete can open a dedicated strength view from the app navigation
- the app can summarize recent strength sessions by volume, sets, reps, and frequency
- the athlete can inspect per-exercise trends across recent weeks or months
- the app can surface simple progression reads such as rising load, rising volume, or stable frequency for recurring lifts
- strength history becomes explorable as a body of work, not just as isolated activity details

## Proposed Feature Slice

### 1. Strength overview dashboard

Recommended first support:

- dedicated `Strength` view or dashboard section
- recent-period summary cards for sessions, total volume, total sets, and total reps
- weekly trend strips for session count and total volume
- breakdowns for most-used exercises or highest-volume exercises
- optional split read such as upper-body, lower-body, push, pull, or core if deterministic heuristics are acceptable

Recommended direction:

- prioritize high-signal summaries that stay legible with messy real-world exercise naming
- keep the first dashboard useful even when some workouts are only partially enriched

### 2. Exercise progression analysis

Recommended first support:

- exercise selector or ranked list of recurring lifts
- recent-session trend for a chosen exercise
- progression metrics such as top load, total reps, total sets, and total volume over time
- clear handling of repeated variants and ambiguous naming without pretending the data is cleaner than it is

Recommended direction:

- start from literal exercise names as stored from Fitbod
- add optional light normalization only where it is deterministic and visibly beneficial
- make progression reads descriptive before making them prescriptive

### 3. Strength session history review

Recommended first support:

- paginated or grouped strength session timeline
- quick session cards showing workout title, date, total volume, sets, reps, and major exercises
- direct navigation from strength analytics into the existing activity detail view

Recommended direction:

- treat the strength view as an index and analysis layer on top of the detailed activity review already shipped in Sprint 24

## Backend Deliverables

### 1. Strength analytics contract

Likely targets:

- `backend/app/services/activities.py`
- new strength analytics service or repository layer
- `backend/app/repositories/activity_details.py`

Deliver:

- endpoint or service methods for strength overview summaries across a selectable time window
- grouped weekly aggregates for sessions, volume, sets, and reps
- per-exercise aggregate reads for recurring lifts
- deterministic filtering so only linked and enriched `WeightTraining` activities contribute to the analysis

### 2. Exercise trend shaping

Likely targets:

- new strength analytics service

Deliver:

- recent-history trend series for named exercises
- per-exercise summaries such as appearance count, last performed date, cumulative volume, and recent best load
- safe handling for sparse or partial workouts

### 3. Coverage

Deliver:

- smoke coverage for overview aggregation across multiple linked Fitbod-enriched sessions
- at least one case where weekly volume and session counts are computed correctly
- at least one case where recurring exercise history is grouped into a trend payload
- at least one case where unlinked or non-enriched strength activities are excluded from strength analytics

## Frontend Deliverables

### 1. Dedicated strength view

Likely targets:

- new `frontend/src/views/Strength.vue`
- `frontend/src/router.js`
- navigation updates for the new view

Deliver:

- dedicated strength page entry in the app
- summary cards and trend visuals for recent strength workload
- ranked exercise lists or focus cards
- links back into activity detail for drill-down

### 2. Trend and filtering UI

Deliver:

- time-range controls such as `4 weeks`, `8 weeks`, or `12 weeks`
- exercise selection or focus filter
- empty states for athletes with imported strength activities but limited enrichment
- strength-specific loading states that do not look like endurance charts bolted onto gym data

## Data And Analysis Notes

Recommended first metrics:

- session count
- total volume in kilograms
- total sets
- total reps
- top load per exercise
- rolling weekly volume
- rolling weekly session frequency

Recommended first grouping rules:

- count only `WeightTraining` activities with linked Fitbod enrichment
- aggregate per exercise using the stored Fitbod exercise names exactly as imported
- optionally add a lightweight derived grouping layer for `push`, `pull`, `legs`, and `core` when the heuristic is explicit and reversible

Recommended first UX rule:

- if the data is uncertain, explain the heuristic briefly instead of presenting the result as ground truth

## Definition Of Done

Sprint 25 should be considered complete when:

- the app has a dedicated strength analytics view
- the view shows meaningful recent strength summaries using linked Fitbod-enriched data
- recurring exercises can be inspected through basic trend analysis
- the athlete can move from strength analytics into existing activity detail drill-down
- smoke coverage exists for overview aggregation and exercise trend shaping
