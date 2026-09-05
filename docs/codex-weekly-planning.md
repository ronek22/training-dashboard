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

Feedback revisions use a separate loopback job. They send the current week and
the athlete's feedback to a new ephemeral Codex run, which verifies the current
saved plan before applying the revision. The feedback text is job input only;
it is not exposed in helper status responses.

Coach chat follows the same loopback job pattern. The browser saves the athlete
message, polls the helper while Codex is working, and persists the returned
coach response. Conversation history therefore survives browser and dashboard
restarts, while Codex sessions themselves remain ephemeral.

The helper accepts browser calls only from the local dashboard origins. Codex
runs from a fresh empty temporary workspace with automatic approval review and
is explicitly instructed not to edit files, run shell commands, browse, or use
other MCP servers. The dashboard repository is not used as its working folder.

## Starting and stopping

The normal `just` or `just up` startup starts the helper before Docker. `just
down` stops both. These commands are also available for troubleshooting:

```text
just codex-helper-status
just codex-helper-start
just codex-helper-stop
```

If the button says the helper is unavailable, restart the dashboard normally.
The helper log is stored locally as `.codex-planning-helper.log` and is ignored
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
