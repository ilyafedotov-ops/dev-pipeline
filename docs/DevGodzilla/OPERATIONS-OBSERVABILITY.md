# DevGodzilla Operations and Observability

> Status: Active
> Scope: Health, metrics, logging, events, webhooks, reconciliation, and tracing as implemented by the current backend
> Source of truth: `devgodzilla/api/app.py`, `devgodzilla/api/routes/{events,logs,metrics,runs,cli_executions,webhooks,reconciliation}.py`, `devgodzilla/services/{events,event_persistence,health,telemetry,reconciliation}.py`, operations-focused tests under `tests/`
> Last updated: 2026-04-20

## Health Surface

Endpoints:

- `GET /health` returns the lightweight service identity payload.
- `GET /health/live` is the process liveness probe.
- `GET /health/ready` runs database, Windmill, and agent availability checks and returns a structured component map.
- `GET /health/agents` returns agent-by-agent availability details.

Implementation notes:

- Windmill health is reported as enabled/disabled based on config and connection success.
- Agent health degrades when only some configured engines are available.

## Metrics Surface

Endpoints:

- `GET /metrics/summary` returns frontend-oriented JSON aggregates.
- `GET /metrics` returns Prometheus text format.

Important behavior:

- `/metrics/summary` is intentionally resilient. If some DB queries fail, it still returns `200` with `degraded: true` and an `errors` list.
- `/metrics` exists even when `prometheus_client` is missing; the module provides no-op metric stubs so the route shape survives.
- Metrics routes are mounted without the API-token dependency.

## Logs, Events, and Streams

Endpoints:

- `GET /events`
- `GET /events/stream`
- `GET /events/recent`
- `GET /logs/stream`
- `GET /logs/recent`
- `GET /runs/{run_id}/logs`
- `GET /runs/{run_id}/logs/stream`
- `GET /cli-executions/{execution_id}/logs`
- `GET /cli-executions/{execution_id}/logs/stream`
- `GET /ws/events`

Important behavior:

- SSE streams support resume semantics with `Last-Event-ID` and explicit `since_id` or `since_bytes`.
- `/events` emits named SSE events; `/events/stream` emits default `message` events for simpler browser consumers.
- Idle SSE streams send heartbeat frames instead of going silent.
- Event payloads are DB-backed, not transient in-memory only.

## Event Persistence Model

- Services publish in-process events through `EventBus`.
- `install_db_event_sink()` attaches a wildcard handler that persists those events into the DB event store.
- Only events with a `protocol_run_id` or `project_id` are persisted.
- Event types are normalized through `events_catalog`, which is why API consumers see canonical event names and categories even when producer code uses class names.

## Structured Logging

- Backend code is expected to log through `devgodzilla.logging.get_logger()`.
- Route handlers already emit structured extras for protocol, step, project, and run context.
- SpecKit, onboarding, runs, metrics, and webhook routes include explicit log coverage because they are high-variance operational paths.

## Run and Execution Introspection

- `JobRun` rows are the durable record of execution attempts.
- The runs API can sync queued/running job rows against Windmill on read.
- CLI executions use an in-process tracker, expose log replay/streaming, and support best-effort cancellation by PID.
- Step execution and QA endpoints write best-effort artifact files for later inspection by the UI and Windmill wrappers.

## Webhook Handling

Endpoints:

- `/webhooks/windmill/job`
- `/webhooks/windmill/flow`
- `/webhooks/github`
- `/webhooks/gitlab`

Security model:

- a matching `X-DevGodzilla-Webhook-Token`
- or accepted provider signatures/tokens for GitHub and GitLab when a webhook token is configured

Behavioral impact:

- Windmill job updates synchronize persisted job-run state.
- Windmill flow completion can complete the owning protocol.
- GitHub/GitLab CI failures can block a protocol.
- CI success can ask the orchestrator to enqueue the next step when nothing is still running.

Tests explicitly cover Windmill flow completion and CI failure blocking.

## Reconciliation and Recovery

Endpoints:

- `POST /reconciliation/run`
- `GET /reconciliation/status`
- `GET /reconciliation/protocols/{protocol_run_id}`
- `GET /reconciliation/steps/{step_run_id}`

Important behavior:

- reconciliation inspects active step runs and compares DB state with Windmill job state
- safe mismatches may be auto-fixed
- ambiguous mismatches are reported as manual follow-up
- the most recent reconciliation report is cached in-process for `/reconciliation/status`

Startup recovery:

- API lifespan runs `recover_stuck_protocols()` best-effort on boot
- failures in that recovery path are logged but do not prevent process startup unless path-contract validation fails

## Telemetry

- OpenTelemetry is optional.
- Startup reads:
  - `OTEL_EXPORTER_OTLP_ENDPOINT`
  - `OTEL_SAMPLE_RATE`
  - `OTEL_CONSOLE_EXPORT`
  - `DEVGODZILLA_ENV`
- When the OTEL packages are installed and initialization succeeds, FastAPI plus supported HTTP client libraries are instrumented.
- When OTEL packages are absent, telemetry cleanly degrades to disabled mode.

## Operational Contributor Checklist

- If you add a new background or long-running path, expose either DB events, persisted job runs, or both.
- If you add a new webhook or stream, define its auth expectations explicitly in the route and tests.
- If you change state transitions that operations depend on, update reconciliation and metrics assumptions at the same time.
