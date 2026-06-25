# Phase 1 Sprint: Adaptive Planning In-App

## Status

Current status:

- partially implemented
- the core `Adjust Remaining Week` flow now exists in the app
- this sprint should be treated as still open until the remaining visibility and status-semantics work is finished

What appears complete already:

- frontend API support for `POST /plans/weekly/adjust`
- Plan page adjustment UI
- save result messaging for changed and preserved dates

What still remains to close Phase 1 cleanly:

- plan revision visibility or snapshots
- clearer `moved` / `skipped` / `replaced` comparison semantics

Ordering note:

- this is the current sprint document for roadmap Phase 1
- [sprint-3-feedback-loop.md](sprint-3-feedback-loop.md) should be treated as the next major sprint after the remaining work here is either completed or intentionally deferred

## Objective

Make weekly plan adjustment usable directly in the app, without relying on chat for the common replanning workflow.

This sprint is the first implementation slice from [docs/roadmap.md](../roadmap.md).

## Why This Sprint

The backend already supports partial plan adjustment through `/plans/weekly/adjust`.

What is missing:

- a UI to trigger adjustments
- clear user feedback after an adjustment
- visibility into what changed and what was protected
- a better mental model for planned vs completed status

This is the highest-leverage next step because it turns an internal capability into a user-facing workflow.

## Sprint Scope

### In scope

- add an `Adjust Remaining Week` action in the Plan view
- allow editing only adjustable days
- submit changes through the existing adjustment endpoint
- show saved result:
  - changed dates
  - preserved dates
  - updated plan content
- improve plan status language where needed
- capture minimal adjustment rationale in the request

### Out of scope

- full plan revision browser
- automatic AI-generated replanning inside the frontend
- drag-and-drop calendar editing
- explicit planned-to-actual linking
- major visual redesign of the Plan page

## User Story

As a user who did not follow the original week exactly, I want to adjust the rest of the week in the app so the plan reflects what I actually did, without overwriting completed days.

## Expected User Flow

1. Open the Plan page.
2. Select the current or active week.
3. Click `Adjust Remaining Week`.
4. See which days are protected because they are in the past or already completed.
5. Edit only the remaining open days.
6. Optionally enter a short adjustment reason.
7. Save.
8. See confirmation with changed vs preserved dates.
9. See the updated week immediately in the existing plan view.

## Deliverables

### 1. Frontend API support

Add API method for:

- `POST /plans/weekly/adjust`

Target file:

- [frontend/src/stores/api.js](../../frontend/src/stores/api.js)

### 2. Plan view adjustment UI

Add a lightweight editing flow in the Plan page.

Recommended approach:

- modal or inline editor attached to the active week card

Target file:

- [frontend/src/views/Plan.vue](../../frontend/src/views/Plan.vue)

Core UI requirements:

- clearly mark protected days
- editable fields for:
  - title
  - session type
  - target duration
  - target distance
  - details
- optional `adaptation_reason`
- cancel and save actions

### 3. Save result feedback

After a successful adjustment:

- show a clear success message
- show changed dates
- show preserved dates
- reload the plan list

### 4. Status polish

Review whether the current labels are clear enough in the updated flow.

At minimum:

- ensure protected/completed days are visually distinct in the editor
- ensure non-matching days are understandable after plan adjustment

## Suggested Implementation Order

1. Add `adjustWeeklyPlan` API helper.
2. Identify the active plan in the Plan view.
3. Add local editor state for adjustable days.
4. Build the adjustment form UI.
5. Submit to backend and handle response.
6. Refresh plans after save.
7. Add user-facing success and error states.
8. Polish labels and protected-day presentation.

## Data Contract

Expected request shape:

```json
{
  "week_start": "2026-06-22",
  "effective_from": "2026-06-25",
  "adaptation_reason": "Missed Tuesday run and moved long session later",
  "days": [
    {
      "date": "2026-06-26",
      "label": "Fri",
      "session_type": "Run",
      "title": "Easy aerobic run",
      "details": "Keep it relaxed",
      "target_duration_min": 45,
      "target_distance_km": 8
    }
  ]
}
```

Expected useful response fields:

- `week_start`
- `effective_from`
- `changed_dates`
- `preserved_dates`
- `plan`

## UX Constraints

- do not let the user edit protected days in the adjustment flow
- do not force editing of every remaining day
- keep the workflow shorter than editing an entire weekly plan from scratch
- preserve the current page structure as much as possible

## Risks

- the Plan page could become too dense if the editor is too large
- date-based protection may confuse users if not explained clearly
- partial updates can feel opaque unless changed dates are shown explicitly

## Definition Of Done

- user can adjust remaining days from the Plan page
- protected days are non-editable in the UI
- save uses `/plans/weekly/adjust`
- success feedback clearly states what changed
- updated plan is visible immediately after save
- errors from invalid adjustments are shown clearly

## Follow-up After This Sprint

Once this sprint is complete, the next best follow-up is:

1. add plan revision history
2. improve moved/skipped/replaced status semantics
3. add post-workout feedback capture

That means:

- items 1 and 2 are still part of closing Phase 1
- item 3 is the bridge into [sprint-3-feedback-loop.md](sprint-3-feedback-loop.md)
