# Daily project ideas review

The Ideas page at `/ideas` complements Roadmap. A daily Codex automation reviews this repository at 09:00 Europe/Warsaw and publishes proposals into `docs/project-ideas.json`. It does not implement proposals. The page shows the last successful review and flags reviews older than 36 hours. Local scheduling depends on Codex and this Mac being available.

## User workflow

Explore an idea, review its evidence and acceptance criteria, and change its status to Shortlisted. Copy the build brief into a Codex task for this project when ready. Mark it Building and then Done yourself. Dismissed ideas remain accessible, and all statuses can be changed back. Refresh ideas reloads the saved review; it does not invoke a model.

Generated proposals are read from the existing read-only docs mount. User decisions persist separately in SQLite's `project_idea_decisions` table. A review cannot reset those decisions. No training data is sent to the daily review; review code and project documentation only.

## Reviewer instructions

1. Check for changes before reading anything else. Take `reviewed_at` from `docs/project-ideas.json` and run `git log --oneline --since="<reviewed_at>" -- . ':!docs/project-ideas.json'` and `git status --short -- . ':!docs/project-ideas.json'`. If both print nothing, the repository has not changed since the last review: publish an empty review (steps 6–7, `ideas: []`, summary "No repository changes since the review of <date>; nothing new to review.") so the page stays current, and stop. Do not read any other file in that case.
2. Read `docs/current-state.md` (a short index; open an entry in `docs/shipped/` only when a candidate idea touches it), `docs/roadmap.md`, the active roadmap, the commits and diffs since `reviewed_at`, and the source/tests those changes touch. Do not read `.env`, credentials, databases, health exports, or private training records.
3. List existing ideas compactly instead of reading the whole catalog: `python3 -c "import json; [print(i['id'], '|', i['title'], '|', i['problem']) for i in json.load(open('docs/project-ideas.json'))['ideas']]"`. Open a full entry only when a candidate is close to it. Do not repeat existing, already implemented, or already planned work, including dismissed proposals. Inspect code before concluding a feature is missing.
4. Brainstorm across athlete-facing usefulness, usability, reliability, and development efficiency. Publish zero to three worthwhile ideas, with a mix of product and engineering improvements over time. No quota: a successful review with zero additions is valid. Do not invent findings or claims of test results.
5. Each new idea needs a unique stable kebab-case ID, title, category (Product/Experience/Reliability/Engineering), effort (Small/Medium/Large), priority (High/Medium/Low), concrete problem, proposal, benefit, one to ten repository evidence strings, two to ten testable acceptance criteria, and created_on (YYYY-MM-DD). Effort is a rough scope estimate, not a time commitment.
6. Write a temporary JSON object with `reviewed_at` (current ISO timestamp with timezone), `summary` (10–2000 characters describing this review), and `ideas` (new proposals only). Follow the field shapes in the existing catalog. Do not include statuses.
7. Publish using `python3 scripts/publish_project_ideas.py --input /absolute/path/to/temporary-review.json`. This validates, rejects stale reviews, deduplicates IDs/titles, preserves existing proposals, and atomically replaces the catalog. Do not edit the catalog directly or change user selections. At 200 ideas the publisher rejects new additions; report that as a capacity issue instead of removing history.
8. Do not modify app code, start development, create tasks, commit, deploy, or update roadmap commitments during the daily review. Notify only when worthwhile new proposals are published, publishing fails, or user action is required; stay quiet when no new ideas are added.

## Verification

Run the focused backend tests with both repository and backend import roots available:

```sh
PYTHONPATH="$PWD:$PWD/backend" python3 -m unittest backend.tests.test_project_ideas
```

Use an environment with backend/requirements.txt installed. Frontend production validation: `npm run build` from frontend. Browser checks should cover loading, filtering, status persistence after reload, copying a brief, mobile layout, empty states, and API failure handling.
