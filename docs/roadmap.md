# Roadmap Index

This file is the stable entrypoint for roadmap discovery. The in-app Roadmap page reads it.

Active roadmap: none

Numbered sprints ended with Sprint 39 (2026-09-29). New work is picked from the Ideas board (`docs/project-ideas.json`, decided in the app) and recorded under "Recently Completed" in `docs/current-state.md`. Roadmap V3 was closed on 2026-10-13.

Archived roadmaps:

- `roadmaps/roadmap-v1.md` — completed foundation roadmap covering Phases 1 through 5
- `roadmaps/roadmap-v2.md` — completed growth roadmap covering Phases 6 through 9
- `roadmaps/roadmap-v3.md` — readiness, execution quality and progression roadmap covering Phases 10 through 12, closed 2026-10-13

## Open Threads

Known gaps that are not on the Ideas board yet. Remove a line when it ships or is dropped. Start each description with a capital letter; the page shows it as written.

- **Data-quality inbox** — One place for missing workout feedback, unmatched planned sessions, missing heart-rate streams and stale benchmarks. The unbuilt half of Sprint 35.
- **Legs every week** — The A–D lift rotation over three days a week often leaves legs with no planned sets.
- **Winter base-to-build arc** — A multi-week shape for the winter cycling block instead of week-by-week planning.
- **Stall blocks beyond Strength** — Show the running block in the Dashboard brief and use block outcomes in later suggestions.
- **Strength sets on Strava** — Waiting for a Strava endpoint that can add sets to an existing activity.

Working rule:

- keep this file short so planning entry cost stays low
- if a new multi-phase roadmap starts, set `Active roadmap:` to its file; mark a finished phase with a `Status: complete` line under its heading
- move completed roadmap generations into `docs/roadmaps/`
