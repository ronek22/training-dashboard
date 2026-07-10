# Sprint 29: LLM Workout Analysis Via MCP For Activity Detail

## Status

Current status:

- complete
- follows completed Sprint 28 heart-rate zones in activity detail and dashboard

Starting point:

- the app already has a dedicated activity detail view with cached Strava-backed detail and strength-specific enrichment where available
- MCP already exposes structured dashboard, planning, coaching, and strength context through deterministic backend reads
- the app can compute more structured workout context than before, but activity detail still stops at charts, stats, and deterministic summaries
- there is no workflow yet that asks an LLM to analyze one workout in context and return a compact athlete-facing read

Dependency note:

- Sprint 23 established the activity detail surface and the on-demand detail cache
- Sprint 26 established that MCP can expose compact deterministic training context for LLM-facing tools
- Sprint 28 should strengthen heart-rate-zone context for endurance activities, which makes single-workout analysis more useful and better grounded
- Sprint 29 should build one narrow LLM-assisted analysis path rather than a broad free-form coaching surface

## Objective

Implement one MCP-backed workflow that lets the system analyze a single workout with an LLM using deterministic app context, then display a compact summary in activity detail.

This sprint should move the app from:

- `activity detail shows raw data and deterministic summaries, but there is no one-shot workout interpretation layer`

to:

- `activity detail can request and display a compact LLM analysis of one workout grounded in deterministic workout context`

## Why This Sprint

That gap matters because:

- athletes often want a fast answer to `what happened in this workout?` rather than reading every chart themselves
- deterministic stats alone are useful, but they do not yet produce a concise narrative about pacing, intensity, execution, or how the workout fit its intent
- LLM analysis is most useful when the context is already structured and limited, which the app now supports better than before
- the activity detail page is the safest first place for LLM interpretation because the scope is one workout, not open-ended coaching

## User Story

As an athlete reviewing one workout, I want the app to produce a compact AI-generated analysis grounded in my workout data and nearby context, so I can quickly understand what stood out without manually interpreting every chart and stat.

## Sprint Scope

### In scope

- one MCP tool or equivalent backend action for single-workout analysis
- deterministic workout-context packaging for one activity
- compact LLM-generated summary shown inside activity detail
- explicit loading, unavailable, and failure states for the analysis block
- conservative prompt and payload shaping so the analysis stays grounded

### Out of scope

- autonomous plan changes or coaching writes triggered from workout analysis
- open-ended chat UI embedded into activity detail
- bulk analysis of all activities
- free-form analysis that bypasses structured backend context
- heavy historical coaching narratives that require large prompt windows

## Product Outcome

After this sprint:

- the athlete can request one AI analysis for a specific activity from the activity detail view
- the analysis is grounded in compact deterministic workout context rather than raw unbounded payloads
- the UI can show a short summary, supporting observations, and clear limitations or confidence notes
- the first LLM-assisted review flow exists without turning the app into a broad chat-first product

## Proposed Feature Slice

### 1. Deterministic single-workout context packaging

Recommended first support:

- one backend contract that gathers the data needed to interpret a single workout
- include modality-aware fields such as distance, duration, pace or power, heart rate, elevation, workout intent, benchmark tag, subjective feedback, and plan linkage when available
- include compact recent-context hints only when they materially help interpretation, such as whether the activity fulfilled a planned session or whether it was a benchmark effort
- keep the payload small and inspectable so it is suitable for MCP and prompt assembly

Recommended direction:

- the deterministic contract should be useful even before the LLM layer is called
- treat this as structured application context, not as prompt text hidden in frontend code

### 2. MCP-backed workout-analysis action

Recommended first support:

- one MCP tool or backend action such as `analyze_activity` or `summarize_workout`
- pass only the compact deterministic workout context and a narrow analysis task
- require the model to return a stable structured shape such as headline, short summary, notable signals, and limitations
- keep the first analysis focused on interpretation, not recommendation or diagnosis

Recommended direction:

- prefer one opinionated analysis action over a generic free-form prompt tunnel
- make the first output schema boring and testable

### 3. Activity-detail analysis block

Recommended first support:

- add an AI workout analysis section to activity detail
- support explicit generation on demand instead of automatic analysis for every open
- render headline, concise narrative summary, and a small list of supporting observations
- show when analysis is unavailable because required detail is missing or the model call failed

Recommended direction:

- keep the UI visibly secondary to deterministic stats and charts
- the analysis should help interpretation, not replace raw evidence

## Backend Deliverables

### 1. Single-workout analysis context builder

Likely targets:

- `backend/app/services/activities.py`
- `backend/app/services/mcp.py`
- optional analysis-specific service module if useful

Deliver:

- compact deterministic workout-analysis context for one activity
- modality-aware shaping for endurance and enriched strength workouts
- explicit flags for missing streams, weak data, or missing plan linkage

### 2. MCP or backend analysis action

Likely targets:

- `backend/app/services/mcp.py`
- `backend/app/adapters/mcp.py`
- any existing OpenAI or LLM integration path already used by the project

Deliver:

- one callable analysis action for a single activity
- stable response schema with compact summary fields
- prompt and contract rules that keep the model grounded in provided data only

### 3. Analysis result storage or caching

Likely targets:

- `backend/app/db.py`
- `backend/app/services/activities.py`

Deliver:

- decide whether single-workout analyses should be cached or regenerated on demand
- if cached, store compact result plus source timestamp or invalidation hint
- if not cached, make the no-cache decision explicit in the contract and UX

### 4. Coverage

Deliver:

- at least one case where a workout-analysis context payload is built successfully
- at least one case where the LLM-facing action returns a stable structured result
- at least one case where missing workout detail makes the analysis unavailable rather than speculative
- at least one case where strength and endurance activities shape context differently

## Frontend Deliverables

### 1. Activity-detail AI analysis section

Likely targets:

- `frontend/src/views/ActivityDetail.vue`

Deliver:

- explicit `Analyze workout` action or equivalent trigger
- loading, success, empty, and failure states
- compact rendering for headline, short summary, and supporting bullets
- clear distinction between deterministic app data and AI-generated interpretation

### 2. UX guardrails

Deliver:

- small disclosure that the analysis is AI-generated and grounded in available workout data
- calm failure copy when analysis is unavailable
- no misleading implication that the analysis is authoritative coaching or medical advice

## MCP And Prompt Notes

Recommended first MCP fields:

- activity identity and modality
- summary stats and available streams
- planned-session linkage and intent when present
- heart-rate-zone summary when available
- strength-workout enrichment when present
- athlete feedback and benchmark metadata when present
- explicit limitations list

Recommended first output schema:

- `headline`
- `summary`
- `key_observations`
- `limitations`
- `confidence_note`

Recommended first prompt rule:

- if the structured context does not support a claim, the model should not invent it

## UX Notes

Recommended first rules:

- show the analysis below core stats, not above them
- keep the first summary short enough to scan in under 20 seconds
- use bullets for supporting observations rather than long paragraphs
- prefer on-demand generation so the athlete stays in control and backend cost stays bounded

Recommended first copy direction:

- `AI workout analysis`
- `Summarized from available workout detail and recent app context`
- `Unavailable because richer workout detail is missing`
- `This is an AI-generated interpretation, not a coaching decision`

## Definition Of Done

Sprint 29 should be considered complete when:

- one activity can be analyzed through an MCP-backed LLM workflow using deterministic workout context
- activity detail can display the returned structured analysis cleanly
- the system stays explicit when data is missing or analysis is unavailable
- the prompt and result schema are narrow, grounded, and testable
- coverage exists for at least one successful analysis and one unavailable case
