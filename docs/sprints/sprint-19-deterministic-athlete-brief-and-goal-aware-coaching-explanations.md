# Sprint 19: Deterministic Athlete Brief And Goal-Aware Coaching Explanations

## Status

Current status:

- completed
- follows completed Sprint 18 rule-based workout templates and rotation state

Starting point:

- the app now has a durable athlete profile, richer goals, requirement-aware plan context, and strength rotation state
- weekly coaching already references some of this context, but the explanation layer is still assembled from overlapping fragments
- MCP and recent-context reads still expose several adjacent structures instead of one compact coaching-ready brief

Dependency note:

- Sprint 18 improved planning continuity inside the app
- the next step should improve how the same structured context is packaged and explained across Dashboard, Plan, and MCP

## Objective

Package athlete, goal, restriction, execution, and rotation context into one deterministic brief, then use that brief to produce clearer goal-aware coaching explanations with less duplication.

This sprint should move the app from:

- `the app has useful context, but coaching explanations still feel assembled from neighboring summaries`

to:

- `the app exposes one compact coaching brief and can explain recommendations in a more coherent, goal-aware way`

## Why This Sprint

That gap matters because:

- coaching UI is starting to show repeated or adjacent signals instead of one clear explanation stack
- MCP and chat surfaces still have to reconstruct the athlete story from several payload fragments
- hybrid planning trust improves when the app can say what it is advancing, what it is maintaining, and what it is deprioritizing
- recent context is now rich enough that packaging quality matters almost as much as raw logic quality

## User Story

As an athlete reading weekly coaching or asking for help through MCP, I want one compact structured coaching brief and clearer goal-aware explanations, so I can understand the recommendation without piecing together several overlapping summaries.

## Sprint Scope

### In scope

- one deterministic athlete brief for MCP and recent-context reads
- clearer separation between recommendation rationale, risk, and recent-pattern summaries
- explicit coaching explanation fields for primary-goal support, secondary-goal maintenance, and deprioritized work
- dashboard and plan wording cleanup where the same coaching point currently appears more than once

### Out of scope

- natural-language goal parsing
- new goal families
- autonomous coaching writes
- large UI redesign beyond explanation clarity

## Product Outcome

After this sprint:

- recent context and MCP reads expose one compact coaching-ready athlete brief
- weekly coaching explanations reference the same structured brief instead of recomputing loosely
- dashboard coaching sections should feel less repetitive and more intentional
- tradeoffs between primary, secondary, and constrained work become easier to inspect

## Proposed Feature Slice

### 1. Deterministic coaching brief

Recommended first brief structure:

- athlete profile summary
- active goals with compact urgency and support state
- modality restrictions
- current weekly execution and recovery state
- current template rotation summary
- current planning risks and conflicts

Recommended direction:

- keep this brief compact, deterministic, and directly reusable by MCP, Dashboard, and coaching services
- prefer one normalized structure over several partially overlapping read shapes

### 2. Goal-aware explanation contract

Recommended explanation fields:

- what this recommendation mainly protects or advances
- what secondary work is being maintained
- what is being reduced, delayed, or deprioritized
- which signals are immediate versus which are recent-pattern context

Recommended direction:

- keep explanations short and inspectable
- avoid duplicating the same text in `Why This Call`, `Recent Patterns`, and adjustment rationale

## Backend Deliverables

### 1. Compact coaching brief packaging

Likely targets:

- `backend/app/services/dashboard.py`
- `backend/app/services/mcp.py`
- `backend/app/services/coaching.py`

Deliver:

- one normalized `athlete_coaching_brief` or equivalent compact context payload
- recent-context and MCP reads that expose the same compact structure
- reduced duplication across coaching reasoning fields

### 2. Clearer coaching explanation fields

Likely targets:

- `backend/app/services/coaching.py`

Deliver:

- structured explanation fields for primary support, secondary support, and deprioritized work
- recommendation rationale and risks that do not simply restate recent-pattern summaries
- stable wording rules for restriction, fatigue, and goal-conflict cases

### 3. Coverage

Deliver:

- smoke assertions for the compact athlete brief shape
- at least one case where explanation output distinguishes primary-goal advancement from deprioritized secondary work
- at least one case where repeated summary text is not emitted in multiple coaching sections

## Frontend Deliverables

### 1. Coaching explanation cleanup

Likely targets:

- `frontend/src/views/Dashboard.vue`
- `frontend/src/views/Plan.vue`

Deliver:

- clearer separation between `Why This Call` and `Recent Patterns`
- compact visibility into the new deterministic coaching brief where useful
- more explicit wording around what the current recommendation is protecting or delaying

## Definition Of Done

Sprint 19 should be considered complete when:

- MCP and recent context expose one compact deterministic coaching brief
- coaching explanations explicitly distinguish what is being advanced, maintained, and deprioritized
- duplicated explanation text across dashboard coaching sections is materially reduced
- smoke coverage includes the new brief and at least one explanation-specific regression case
