# Documentation

This directory is the source of truth for product planning and engineering decisions.

## Structure

- `spec-kit.md` — Spec Kit setup and feature workflow
- `specs/` — feature specifications, implementation plans, and task lists

- `roadmap.md` — roadmap entrypoint and active-roadmap pointer
- `roadmaps/` — archived and active roadmap files by generation
- `decisions.md` — durable decisions, tradeoffs, and conventions
- `architecture.md` — high-level system design and data flow
- `project-structure.md` — practical codebase map by backend/frontend area
- `current-state.md` — what is implemented now, a one-line index of shipped features, and what should happen next
- `shipped/` — full shipped-feature entries by month (`YYYY-MM.md`) and the old sprint records (`earlier.md`)
- `coach-helper.md` — local one-click Codex actions and troubleshooting
- `agent-workflow.md` — habits that keep coding-agent sessions cheap on this large repository
- `sprints/` — concrete implementation plans for the next work slices

## Working Rule

New planning artifacts should go here instead of the repository root.

Examples:

- feature roadmaps
- sprint plans
- architecture notes
- product decisions
- implementation tradeoffs

If a decision is important enough to influence future work, it should be written down in `docs/decisions.md`.
