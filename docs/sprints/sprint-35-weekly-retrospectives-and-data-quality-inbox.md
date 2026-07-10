# Sprint 35: Weekly Retrospectives And Data-Quality Inbox

## Status

Current status:

- proposed
- follows proposed Sprint 34 strength progression and stall detection

Starting point:

- the app can already show dashboard summaries, multi-week execution analysis, heart-rate zone context, strength trends, coaching history, and single-workout AI analysis
- users can inspect many slices of the past, but the product still lacks one compact retrospective workflow for `what actually stood out this week?`
- trust also depends on cleanup visibility, yet missing feedback, weak links, stale benchmarks, and missing detail are still scattered rather than organized

Dependency note:

- Sprint 11 and Sprint 19 created stronger execution and coaching summary foundations
- Sprint 28 and Sprint 29 improved per-workout review
- Sprint 30 through Sprint 34 should create stronger readiness, goal, execution, and strength context the retrospective can reuse
- the next step should package recent learning and trust gaps into one practical weekly workflow

## Objective

Add a compact weekly and recent-block retrospective plus a focused data-quality inbox so the app can summarize what mattered recently and what should be cleaned up next.

This sprint should move the app from:

- `the app has many review surfaces, but no compact retrospective and cleanup workflow`

to:

- `the app can summarize the recent training block and explicitly surface the highest-value missing-data or review tasks`

## Why This Sprint

That gap matters because:

- users need one practical answer to `what stood out this week?`
- recent patterns are more useful when they are summarized across readiness, goal support, workout quality, and strength continuity
- data hygiene directly affects trust in coaching and analysis
- a focused inbox is more useful than silent partial coverage

## User Story

As an athlete closing out the week, I want the app to summarize what went well, what drifted, and what data or review tasks still need attention, so I can both learn from the week and keep the product trustworthy.

## Sprint Scope

### In scope

- weekly retrospective summary
- recent-block retrospective such as last 4 weeks
- compact data-quality or review inbox
- dashboard and MCP exposure of the new retrospective context

### Out of scope

- broad notifications system
- chat-first retrospective as the canonical source of truth
- endless historical reporting
- automatic cleanup actions that silently rewrite data

## Product Outcome

After this sprint:

- dashboard can show one compact retrospective of the recent week or block
- the app can highlight notable wins, misses, readiness patterns, and progression signals
- a small inbox can surface the most important missing or stale inputs
- trust improves because the app is more explicit about what still needs attention

## Proposed Feature Slice

### 1. Weekly and block retrospective

Recommended first support:

- summarize the last week and optionally the recent 4-week block
- include compact themes such as:
  - readiness pattern
  - goal support and missed requirements
  - execution-quality highlights
  - zone-distribution or benchmark context where relevant
  - strength continuity and progression notes

Recommended direction:

- keep the summary evidence-based and scan-friendly
- prefer a few strong takeaways over an exhaustive report

### 2. Data-quality inbox

Recommended first support:

- surface high-value cleanup items such as:
  - missing subjective feedback
  - unmatched planned sessions
  - activities missing richer detail or cached streams
  - stale benchmark evidence for active goals
  - unmatched or incomplete strength enrichment
- rank items by impact on product trust or coaching usefulness

Recommended direction:

- the inbox should feel like practical maintenance, not generic nagging
- keep actions lightweight where possible

### 3. MCP and dashboard packaging

Recommended first support:

- expose the retrospective and inbox through dashboard reads and MCP context
- make it easy for chat surfaces to reference the same recent-week summary
- keep the payload compact enough for reuse

Recommended direction:

- package one deterministic retrospective context instead of many loosely related fragments

## Backend Deliverables

### 1. Retrospective summary builder

Likely targets:

- `backend/app/services/dashboard.py`
- `backend/app/services/activities.py`
- `backend/app/services/strength.py`

Deliver:

- weekly and block retrospective payload
- compact notable-signals fields with explicit evidence backing
- integration with readiness, goal-readiness, and workout-quality context where available

### 2. Inbox builder

Likely targets:

- `backend/app/services/dashboard.py`
- `backend/app/services/mcp.py`

Deliver:

- prioritized data-quality or review items
- impact labels and compact suggested actions
- conservative logic that avoids noisy low-value alerts

### 3. Coverage

Deliver:

- at least one case where the retrospective highlights a positive pattern
- at least one case where it surfaces an important miss or drift
- at least one case where the inbox returns meaningful cleanup items

## Frontend Deliverables

### 1. Dashboard retrospective and inbox

Likely targets:

- `frontend/src/views/Dashboard.vue`

Deliver:

- compact retrospective card or section
- focused inbox presentation for top cleanup items
- clear empty states when no high-priority cleanup is needed

## UX Notes

Recommended first rules:

- retrospective should read like a practical weekly review, not a wall of analysis
- inbox should prioritize only a handful of items
- explain why each cleanup item matters
- make positive patterns visible, not only issues

Recommended first copy direction:

- `Weekly retrospective`
- `What stood out`
- `Needs review`
- `Missing workout feedback is limiting readiness confidence`
- `Benchmark evidence is stale for this goal`

## Definition Of Done

Sprint 35 should be considered complete when:

- the app can show a compact weekly or recent-block retrospective
- the app can surface a focused data-quality inbox
- dashboard and MCP can read the same context
- the retrospective stays evidence-based and the inbox stays high-signal
