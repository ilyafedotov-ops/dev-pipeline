.PHONY: orchestrator-setup migrate deps compose-deps compose-down

VENV := .venv
PY := $(VENV)/bin/python
PIP := $(VENV)/bin/pip
ALEMBIC := $(VENV)/bin/alembic
REQS := requirements-orchestrator.txt

$(VENV):
	python3 -m venv $(VENV)

deps: $(VENV)
	$(PIP) install -r $(REQS)

migrate: $(VENV)
	$(ALEMBIC) upgrade head

# One-shot setup for the orchestrator: create venv, install deps, apply migrations.
orchestrator-setup: deps migrate
	@echo "Orchestrator ready. DB: $$DEKSDENFLOW_DB_URL or $$DEKSDENFLOW_DB_PATH (default .deksdenflow.sqlite)"

# Start only the Postgres/Redis containers (host ports 5433/6380) for local runs.
compose-deps:
	docker compose up -d db redis

# Stop Postgres/Redis containers started via compose-deps.
compose-down:
	docker compose stop db redis
