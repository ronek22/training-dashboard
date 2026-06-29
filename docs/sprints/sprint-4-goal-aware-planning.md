# Sprint 4: Goal-Aware Planning

## Status

Current status:

- complete
- follows the first functional implementation of Sprint 3 feedback and daily guidance

Completed so far:

- active goal context attached to weekly plan responses
- per-day goal support mapping in plan data
- initial goal focus summary in the Plan view
- focused backend coverage for goal-aware plan responses
- reusable planning-focused pacing guidance in goal responses
- Goals view now shows planning cues derived from current pace and remaining target
- recent planning context now includes active goals plus compact goal pacing priority for MCP/coaching flows
- Sprint 4 is complete enough to move on to planned-to-actual linking

Dependency note:

- Sprint 3 introduced feedback capture and recommendation signals
- this sprint should make weekly plans reflect active goals more directly

## Objective

Make weekly plans feel connected to current goals instead of living beside them.

This sprint should move the app from:

- `I have goals`
- `I have plans`

to:

- `this week’s plan is helping my current goals on purpose`

## Why This Sprint

The product already has:

- active goals with progress tracking
- weekly plans with adjustment support
- plan-vs-actual comparison
- first-pass coaching feedback and recommendation signals

What is still missing is a clear bridge between the target and the plan.

That gap matters because:

- goals are visible, but they do not shape planning strongly enough
- plans are still mostly generic unless the user interprets them manually
- coaching context is weaker when goals and sessions are not explicitly related
- future adaptations will be better if the system knows what each session supports

## User Story

As a user with active training goals, I want the weekly plan to show which sessions support which goals, so the plan feels intentional and easier to evaluate.

## Sprint Scope

### In scope

- attach active goal context to weekly plan responses
- show goal support inside the Plan view
- surface which sessions support which goals
- add lightweight goal-aware planning context for future coaching and prompt flows
- improve short-term goal pacing visibility where it directly supports planning decisions

### Out of scope

- automatic full plan generation from goals alone
- autonomous rewrites of plans with no review step
- heavy forecasting or statistical modeling
- deep planned-to-actual linkage
- structured workout-intent taxonomy beyond current session types

## Product Outcome

After this sprint:

- weekly plans show active goals that matter for that week
- plan days can explain which goal a session supports
- goals and plans feel like one workflow rather than separate features
- future coaching actions can use goal-aware plan context more reliably

## Proposed Feature Slice

### 1. Plan goal context

Each weekly plan response should include:

- active goals relevant to the plan window
- lightweight session support mapping
- simple counts or labels showing goal coverage

Important constraint:

- keep linkage rule-based and inspectable
- do not invent sophisticated scoring for session contribution yet

### 2. Plan UI goal focus

Update the Plan view so each week shows:

- which goals are active
- current goal progress
- how many sessions in the week support that goal

Recommended UX:

- compact summary at the top of the week card
- per-day support pills or tags
- avoid turning the Plan page into a second Goals page

### 3. Goal-aware coaching context

Extend planning and coaching context so future plan-generation or coaching flows can access:

- relevant active goals
- progress versus target
- current week support coverage

This is groundwork for later MCP coaching improvements without needing a protocol redesign now.

### 4. Planning-focused goal pacing

Add only the goal pacing context that helps planning decisions directly, such as:

- ahead / on pace / behind
- remaining target
- short summary of current risk or pressure

Do not overbuild this into a predictive analytics layer yet.

## Backend Deliverables

### 1. Goal-aware plan serialization

Likely target:

- `backend/app/services/plans.py`

Deliver:

- relevant-goal selection for each plan week
- per-day support mapping
- goal context bundled in weekly plan responses

### 2. Goal pacing support

Likely target:

- `backend/app/services/goals.py`

Deliver:

- reusable goal progress and pace information that can support planning views

### 3. Context upgrade for future planning flows

Likely targets:

- existing plan/dashboard/MCP context paths

Deliver:

- enough goal-aware context that later coaching flows do not need ad hoc joins

## Frontend Deliverables

### 1. Plan goal summary

Update `frontend/src/views/Plan.vue`:

- show active goals for each week
- show goal progress context
- show how sessions support those goals

### 2. Optional small goal-planning touchpoints

If needed during the sprint:

- small Goal view polish for planning-relevant pacing
- small Dashboard references only if they help plan decisions directly

## Suggested Implementation Order

1. add goal-aware context to weekly plan serialization
2. expose per-day support mapping
3. surface goal context in the Plan view
4. add focused test coverage for goal-aware plan responses
5. decide whether small pacing follow-up belongs here or in the next sprint

## Risks

- weak linkage rules could look arbitrary if they are too broad
- overly dense plan UI could reduce readability
- goals may still feel shallow if support labels are vague

## Design Constraints

- keep goal linkage explicit and understandable
- prefer simple support labels over hidden scoring
- preserve current plan readability
- avoid automatic rewrites without user review

## Definition Of Done

- weekly plans include active goal context
- plan days can show which goals they support
- users can understand why the week supports a current target
- goal-aware plan behavior has backend coverage beyond manual inspection

## Follow-up After This Sprint

Once this sprint is complete, the next best product follow-ups are:

1. planned-to-actual explicit linking
2. structured workout intent
3. one-shot coaching MCP action for weekly analysis and adjustment
