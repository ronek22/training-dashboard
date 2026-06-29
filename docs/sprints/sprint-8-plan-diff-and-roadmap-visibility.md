# Sprint 8: Plan-Diff Confirmation And Roadmap Visibility

## Status

Current status:

- complete
- follows completed Sprint 7 one-shot coaching work

Starting point:

- weekly coaching now returns a structured recommendation plus optional preview-only adjustment payload
- Dashboard can already surface weekly coaching and hand a preview adjustment into the Plan flow
- Plan comparison, explicit linking, structured workout intent, and revision visibility are now stable enough to support an approval step
- roadmap, sprint, and current-state tracking already lives in markdown under `docs/`, but it is invisible in the app

Dependency note:

- the main remaining coaching workflow gap is explicit before/after approval of proposed plan changes
- the roadmap visibility idea is viable if the UI reads structured markdown metadata instead of trying to interpret arbitrary prose

Completed so far:

- weekly coaching proposed adjustments now include a structured before/after diff payload
- the Plan view now exposes a dedicated approval surface with explicit approve, cancel, and optional editor handoff actions
- plan adjustment preview and approval are now separated cleanly at the API level
- roadmap and sprint status are now available through a read-only docs-backed backend route
- the app now includes a dedicated read-only Roadmap view sourced from markdown under `docs/`
- the backend container setup now mounts `docs/` so roadmap visibility works in Docker as well as local development

Validation note:

- backend syntax checks passed for the Sprint 8 backend changes
- targeted smoke assertions were added for docs-backed planning status and adjustment diff preview shapes
- full backend and frontend environment validation still depends on locally installed FastAPI and Vite dependencies

Completion note:

- Sprint 8 can be treated as complete for the current roadmap slice
- the main remaining work is deeper coaching analysis and stronger multi-week visibility rather than approval-flow basics

## Objective

Complete the coaching loop by making proposed weekly changes reviewable and explicitly confirmable, while also exposing roadmap and sprint progress in a read-only in-app view sourced from the existing docs.

This sprint should move the app from:

- `coaching can suggest changes, but approval is still indirect`

to:

- `coaching can propose a concrete diff, and the user can inspect and approve it cleanly`

and additionally from:

- `roadmap progress exists only in markdown files`

to:

- `roadmap progress is visible in the UI without making docs editable in-app`

## Why This Sprint

Sprint 7 made the recommendation layer coherent, but there is still friction between recommendation and action.

That gap matters because:

- users should not have to infer plan changes from a draft handoff
- coaching recommendations become easier to trust when the exact week diff is visible before save
- roadmap and sprint progress are currently valuable only to someone reading the repository directly
- a read-only docs-backed progress view can improve visibility without creating a second source of truth

## User Stories

As a user reviewing a coaching suggestion, I want to see exactly what would change in my week before saving it, so I can approve the recommendation confidently.

As a user following product progress, I want to see roadmap and sprint status inside the app, so I can understand what is done, what is active, and what is next without editing anything in the UI.

## Sprint Scope

### In scope

- show explicit before/after weekly plan differences for coaching-proposed changes
- add a dedicated confirmation step before saving a proposed weekly adjustment
- keep roadmap and sprint tracking read-only in the UI
- derive roadmap and sprint status from structured markdown docs already in the repo
- represent progress visually with lightweight cards, timelines, progress bars, or other deterministic diagrams built from metadata

### Out of scope

- free-form markdown editing in the UI
- turning arbitrary markdown prose into generated charts
- autonomous write-through coaching with no user approval
- a full documentation CMS
- broad roadmap process redesign outside the existing `docs/` structure

## Product Outcome

After this sprint:

- the user can inspect concrete weekly plan diffs before accepting coaching-proposed changes
- saving a coaching adjustment becomes an explicit approval action instead of an indirect draft handoff
- roadmap and sprint progress becomes visible in-app without introducing a second editable planning system
- docs remain the source of truth for roadmap state

## Proposed Feature Slice

### 1. Coaching diff confirmation flow

The Plan workflow should support:

- current plan snapshot
- proposed plan snapshot
- day-level change highlighting
- explicit confirm or cancel actions

Recommended visible states:

- unchanged
- edited
- added
- removed
- protected or locked

Important constraint:

- the approval UI should explain changes clearly without turning into a full custom plan editor

### 2. Read-only roadmap and sprint visibility

The app should expose a compact planning status view sourced from `docs/`.

Recommended contents:

- current roadmap phase
- completed vs planned sprint list
- current recommended next sprint
- lightweight completion indicators
- links or references back to the underlying docs structure if useful

Important constraint:

- parsing should rely on stable headings, status fields, or lightweight metadata rather than trying to infer meaning from arbitrary paragraphs

### 3. Docs-backed visualization

The UI can render simple deterministic visuals from structured doc fields.

Good examples:

- sprint status chips
- phase progress bars
- milestone timelines
- completion counts by sprint or phase

Avoid:

- speculative chart generation from prose
- visuals that require manual UI-only data entry

## Backend Deliverables

### 1. Plan diff payload

Likely targets:

- `backend/app/services/plans.py`
- `backend/app/services/coaching.py`

Deliver:

- a structured before/after diff payload for proposed weekly adjustments
- explicit per-day and per-session change semantics that the UI can render directly

### 2. Approval-friendly coaching handoff

Likely targets:

- `backend/app/routers/`
- `backend/app/services/coaching.py`

Deliver:

- a stable contract for previewing and then approving a proposed adjustment
- clear separation between preview data and persisted plan writes

### 3. Docs metadata reader

Likely targets:

- new focused helper in `backend/app/services/`
- optionally a lightweight router for read-only docs-backed planning status

Deliver:

- a deterministic parser for roadmap and sprint status from `docs/`
- a normalized response shape for frontend consumption

### 4. Coverage

Likely targets:

- backend smoke tests
- focused parsing and diff tests if the new logic expands enough

Deliver:

- assertions for coaching diff payload shape
- assertions that docs-backed planning status reads expected metadata cleanly

## Frontend Deliverables

### 1. Plan approval UI

Likely targets:

- `frontend/src/views/Plan.vue`

Deliver:

- a review surface for coaching-proposed changes
- compact visual diff states
- explicit confirm and cancel actions

### 2. Read-only roadmap visibility UI

Possible targets:

- a new dedicated view
- or a compact planning-status panel if a whole page is unnecessary

Deliver:

- sprint and roadmap progress cards sourced from backend docs metadata
- visuals that fit the existing product language without pretending to be editable

## Suggested Implementation Order

1. define the structured plan-diff contract
2. add explicit preview-vs-approve handling for coaching-proposed adjustments
3. implement the Plan approval UI
4. define the minimal docs metadata shape needed for roadmap visibility
5. expose docs-backed roadmap status through a read-only route
6. build the read-only roadmap or sprint progress UI

## Risks

- if the diff contract is too loose, the approval UI will feel ambiguous
- if docs parsing depends on prose instead of metadata, roadmap visibility will be brittle
- combining approval flow and roadmap visibility in one sprint could sprawl unless the docs-backed UI stays intentionally lightweight

## Design Constraints

- docs remain the source of truth for roadmap and sprint status
- roadmap visibility in-app must be read-only
- proposed coaching changes must be explicit before they can be saved
- deterministic metadata and inspectable payloads are preferred over clever parsing or hidden automation

## Definition Of Done

Sprint 8 should be considered complete when:

- coaching-proposed weekly changes can be previewed as a clear diff before save
- the user must explicitly confirm or cancel that proposed change set
- roadmap and sprint progress is visible in the app from docs-backed metadata
- the UI does not allow roadmap or sprint editing
- the new docs and implementation direction leave a clear follow-up path for deeper multi-week coaching or broader project visibility work
