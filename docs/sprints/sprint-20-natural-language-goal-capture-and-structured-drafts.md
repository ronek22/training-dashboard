# Sprint 20: Natural-Language Goal Capture And Structured Drafts

## Status

Current status:

- complete
- follows Sprint 19 deterministic athlete brief and goal-aware coaching explanations

Starting point:

- the app now supports richer goal families and structured goal creation in the UI
- goal creation is more capable than before, but it still assumes the user thinks in schema fields first
- MCP and chat surfaces could help capture goals, but there is no normalized draft pipeline yet

Dependency note:

- natural-language goal capture should only happen after the richer goal schema is stable
- draft generation should map into the same canonical structured goal model rather than invent a second goal path

## Objective

Allow natural-language goal ideas to become structured draft goals that users can explicitly review before saving.

This sprint should move the app from:

- `advanced goals are supported, but the user still has to speak the schema directly`

to:

- `the user can describe a goal naturally and the app can convert it into a structured draft for review`

## Why This Sprint

That gap matters because:

- users often think in plain language before they think in goal-family fields
- richer goals become less useful if creation friction is too high
- MCP and chat integration are better when they can hand back structured drafts instead of prose-only suggestions

## User Story

As an athlete thinking in plain language, I want to describe a goal naturally and get a structured draft back, so I can save richer goals without manually translating everything into the app’s schema.

## Sprint Scope

### In scope

- draft parsing from natural-language goal input
- explicit review-before-save flow
- support for the currently implemented goal families
- MCP-first helper support, with optional lightweight in-app drafting entry if it stays small

### Out of scope

- free-form goal storage as canonical truth
- AI-authored training plans from goal text alone
- broad conversational coaching redesign

## Product Outcome

After this sprint:

- the app can convert supported natural-language goal requests into structured goal drafts
- users can review and approve the parsed goal before save
- the same goal schema stays canonical whether the draft came from forms or parsing

## Proposed Feature Slice

### 1. Supported goal utterances

Recommended first examples:

- `run 10k in under 40 minutes by October`
- `hold 300W for 10 minutes`
- `ride 6 hours of zone 2 per week`
- `lift twice per week`

Recommended direction:

- support a limited, high-confidence subset first
- prefer draft failure over silently saving a wrong structure

### 2. Draft review contract

Recommended draft fields:

- inferred goal family
- title suggestion
- parsed target fields
- confidence or parse warnings
- questions or missing fields if the input is incomplete

Recommended direction:

- draft review should stay explicit before the write happens
- incomplete parses should still be useful if they can hand the user a partially filled structured draft

## Backend Deliverables

### 1. Goal draft parsing

Likely targets:

- `backend/app/services/goals.py`
- `backend/app/models/goals.py`
- `backend/app/routers/goals.py`

Deliver:

- a read or preview route for natural-language goal drafts
- deterministic parsing into the existing structured goal schema
- parse warnings for ambiguous or unsupported inputs

### 2. MCP and optional app integration

Likely targets:

- `backend/app/services/mcp.py`
- `frontend/src/views/Goals.vue`

Deliver:

- MCP helper support for goal drafting
- optional lightweight in-app entry for pasting a natural-language goal and reviewing the draft

### 3. Coverage

Deliver:

- smoke assertions for at least three supported utterance types
- at least one ambiguous parse case that returns a draft warning rather than a silent wrong save

## Definition Of Done

Sprint 20 should be considered complete when:

- supported natural-language goal text can be converted into structured goal drafts
- users must explicitly review or approve the parsed goal before save
- the same canonical goal schema is used for drafted and manually created goals
- smoke coverage includes both successful and warning-bearing draft cases
