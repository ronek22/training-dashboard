<!--
Sync Impact Report (remove before committing):
Version: unconfigured template -> 1.0.0 (initial adoption).
Principles: replaced all five template slots with project-specific rules.
Added sections: Architecture Constraints; Development Workflow.
Removed sections: none. Deferred placeholders: none.
-->
# Training Dashboard Constitution

## Core Principles

### I. Small, Traceable Product Changes

New features MUST define the athlete-facing outcome, scope, and testable acceptance
criteria before implementation. Prefer small improvements to speculative rewrites.
Feature specifications MUST link relevant existing sprint and roadmap documents,
so implemented behavior and planned work remain distinguishable.

### II. Athlete Control and Preserved History

Training-plan changes MUST preserve past and completed sessions unless the user
explicitly requests changing them. Coaching recommendations MUST remain distinct
from saved plans, with explicit user control over applying changes. Existing
revision history and protection behavior MUST be preserved by new write paths.

### III. Trustworthy Training Data

Imports MUST preserve source provenance and avoid duplicate activities on reruns.
Ambiguous matches MUST be surfaced rather than silently merged. Missing measurements
MUST remain distinguishable from zero. Derived metrics and coaching interpretations
MUST identify their supporting data and limitations. Database changes MUST preserve
existing records; tests MUST use temporary databases rather than athlete data.

### IV. Incremental Architecture

Changes MUST fit the existing FastAPI, SQLite, Vue 3, and Vite architecture unless
a documented requirement justifies departure. Keep SQL in repositories, business
rules in services, validation in models, and transport wiring in routers/adapters.
HTTP and MCP entry points MUST share domain behavior. Prefer existing components
and conventions before introducing dependencies or additional abstractions.

### V. Proportionate Verification and Documentation

Each implementation MUST verify its acceptance criteria and record the checks run.
Changes to imports, calculations, protected-day behavior, persistence, or API/MCP
contracts MUST include relevant regression coverage. UI changes MUST check affected
flows, keyboard access, responsive layout, and loading, empty, and error states.
Documentation-only changes need artifact checks rather than application test runs.
Update affected sprint, roadmap, and feature status documents before closing work.

## Architecture Constraints

The application is a personal training dashboard with a FastAPI/SQLite backend,
a Vue 3/Vite frontend, and HTTP plus local stdio MCP interfaces. Existing architecture
and durable decisions are documented in `docs/architecture.md` and `docs/decisions.md`.
Credentials, local databases, and personal exports MUST stay out of version control
and specification examples. Use synthetic examples for sensitive training data.

## Development Workflow

Read `CODEX.md`, `docs/current-state.md`, and the relevant existing planning documents
before scoping work. For new features use specify, optional clarify, plan, tasks,
analyze, implement, and converge. Routine small fixes may use a proportionate workflow.

Feature artifacts live in `docs/specs/`; the root `specs` symlink supports upstream
Spec Kit scripts. `.specify/` holds toolkit infrastructure and this constitution.
Existing sprints and roadmaps remain the planning index; do not duplicate their history.
Use `backend/.venv/bin/python` for backend verification and a temporary
`TRAINING_DB_PATH` for checks that initialize a database. Run frontend builds and
relevant behavioral checks when frontend code changes.

## Governance

Plans and reviews MUST check these principles and document justified exceptions.
Amend this file when project requirements change, explain the reason, and update
affected durable decisions. Use major versions for incompatible principle changes,
minor versions for added or expanded principles, and patches for clarifications.
Explicit user instructions take precedence; `CODEX.md` remains repository guidance.

**Version**: 1.0.0 | **Ratified**: 2026-09-10 | **Last Amended**: 2026-09-10
