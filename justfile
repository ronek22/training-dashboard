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
    # Prefer the backend virtualenv (pip install -r backend/requirements.txt); fall back to .tmp_test_deps.
    if [ -x "{{root}}/backend/.venv/bin/python" ]; then py="{{root}}/backend/.venv/bin/python"; else py=python3; fi; \
    PYTHONPATH="{{root}}/.tmp_test_deps:{{root}}" PYTHONPYCACHEPREFIX="{{root}}/.tmp_pycache" "$py" -m unittest discover -s backend/tests

# Run the helper-script tests (Codex planning, recovery, Sunday review, team coaching).
test-scripts:
    if [ -x "{{root}}/backend/.venv/bin/python" ]; then py="{{root}}/backend/.venv/bin/python"; else py=python3; fi; \
    cd "{{root}}" && PYTHONPATH="{{root}}/.tmp_test_deps:{{root}}" PYTHONPYCACHEPREFIX="{{root}}/.tmp_pycache" "$py" -m unittest scripts.test_codex_planning_helper scripts.test_recovery_helper scripts.test_sunday_review scripts.test_team_coaching_helper

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
