# Sprint 10: Coaching History And Revision Timeline

## Status

Current status:

- planned
- follows planned Sprint 9 app redesign and information hierarchy work

Starting point:

- weekly coaching is now available as a structured read
- coaching-proposed changes can be reviewed as a diff and explicitly approved
- plan revisions are stored, but the UI only emphasizes the latest change
- coaching output is useful in the moment, but it is still mostly a single-snapshot workflow

Dependency note:

- the next trust gap is historical visibility, not basic approval
- users can now approve changes safely, but they still cannot easily answer `what changed over the last few weeks and why`

## Objective

Make coaching and plan changes visible over time instead of only at the latest-week snapshot level.

This sprint should move the app from:

- `I can inspect the latest recommendation and latest revision`

to:

- `I can see the sequence of coaching guidance, approvals, and resulting plan changes over time`

## Why This Sprint

Sprint 8 completed the approval loop, but the product still lacks continuity.

That gap matters because:

- users need to understand change over time, not only the latest diff
- recommendation trust improves when past adjustments and their reasons stay visible
- coaching becomes more useful when the app can reference earlier decisions explicitly
- later multi-week analysis will be awkward if history is still hidden behind raw rows or notes

## User Story

As a user following adaptive coaching, I want to see past recommendations and plan revisions in a clear timeline, so I can understand how the app has adjusted my training over time.

## Sprint Scope

### In scope

- expose coaching history in a compact read-only timeline
- make weekly plan revision history more visible than the latest revision banner alone
- connect recommendation, approval, and saved plan change metadata where possible
- keep the initial history flow deterministic and lightweight

### Out of scope

- full audit logging of every UI interaction
- editable timeline annotations
- speculative analysis of whether an old recommendation was `correct`
- major storage redesign beyond what is needed for practical history reads

## Product Outcome

After this sprint:

- users can inspect recent coaching decisions across multiple weeks
- plan revision history becomes part of the normal planning workflow
- recommendation traceability improves without introducing autonomous logic
- later multi-week analysis has a clearer historical foundation

## Proposed Feature Slice

### 1. Coaching history model

Recommended direction:

- store or derive a lightweight weekly coaching snapshot history
- preserve headline, status, rationale summary, and related week metadata
- avoid storing verbose generated text if compact structured fields are enough

### 2. Revision timeline

The Plan workflow should expose:

- revision timestamps
- effective dates
- adaptation reasons
- changed dates
- links between revisions and coaching-triggered changes where practical

### 3. Read surfaces

Good first surfaces:

- a compact coaching history panel on Dashboard
- a fuller revision timeline in Plan
- deterministic list or timeline presentation rather than complex visualization

## Backend Deliverables

### 1. History reader

Likely targets:

- `backend/app/services/coaching.py`
- `backend/app/services/plans.py`
- new focused helper if history shaping grows

Deliver:

- a normalized response for recent coaching history
- a normalized response for richer plan revision timeline reads

### 2. Persistence upgrade if needed

Possible targets:

- `backend/app/db.py`
- `backend/app/repositories/`

Deliver:

- minimal additive storage only if current derived history is not enough
- no broad migration beyond what the timeline actually needs

### 3. Coverage

Deliver:

- smoke assertions for history payload shapes
- at least one assertion connecting revision metadata to rendered-friendly fields

## Frontend Deliverables

### 1. Plan revision timeline

Likely target:

- `frontend/src/views/Plan.vue`

Deliver:

- a clearer multi-entry revision history surface
- compact timeline cards or rows that fit the current product language

### 2. Dashboard coaching history

Likely target:

- `frontend/src/views/Dashboard.vue`

Deliver:

- a recent coaching history panel that complements the latest one-shot coaching card

## Definition Of Done

Sprint 10 should be considered complete when:

- recent coaching decisions are visible across more than one week
- plan revisions are easier to inspect than the current latest-only treatment
- history stays read-only, deterministic, and clearly tied to real saved changes
