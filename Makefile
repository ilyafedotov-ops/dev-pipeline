.PHONY: orchestrator-setup migrate deps

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
