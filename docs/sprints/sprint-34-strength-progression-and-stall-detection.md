# Sprint 34: Strength Progression And Stall Detection

## Status

Current status:

- proposed
- follows proposed Sprint 33 closed-loop weekly adaptation

Starting point:

- the app already supports manual Fitbod import, durable activity linkage, enriched strength detail, recurring lift analysis, simple PR reads, and strength context in MCP
- template rotation state exists, but the product still offers limited guidance about whether a lift or program is progressing, stalling, or should repeat before advancing
- strength work is visible, yet progression decisions still require substantial manual interpretation

Dependency note:

- Sprint 24 through Sprint 26 created the strength enrichment, analytics, and MCP foundation
- Sprint 18 created the template rotation and continuity logic
- the next step should use that foundation to add deterministic progression guidance before broader automation grows

## Objective

Add deterministic strength progression and stall-detection reads so the app can explain how key lifts are moving and what the next sensible action is.

This sprint should move the app from:

- `strength history is visible, but progression interpretation is still shallow`

to:

- `the app can summarize lift progression state and suggest whether to advance, repeat, or ease off`

## Why This Sprint

That gap matters because:

- hybrid athletes need strength progression clarity without leaving the app or manually studying raw history
- recurring lifts and template rotation already create the context needed for practical progression guidance
- the product should treat gym work as a true training system, not only a historical import
- closed-loop weekly adaptation becomes more credible when it understands whether strength work is progressing or stalling

## User Story

As an athlete following recurring strength sessions, I want the app to show whether important lifts are progressing, stalling, or under-dosed and what I should likely do next, so my gym work has the same planning clarity as endurance training.

## Sprint Scope

### In scope

- progression state for recurring lifts and template-backed sessions
- stall-detection and under-exposure signals
- next-action guidance such as `advance`, `repeat`, `hold`, or `deload` where the evidence is clear
- Strength view and MCP visibility for the new progression reads

### Out of scope

- advanced exercise normalization beyond current deterministic heuristics
- estimated 1RM-heavy modeling as the primary logic
- automatic load writes back into templates or Fitbod
- bodybuilding-specific hypertrophy scoring systems

## Product Outcome

After this sprint:

- important lifts can show clearer progression state
- the Strength view can highlight stalled, advancing, or under-exposed patterns
- coaching and MCP can discuss strength work with more practical specificity
- the strength side of the app becomes more action-oriented rather than purely descriptive

## Proposed Feature Slice

### 1. Progression state modeling

Recommended first support:

- track recent best load, rep quality proxy, exposure frequency, and time since last meaningful improvement
- define compact states such as `advancing`, `holding`, `stalled`, `under_exposed`, or `insufficient_data`
- expose why a state was chosen

Recommended direction:

- use conservative exercise grouping and simple progression evidence
- avoid pretending to detect nuanced physiology from sparse lifting logs

### 2. Next-action guidance

Recommended first support:

- suggest actions like `advance next session`, `repeat current load`, `maintain while hybrid load is high`, or `deload / reduce expectation`
- connect guidance back to template rotation when a template-backed sequence exists

Recommended direction:

- keep the first action space small and inspectable
- prefer clear practical choices over elaborate strength theory

### 3. Surface integration

Recommended first support:

- progression summary in `Strength`
- lift-level detail for selected exercises
- MCP exposure of progression and stall state for chat-based analysis

Recommended direction:

- UI should highlight only the most actionable lifts first
- do not drown the screen in labels for every accessory exercise

## Backend Deliverables

### 1. Strength progression engine

Likely targets:

- `backend/app/services/strength.py`
- `backend/app/services/activities.py`

Deliver:

- progression state and next-action fields for recurring lifts
- template-aware continuity hooks where useful
- explicit insufficient-data handling

### 2. Shared contract shaping

Likely targets:

- `backend/app/services/strength.py`
- `backend/app/services/mcp.py`

Deliver:

- frontend- and MCP-friendly progression payloads
- compact summaries for stalled, advancing, and under-exposed lifts

### 3. Coverage

Deliver:

- at least one lift showing advancing behavior
- at least one lift showing stall or hold behavior
- at least one under-exposed or insufficient-data case

## Frontend Deliverables

### 1. Strength progression UI

Likely targets:

- `frontend/src/views/Strength.vue`

Deliver:

- compact progression overview for key lifts
- selected-lift progression state and next-action visibility
- calm empty and limitation states

## UX Notes

Recommended first rules:

- prioritize major recurring lifts before accessories
- show trend plus action, not trend alone
- make `not enough exposure` distinct from `stalled`
- keep language practical rather than coachy

Recommended first copy direction:

- `Advancing`
- `Holding steady`
- `Stalled recently`
- `Needs more repeated exposure`
- `Repeat current prescription`

## Definition Of Done

Sprint 34 should be considered complete when:

- the app exposes deterministic progression state for at least a useful subset of recurring lifts
- Strength and MCP surfaces can show progression and next-action guidance
- stall, hold, and weak-evidence cases are all represented explicitly
