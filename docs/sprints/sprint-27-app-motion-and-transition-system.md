# Sprint 27: App Motion And Transition System

## Status

Current status:

- done
- follows completed Sprint 26 Fitbod-enriched strength history in MCP

Completed in Sprint 27:

- added shared motion tokens and reusable transition primitives in the frontend shell and global styles
- implemented reduced-motion-safe overlay, modal, expand-collapse, and contextual detail transitions
- refined route behavior so major navigation avoids jarring handoff effects while activity detail still preserves directional context
- replaced blunt loading states on key views with more intentional loading shells where they improved perceived responsiveness
- fixed overlay positioning and view-refresh cases that made some transitions feel heavier or visually unstable

Starting point:

- the app now has stronger information architecture across dashboard, calendar, goals, strength, activities, and activity detail
- core flows are functional, but view changes and state changes still feel abrupt
- some screens are visually dense, which makes transitions, hierarchy changes, and loading states feel heavier than they should
- recent UI improvements exposed a gap in motion design: the app needs shared rules for how screens enter, update, expand, and hand off context

Dependency note:

- Sprint 9 established the modern visual direction of the app
- later sprints expanded the product surface substantially, especially around detail views, calendar interactions, and strength analysis
- the next step should add a consistent motion layer so the product feels intentional rather than static

## Objective

Introduce a lightweight but consistent motion and transition system across the app so navigation, loading, reveal, and overlay flows feel smoother, clearer, and more connected.

This sprint should move the app from:

- `the app is visually solid but mostly snaps between states with little motion guidance`

to:

- `the app has a shared motion language that improves flow, focus, and perceived responsiveness without adding noise`

## Why This Sprint

That gap matters because:

- abrupt state changes make the app feel heavier than it is, even when data loads quickly
- transitions can reinforce context, especially when moving between calendar, activities, strength, goals, and activity detail
- compact screens benefit from animated hierarchy shifts such as expand, collapse, filter changes, and modal entry
- a shared motion system is better than one-off animations because it produces consistency and keeps future UI work disciplined

## User Story

As an athlete using the training dashboard regularly, I want screens and UI state changes to flow smoothly, so the app feels more intuitive and polished when I navigate, inspect details, and review changing data.

## Sprint Scope

### In scope

- shared motion tokens for duration, easing, distance, and opacity changes
- route-level transitions between major app views
- reusable enter, exit, fade, slide, and expand-collapse motion primitives
- improved modal, drawer, and detail-panel transitions
- loading and empty-state motion where it materially improves clarity
- reduced-motion support for accessibility

### Out of scope

- decorative animation that does not improve clarity or hierarchy
- large chart animation systems that risk hurting readability or performance
- custom canvas or WebGL motion work
- rewriting major layouts only to justify animation

## Product Outcome

After this sprint:

- moving between major screens feels smoother and more intentional
- drill-down flows such as calendar to activity detail feel more connected
- cards, panels, and drawers reveal content with consistent motion instead of abrupt jumps
- loading and filter changes feel lighter and easier to follow
- users who prefer reduced motion get a calmer version of the same UI

## Proposed Feature Slice

### 1. Shared motion foundation

Recommended first support:

- global motion tokens in shared CSS variables
- named easing and duration scales such as `fast`, `base`, and `slow`
- a small set of reusable transition classes for fade, lift, slide, and expand
- a reduced-motion override strategy using `prefers-reduced-motion`

Recommended direction:

- keep the first system small and opinionated
- prefer a few reusable primitives over per-screen custom animation rules

### 2. Route and context transitions

Recommended first support:

- route transitions between major navigation views
- context-preserving entry into activity detail and return flows
- gentle section reveals for high-level screens such as dashboard, goals, and strength

Recommended direction:

- route motion should be subtle and fast
- motion should reinforce directional flow without making the app feel slow

### 3. Stateful UI motion

Recommended first support:

- expand-collapse transitions for goals context panels and similar dense sections
- modal and feedback overlay transitions
- calendar card hover, focus, and reveal polish
- loading skeleton or shimmer treatment where it improves perceived responsiveness

Recommended direction:

- use motion to clarify hierarchy changes
- avoid stacking multiple animated effects in the same interaction

## Frontend Deliverables

### 1. Shared motion primitives

Likely targets:

- `frontend/src/App.vue`
- `frontend/src/style.css`
- shared component styles or layout wrappers

Deliver:

- shared timing, easing, and transition variables
- reusable transition wrappers or utility classes
- reduced-motion-safe defaults

### 2. Route and view polish

Likely targets:

- router shell and top-level view containers
- `frontend/src/views/Calendar.vue`
- `frontend/src/views/Goals.vue`
- `frontend/src/views/Strength.vue`
- `frontend/src/views/ActivityDetail.vue`

Deliver:

- subtle route transitions between main views
- improved contextual transitions into activity detail
- intentional stagger or reveal patterns where they help readability

### 3. Overlay and state transitions

Likely targets:

- feedback modal and any shared overlay components
- expandable sections in goals or other dense screens

Deliver:

- modal entry and exit polish
- smoother expand and collapse behavior
- clearer loading-to-loaded transitions

## Backend Deliverables

Backend impact should stay minimal in this sprint.

Deliver:

- no major backend work by default
- only small contract or loading-state support if frontend motion benefits from clearer pending-state signals

## Performance And Accessibility Notes

Recommended first rules:

- animate opacity and transform before layout-heavy properties where possible
- keep durations short and consistent
- support `prefers-reduced-motion` from the first implementation
- avoid motion that obscures content or delays interaction readiness

Recommended first UX rule:

- if animation does not improve orientation, hierarchy, or perceived responsiveness, it should not exist

## Definition Of Done

Sprint 27 should be considered complete when:

- the app has a shared motion foundation with reusable primitives
- major route changes and key overlays use consistent transitions
- at least the highest-traffic screens gain purposeful, lightweight motion polish
- reduced-motion behavior is implemented
- the UI feels smoother without becoming visually noisy or slower to use
