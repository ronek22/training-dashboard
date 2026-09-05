# Sprint 35: Weekly Retrospectives And Data-Quality Inbox

## Status

Current status:

- partially implemented: Sunday review and retained review history (2026-09-05)
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

## Implemented: Automatic AI Sunday Review (2026-09-05)

The dashboard displays an AI-generated review with three short sections: what
improved, what did not go to plan, and one proposed change for next week. There
is no athlete input form. Reviews are immutable and retained by week in SQLite.

The local planning helper runs the review worker independently of browser visits.
It becomes due Sunday at 23:59 Europe/Warsaw (DST-aware). On startup or after sleep,
it catches up the most recently due week. It checks saved state before invoking AI,
retries failures after 15 minutes, and does not overwrite generated reviews.
The app backend and local AI helper must be running; this does not wake a sleeping Mac.

AI receives the exact week's activities, plans, feedback, coach notes, and four
weeks of comparison data and prior reviews. It assesses the preceding week's
suggestion using observed evidence, acknowledging uncertainty rather than claiming
causation. Suggested changes do not automatically modify plans. The dashboard
refreshes reviews while open and retains prior assessments in its history.

API: `GET /reviews/weekly`, `GET /reviews/weekly/context?week_start=YYYY-MM-DD`,
and `PUT /reviews/weekly` for validated AI output. Sunday timing is enforced on
writes. The additive migration distinguishes legacy manual rows from AI reviews.
Legacy manual rows are not presented as AI-generated content.

Validation covers scheduling before/after the Sunday boundary, DST and UTC,
restart deduplication, generation, invalid output, retry backoff, database
persistence, immutable history, prior-suggestion linkage, and context date bounds.

The data-quality inbox, block retrospectives, and MCP packaging remain pending.
