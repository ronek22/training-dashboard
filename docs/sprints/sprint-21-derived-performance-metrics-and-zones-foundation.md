# Sprint 21: Derived Performance Metrics And Zones Foundation

## Status

Current status:

- planned
- follows Sprint 20 natural-language goal capture and structured drafts

Starting point:

- the app already stores activities, basic metrics, and some stream-derived summaries
- richer goals now exist, but performance-oriented goals still rely on shallow progress signals
- zone-based and benchmark-oriented goals need better derived data foundations

Dependency note:

- before benchmark-specific planning becomes stronger, the app needs reusable derived reads such as best efforts and zone-aware totals
- zones and thresholds should be explicit user-controlled inputs before the app leans on them heavily

## Objective

Build the first reusable derived performance reads and explicit zone/threshold settings needed for stronger benchmark and process-goal evaluation.

This sprint should move the app from:

- `the app knows raw activity data, but many performance and zone-dependent goals still lean on coarse summaries`

to:

- `the app has reusable derived performance reads and explicit zone definitions that later goal logic can trust`

## Why This Sprint

That gap matters because:

- event and benchmark goals need first-class performance signals
- zone-based process goals are weak if thresholds or zones are implicit
- later coaching work should depend on stable derived metrics, not ad hoc calculations spread across features

## User Story

As an athlete tracking benchmark or zone-based goals, I want the app to compute compact reusable performance reads and use explicit zone settings, so goal progress and coaching can rely on trustworthy derived signals.

## Sprint Scope

### In scope

- compact best-effort or best-recent derived reads
- explicit user-defined zones or threshold anchors
- conservative integration of those reads into goal evaluation surfaces

### Out of scope

- automatic threshold detection
- deep physiological modeling
- broad sports-science engine work

## Product Outcome

After this sprint:

- the app can expose compact derived reads like best recent benchmark efforts
- users can persist zones or threshold anchors the goal engine can trust
- benchmark and zone-dependent goals have a better data foundation for later progression

## Proposed Feature Slice

### 1. Derived reads

Recommended first derived signals:

- best recent run benchmarks such as 5k or 10k when inferable
- best recent 10-minute power when data exists
- longest recent steady zone-2 block where stream summaries allow it

Recommended direction:

- keep the reads compact and additive
- expose them as reusable backend summaries rather than only embedding them inside one screen

### 2. Zones and thresholds

Recommended first settings:

- running threshold pace anchor
- cycling threshold power anchor
- simple zone-setting payloads stored in settings

Recommended direction:

- manual-first is acceptable
- goal and coaching logic should know whether a zone-dependent signal is trustworthy or unavailable

## Backend Deliverables

### 1. Derived performance summaries

Likely targets:

- `backend/app/services/activities.py`
- `backend/app/services/metrics.py`
- `backend/app/services/goals.py`

Deliver:

- compact best-effort summary reads
- reusable contracts for benchmark-oriented goal logic

### 2. Zone and threshold persistence

Likely targets:

- `backend/app/services/settings.py`
- `backend/app/models/settings.py`
- `backend/app/repositories/settings.py`

Deliver:

- persisted zone or threshold settings
- normalized read contracts that expose whether the data is set and usable

### 3. Coverage

Deliver:

- smoke assertions for derived benchmark reads
- at least one case where missing threshold settings keep a zone-dependent read explicitly unavailable instead of guessed

## Frontend Deliverables

### 1. Goal and settings visibility

Likely targets:

- `frontend/src/views/Goals.vue`
- `frontend/src/views/Dashboard.vue`

Deliver:

- lightweight zone/threshold editing
- clearer benchmark or zone-foundation visibility where richer goals depend on it

## Definition Of Done

Sprint 21 should be considered complete when:

- the app exposes compact derived performance summaries for later goal logic
- explicit zone or threshold settings can be stored and read back
- zone-dependent behavior does not guess when settings are missing
- smoke coverage includes both available and unavailable derived-signal cases
