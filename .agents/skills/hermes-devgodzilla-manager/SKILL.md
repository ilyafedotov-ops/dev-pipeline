---
name: hermes-devgodzilla-manager
description: >
  Use when Hermes should stay the manager for user-facing task intake, tracking,
  clarification, approvals, and result validation while delegating code
  execution to DevGodzilla through the repo-local Hermes bridge. Trigger for
  Hermes/Telegram remote-operation flows, manager-vs-executor split, or
  DevGodzilla-backed software delivery from Hermes.
---

# Hermes DevGodzilla Manager

Hermes is the manager layer.
DevGodzilla is the executor layer.

Use this skill when Hermes should:
- clarify user intent and acceptance criteria;
- create a structured work order;
- call only the Hermes bridge surface, not raw DevGodzilla API endpoints;
- monitor project, protocol, and step progress;
- choose the right DevGodzilla delivery flow for the job;
- ask for approval before risky actions;
- summarize QA evidence, artifacts, and PR outcomes for the user.

Do not use this skill to:
- let Hermes edit code directly when DevGodzilla should execute;
- expose DevGodzilla tokens or raw secrets to Telegram;
- bypass QA failures, policy findings, or approval gates;
- give Hermes unrestricted HTTP access to the full DevGodzilla API.

## Placement

This skill is repo-local and lives under:

```text
.agents/skills/hermes-devgodzilla-manager/
```

Keep it in-repo so the behavior is versioned with the bridge/API contract.
Do not make `~/.hermes/...` the canonical source for this integration.

## Runtime Topology

Preferred flow:

```text
Telegram -> Hermes -> Hermes bridge -> DevGodzilla API -> Windmill/engines/QA/git
```

Telegram is only a user channel.
Hermes is responsible for orchestration and decisions.
DevGodzilla remains the system of record for project/protocol/step state and artifacts.

For local Docker-backed DevGodzilla, the API process must be able to access the same filesystem path stored in `project.local_path` / `run.worktree_path`.
If the backend cannot see that path, bridge reads may return stale metadata, null spec content, or misleading policy/artifact results.

## Delivery Modes

Hermes should choose one of two primary delivery modes.

### 1. One-shot feature delivery

Use this when the user asks for a clearly-scoped feature or change that should be planned and executed as one coherent delivery flow.

Preferred DevGodzilla path:

1. ensure project exists
2. onboard project if repo/specify/discovery state is missing
3. create spec
4. generate plan
5. generate tasks
6. create protocol from spec/tasks
7. plan protocol
8. execute next step(s)
9. inspect QA and artifacts
10. open PR if appropriate

Choose this mode when:
- the request is a substantial new feature;
- the user expects an end-to-end delivery run;
- Hermes wants one protocol that represents the whole feature;
- the repo is new to DevGodzilla or needs fresh onboarding/discovery first.

### 2. Brownfield incremental delivery

Use this when the project already exists and Hermes should break feature work into smaller actionable work items for an existing codebase.

Preferred DevGodzilla path:

1. ensure project exists and is onboarded
2. start brownfield run
3. inspect task-cycle work items
4. build context for the selected work item
5. implement one work item
6. review and QA the work item
7. continue item-by-item until the feature is complete

Choose this mode when:
- the project is already onboarded and understood;
- the user asks for iterative work in an existing system;
- Hermes wants tighter control over execution and validation of smaller increments;
- multiple small changes or follow-up fixes are expected rather than a single monolithic run.

## Onboarding Rules

Hermes should treat onboarding as a first-class managed process.

Before delivery work starts, Hermes should check whether:
- the project exists in DevGodzilla;
- `project.local_path` is ready;
- `.specify/` has been initialized;
- discovery outputs are available when needed for a legacy or unfamiliar codebase.

Use onboarding when:
- the project is new to DevGodzilla;
- the repository was never cloned or linked;
- branch/worktree/specify state is missing;
- discovery context is needed before feature work.

Onboarding sequence:

1. create or locate the project
2. call project onboarding
3. poll onboarding/progress state
4. continue only after repo/specify/discovery state is usable

For existing projects, Hermes should avoid re-onboarding unless repo state is missing or stale.

## Bridge Surface

Use the bridge routes exposed by `scripts/hermes_bridge.py`:

- `GET /health`
- `GET /tools/projects`
- `POST /tools/projects`
- `POST /tools/projects/{project_id}/onboard`
- `POST /tools/specs/create`
- `POST /tools/specs/plan`
- `POST /tools/specs/tasks`
- `GET /tools/specs/{spec_run_id}`
- `GET /tools/specs/{spec_run_id}/content`
- `POST /tools/protocols`
- `POST /tools/protocols/{protocol_id}/plan`
- `GET /tools/protocols/{protocol_id}`
- `GET /tools/protocols/{protocol_id}/steps`
- `GET /tools/protocols/{protocol_id}/artifacts`
- `GET /tools/protocols/{protocol_id}/policy`
- `POST /tools/protocols/{protocol_id}/run-next-step`
- `POST /tools/steps/{step_id}/execute-with-qa`
- `GET /tools/steps/{step_id}/quality`
- `GET /tools/steps/{step_id}/artifacts`
- `POST /tools/projects/{project_id}/brownfield-run`
- `GET /tools/projects/{project_id}/task-cycle`
- `GET /tools/work-items/{work_item_id}`
- `POST /tools/work-items/{work_item_id}/build-context`
- `POST /tools/work-items/{work_item_id}/implement`
- `POST /tools/work-items/{work_item_id}/review`
- `POST /tools/work-items/{work_item_id}/qa`
- `POST /tools/protocols/{protocol_id}/feedback`
- `POST /tools/protocols/{protocol_id}/open-pr`

## Brownfield Modes

When using `POST /tools/projects/{project_id}/brownfield-run`, Hermes should choose `output_mode` intentionally:

- `task_cycle`: preferred for incremental managed delivery on existing projects; creates work items and auto-advances the first actionable step
- `tasks_only`: generate artifacts only; do not create protocol or sprint
- `tasks_to_sprint`: generate tasks and sync them into a sprint
- `protocol`: generate a protocol from brownfield analysis without task-cycle auto-advance
- `protocol_to_sprint`: generate protocol and synchronize it into sprint flow

Default recommendation:
- use `task_cycle` for existing-project feature work that Hermes wants to supervise step-by-step
- use `protocol` when Hermes still wants a protocol artifact but not the full task-cycle workflow

## Feedback Rules

Bridge feedback actions:

- `retry`
- `approve`
- `reject`
- `clarify_create`
- `clarify_answer`

Use `clarify_create` to open a clarification.
Use `clarify_answer` only when responding to an existing clarification key.

## Manager Rules

Hermes should:
- treat DevGodzilla as the executor and source of truth for execution state;
- keep its own state small: project id, protocol id, step id, work item id, correlation id, user approvals;
- prefer polling structured state over interpreting raw logs;
- check `GET /health` before assuming the bridge/backend is usable, and treat degraded readiness as a signal to inspect agent/backend availability before starting a run;
- read generated spec metadata and content through bridge spec routes before approving or executing a new work order;
- use protocol policy/artifact routes to verify protocol-level remediation, not step QA alone;
- prefer dedicated policy routes over cached step payload fields when validating current state:
  `GET /tools/protocols/{protocol_id}/policy`
  `GET /tools/steps/{step_id}/quality` plus underlying policy endpoints via protocol/step checks
- treat embedded `policy` data in `GET /tools/protocols/{protocol_id}/steps` as historical/cached execution metadata, not the canonical live policy view;
- report policy findings explicitly to the user when they exist, including:
  code
  message
  scope
  severity
  whether the finding is blocking or advisory
- distinguish clearly between:
  execution succeeded but warnings remain
  execution blocked by policy
  bridge/backend inconsistency where policy findings appear stale or incompatible with observed filesystem artifacts
- validate completion through QA outcomes and artifacts, not just “execution finished”.

Hermes should not:
- bypass onboarding for a repo that DevGodzilla does not yet understand;
- use one-shot protocol mode for every small follow-up change in a mature brownfield project;
- expose full artifact/log content into Telegram unless explicitly requested and safe.

## Remote Operation Rules

For Telegram or other remote channels:

- send compact status updates, not raw logs by default;
- send artifact summaries before content;
- include warning/error summaries when present instead of hiding them behind a generic "completed" status;
- if policy findings exist, surface the top findings verbatim enough for actionability, for example:
  `policy.protocol.missing_file`: `Required protocol file missing: README.md`
  `policy.protocol.no_steps`: `No step files found in protocol directory`
- treat merge/deploy/destructive changes as approval-required;
- keep correlation ids in Hermes state so retries stay idempotent at the manager layer.

## Brownfield Task-Cycle Verification Pitfalls

When validating brownfield/task-cycle runs through the bridge:

- `POST /tools/projects/{project_id}/brownfield-run` may return success immediately while the real work continues in background; use the returned `poll_hint` and then inspect `GET /tools/projects/{project_id}/task-cycle`.
- identify the newly created brownfield run by the newest work item / protocol ids and confirm the associated `protocol_run_id` before acting on a work item.
- do not treat work-item state alone as proof that PR creation is ready; a work item may show `status=ready_for_pr` while `pr_ready=false`. Report that as a backend inconsistency.
- do not treat a successful `POST /tools/protocols/{protocol_id}/open-pr` HTTP response as proof that a PR exists; inspect the returned payload and require `status` to indicate success plus a non-null PR URL/number.
- if the bridge is unreachable but the shared UI-backed API is healthy, report bridge unavailability separately from executor failure; manager-side recovery may require restarting the local bridge against the shared API base URL before continuing.

## One-Shot Protocol Smoke-Test Pitfalls

When using the one-shot SpecKit -> protocol flow to validate end-to-end execution and PR creation on an existing project:

- do not trust freshly generated `spec.md`, `plan.md`, and `tasks.md` blindly; they may be placeholder-quality even when the API returns success. Inspect them before protocol creation.
- if the generated task list is generic (`Implement main feature`, `Write unit tests`, etc.), replace it with concrete file paths, expected behaviors, and exact verification commands before creating the protocol. Otherwise the run is not a meaningful smoke test.
- also tighten `spec.md` and `plan.md` when they contain template placeholders, so the protocol steps inherit useful context instead of generic boilerplate.
- after creating the protocol, inspect the generated `_runtime/step-*.md` prompts to verify that the concrete task details propagated into the step prompts.
- before blaming the feature prompt, check the executor model configuration. In this repo, `devgodzilla/config/agents.yaml` can point `opencode` at an unavailable model; this causes step 1 to fail immediately with `ProviderModelNotFoundError` and empty diffs/artifacts.
- for protocol smoke tests, explicitly verify these outputs before claiming success: step status, step artifacts, step quality, protocol policy findings, PR-open response payload, git diff, and untracked/generated files in the worktree.
- if execution fails before commit/PR, still audit the worktree for commit hygiene risk. Generated `.specify/*`, `specs/<feature>/*`, `_runtime/*`, and `.devgodzilla/steps/*/artifacts/*` files can remain untracked and would be dangerous to include in a naive commit.
- treat protocol policy findings as potentially stale when filesystem evidence disagrees. Example: the policy API may still report missing `README.md` even when `_runtime/README.md` exists; record that as a backend inconsistency instead of assuming the file is absent.
- do not treat PR creation eligibility as equivalent to protocol existence. A blocked protocol cannot open a PR, so a valid smoke test must reach at least running/completed state and then confirm the PR response includes a real URL/number, not just a nominal success message.
