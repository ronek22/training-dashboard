set dotenv-load := true
set shell := ["bash", "-cu"]

root := justfile_directory()

# Start the dashboard in the background (default).
default: up-detached

# Start the dashboard in the foreground.
up: coach-helper-start
    docker compose up --build

# Start the dashboard in the background.
up-detached: coach-helper-start
    docker compose up -d --build

# Stop the dashboard.
down:
    docker compose down
    python3 "{{root}}/scripts/coach_helper.py" stop

# Restart the dashboard in the background.
restart: down up-detached

# Follow service logs.
logs:
    docker compose logs -f

# Manage the loopback-only coach helper (runs Codex or Claude, see COACH_CLI).
# Prefers the launchd service when installed, so launchd keeps supervising it.
coach-helper-start:
    if launchctl print "gui/$(id -u)/com.trainingdashboard.coach-helper" >/dev/null 2>&1; then \
        launchctl kickstart "gui/$(id -u)/com.trainingdashboard.coach-helper"; \
        python3 "{{root}}/scripts/coach_helper.py" status; \
    else \
        python3 "{{root}}/scripts/coach_helper.py" start; \
    fi

coach-helper-stop:
    python3 "{{root}}/scripts/coach_helper.py" stop

coach-helper-status:
    python3 "{{root}}/scripts/coach_helper.py" status

# Run the helper under launchd: starts at login, restarts if it dies.
coach-helper-install:
    "{{root}}/scripts/coach_helper_service.sh" install

coach-helper-uninstall:
    "{{root}}/scripts/coach_helper_service.sh" uninstall

# Run the backend test suite.
test-backend:
    # Prefer the backend virtualenv (pip install -r backend/requirements.txt); fall back to .tmp_test_deps.
    if [ -x "{{root}}/backend/.venv/bin/python" ]; then py="{{root}}/backend/.venv/bin/python"; else py=python3; fi; \
    PYTHONPATH="{{root}}/.tmp_test_deps:{{root}}" PYTHONPYCACHEPREFIX="{{root}}/.tmp_pycache" "$py" -m unittest discover -s backend/tests

# Run the helper-script tests (coach helper, recovery, Sunday review, team coaching).
test-scripts:
    if [ -x "{{root}}/backend/.venv/bin/python" ]; then py="{{root}}/backend/.venv/bin/python"; else py=python3; fi; \
    cd "{{root}}" && PYTHONPATH="{{root}}/.tmp_test_deps:{{root}}" PYTHONPYCACHEPREFIX="{{root}}/.tmp_pycache" "$py" -m unittest scripts.test_coach_helper scripts.test_recovery_helper scripts.test_sunday_review scripts.test_team_coaching_helper scripts.test_meal_helper

# Run the frontend behavior tests.
test-frontend:
    cd "{{root}}/frontend" && npm test

# Build the frontend (catches template and import errors).
build-frontend:
    cd "{{root}}/frontend" && npm run build

# One check before shipping: frontend tests, frontend build, backend and helper tests.
check: test-frontend build-frontend test-backend test-scripts
    @echo "All checks passed."

# Create the test environments from scratch (backend virtualenv and frontend packages).
setup-checks:
    python3 -m venv "{{root}}/backend/.venv"
    "{{root}}/backend/.venv/bin/pip" install -r "{{root}}/backend/requirements.txt"
    cd "{{root}}/frontend" && npm ci

# Serve the built iPhone app on the Mac's Wi-Fi IP (find it in System Settings > Wi-Fi > Details).
phone ip:
    TRAINLOG_LAN_IP="{{ip}}" docker compose -f docker-compose.yml -f docker-compose.phone.yml up -d --build backend phone
    @echo "Open http://{{ip}}:3080 on your iPhone, then Share > Add to Home Screen."

# Stop only the iPhone frontend.
phone-stop ip:
    TRAINLOG_LAN_IP="{{ip}}" docker compose -f docker-compose.yml -f docker-compose.phone.yml stop phone

# Push the widget script to Scriptable's iCloud folder (keeps Scriptable's icon header).
widget-sync:
    #!/usr/bin/env bash
    set -euo pipefail
    target="$HOME/Library/Mobile Documents/iCloud~dk~simonbs~Scriptable/Documents/TrainLog.js"
    { head -n 3 "$target" | grep '^//' || true; cat "{{root}}/docs/iphone-widget.js"; } > "$target.tmp"
    mv "$target.tmp" "$target"
    echo "Synced to Scriptable/TrainLog.js"
