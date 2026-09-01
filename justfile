set dotenv-load := true
set shell := ["bash", "-cu"]

root := justfile_directory()

# Start the dashboard in the background (default).
default: up-detached

# Start the dashboard in the foreground.
up: codex-helper-start
    docker compose up --build

# Start the dashboard in the background.
up-detached: codex-helper-start
    docker compose up -d --build

# Stop the dashboard.
down:
    docker compose down
    python3 "{{root}}/scripts/codex_planning_helper.py" stop

# Restart the dashboard in the background.
restart: down up-detached

# Follow service logs.
logs:
    docker compose logs -f

# Manage the loopback-only Codex weekly-planning helper.
codex-helper-start:
    python3 "{{root}}/scripts/codex_planning_helper.py" start

codex-helper-stop:
    python3 "{{root}}/scripts/codex_planning_helper.py" stop

codex-helper-status:
    python3 "{{root}}/scripts/codex_planning_helper.py" status

# Run the backend test suite.
test-backend:
    PYTHONPATH="{{root}}/.tmp_test_deps:{{root}}" PYTHONPYCACHEPREFIX="{{root}}/.tmp_pycache" python3 -m unittest discover -s backend/tests
