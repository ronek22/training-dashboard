# Codex project instructions

Working in `ios/` (the native iPhone app)? Follow `ios/AGENTS.md`; it overrides this file.

The root agent owns architecture, decomposition, integration, and final verification.
Work inline by default. Every subagent starts cold and re-reads what it needs, so delegation
multiplies token use. Spawn one only for a broad read-only search across many files whose
conclusion is all you need, or when the user asks for it.

Do not delegate work whose context you already hold, and do not delegate merely for parallelism.
Do not let multiple implementation agents edit the same files without explicit ownership boundaries.
User instructions always take precedence over this orchestration policy.

## Keep context small

- Web and backend work: scope searches to `backend/`, `frontend/` and `docs/`; skip `ios/`.
- Start from `docs/current-state.md` (a short index) and `docs/project-structure.md`. A shipped
  feature's full entry is in `docs/shipped/YYYY-MM.md`: grep its `### Title` and read that range,
  not the whole file. Skip `docs/sprints/`, `docs/roadmaps/` and `docs/specs/` unless the task is
  about them.
- Files over ~1,000 lines (`views/Mountains.vue`, `views/Dashboard.vue`, `services/goals.py`,
  `services/plans.py`, the larger tests): grep for the symbol, then read only the lines around it.
  Plan and Goals are split into `plan/` and `goals/` (components, composables, tested helpers).
- Tests: run the focused file first
  (`PYTHONPATH="$PWD" backend/.venv/bin/python -m unittest -q backend.tests.test_<area>`,
  `cd frontend && npm test`), then `just check` once before finishing. Both print only a
  summary when they pass; pipe anything else long through `tail`.
- Spec Kit (`docs/spec-kit.md`) is for features that span several sessions. Small fixes and
  single-session features go straight to code, tests and the shipped entry.

## UI redesign

For any frontend/UI work, follow `docs/design/REDESIGN.md` and match the page's artboard screenshot in `docs/design/screens/`. Read only that page's PNG and grep its `.dc.html` for exact values; never read whole artboards. Work on branch `redesign-multisport`.
