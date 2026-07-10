# Sprint 30: Readiness And Fatigue Foundation

## Status

Current status:

- complete
- follows completed Sprint 29 LLM workout analysis via MCP for activity detail

Starting point:

- the app can already summarize training history, goal pressure, feedback, restrictions, heart-rate zones, benchmarks, and single-workout analysis
- dashboard and coaching can explain what happened recently, but they still do not expose one shared readiness layer
- users can inspect several signals manually, yet the app cannot answer `am I ready to push, maintain, or back off?` in a compact deterministic way
- later adaptation and goal-readiness work would currently need to reconstruct readiness logic from scattered data

Implemented outcome:

- dashboard now surfaces a compact readiness read directly alongside daily guidance instead of leaving the user to infer short-horizon strain manually
- coaching now consumes one shared readiness summary with explicit state, evidence, and limitations instead of rebuilding ad hoc recovery reads
- MCP and recent-context payloads now expose the same deterministic readiness object for external consumers
- readiness now distinguishes `ready`, `watch`, `strained`, and `insufficient_data` without collapsing everything into one opaque score

Dependency note:

- Sprint 3 established subjective feedback and lightweight recovery-aware signals
- Sprint 21 and Sprint 28 added performance anchors, benchmarks, and heart-rate-zone context
- Sprint 29 improved workout interpretation, but still at the single-session level
- the next step should create one reusable readiness contract before more planning logic depends on it

## Objective

Add a conservative readiness and fatigue layer that combines recent training density, recovery signals, and data-quality limits into one compact summary for dashboard, coaching, and MCP consumers.

This sprint should move the app from:

- `the app has useful review signals, but readiness must still be inferred manually`

to:

- `the app can expose a compact deterministic readiness read with clear supporting factors and limitations`

## Why This Sprint

That gap matters because:

- planning quality improves when the app can distinguish productive load from accumulating strain
- users need a practical answer to `how hard should the next 48 hours be?`
- later goal-readiness and adaptation work should reuse one inspectable readiness source instead of inventing new heuristics in each surface
- explicit unavailable states are better than vague wellness language or false precision

## User Story

As an athlete deciding how hard to train next, I want the app to summarize whether recent load and recovery signals suggest readiness or strain, so I can understand the current training state without manually combining several charts and notes.

## Sprint Scope

### In scope

- deterministic readiness state derived from recent workload, session density, and feedback context
- compact supporting factors such as recent hard-session count, subjective recovery burden, and missing-data limits
- dashboard, coaching, and MCP visibility for the new readiness read
- explicit unavailable or weak-confidence states when evidence is missing

### Out of scope

- medical guidance or injury diagnosis
- HRV, sleep, or wearable-native recovery integration
- automated plan rewrites based on readiness
- modality-specific physiology models that imply more precision than the data supports

## Product Outcome

After this sprint:

- dashboard can show a compact readiness card or summary
- coaching can reference readiness as a structured input instead of broad prose
- MCP consumers can read the same deterministic readiness context
- the app becomes more capable of answering short-horizon training questions without over-claiming certainty

## Proposed Feature Slice

### 1. Shared readiness contract

Recommended first support:

- define a small readiness state set such as `ready`, `watch`, `strained`, and `insufficient_data`
- compute the state from a conservative combination of recent load, hard-session density, and subjective feedback burden
- attach explicit reasons so the state is inspectable rather than opaque

Recommended direction:

- keep the first model compact and explainable
- prefer a few robust signals over a large pseudo-scientific readiness score

### 2. Dashboard and coaching visibility

Recommended first support:

- show readiness as a compact dashboard summary near daily guidance or weekly coaching
- let coaching reference readiness in the structured rationale and next-48-hour guidance
- keep the first read calm and practical rather than alarmist

Recommended direction:

- readiness should inform decisions, not dominate the entire product
- copy should stay grounded in observable recent training behavior

### 3. MCP exposure and trust states

Recommended first support:

- expose readiness through a deterministic MCP read or in existing compact context payloads
- include explicit supporting factors and limitations
- mark when missing feedback, weak activity detail, or mixed modality evidence lowers confidence

Recommended direction:

- make the first payload boring and stable
- if readiness is weakly supported, say so directly

## Backend Deliverables

### 1. Readiness service

Likely targets:

- `backend/app/services/dashboard.py`
- `backend/app/services/coaching.py`
- optional readiness-specific service module if useful

Deliver:

- reusable readiness summary builder
- explicit state, supporting factors, and limitations fields
- conservative logic for missing-data handling

### 2. Dashboard and MCP shaping

Likely targets:

- `backend/app/services/dashboard.py`
- `backend/app/services/mcp.py`

Deliver:

- readiness payload in dashboard reads
- compact readiness inclusion in MCP-facing context where appropriate
- structured fields suitable for frontend display and prompt grounding

### 3. Coverage

Deliver:

- at least one case where a balanced week returns `ready`
- at least one case where dense recent load or poor feedback returns `watch` or `strained`
- at least one case where missing evidence produces an explicit weak or unavailable state

## Frontend Deliverables

### 1. Dashboard readiness surface

Likely targets:

- `frontend/src/views/Dashboard.vue`

Deliver:

- compact readiness card or summary section
- supporting reasons and calm limitation copy
- visual treatment that distinguishes usable and unavailable states cleanly

### 2. Coaching visibility

Likely targets:

- dashboard coaching components or related shared UI

Deliver:

- readiness-aware coaching rationale display
- no requirement for a large new workflow

## UX Notes

Recommended first rules:

- avoid one giant readiness number
- show a state plus 2-3 evidence points
- distinguish `not enough evidence` from `strained`
- keep the read useful in under 10 seconds

Recommended first copy direction:

- `Readiness`
- `Recent load looks manageable`
- `Watch short-term strain`
- `Limited by missing recovery or activity detail`

## Definition Of Done

Sprint 30 should be considered complete when:

- the app exposes one deterministic readiness summary with supporting factors
- dashboard and coaching can consume that summary
- MCP can read the same context without rebuilding it from raw data
- missing-data cases are explicit and conservative
