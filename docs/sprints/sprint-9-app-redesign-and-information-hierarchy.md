# Sprint 9: App Redesign And Information Hierarchy

## Status

Current status:

- planned
- follows completed Sprint 8 plan-diff confirmation and roadmap visibility work

Starting point:

- the app is already clean, usable, and visually consistent
- roadmap visibility and plan approval flows now exist, but important states are still too visually equal
- many screens lean on the same dark-card treatment without a strong sense of priority or focus
- current and historical information often share the same visual weight

Dependency note:

- the next product gap is not raw capability, but clarity of emphasis
- before adding more historical analysis, the app should better communicate what matters most right now

## Objective

Improve visual hierarchy, emphasis, and page-level clarity so the app highlights what is important now and what is secondary.

This sprint should move the app from:

- `the app is clean, but visually flat`

to:

- `the app clearly signals what is current, important, actionable, and historical`

## Why This Sprint

The current UI is functional, but it does not always guide attention well enough.

That gap matters because:

- current week and old weeks can feel too similar in Plan
- important coaching and execution signals are not always visually dominant
- screens can feel uniform instead of intentionally structured
- the app should communicate priority through layout, color, scale, and contrast rather than only text

## User Story

As a user reviewing my training dashboard and plan, I want the most important information to stand out clearly, so I know what needs attention now and what is secondary or historical.

## Sprint Scope

### In scope

- improve visual hierarchy across key product surfaces
- distinguish current, active, historical, and secondary states more clearly
- redesign emphasis in Plan, Dashboard, and related high-value views
- preserve the current product simplicity while making it feel more intentional

### Out of scope

- a full design-system rewrite
- rebranding the product from scratch
- decorative redesign with no product-clarity benefit
- major feature work unrelated to presentation and emphasis

## Product Outcome

After this sprint:

- the app will better communicate importance and recency
- current-week planning and coaching will stand out more clearly than older history
- dashboards and plans will feel more directed, not just uniformly clean
- later feature sprints will land on a stronger visual foundation

## Proposed Feature Slice

### 1. Information hierarchy pass

Priority surfaces:

- Dashboard
- Plan
- Roadmap
- Goals where useful

Key direction:

- make primary states visually dominant
- reduce equal treatment of all cards and sections
- improve page scanning and section prioritization

### 2. Current-versus-historical distinction

Recommended behavior:

- current week should look clearly more important than older weeks
- active recommendations should stand out more than read-only context
- historical content should remain available but visually quieter

### 3. Emphasis language

Recommended tools:

- stronger typography contrast
- selective use of accent color
- differentiated card treatments
- better spacing rhythm
- clearer section grouping and focal points

Important constraint:

- avoid a noisy or over-designed interface
- emphasis should come from deliberate hierarchy, not arbitrary ornament

## Backend Deliverables

### 1. Minimal contract support if needed

Likely targets:

- existing plan or dashboard payloads only where the frontend truly needs clearer status markers

Deliver:

- no backend expansion unless UI emphasis requires a missing state or summary field

## Frontend Deliverables

### 1. Plan redesign pass

Likely target:

- `frontend/src/views/Plan.vue`

Deliver:

- stronger current-week emphasis
- clearer distinction between active and historical weeks
- better signaling for important statuses, revisions, and coaching approvals

### 2. Dashboard hierarchy pass

Likely target:

- `frontend/src/views/Dashboard.vue`

Deliver:

- clearer top-level focus areas
- stronger priority for immediate coaching, recovery, and planning signals

### 3. Shared visual language refinement

Likely targets:

- `frontend/src/App.vue`
- `frontend/src/style.css`
- relevant shared components

Deliver:

- more intentional typography, contrast, spacing, and section hierarchy
- a UI that remains clean but feels less flat and more guided

## Definition Of Done

Sprint 9 should be considered complete when:

- important current information stands out more clearly than historical information
- the Plan view makes current and old weeks visually distinct
- the overall app feels more intentionally structured without becoming noisy or hard to scan

