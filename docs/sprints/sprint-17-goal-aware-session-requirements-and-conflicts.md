# Sprint 17: Goal-Aware Session Requirements And Conflicts

## Status

Current status:

- planned
- follows completed Sprint 16 richer goal families work

Starting point:

- the app now supports explicit accumulation, process, event-performance, and benchmark goal families
- goal reads are richer and clearer, but most family-specific behavior is still presentation-first rather than planning-first
- weekly coaching can reference richer goals, but it still cannot map them into explicit weekly requirements or tell the truth when goals compete

Dependency note:

- Sprint 16 made goals more realistic to define, but not yet realistic enough to plan from
- the next quality step is not more dashboard surface area; it is better translation from goals into weekly structure and clearer conflict handling

## Objective

Make richer goals matter inside the planning workflow by mapping them to session requirements and exposing conflicts or deprioritized tradeoffs more explicitly.

This sprint should move the app from:

- `goals are richer to read, but planning still treats them mostly like background context`

to:

- `goals can express what kinds of sessions they need and when goals compete the app can explain that honestly`

## Why This Sprint

The app now knows more about the athlete and their goals than it did before, but planning quality still lags behind that richer context.

That gap matters because:

- a 10k event goal, a weekly Z2 process goal, and a strength-frequency goal should not shape the week in the same way
- current goal support in Plan is visible, but still too shallow to guide weekly structure with confidence
- hybrid athletes need the app to surface conflicts rather than quietly flattening all pressure into one generic signal
- later coaching upgrades will be weak if the app still cannot explain which session supports which requirement and what gets deprioritized

## User Story

As an athlete using the dashboard for planning and coaching, I want the app to show what weekly work each goal actually needs and where goals compete, so the plan reflects real tradeoffs instead of generic pressure.

## Sprint Scope

### In scope

- deterministic goal-to-session requirement mapping
- explicit weekly requirement summaries per active goal
- clearer support labeling in Plan and Dashboard where sessions contribute to richer goals
- visible conflict and deprioritization summaries for competing goals or modality demands
- lightweight coaching wording upgrades that reference supported requirements and conflicts

### Out of scope

- full automatic week generation from goal requirements alone
- deep training-theory engines or periodization systems
- dynamic optimization across every possible session arrangement
- probability-based readiness or success scoring

## Product Outcome

After this sprint:

- active goals can expose what kinds of sessions or weekly ingredients they need
- plan support becomes more meaningful than simple modality matching
- hybrid and competing goals can be shown as explicit conflicts or tradeoffs
- coaching can explain not only which goal is under pressure, but what kind of work matters next and what may need deprioritizing

## Proposed Feature Slice

### 1. Goal-to-session requirement mapping

Recommended first requirement concepts:

- event-performance goals can require event-specific quality, long aerobic support, or benchmark support depending on modality
- process goals can require repeatable weekly ingredients like strength frequency or aerobic time
- benchmark goals can require targeted quality or rehearsal rather than generic accumulation
- accumulation goals can remain the simplest family and mostly map to volume-supporting sessions

Recommended direction:

- keep mappings explicit and inspectable
- prefer a small vocabulary of requirement types over free-form requirement prose
- allow one goal to expose more than one requirement when needed, but keep the first version compact

### 2. Weekly support and gap visibility

Recommended behavior:

- each active goal should expose a compact weekly requirement summary
- plans should show which sessions support which requirement type, not only which goal title
- missing support should be visible in plan context when a goal has no meaningful supporting session this week

### 3. Conflict and deprioritization visibility

Recommended behavior:

- when goals compete, the app should expose a small structured conflict summary rather than silently averaging them
- coaching can explicitly note when one goal is temporarily deprioritized because another goal, restriction, or recovery constraint is more important
- hybrid athletes should see when lower-body strength, run intensity, ride volume, or availability constraints are pulling against each other

## Backend Deliverables

### 1. Requirement mapping and summaries

Likely targets:

- `backend/app/services/goals.py`
- `backend/app/services/plans.py`
- `backend/app/models/goals.py`

Deliver:

- deterministic goal-family-to-requirement mapping
- normalized requirement summaries on active goals
- gap signals for unsupported or weakly supported goals

### 2. Planning and coaching integration

Likely targets:

- `backend/app/services/plans.py`
- `backend/app/services/coaching.py`
- `backend/app/services/dashboard.py`

Deliver:

- richer `goal_context` in plans with requirement-aware support labels
- compact conflict and deprioritization summaries in dashboard and coaching reads
- first-pass coaching wording that references support gaps and tradeoffs rather than only pace pressure

### 3. Coverage

Deliver:

- smoke assertions for at least two different goal-family requirement mappings
- at least one case where a goal is shown as unsupported or conflicted in plan, dashboard, or coaching output
- at least one case where a hybrid or competing-goal tradeoff becomes visible rather than implicit

## Frontend Deliverables

### 1. Requirement-aware goal visibility

Likely targets:

- `frontend/src/views/Goals.vue`
- `frontend/src/views/Plan.vue`

Deliver:

- compact requirement summaries on goals where they help explain what matters next
- clearer support cues in Plan for why a session matters to a goal

### 2. Conflict visibility

Likely targets:

- `frontend/src/views/Dashboard.vue`
- `frontend/src/views/Goals.vue`
- `frontend/src/views/Plan.vue`

Deliver:

- visible conflict or deprioritization cues when goals compete
- lightweight wording that stays readable and does not overwhelm the primary weekly workflow

## Definition Of Done

Sprint 17 should be considered complete when:

- active goals expose deterministic weekly requirement summaries
- plan and dashboard surfaces can show support gaps or unsupported goals more explicitly
- coaching can reference requirement type or conflict where it materially changes interpretation
- competing goals can become visibly deprioritized or conflicted instead of only showing undifferentiated pressure
