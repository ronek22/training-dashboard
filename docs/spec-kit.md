# Spec Kit workflow

This repository uses [GitHub Spec Kit](https://github.com/github/spec-kit) v1.0.6
with the Codex skills integration and Bash scripts. The toolkit is checked into
`.specify/` and `.agents/skills/`; normal feature work does not require the Specify CLI.

## Start a feature

Open a fresh Codex task in this project to discover the installed skills. Invoke
these skills in order, reviewing the artifacts as you go:

1. `$speckit-specify <describe the desired behavior and acceptance criteria>`
2. `$speckit-clarify` when requirements need clarification.
3. `$speckit-plan` to design changes against the existing architecture.
4. `$speckit-tasks` to produce an executable task list.
5. `$speckit-analyze` to check consistency before implementation.
6. `$speckit-implement` to implement the tasks and verify behavior.
7. `$speckit-converge` to compare the implementation with its artifacts; repeat
   implementation and convergence while actionable work remains.

The project constitution is already initialized at
[constitution.md](../.specify/memory/constitution.md). Use `$speckit-constitution`
when the project's principles change. `$speckit-checklist` is available for
requirements quality checks. `$speckit-taskstoissues` is optional; publishing
issues is a separate action, not required to use this workflow.

Start with the next bounded feature, linking its existing sprint or roadmap.
Do not describe unfinished work as implemented or retroactively rewrite all sprints.

## Where files live

- `docs/specs/NNN-feature-name/`: spec, plan, tasks, and supporting artifacts.
- `specs`: relative symlink to `docs/specs`, preserving upstream script paths.
- `.specify/memory/constitution.md`: shared project principles.
- `.specify/templates/`, `.specify/scripts/`, `.specify/workflows/`: upstream tooling.
- `.agents/skills/speckit-*/SKILL.md`: project-local Codex skills.
- `.specify/feature.json`: ignored, checkout-local active-feature pointer.

Keep `docs/sprints/`, roadmaps, and `docs/current-state.md` updated with outcomes
and links to feature artifacts. Commit the skills, toolkit files, specs symlink,
and documents together. No Git extension is enabled; core feature scaffolding
creates artifact directories without automatically switching branches. When a
branch is needed, use the repository's `codex/` prefix.

## Reproduce or upgrade

Initialization used the official source pinned to a release:

```bash
uvx --from git+https://github.com/github/spec-kit.git@v1.0.6 specify init --here --integration codex --integration-options="--skills" --script sh --force --non-interactive
```

This is a setup command, not something to run before every feature. `--force` can
overwrite toolkit files; review local changes before rerunning or upgrading.
Keep the `specs` symlink and project constitution. Review upstream release notes
and generated changes before changing the pin. The CLI was run through `uvx`,
not installed globally.
