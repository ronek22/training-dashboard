# Development skills installation and trial

Installed on 2026-09-10 in `/Users/jakubronkiewicz/.codex/skills`. All eight entrypoints exist and have YAML frontmatter. Installation used the bundled skill-installer script and upstream repositories' main branches. Skills were read and applied manually in this turn; automatic discovery/triggering is available on the next turn and was not tested here.

| Skill | Upstream | Trial and result |
| --- | --- | --- |
| vue-testing-best-practices | vuejs-ai/skills | Reviewed existing behavior tests and ran `node --test tests/*.test.mjs`: 19 passed. Existing tests cover JavaScript logic, not mounted Vue components. |
| systematic-debugging | obra/superpowers | Reproduced backend test failures, separated dependency/import-path failures from test failures, and confirmed missing fixture schema with an isolated experiment. |
| web-design-guidelines | vercel-labs/agent-skills | Fetched current interface guidelines and reviewed Sync.vue plus the app shell; findings below. |
| vue | antfu/skills | Reviewed Sync.vue Composition API usage. Computed derived state and concurrent source loading are appropriate. Installed Vue is 3.5.39, matching the skill's 3.5 baseline. No TypeScript migration performed. |
| pinia | antfu/skills | Confirmed createPinia is initialized but no defineStore calls exist in frontend/src. stores/api.js is an Axios wrapper, not a Pinia store. Useful for future stores; no current store behavior to test. Skill targets Pinia 3.0.4, while this project resolves 2.3.1, so version-specific guidance needs checking. |
| security-best-practices | openai/skills | Sampled FastAPI and Vue security guidance against API/MCP setup and frontend HTML rendering. Deployment finding below; not a complete security audit. |
| mcp-builder | anthropics/skills | Validated all 25 tool definitions with the installed MCP SDK's Tool model; all have annotations. Parsed stdio server syntax. HTTP adapter already uses stateless Streamable HTTP. No live client handshake or write tools tested. |
| playwright | openai/skills | CLI works; opened /sync in a dedicated browser, switched from Strava to Fitbod, verified active/pressed state and the Fitbod panel, resized to 390×844, saved and inspected a screenshot. |

## Verification results

- Frontend production build passed (Vite 5.4.21); existing Vite CJS API deprecation warning remains.
- Frontend logic tests: 19 passed, zero failed.
- Original `just test-backend`: 58 tests reported, 17 errors. Missing fitdecode/ijson and inconsistent app versus backend.app import roots prevented parts of the suite from loading.
- Installed declared backend dependencies into `/private/tmp/dashboard-skills-test-venv`, without changing the project's dependency files or global Python environment.
- Reran with both repository root and backend directory on PYTHONPATH: 132 tests, two assertion failures and four errors (126 passed).
- Three errors came from PlanDayComparisonTests creating only weekly_plans, while `_attach_strength_plan_identity` now queries strength_workout_sessions. A temporary in-process setUp wrapper added the missing empty table; all eight tests in that class then passed. This experiment did not edit the test file.
- Remaining error: test_activity_crud_and_stats inserts 2026-06-24 and queries the last 30 days, which excludes that date on 2026-09-10.
- Remaining assertions: MCP data_source.kind expects fitbod_enriched_strength_history but receives linked_exercise_level_strength_history; plan/coaching test expects an Autumn 10k goal-support entry which is absent. These were observed, not fully diagnosed or changed.

Backend output: `/private/tmp/dashboard-skills-backend.log`.

## Concrete review findings

- `frontend/src/App.vue:99` and `frontend/src/views/Sync.vue:2`: nested main landmarks. Keep one main landmark and use a section/div for the page wrapper.
- `frontend/src/views/Sync.vue:299`: selected source is component-local state. Switching to Fitbod leaves the URL at /sync, so refresh/deep links cannot preserve the selected source. Consider a source query parameter.
- `frontend/package.json`: frontend tests exist but no npm test script exposes them; adding a script would make the check easier to discover and run.

Guidelines used: https://raw.githubusercontent.com/vercel-labs/web-interface-guidelines/main/command.md

## Security sample

SEC-01 — High if reachable by untrusted clients: `backend/app/services/mcp.py:5` explicitly declares noauth; `backend/app/main.py:68` creates the app without authentication dependencies and mounts MCP at line 95. `docker-compose.yml:6` publishes port 8000 without restricting the host address to loopback. `backend/app/main.py:72` allows all CORS origins. This is an intentional local-app design, not a newly introduced regression. Before exposing the service beyond trusted access, enforce authentication at the appropriate boundary and narrow network/origin access. External firewall or proxy protection was not inspected; internet reachability was not tested. A source search found no v-html use in frontend/src, but that is not proof of complete XSS protection.

## Browser limitations

The temporary Vite server served the frontend only. Its API proxy targets the Docker hostname backend, unavailable from this standalone host process. Seven API requests returned 500 and the favicon returned 404. This tested UI rendering, panel switching, and the unavailable-backend state, not a working end-to-end data integration. No imports, external messages, or live data writes were performed.

Screenshot: `output/playwright/skills-mobile-smoke.png`.

## Recommendation after trying them

Use Vue testing, systematic debugging, web design guidelines, and Playwright for routine dashboard work. Vue is compatible with the installed version. Use MCP builder when changing the integration, and security-best-practices for explicit security reviews. Keep Pinia available for future state-management work. These trials demonstrate usable workflows and concrete findings, not a measured speed or quality improvement against a no-skill baseline.

No application source files were changed by this trial. Existing uncommitted work was preserved.
