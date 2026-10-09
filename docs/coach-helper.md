# One-click and conversational Codex actions

The Plan page can create or update the current week's plan without opening a
second app. Before generation, an optional planning brief lets the athlete add
fresh schedule constraints, recovery feedback, preferred session placement, or
week-specific priorities. Quick-input chips cover common constraints, while an
empty brief still generates from dashboard context alone.

After generation, the current plan exposes a **Refine with Codex** action. The
athlete can describe what should move, change, or receive less or more emphasis,
or use a quick-feedback chip. Codex rereads the saved plan and live context,
then revises only eligible remaining days through the normal adjustment tool.
Past and completed days remain protected, and the adjustment is recorded in
the plan revision history.

Activity Detail uses the same helper to generate or refresh its structured
workout-analysis panel. Codex reads the deterministic activity context and
saves the assessment, observations, limitations, and confidence note through
the existing MCP tools.

The app shell includes a floating Coach button that opens persistent, separate
chat conversations from any dashboard page. Coach Notes remains focused on
saved coaching observations. Each athlete
message and coach reply is saved in the dashboard database under its selected
conversation. Users can start, switch between, and delete conversations; an
existing pre-conversation chat is preserved as `Previous conversation`. The
local helper sends the latest question and up to 20 recent messages from only
the active conversation to an ephemeral `codex exec` run, which reads live
training context through the `training_dashboard` MCP server. The drawer stays
mounted while navigating between dashboard pages. Chat is
deliberately read-only: it can explain or propose training changes but cannot
update the weekly plan or write other dashboard data.

## How it works

1. The Plan page sends the current Monday to a small helper at
   `http://127.0.0.1:8765`, together with the optional planning brief.
2. The helper starts `codex exec` with the existing Codex login and the
   configured `training_dashboard` MCP server.
3. Codex reads the athlete, readiness, goals, recent training, existing plan,
   strength context, and week-specific athlete input, then writes the plan
   through MCP. Recovery evidence and modality restrictions remain safety
   boundaries when they conflict with the brief.
4. The page polls the job and refreshes the saved plan automatically.

If the selected Codex model reports temporary capacity pressure, the helper
retries the same bounded request with `gpt-5.6-terra` and then
`gpt-5.6-luna`. The full workflow still shares one 15-minute timeout. Override
or disable this comma-separated fallback list with the
`CODEX_FALLBACK_MODELS` environment variable. Successful jobs expose only the
final Codex message, and failed jobs return a concise error instead of raw CLI
event logs.

### Running on Claude instead of Codex

Set `COACH_CLI=claude` in `.env` (or the environment) and restart the helper
(`just coach-helper-stop && just coach-helper-start`). Every helper job —
plans, revisions, activity analysis, coach chat, daily state, recovery, team
and cycling reviews, Sunday review — then runs `claude -p` instead of
`codex exec`, using the same prompts. `COACH_CLI=codex` (the default) switches
back. The helper status response reports the active `coach_cli` and model.

The Claude run is locked down: no built-in tools, no user settings or memory,
only the `training_dashboard` MCP server at `http://localhost:8000/mcp`
(override with `TRAINING_DASHBOARD_MCP_URL`). It uses `sonnet` and retries with
`opus` on overload; override with `CLAUDE_MODEL` and `CLAUDE_FALLBACK_MODELS`.
`CLAUDE_CLI_PATH` points at a non-standard install. Claude runs count against
the Claude plan's usage limits.

### Meal estimates (Food page)

`POST /meal-estimate` takes `{text, image?: {media_type, data}}` (Polish or
English text, a base64 photo, or both) and returns editable food items with
grams, kcal and macros. It always runs Claude, whatever `COACH_CLI` says,
because Claude reads the photo through `--input-format stream-json`. The run
has no tools and no MCP server, and nothing is saved: the Food page shows the
items, the athlete corrects them, and the page saves them through
`/nutrition/food/entries`. Saved staples are passed in as reference values.
Each estimate is one short Sonnet call (~5–10 s), logged as "Meal estimate".

### Usage tracking

Every CLI attempt appends one line to `.coach-usage.jsonl` (gitignored): job
kind, CLI, model, success, duration, token counts and, for Claude, the
API-equivalent cost and the plan's 5-hour and weekly utilization. Only counters
are stored, never prompts or answers. The helper serves a summary at `/usage`,
shown on the **Coach usage** page (System section). Plain `codex exec` runs log
no token counts; Codex coach chat does.

The plan utilization covers the whole Claude account. To estimate the coach's
slice, the helper prices the interactive Claude Code sessions recorded under
`~/.claude/projects` (or `$CLAUDE_CONFIG_DIR/projects`) at API list prices,
skipping the coach's own temp-dir transcripts, and scales the window's
utilization by the coach's share of that spend. claude.ai and Claude app chats
are not visible locally, so the estimate reads high on days with chat use.

Feedback revisions use a separate loopback job. They send the current week and
the athlete's feedback to a new ephemeral Codex run, which verifies the current
saved plan before applying the revision. The feedback text is job input only;
it is not exposed in helper status responses.

Coach chat follows the same loopback job pattern. The browser saves the athlete
message, polls the helper while Codex is working, and persists the returned
coach response. Conversation history therefore survives browser and dashboard
restarts, while Codex sessions themselves remain ephemeral.

### Debugging coach chat

Coach chat reads the CLI's JSON event stream while the agent is running. The
chat shows the current stage, elapsed time, and time since the last reported
activity. Expand the debug details to inspect the model, attempt, job ID, and
timestamped tool activity. A quiet period means no new events have arrived;
it does not prove the agent has stopped working. The request still has a shared
15-minute deadline across model attempts.

Use **Copy diagnostics** to capture the current run for troubleshooting. The
diagnostics include tool names and statuses, retries, and token counts when
reported. They exclude prompts, conversation text, reasoning, tool arguments,
and tool results. The timeline retains at most 100 recent events and reports
when older events have been dropped. Diagnostics remain available in the
current chat view after success or failure; they are not saved with conversation
history and are lost when the helper restarts.

The same structured diagnostics are available from
`GET http://127.0.0.1:8765/coach-chat/<job_id>`. The local helper log also records
safe activity events with their job IDs. After updating the helper, restart it
once existing requests finish to enable live diagnostics for new requests.
Older helper processes continue to show the original status message.

The helper accepts browser calls only from the local dashboard origins. Codex
runs from a fresh empty temporary workspace with automatic approval review and
is explicitly instructed not to edit files, run shell commands, browse, or use
other MCP servers. The dashboard repository is not used as its working folder.

## Starting and stopping

The normal `just` or `just up` startup starts the helper before Docker. `just
down` stops both. These commands are also available for troubleshooting:

```text
just coach-helper-status
just coach-helper-start
just coach-helper-stop
```

If the button says the helper is unavailable, restart the dashboard normally.
The helper log is stored locally as `.coach-helper.log` and is ignored
by Git.

The Codex CLI must be installed or bundled with the ChatGPT/Codex macOS app, and
the `training_dashboard` MCP connection must point to
`http://localhost:8000/mcp`.

## Automatic Sunday AI review

The same helper also generates a short weekly review on Sundays at 23:59 in
Europe/Warsaw. It runs independently of the dashboard browser tab and catches up
the most recently due week when the helper starts again. Both backend and helper
must be running. Failures retry after 15 minutes; generated reviews are retained
and never overwritten. The dashboard shows the three takeaways and an evidence-based
assessment of the previous week's suggestion, without asking the athlete to fill in a form.
