# Sprint 32: Planned-Vs-Actual Workout Quality

## Status

Current status:

- proposed
- follows completed Sprint 31 goal readiness and `what matters next`

Starting point:

- the app already supports planned-session IDs, explicit activity linking, structured workout intent, heart-rate zones, benchmark tags, strength enrichment, and activity-detail analysis
- plan comparison can say whether a session happened, but it still says relatively little about whether the session achieved its intended training effect
- goal-readiness and coaching quality are limited when the system treats all completed sessions as equally successful

Dependency note:

- Sprint 5 and Sprint 6 established linkage and workout-intent foundations
- Sprint 23, Sprint 28, and Sprint 29 improved activity detail, zone visibility, and workout interpretation
- the next step should convert that evidence into conservative execution-quality judgments for linked sessions

## Objective

Add intent-aware workout-quality evaluation so the app can judge whether a completed session matched its planned purpose, not just whether it was completed.

This sprint should move the app from:

- `a completed session counts as done even if execution quality is unclear`

to:

- `the app can summarize whether a linked session matched, drifted from, or only partially satisfied its planned intent`

## Why This Sprint

That gap matters because:

- an easy run that turns into a threshold effort should not be treated the same as well-executed aerobic work
- a quality workout can be present on the calendar but still miss enough specific work
- strength sessions may be logged but under-delivered relative to the intended template
- later coaching and adaptation decisions need better evidence than completion alone

## User Story

As an athlete reviewing my training week, I want the app to tell me whether completed sessions were executed in line with their intended purpose, so I can understand training quality rather than only volume or attendance.

## Sprint Scope

### In scope

- conservative quality evaluation for linked planned sessions with explicit intent
- first-pass execution-quality support for easy, long, quality, and strength session types where evidence is strong enough
- activity-detail and plan-review visibility for execution-quality outcomes
- matched, partial, drifted, and unavailable states

### Out of scope

- granular interval-by-interval workout builder validation
- pace, power, and heart-rate mixed scoring that exceeds current data trust
- hidden heuristic judgments without explicit rationale
- automatic plan changes triggered directly from quality outcomes

## Product Outcome

After this sprint:

- linked sessions can show whether execution aligned with intent
- activity detail can explain why a session quality read is partial or drifted
- weekly review gains stronger evidence for coaching and adaptation
- the product becomes more honest about `completed but not really as planned`

## Proposed Feature Slice

### 1. Intent-aware quality rules

Recommended first support:

- easy aerobic sessions: detect excessive higher-zone drift when zone evidence is available
- long sessions: check whether expected duration or aerobic emphasis was meaningfully preserved
- quality sessions: detect whether enough workload occurred in the intended intensity band when evidence exists
- strength sessions: compare enriched completion against expected template coverage where practical

Recommended direction:

- start with a narrow set of intent types that already have explicit structure
- if intent or detail is weak, mark the result unavailable rather than guessing

### 2. Shared execution-quality contract

Recommended first support:

- compact state such as `matched`, `partial`, `drifted`, `completed_without_evidence`, or `unavailable`
- supporting reasons and limitations fields
- compatibility with dashboard, plan review, activity detail, and coaching reads

Recommended direction:

- make the result inspectable
- avoid collapsing everything into one score

### 3. Athlete-facing review surfaces

Recommended first support:

- execution-quality summary in activity detail
- plan-day or weekly-review cues where a linked session meaningfully drifted
- coaching references that differentiate missed sessions from poorly executed ones

Recommended direction:

- use this to sharpen review, not to shame the athlete
- keep the first UI compact and evidence-first

## Backend Deliverables

### 1. Execution-quality evaluation

Likely targets:

- `backend/app/services/activities.py`
- `backend/app/services/plans.py`
- `backend/app/services/strength.py`

Deliver:

- reusable execution-quality evaluator for supported intent types
- structured result contract with supporting reasons
- explicit handling for weak or missing activity detail

### 2. Surface integration

Likely targets:

- `backend/app/services/dashboard.py`
- `backend/app/services/coaching.py`

Deliver:

- weekly-review and coaching payload fields that can reference execution quality
- no requirement for broad rewrite of existing comparison contracts

### 3. Coverage

Deliver:

- at least one matched easy or long session case
- at least one drifted or partial session case
- at least one unavailable case where detail is missing
- at least one strength-specific quality case if template evidence is present

## Frontend Deliverables

### 1. Activity and plan review visibility

Likely targets:

- `frontend/src/views/ActivityDetail.vue`
- `frontend/src/views/Plan.vue`

Deliver:

- execution-quality section or badge in activity detail
- compact cues in plan review for important drifted or partial sessions
- limitation messaging when evidence is incomplete

## UX Notes

Recommended first rules:

- use states and reasons instead of a universal grade
- distinguish `not enough evidence` from `poor execution`
- preserve dignity in the copy
- show the intended purpose alongside the quality read

Recommended first copy direction:

- `Matched intended effort`
- `Drifted harder than planned`
- `Completed with limited evidence`
- `Not enough detail to judge workout quality`

## Definition Of Done

Sprint 32 should be considered complete when:

- the app can evaluate workout quality for at least a narrow supported set of linked intent types
- activity detail and review surfaces can show the result clearly
- coaching can distinguish execution-quality misses from simple non-completion
- missing-data cases remain explicit and conservative
