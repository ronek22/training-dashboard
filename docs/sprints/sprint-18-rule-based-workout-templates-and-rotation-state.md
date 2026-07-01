# Sprint 18: Rule-Based Workout Templates And Rotation State

## Status

Current status:

- complete
- follows Sprint 17 goal-aware session requirements and conflicts

Starting point:

- the app already supports richer goals, athlete profile context, modality restrictions, and weekly plan adjustment
- Sprint 17 is intended to make goal requirements and conflicts visible in planning
- the planner still treats many sessions too generically, especially strength, and does not yet understand durable progression rules such as workout rotation

Dependency note:

- once Sprint 17 can express what kinds of work a goal needs, the next step is to make the week generator and adjustment flow preserve real training logic
- this is especially important for hybrid athletes using structured strength programs rather than interchangeable “strength” sessions

## Objective

Move the planner from generic recurring session labels toward rule-based workout sequencing that can preserve workout identity, rotation state, and simple coaching rules across weeks.

This sprint should move the app from:

- `the weekly plan can schedule strength, but it does not understand the athlete's actual strength program`

to:

- `the weekly plan can schedule specific reusable workout templates and continue them across weeks using explicit rules`

## Why This Sprint

The app is already moving toward a rule-based coach rather than a static calendar generator, but it still loses too much long-term training structure when composing or adjusting a week.

That gap matters because:

- a rotating strength program should continue from the last completed workout rather than restart each Monday
- missed sessions often need postponement, not silent skipping or template reset
- hybrid planning needs durable rules such as `prefer riding while running is restricted` or `delay lower-body work when heel symptoms worsen`
- weekly plans become easier to trust when they schedule named templates like `Workout C` instead of generic `Strength`

## User Story

As an athlete following a repeating strength program inside a hybrid training week, I want the planner to remember where I am in the rotation and schedule the next logical workout using clear rules, so my week preserves training continuity instead of treating every strength day as interchangeable.

## Sprint Scope

### In scope

- reusable workout templates for recurring programmed sessions
- persisted rotation state for template-based sequences such as strength A/B/C/D
- deterministic planner rules that can guide week generation and adjustment
- weekly plan support for scheduling template identities instead of only generic modality labels
- lightweight visibility into current rotation state and next programmed workout

### Out of scope

- a full drag-and-drop workout-program authoring system
- deep exercise-level programming or set/rep progression engines
- AI-generated program design from scratch
- broad free-form rule authoring language

## Product Outcome

After this sprint:

- the app can represent structured reusable workout templates like `Workout A`, `Workout B`, `Workout C`, and `Workout D`
- the planner can remember `last completed` and `next workout` state for a rotation
- weekly planning and adjustment can preserve a rotation instead of restarting it
- athlete profile or planning settings can store durable planning rules that shape how templates are selected

## Proposed Feature Slice

### 1. Workout templates

Recommended first template behavior:

- allow a small set of named templates for recurring structured sessions
- support strength as the first template-backed modality
- separate template identity from weekly schedule placement

Example direction:

- `Workout A` = `Upper Chest`
- `Workout B` = `Back + Arms`
- `Workout C` = `Wide Shoulders`
- `Workout D` = `Lower + Core`

Recommended modeling:

- the weekly plan should schedule `Workout C` on Wednesday rather than storing all workout content in the plan row itself
- the template definition should remain durable and reusable across weeks

### 2. Rotation state

Recommended first rotation behavior:

- persist `last completed workout` and `next workout`
- advance only when a planned template-backed workout is actually completed
- postpone missed workouts instead of automatically skipping ahead

Example logic:

- last completed `B`
- next workout `C`
- if `C` is missed, keep `C` as next instead of jumping to `D`
- if `C` is completed, advance to `D`

### 3. Rule-based planning inputs

Recommended first planner rules:

- continue rotation instead of restarting each week
- never repeat the same workout consecutively
- preserve completed sessions
- delay lower-body work when injury or restriction context makes it inappropriate
- prefer riding over running while running is restricted
- replace true rest with recovery movement only when that rule is explicitly enabled

Recommended direction:

- keep the first rule set explicit and settings-backed
- prefer toggles, enumerated behaviors, or structured notes over a generic scripting system

## Backend Deliverables

### 1. Template and rotation persistence

Likely targets:

- `backend/app/models/settings.py`
- `backend/app/repositories/settings.py`
- `backend/app/services/settings.py`
- `backend/app/models/plans.py`

Deliver:

- persisted workout-template definitions or template references
- persisted template rotation state such as `last_completed` and `next_template`
- normalized read contracts for planner-facing state

### 2. Planning and activity integration

Likely targets:

- `backend/app/services/plans.py`
- `backend/app/services/activities.py`
- `backend/app/services/coaching.py`

Deliver:

- plan sessions can carry template identity
- completion of a template-backed session can advance rotation state
- weekly adjustment logic can preserve or postpone template order rather than flattening back to generic strength blocks

### 3. Coverage

Deliver:

- smoke assertions for creating or reading a simple template rotation
- at least one case where completing a workout advances `next workout`
- at least one case where a missed workout is postponed rather than skipped
- at least one case where a restriction-aware rule changes which template-backed session is preferred

## Frontend Deliverables

### 1. Template and rotation visibility

Likely targets:

- `frontend/src/views/Goals.vue`
- `frontend/src/views/Plan.vue`
- `frontend/src/views/Dashboard.vue`

Deliver:

- visible `current rotation` or `next workout` summary for template-backed programs
- plan cards that show `Workout C` or equivalent template identity rather than only `Strength`
- lightweight explanation of why a given template appears next

### 2. Durable rule configuration

Likely targets:

- `frontend/src/views/Goals.vue`
- a future compact settings surface if needed

Deliver:

- simple editable rule controls for rotation continuation and skip/postpone behavior
- lightweight profile or planner-rule wording that keeps the feature understandable

## Definition Of Done

Sprint 18 should be considered complete when:

- the app can schedule specific reusable workout templates instead of only generic strength sessions
- template rotation state persists across weeks and advances on completion
- missed template-backed sessions can be postponed instead of silently skipped
- at least one rule-based planning behavior changes weekly adjustment output in a visible and inspectable way

Implemented slice:

- settings-backed strength templates and persisted rotation state now exist
- generic strength plan days are normalized into named templates like `Workout A` and `Workout B`
- linked completion of template-backed strength sessions advances the persisted next-workout pointer
- missed strength sessions stay pending so later plan creation postpones them instead of skipping ahead
- restriction-aware assignment can delay lower-body strength while running is limited or blocked
- `Goals`, `Plan`, and `Dashboard` now surface the current rotation and next programmed workout
