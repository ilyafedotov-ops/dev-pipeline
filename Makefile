.PHONY: orchestrator-setup migrate deps compose-deps compose-down demo-harness ctl-status ctl-health ctl-watch ctl-logs

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
	@echo "Orchestrator ready. DB: $$DEVGODZILLA_DB_URL or $$DEVGODZILLA_DB_PATH (default .devgodzilla.sqlite)"

# Start only the Postgres/Redis containers (host ports 5433/6380) for local runs.
compose-deps:
	docker compose up -d db redis

# Stop Postgres/Redis containers started via compose-deps.
compose-down:
	docker compose stop db redis

demo-harness: $(VENV)
	DEVGODZILLA_AUTO_CLONE=false $(PY) -m pytest tests/test_devgodzilla_*.py -q

# Stack manager shortcuts (see scripts/pipeline-ctl.sh help for full command surface).
ctl-status:
	@scripts/pipeline-ctl.sh status

ctl-health:
	@scripts/pipeline-ctl.sh health --exit-code

ctl-watch:
	@scripts/pipeline-ctl.sh watch

ctl-logs:
	@scripts/pipeline-ctl.sh logs
