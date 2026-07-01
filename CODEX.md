# CODEX

This file is the root guidance note for working in this repository.

## Documentation Rule

- Treat `docs/` as the default home for planning and decision documents.
- Save new roadmaps, sprint plans, architecture notes, and durable product decisions in `docs/`.
- Prefer updating an existing document in `docs/` instead of scattering notes across the repository root.
- When a sprint or planned feature is implemented, update the corresponding documentation before closing the task.
- Mark the relevant sprint, roadmap, or feature-status documents as complete or implemented when that work is done.

## Primary Documents

- [docs/README.md](docs/README.md)
- [docs/roadmap.md](docs/roadmap.md)
- [docs/decisions.md](docs/decisions.md)

## Working Preference

- Keep product planning pragmatic and implementation-oriented.
- Favor small, compounding improvements over speculative rewrites.
- Preserve user control around training-plan changes and coaching actions.

## Backend Environment

- The backend Python environment already exists at `backend/.venv`.
- When running backend tests or backend Python commands, prefer the executables from `backend/.venv/bin/` instead of the system Python.
- Do not report missing backend dependencies until you have first tried the repo virtualenv, for example `backend/.venv/bin/python -m unittest ...`.
