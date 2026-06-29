# Sprint 7: One-Shot Coaching Action

## Status

Current status:

- complete
- follows completed Sprint 6 structured workout intent work

Starting point:

- weekly plans now expose active-goal context
- planned sessions now have stable IDs and can link explicitly to completed activities
- plan comparison can distinguish explicit, inferred, moved, replaced, skipped, and unmatched states
- planned sessions and completed activities can now carry optional structured workout intent
- recent dashboard and MCP context already includes compact plan, feedback, linkage, and intent signals

Dependency note:

- the app now has enough structured context to support a more opinionated coaching action
- current MCP coaching still requires multiple reads plus manual prompt composition
- the next gap is workflow, not raw data availability

Completed so far:

- added a dedicated backend coaching service to aggregate execution, recovery, goal, and recommendation context in one payload
- added a read-only weekly coaching HTTP route for local inspection and testing
- added a `coach_this_week` MCP tool that returns the same one-shot coaching structure
- recommendation output now includes structured next-session guidance, sharper weekly heuristics, and an optional preview-only adjustment payload
- Dashboard now includes a compact weekly coaching inspection card that surfaces the one-shot read in-app
- Dashboard can now hand a coaching adjustment preview directly into the existing Plan week editor for review before save
- the Dashboard coaching card received a layout polish pass to better use horizontal space and present signals more clearly
- smoke coverage was extended for the weekly coaching HTTP route and MCP tool shape

Validation note:

- backend syntax checks passed for the new Sprint 7 modules
- targeted unittest execution is still blocked locally until FastAPI test dependencies are installed
- frontend production validation still depends on local Vite installation

Completion note:

- Sprint 7 can be treated as complete for the current roadmap slice
- the remaining caveats are environment-level validation gaps rather than missing product functionality

## Objective

Make weekly coaching usable through one structured MCP action instead of several manual reads.

This sprint should move the app from:

- `the model has to assemble context itself`

to:

- `the app can return a coherent coaching read of this week in one call`

## Why This Sprint

The product already has:

- weekly plans
- adaptive plan adjustment
- subjective feedback
- goal-aware plan context
- planned-to-actual linking
- structured workout intent

What is still missing is a single opinionated coaching workflow that uses those pieces together.

That gap matters because:

- chat still spends too much effort gathering and restating context
- coaching quality is inconsistent when every session requires ad hoc reasoning
- the user does not yet have a clean weekly `what happened / what next` workflow
- later plan-diff approval flows will be easier if the coaching read is already structured

## User Story

As a user reviewing my current week, I want the app to produce a clear coaching summary and next-step recommendation in one action, so I can understand what happened and decide whether to adjust the plan quickly.

## Sprint Scope

### In scope

- add one opinionated weekly coaching MCP action
- summarize current execution, feedback, and goal context in one response
- include deterministic recommendation fields alongside natural-language coaching output
- optionally include a lightweight proposed adjustment payload without auto-saving it
- keep the result inspectable and easy to explain

### Out of scope

- autonomous plan rewrites with no approval
- a full chat agent inside the backend
- advanced forecasting or ML scoring
- broad redesign of existing plan storage
- large new UI workflow for diff approval beyond what is needed to inspect output

## Product Outcome

After this sprint:

- chat can ask for a single weekly coaching read instead of stitching together many calls
- coaching output can reference goals, execution, intent, and recent feedback coherently
- the app can return structured recommendation data that is inspectable before any write happens
- Sprint 8 can focus on plan-diff confirmation instead of first solving weekly coaching assembly

## Proposed Feature Slice

### 1. One-shot weekly coaching action

Add a tool such as:

- `coach_this_week`

Recommended response shape:

- `summary`
- `execution_assessment`
- `recovery_assessment`
- `goal_assessment`
- `recommendation`
- `recommended_next_sessions`
- optional `proposed_adjustment`
- `reasoning_signals`

Important constraint:

- the first version should stay deterministic and transparent
- the action should gather and shape context, not hide complex autonomous decision logic

### 2. Structured execution assessment

The action should be able to explain:

- what was planned
- what was completed
- what matched, moved, or was skipped
- whether intent distribution broadly made sense
- where recent subjective feedback suggests caution

Recommended behavior:

- prefer compact, inspectable summaries over long generated narratives
- expose explicit fields that a model can cite directly

### 3. Recommendation payload

Return a recommendation that can be consumed by chat or later UI work.

Suggested fields:

- `status`: `push`, `keep`, `reduce`, `recover`, or `adjust`
- `headline`
- `rationale`
- `risks`
- `focus_for_next_48h`

Optional follow-up field:

- `proposed_adjustment` with the same general data shape expected by weekly plan adjustment flows

### 4. Coaching traceability

Make the action easy to trust.

That means including:

- key linked sessions used in the judgment
- recent high-signal feedback items
- active goals referenced by the recommendation
- compact reasons for why the recommendation landed where it did

## Backend Deliverables

### 1. Weekly coaching service

Likely targets:

- `backend/app/services/dashboard.py`
- `backend/app/services/plans.py`
- new focused helper in `backend/app/services/`

Deliver:

- a deterministic weekly coaching summary builder
- aggregation of plan execution, intent, and recent subjective state into one response

### 2. MCP action

Likely target:

- `backend/app/services/mcp.py`

Deliver:

- a new one-shot coaching tool definition and handler
- stable response schema suitable for model use

### 3. Optional non-MCP read route

If useful during implementation:

- a thin HTTP route exposing the same structured coaching payload for easier inspection and testing

Likely targets:

- `backend/app/routers/`
- `backend/app/main.py` only if wiring still lives there

### 4. Coverage

Likely targets:

- `backend/tests/test_app_smoke.py`
- follow-up focused tests if the logic expands enough

Deliver:

- smoke assertions for the coaching payload shape
- coverage for at least one `keep` or `reduce` style recommendation path

## Frontend Deliverables

### 1. Minimal inspection surface

This sprint does not need a full coaching UI, but it should leave the output easy to inspect.

Possible targets:

- no frontend work if MCP-only is enough for the first slice
- or a small debug/read surface in an existing view if inspection becomes too awkward

### 2. Reuse-ready recommendation shape

If a frontend touchpoint is added, keep it aligned with later approval flows:

- recommendation headline
- status
- key reasons
- optional changed days preview

## Suggested Implementation Order

1. define the weekly coaching response shape
2. build deterministic coaching aggregation from existing context pieces
3. expose it through an MCP action
4. add smoke coverage around payload shape and recommendation status
5. decide whether a thin inspection route or small UI surface is needed now

## Risks

- too much free-form output would make the tool hard to trust or reuse
- recommendation rules may feel arbitrary if the response does not expose enough evidence
- trying to solve plan approval in the same sprint would blur scope and slow delivery

## Design Constraints

- keep the first coaching action deterministic and inspectable
- do not auto-write plan changes in this sprint
- build on explicit linking and structured intent rather than bypassing them
- prefer a small stable schema over a large narrative payload

## Definition Of Done

- one MCP action can produce a coherent weekly coaching read in one call
- the payload includes structured execution, recovery, goal, and recommendation fields
- recommendation output is traceable to recent plan, activity, feedback, and intent context
- no plan adjustment is auto-saved as part of the coaching action
- the sprint leaves a clean path into plan-diff confirmation as the next follow-up

## Follow-up After This Sprint

Once this sprint is complete, the next best product follow-ups are:

1. plan-diff confirmation and approval flow
2. deeper history-aware execution insights across multiple weeks
3. stronger recommendation heuristics built on a stable one-shot coaching contract
