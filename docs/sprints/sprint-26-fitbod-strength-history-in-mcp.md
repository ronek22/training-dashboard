# Sprint 26: Fitbod-Enriched Strength History In MCP

## Status

Current status:

- planned
- follows completed Sprint 25 strength view and lifting trend analysis

Starting point:

- the app can now import Fitbod CSV exports, reconstruct workout sessions, and link them to stored `WeightTraining` activities
- linked strength activities can show enriched exercise, set, rep, and volume detail in activity review
- the dedicated `Strength` view now exposes deterministic session trends, recurring lifts, selected-lift analysis, and simple PR reads
- MCP already exposes useful endurance, planning, goal, and coaching context, but it still under-serves imported strength history

Dependency note:

- Sprint 24 created the durable Fitbod enrichment pipeline
- Sprint 25 converted that enrichment into athlete-facing app analytics
- the next step should expose the same structured strength history to MCP so chat surfaces can reason about gym work without rebuilding context from raw activity rows

## Objective

Expose Fitbod-enriched strength history and summary reads through MCP so chat-based tools can inspect recent strength sessions, recurring lifts, and simple progression context using the same deterministic data that now powers the app’s strength view.

This sprint should move the app from:

- `strength analytics are visible in the app, but MCP has no first-class access to that enriched strength history`

to:

- `MCP can return compact, deterministic strength context built from linked Fitbod-enriched workouts`

## Why This Sprint

That gap matters because:

- chat tools currently see strength work mostly as generic `WeightTraining` rows unless they are hand-walked through app-specific screens
- richer coaching or planning conversations around gym work need access to actual lifts, frequency, volume, and notable PRs
- the app already computes deterministic strength summaries, so MCP should reuse them instead of forcing prompt reconstruction or duplicate logic
- this is the cleanest bridge from app-only strength analytics into future coaching and assistant workflows

## User Story

As an athlete using MCP-connected chat tools with the training dashboard, I want those tools to access my Fitbod-enriched strength history in a structured way, so gym work can be discussed with the same fidelity as endurance and planning context.

## Sprint Scope

### In scope

- MCP read surface for linked Fitbod-enriched strength summaries
- deterministic recent-strength context built from the existing strength analytics contract
- compact exposure of recent sessions, recurring lifts, selected-lift trend detail, and important PRs
- lightweight query controls such as time window and optional exercise focus
- tests that confirm MCP excludes unmatched or non-enriched strength activity rows

### Out of scope

- write actions that edit Fitbod links or imported strength history through MCP
- estimated 1RM modeling or advanced strength-readiness coaching
- automatic exercise normalization beyond the existing deterministic heuristics
- free-form prompt-generated strength narratives as the canonical contract

## Product Outcome

After this sprint:

- MCP clients can request recent strength context directly from the dashboard backend
- chat tools can inspect deterministic summaries such as session count, workload, recurring lifts, and major PRs
- recent enriched strength sessions can be surfaced without manually browsing the app UI first
- the app has one shared strength-analysis source that serves both frontend and MCP consumers

## Proposed Feature Slice

### 1. MCP strength summary read

Recommended first support:

- one MCP read that returns recent strength overview context
- reuse the existing backend strength analytics service rather than duplicating aggregation logic
- support a small parameter set such as `weeks`, `body_part`, and optional `exercise`
- keep the result compact enough for prompt context while still preserving lift-level signal

Recommended direction:

- package deterministic reads rather than asking the model to infer meaning from raw history
- prefer one compact strength-specific MCP response over several loosely related generic reads

### 2. Recent session and lift detail in MCP

Recommended first support:

- recent matched Fitbod-enriched strength sessions
- recurring-lift ranking with frequency, volume, and recent best load
- selected-exercise trend payload with recent appearances
- important PR list for major lifts such as bench press, squat, deadlift, overhead press, row, and pull-up when present

Recommended direction:

- expose the same exact-name exercise logic currently used in the app unless a deterministic grouping improvement is explicitly introduced
- preserve enough structure that downstream chat tools can answer focused questions without large extra fetches

### 3. MCP contract hygiene

Recommended first support:

- clear indication that only linked and enriched `WeightTraining` sessions contribute
- compact heuristics note when body-part grouping is used
- stable field names suitable for both internal prompt assembly and external MCP consumers

Recommended direction:

- make the first contract boring, inspectable, and easy to test
- treat this as shared application context, not as a one-off prompt helper

## Backend Deliverables

### 1. MCP strength context route

Likely targets:

- `backend/app/services/mcp.py`
- `backend/app/adapters/mcp.py`
- `backend/app/services/strength.py`

Deliver:

- MCP read support for recent strength overview data
- deterministic query parameters with safe defaults
- response shaping that reuses the existing strength analytics contract where appropriate

### 2. Shared contract shaping

Likely targets:

- `backend/app/services/strength.py`

Deliver:

- any small contract refinements needed so frontend and MCP consumers can share the same source
- compact fields for important PRs, recurring lifts, recent sessions, and selected-exercise trend reads
- explicit filtering guarantees around matched enriched sessions only

### 3. Coverage

Deliver:

- at least one case where MCP strength context returns linked Fitbod-enriched session summaries
- at least one case where unmatched or non-enriched strength rows are excluded
- at least one case where recurring lift or PR data appears in the MCP payload

## Frontend Deliverables

Frontend impact should stay light in this sprint.

Deliver:

- no major UI required unless a lightweight MCP or debug inspection surface is useful
- optional docs or dev-facing visibility if the team wants to inspect the new MCP payload locally

## Data And Analysis Notes

Recommended first MCP fields:

- selected window
- summary totals for sessions, workload, sets, reps, and distinct exercises
- recurring lifts with recent best load
- selected-exercise trend history
- important PRs
- recent enriched sessions
- heuristics note for body-part grouping

Recommended first UX rule:

- MCP should receive compact structured strength context, not giant raw workout dumps by default

## Definition Of Done

Sprint 26 should be considered complete when:

- MCP can expose recent Fitbod-enriched strength context through a deterministic read
- the payload includes useful recent summary, lift-level, and session-level fields
- the payload excludes unmatched or non-enriched strength activity rows
- coverage exists for at least one positive and one exclusion case
