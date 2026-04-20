# DevGodzilla State Models

> Status: Active
> Scope: Persisted and runtime state values that contributors must preserve across API, service, and DB changes
> Source of truth: `devgodzilla/models/domain.py`, `devgodzilla/services/task_cycle.py`, `devgodzilla/services/quality.py`, `devgodzilla/db/`, state-oriented tests under `tests/`
> Last updated: 2026-04-20

## State Authority

- Persisted state is defined by the domain models and DB behavior, not only by the request enums in `devgodzilla/api/schemas.py`.
- Several response models expose `status: str`, which means new runtime/domain values can surface even when older request enums are narrower.
- When these ever diverge, contributors should update the domain model, service logic, tests, and docs together.

## Project

- `active`
- `archived`
- `deleted`

Notes:

- Archived projects are excluded from the "active projects" count in `/metrics/summary`.
- Project policy and secret state are persisted alongside the project record, but the GitHub token is masked from API responses.

## ProtocolRun

Authoritative values in `models/domain.py`:

- `pending`
- `planning`
- `planned`
- `running`
- `paused`
- `blocked`
- `needs_qa`
- `failed`
- `cancelled`
- `completed`

Observed transition rules:

- create -> `pending`
- start -> `planning` or `running`, depending on the path
- planning success -> `planned`
- resume -> `running`
- pause -> `paused`
- policy or QA hard failure -> `blocked`
- cancel -> `cancelled`
- all terminal steps complete with no failed step -> `completed`
- any failed step when closing out the protocol -> `failed`

## StepRun

Authoritative values in `models/domain.py`:

- `pending`
- `running`
- `needs_qa`
- `completed`
- `failed`
- `skipped`
- `blocked`
- `cancelled`
- `timeout`

Observed transition rules:

- planning materializes new steps in `pending`
- execution start -> `running`
- successful execution commonly -> `needs_qa`
- QA verdict `pass`, `warn`, or `skip` -> `completed`
- QA verdict `fail` or `error` -> `failed`
- execution-policy blocking or open blocking clarifications -> `blocked`

## SpecRun

Authoritative values:

- `specifying`
- `specified`
- `planning`
- `planned`
- `tasks`
- `clarified`
- `checklisted`
- `analyzed`
- `implemented`
- `failed`
- `cleaned`

Notes:

- Tests explicitly lock all 11 values.
- Cleanup is a terminal post-processing state, not a failure state.

## JobRun

Backend job-run values:

- `queued`
- `running`
- `succeeded`
- `failed`
- `cancelled`

Windmill mapping:

- Windmill `completed` -> `succeeded`
- Windmill `failed` -> `failed`
- Windmill `canceled` -> `cancelled`

The runs API can sync queued/running job rows against Windmill on read.

## Clarification

Observed persisted statuses used by routes and tests:

- `open`
- `answered`

Important fields:

- scope may be project-, protocol-, or step-scoped
- `blocking` determines whether planning or execution may stop
- answer payloads are stored as structured JSON, currently with `{"text": ...}`

## QA Verdict

Authoritative values in `QualityService`:

- `pass`
- `warn`
- `fail`
- `skip`
- `error`

State mapping:

- `pass` -> step `completed`
- `warn` -> step `completed`
- `skip` -> step `completed`
- `fail` -> step `failed`, protocol `blocked`
- `error` -> step `failed`, protocol `blocked`

UI-facing summary mapping:

- `pass` and `skip` render as `passed`
- `warn` renders as `warning`
- `fail` and `error` render as `failed`

## Task-Cycle Work Item

Task-cycle status values in `TaskCycleService`:

- `queued`
- `context_ready`
- `in_progress`
- `awaiting_review`
- `needs_rework`
- `ready_for_pr`
- `pr_ready`
- `blocked`

Related sub-state fields:

- `context_status`
- `review_status`
- `qa_status`
- `iteration_count`
- `max_iterations`
- `blocking_clarifications`
- `blocking_policy_findings`

These are derived from step runtime state plus persisted QA/clarification data and are surfaced through `WorkItemOut`.

## Persistence and Artifact Model

- DB rows hold canonical status for projects, protocols, steps, spec runs, job runs, clarifications, QA results, and events.
- `runtime_state` on `StepRun` is used for task-cycle metadata and other execution-scoped state that does not justify a dedicated table yet.
- Filesystem artifacts are important secondary state:
  - protocol runtime artifacts under `.protocols/<protocol>/.devgodzilla/steps/<step_id>/artifacts/`
  - SpecKit artifacts under `.specify/` and `specs/`
  - run logs and report paths persisted onto job/QA rows

## Contributor Notes

- Add new status values only with tests. This repo already has explicit status-property coverage for protocol, step, and spec-run values.
- Prefer documenting the domain model values even when request enums are narrower or older.
