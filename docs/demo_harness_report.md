# Demo Harness Findings and Feature Ideas

## What was added
- Harness `tests/test_demo_harness.py` spins up a temp workspace, runs onboarding, exercises the planning stub when Codex is absent, audits/backfills the ProtocolSpec, executes a demo step, and drives QA-to-complete via the QA skip policy. It runs fully offline (`TASKSGODZILLA_AUTO_CLONE=false`, Codex stubbed).
- Planning stub now creates protocol files/spec/steps with QA skip, so offline runs don’t require manual seeding.
- Stub execution now honors QA skip and completes the protocol when all steps finish.
- `demo_bootstrap/` seeded with a tiny hello-world app for onboarding copies.
- Health-check wiring: `scripts/demo_harness.py` and `make demo-harness` run the harness quickly.
- TerraformManager guard: `scripts/terraformmanager_checklist.py` (+ smoke option) and `tests/test_terraformmanager_checklist.py` catch missing assets referenced in the checklist.
- Offline doc check: `scripts/offline_discovery_check.py` + tests assert required prompts/docs exist and are non-empty.

## Gaps surfaced
- TerraformManager automation is partial: checklist script has a smoke option for help commands but does not yet execute the workflow end-to-end (API/CLI/UI).

## How to run the full demo harness (API + worker)
1. Env: export `TASKSGODZILLA_DB_PATH=/tmp/tasksgodzilla-ci.sqlite`, `TASKSGODZILLA_REDIS_URL=fakeredis://` (or a real Redis URL), and set `VENV_PATH=.venv` if you use a local venv.
2. Start API: `.venv/bin/python scripts/api_server.py --host 0.0.0.0 --port 8010` (SQLite + fakeredis will run inline worker threads when fakeredis is configured).
3. Start worker (if using real Redis): `.venv/bin/python scripts/rq_worker.py` with the same env vars.
4. Run the harness end-to-end from another shell: `.venv/bin/python scripts/demo_harness.py` (or `make demo-harness`). This executes onboarding → planning stub → spec audit → step execution → QA skip and asserts protocol completion.
5. Capture outputs: harness logs are printed to stdout; planning output can be copied from `.protocols/<run>/.tmp/planning.json` if you need to inspect it.
6. Validate: rerun `scripts/ci/lint.sh`, `scripts/ci/typecheck.sh`, `scripts/ci/test.sh` to ensure the harness did not regress other flows.

## Feature ideas (BMAD/CodeMachine-inspired)
1) Track-aware planning: add quick/method/enterprise tracks (mirroring BMAD) that tune planning depth, required artifacts (PRD/architecture/UX), and QA policies; expose as flags on `protocol_pipeline.py` and in StepSpec templates.  
2) Agent bundles: ship presets for common roles (PM, architect, reviewer, QA) as reusable StepSpecs/policies so CodeMachine imports and Codex planning can attach richer role intent without custom wiring.  
3) Governance docs as first-class outputs: require/spec-gate solution design, implementation plan, and validation checklist per protocol, with a checker that fails planning when they’re missing or stale.  
4) Offline discovery fallback: a stubbed discovery step that at least asserts CI scripts/prompts exist and populates placeholder commands when Codex is absent, so new repos don’t stall on discovery.  
5) Workflow checklist automation: codify `docs/terraformmanager-workflow-plan.md` into a script/test that runs the API/CLI/UI checks and reports drifts, similar to CodeMachine regression harnesses.

## Validation coverage
- Harness runs onboarding → planning stub → spec audit → step execution → QA skip → protocol completion entirely offline. Pytest is required to execute it locally (`python3 -m pytest tests/test_demo_harness.py`).
