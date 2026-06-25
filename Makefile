SHELL := /bin/bash

ifneq (,$(wildcard .env))
include .env
export
endif

COMPOSE ?= docker compose
NGROK ?= ngrok
NGROK_PORT ?= 8000
NGROK_URL ?=

.PHONY: up up-detached down restart logs tunnel chatgpt test-backend

up:
	$(COMPOSE) up --build

up-detached:
	$(COMPOSE) up -d --build

down:
	$(COMPOSE) down

restart: down up-detached

logs:
	$(COMPOSE) logs -f

tunnel:
	@command -v $(NGROK) >/dev/null || { echo "ngrok is not installed or not in PATH."; exit 1; }
	@echo "Starting ngrok for http://localhost:$(NGROK_PORT)"
	@if [ -n "$(NGROK_URL)" ]; then \
		echo "Using static ngrok URL: $(NGROK_URL)"; \
		echo "Use $(NGROK_URL)/mcp in ChatGPT."; \
		$(NGROK) http $(NGROK_PORT) --url=$(NGROK_URL); \
	else \
		echo "Use the HTTPS forwarding URL with /mcp in ChatGPT."; \
		$(NGROK) http $(NGROK_PORT); \
	fi

chatgpt:
	@command -v $(NGROK) >/dev/null || { echo "ngrok is not installed or not in PATH."; exit 1; }
	$(COMPOSE) up -d --build
	@echo "Dashboard: http://localhost:3000"
	@echo "Backend:   http://localhost:8000"
	@if [ -n "$(NGROK_URL)" ]; then \
		echo "Starting ngrok with static URL $(NGROK_URL). In ChatGPT, connect $(NGROK_URL)/mcp."; \
		$(NGROK) http $(NGROK_PORT) --url=$(NGROK_URL); \
	else \
		echo "Starting ngrok. In ChatGPT, connect the HTTPS URL plus /mcp."; \
		$(NGROK) http $(NGROK_PORT); \
	fi

test-backend:
	PYTHONPATH=$(CURDIR)/.tmp_test_deps:$(CURDIR) PYTHONPYCACHEPREFIX=$(CURDIR)/.tmp_pycache python3 -m unittest discover -s backend/tests
