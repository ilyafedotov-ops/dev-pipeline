# Service Selection Guide

This guide helps you choose the right service for common tasks in TasksGodzilla.

## Quick Reference

| Task | Service | Method |
|------|---------|--------|
| Create a protocol run | OrchestratorService | `create_protocol_run()` |
| Start protocol planning | OrchestratorService | `start_protocol_run()` |
| Execute a step | ExecutionService | `execute_step()` |
| Run QA for a step | QualityService | `run_for_step_run()` |
| Check token budget | BudgetService | `check_and_track()` |
| Setup git worktree | GitService | `ensure_worktree()` |
| Push and create PR | GitService | `push_and_open_pr()` |
| Resolve prompt path | PromptService | `resolve()` |
| Build protocol spec | SpecService | `build_from_protocol_files()` |
| Validate spec | SpecService | `validate_and_update_meta()` |
| Onboard new project | OnboardingService | `register_project()` |
| Enqueue a job | QueueService | `enqueue_*()` |
| Record metrics | TelemetryService | `observe_tokens()` |

## Decision Tree

### I need to work with protocols...

#### Creating or managing protocol lifecycle
→ **OrchestratorService**
- Creating new protocol runs
- Starting/pausing/resuming/cancelling protocols
- Checking protocol completion
- Managing protocol state transitions

```python
orchestrator = OrchestratorService(db)
run = orchestrator.create_protocol_run(
    project_id=1,
    protocol_name="feature-123",
    status="pending",
    base_branch="main"
)
job = orchestrator.start_protocol_run(run.id, queue)
```

#### Building or validating protocol specs
→ **SpecService**
- Building specs from protocol files
- Building specs from CodeMachine configs
- Validating specs
- Creating step runs from specs
- Resolving protocol/step paths

```python
spec_service = SpecService(db)
spec = spec_service.build_from_protocol_files(
    protocol_run_id=123,
    protocol_root=Path("/path/to/.protocols/feature-123")
)
errors = spec_service.validate_and_update_meta(
    protocol_run_id=123,
    protocol_root=protocol_root
)
```

### I need to work with steps...

#### Executing steps
→ **ExecutionService**
- Running step execution
- Handling Codex or CodeMachine execution
- Managing execution workflow (repo setup → execution → push → QA)

```python
execution_service = ExecutionService(db)
execution_service.execute_step(step_run_id=456)
```

#### Running QA on steps
→ **QualityService**
- Running QA checks
- Building QA prompts
- Determining verdicts
- Handling inline QA

```python
quality_service = QualityService(db=db)
quality_service.run_for_step_run(step_run_id=456)
```

#### Managing step lifecycle
→ **OrchestratorService**
- Enqueueing steps
- Retrying steps
- Applying trigger/loop policies
- Handling step completion

```python
orchestrator = OrchestratorService(db)
step, job = orchestrator.enqueue_next_step(protocol_run_id=123, queue)
orchestrator.handle_step_completion(step_run_id=456, qa_verdict="PASS")
```

### I need to work with git...

#### Any git operation
→ **GitService**
- Ensuring repositories exist
- Creating/managing worktrees
- Checking remote branches
- Pushing branches
- Creating PRs/MRs
- Triggering CI

```python
git_service = GitService(db)
repo_root = git_service.ensure_repo_or_block(project, run)
worktree = git_service.ensure_worktree(repo_root, "feature-123", "main")
pushed = git_service.push_and_open_pr(worktree, "feature-123", "main")
```

### I need to work with budgets...

#### Any token budget operation
→ **BudgetService**
- Checking token budgets
- Tracking token usage
- Recording actual usage
- Enforcing budget limits

```python
budget_service = BudgetService()
estimated = budget_service.check_and_track(
    prompt_text="...",
    model="gpt-5.1-high",
    phase="exec",
    budget_mode="strict",
    max_tokens=10000
)
budget_service.record_usage(
    protocol_run_id=123,
    step_run_id=456,
    phase="exec",
    model="gpt-5.1-high",
    prompt_tokens=1000,
    completion_tokens=500
)
```

### I need to work with prompts...

#### Any prompt operation
→ **PromptService**
- Resolving prompt paths
- Getting prompt versions
- Resolving QA prompts
- Building QA context

```python
prompt_service = PromptService(workspace_root=workspace_root)
path, text, version = prompt_service.resolve("prompts/my-prompt.md")
qa_path, qa_version = prompt_service.resolve_qa_prompt(
    qa_config, protocol_root, workspace_root
)
context = prompt_service.build_qa_context(
    protocol_root, step_path, workspace_root
)
```

### I need to work with projects...

#### Onboarding new projects
→ **OnboardingService**
- Registering projects
- Setting up workspaces
- Running discovery
- Handling clarifications

```python
onboarding_service = OnboardingService(db)
project = onboarding_service.register_project(
    name="my-project",
    git_url="https://github.com/org/repo",
    base_branch="main"
)
repo_root = onboarding_service.ensure_workspace(
    project_id=project.id,
    clone_if_missing=True,
    run_discovery_pass=True
)
```

### I need to work with jobs...

#### Enqueueing background jobs
→ **QueueService**
- Enqueueing any job type
- Managing job queue

```python
queue_service = QueueService.from_redis_url("redis://localhost:6379/0")
job = queue_service.enqueue_plan_protocol(protocol_run_id=123)
job = queue_service.enqueue_execute_step(step_run_id=456)
```

### I need to work with metrics...

#### Recording metrics
→ **TelemetryService**
- Recording token usage
- Tracking execution metrics

```python
telemetry_service = TelemetryService()
telemetry_service.observe_tokens("exec", "gpt-5.1-high", 5000)
```

### I need to work with CodeMachine...

#### Importing CodeMachine workspaces
→ **CodeMachineService**
- Importing workspaces
- Managing CodeMachine configs

```python
codemachine_service = CodeMachineService(db)
codemachine_service.import_workspace(
    project_id=1,
    protocol_run_id=123,
    workspace_path="/path/to/.codemachine"
)
```

### I need to decompose steps...

#### Decomposing protocol steps
→ **DecompositionService**
- Decomposing step files
- Skipping simple steps

```python
decomposition_service = DecompositionService()
result = decomposition_service.decompose_protocol(
    protocol_root=protocol_root,
    model="gpt-5.1-high",
    skip_simple=True
)
```

## Common Patterns

### Pattern: Full Protocol Execution

```python
# 1. Create protocol
orchestrator = OrchestratorService(db)
run = orchestrator.create_protocol_run(
    project_id=1,
    protocol_name="feature-123",
    status="pending",
    base_branch="main"
)

# 2. Start planning
queue = QueueService.from_redis_url(config.redis_url)
job = orchestrator.start_protocol_run(run.id, queue)

# 3. Worker executes planning (creates spec and steps)
# ... planning happens in background ...

# 4. Enqueue first step
step, job = orchestrator.enqueue_next_step(run.id, queue)

# 5. Worker executes step
execution_service = ExecutionService(db)
execution_service.execute_step(step.id)

# 6. Worker runs QA
quality_service = QualityService(db=db)
quality_service.run_for_step_run(step.id)

# 7. Handle completion and trigger next steps
orchestrator.handle_step_completion(step.id, qa_verdict="PASS")

# 8. Check if protocol is complete
completed = orchestrator.check_and_complete_protocol(run.id)
```

### Pattern: Manual Step Execution (No Queue)

```python
# Setup services
git_service = GitService(db)
budget_service = BudgetService()
execution_service = ExecutionService(db)
quality_service = QualityService(db=db)
orchestrator = OrchestratorService(db)

# Get step
step = db.get_step_run(step_run_id)
run = db.get_protocol_run(step.protocol_run_id)
project = db.get_project(run.project_id)

# Execute
execution_service.execute_step(step.id)

# QA
quality_service.run_for_step_run(step.id)

# Complete
orchestrator.handle_step_completion(step.id, qa_verdict="PASS")
```

### Pattern: Project Onboarding

```python
# 1. Register project
onboarding_service = OnboardingService(db)
project = onboarding_service.register_project(
    name="my-project",
    git_url="https://github.com/org/repo",
    base_branch="main",
    ci_provider="github"
)

# 2. Setup workspace
repo_root = onboarding_service.ensure_workspace(
    project_id=project.id,
    clone_if_missing=True,
    run_discovery_pass=True
)

# 3. Or run full setup job
onboarding_service.run_project_setup_job(project_id=project.id)
```

### Pattern: Budget-Aware Execution

```python
budget_service = BudgetService()
config = load_config()

# Check protocol budget before execution
budget_service.check_protocol_budget(
    protocol_run_id=123,
    estimated_tokens=5000,
    max_protocol_tokens=config.max_tokens_per_protocol,
    budget_mode=config.token_budget_mode
)

# Check step budget
budget_service.check_step_budget(
    step_run_id=456,
    estimated_tokens=5000,
    max_step_tokens=config.max_tokens_per_step,
    budget_mode=config.token_budget_mode
)

# Execute with budget tracking
estimated = budget_service.check_and_track(
    prompt_text=prompt,
    model=model,
    phase="exec",
    budget_mode=config.token_budget_mode,
    max_tokens=config.max_tokens_per_step
)

# Record actual usage after execution
budget_service.record_usage(
    protocol_run_id=123,
    step_run_id=456,
    phase="exec",
    model=model,
    prompt_tokens=1000,
    completion_tokens=500
)
```

### Pattern: Git Workflow

```python
git_service = GitService(db)

# 1. Ensure repo exists
repo_root = git_service.ensure_repo_or_block(
    project, run, job_id="job-123"
)

# 2. Create worktree
worktree = git_service.ensure_worktree(
    repo_root,
    run.protocol_name,
    run.base_branch
)

# 3. ... make changes in worktree ...

# 4. Push and create PR
pushed = git_service.push_and_open_pr(
    worktree,
    run.protocol_name,
    run.base_branch
)

# 5. Trigger CI
if pushed:
    triggered = git_service.trigger_ci(
        worktree,
        run.protocol_name,
        project.ci_provider
    )
```

## Anti-Patterns

### ❌ Don't: Call worker functions directly

```python
# BAD
from tasksgodzilla.workers.codex_worker import handle_execute_step
handle_execute_step(step_run_id, db)
```

```python
# GOOD
execution_service = ExecutionService(db)
execution_service.execute_step(step_run_id)
```

### ❌ Don't: Access database directly from API/CLI

```python
# BAD
run = db.create_protocol_run(...)
db.update_protocol_status(run.id, "planning")
```

```python
# GOOD
orchestrator = OrchestratorService(db)
run = orchestrator.create_protocol_run(...)
job = orchestrator.start_protocol_run(run.id, queue)
```

### ❌ Don't: Duplicate service logic

```python
# BAD
def my_custom_budget_check(prompt, max_tokens):
    estimated = estimate_tokens(prompt)
    if estimated > max_tokens:
        raise BudgetExceededError(...)
```

```python
# GOOD
budget_service = BudgetService()
estimated = budget_service.check_and_track(
    prompt, model, phase, budget_mode, max_tokens
)
```

### ❌ Don't: Mix service responsibilities

```python
# BAD - ExecutionService doing git operations directly
def execute_step(self, step_run_id):
    # ... execution logic ...
    run_process(["git", "push", "origin", branch])  # Don't do this!
```

```python
# GOOD - Use GitService
def execute_step(self, step_run_id):
    # ... execution logic ...
    git_service = GitService(self.db)
    git_service.push_and_open_pr(worktree, protocol_name, base_branch)
```

## Service Selection Checklist

When choosing a service, ask:

1. **What domain does this task belong to?**
   - Protocol/step lifecycle → OrchestratorService
   - Execution → ExecutionService
   - QA → QualityService
   - Git → GitService
   - Budget → BudgetService
   - Prompts → PromptService
   - Specs → SpecService
   - Onboarding → OnboardingService
   - Jobs → QueueService
   - Metrics → TelemetryService

2. **Is this a cross-cutting concern?**
   - Logging → Use `tasksgodzilla.logging`
   - Errors → Use `tasksgodzilla.errors`
   - Config → Use `tasksgodzilla.config`

3. **Does a service already exist for this?**
   - Check service docstrings
   - Check this guide
   - Check `docs/services-dependencies.md`

4. **Should I create a new service?**
   - Only if it's a new domain
   - Only if it has clear boundaries
   - Only if it doesn't fit existing services

## Getting Help

If you're unsure which service to use:

1. Check this guide
2. Check service docstrings in `tasksgodzilla/services/`
3. Check `docs/services-dependencies.md` for dependency relationships
4. Check `docs/services-architecture.md` for overall architecture
5. Look at existing code in `tasksgodzilla/api/` or `tasksgodzilla/workers/` for examples
