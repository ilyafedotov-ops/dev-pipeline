# Spec-Kit Integration Plan for TasksGodzilla

## Executive Summary

This document outlines a detailed integration plan for incorporating [GitHub spec-kit](https://github.com/github/spec-kit) into TasksGodzilla. The integration will replace and enhance several workflow components while preserving the existing orchestration, execution, and quality assurance infrastructure.

**Key Value Proposition:**
- Replace LLM-based protocol planning with spec-kit's structured specification methodology
- Adopt proven templates for feature specs, implementation plans, and task breakdowns
- Leverage spec-kit's constitution-driven quality gates
- Enable multi-agent support (18+ AI coding assistants)
- **Consolidate artifacts into single `.specify/` directory** (remove `.protocols/`)

**Migration Philosophy: Clean Cut, No Fallbacks**

> ⚠️ **IMPORTANT**: This integration follows a **complete replacement** strategy:
> - NO backward compatibility layers
> - NO feature flags for gradual rollout
> - NO legacy code paths after migration
> - NO redundant services
> - **NO new service names** - existing services are rewritten, not replaced
>
> Existing `.protocols/` data must be migrated BEFORE deployment. The old structure
> will be completely removed, not deprecated.

**Refactoring Approach:**

| Service | Action | Notes |
|---------|--------|-------|
| `PlanningService` | **REWRITE** | Calls spec-kit + parses output directly |
| `DecompositionService` | **DELETE** | Merged into `PlanningService` |
| `SpecService` | **DELETE** | Merged into `PlanningService` |
| `ExecutionService` | **REWRITE** | Same name, writes to `_runtime/` |
| `QualityService` | **REWRITE** | Same name, adds constitutional gates |
| `PolicyService` | **REWRITE** | Same name, reads `constitution.md` |
| `OrchestratorService` | **REWRITE** | Same name, adds DAG execution |

**Streamlined architecture - no redundant services:**
```
PlanningService:
  1. Calls spec-kit CLI (specify, plan, tasks)
  2. Parses output files directly (no separate SpecService)
  3. Creates ProtocolRun + StepRuns
  4. Returns ready-to-execute protocol
```

**Critical Decision: Consolidated Directory Structure**

`.protocols/` is **REMOVED**. All artifacts move to `.specify/`:

```
specs/<feature-branch>/
├── spec.md          # Spec-kit: Requirements
├── plan.md                  # Spec-kit: Architecture
├── tasks.md                 # Spec-kit: Task breakdown
└── _runtime/                # TasksGodzilla: Execution artifacts
    ├── context.md
    ├── log.md
    ├── quality-report.md
    └── runs/<run-id>/       # Per-execution outputs
```

---

## 1. Systems Comparison

### 1.1 Current TasksGodzilla Workflow

```
[Task Description]
    → Planning (LLM generates plan.md + step files)
    → Decomposition (LLM refines complex steps)
    → Execution (Codex/OpenCode per step)
    → QA (LLM-based validation)
    → CI Integration
```

**Artifacts (TO BE REMOVED):**
```
.protocols/<protocol-name>/          ← DELETED AFTER MIGRATION
├── plan.md
├── context.md
├── log.md
├── 01-step.md
├── 02-step.md
└── quality-report.md
```

### 1.2 Spec-Kit Workflow

```
[Feature Idea]
    → /speckit.constitution (governance principles)
    → /speckit.specify (structured specification)
    → /speckit.plan (implementation plan)
    → /speckit.tasks (actionable breakdown)
    → /speckit.implement (execution)
```

**Artifacts (Original Spec-Kit):**
```
.specify/
├── memory/
│   └── constitution.md
├── specs/
│   └── <branch-name>/
│       ├── spec.md
│       ├── plan.md
│       └── tasks.md
└── templates/
```

### 1.3 Consolidated Structure (NEW)

**`.protocols/` is DEPRECATED.** All artifacts consolidate into `.specify/` with TasksGodzilla runtime extensions.

```
.specify/                                    # SINGLE SOURCE OF TRUTH
├── memory/
│   └── constitution.md                      # Governance (maps to PolicyPack)
│
├── templates/                               # Shared templates
│   ├── spec-template.md
│   ├── plan-template.md
│   ├── tasks-template.md
│   └── checklist-template.md
│
└── specs/
    └── <feature-branch>/                    # Per-feature directory
        │
        │── spec.md                  # FROM SPEC-KIT: Requirements
        │── plan.md                          # FROM SPEC-KIT: Architecture
        │── tasks.md                         # FROM SPEC-KIT: Task breakdown
        │
        └── _runtime/                        # TASKSGODZILLA EXTENSION
            ├── context.md                   # Execution context
            ├── log.md                       # Runtime execution log
            ├── quality-report.md            # QA verdict summary
            │
            └── runs/                        # Per-execution artifacts
                └── <run-id>/
                    ├── metadata.json        # Run metadata, timing, status
                    ├── step-outputs/        # Per-step execution outputs
                    │   ├── 01-output.md
                    │   ├── 02-output.md
                    │   └── ...
                    └── qa/                  # QA artifacts per run
                        ├── checklist.md
                        └── gate-results.json
```

**Key Design Decisions:**

| Aspect | Decision | Rationale |
|--------|----------|-----------|
| Root directory | `.specify/` only | Single source of truth, cleaner project |
| Runtime prefix | `_runtime/` | Underscore indicates generated/ephemeral |
| Multi-run support | `runs/<run-id>/` | Support retries, history, comparison |
| Spec files location | Top level of feature dir | Matches spec-kit conventions |
| QA separation | Per-run QA artifacts | Each execution has own verdict |

**Path Mapping (Old → New):**

| Old Path | New Path |
|----------|----------|
| `.protocols/<name>/plan.md` | `specs/<branch>/plan.md` |
| `.protocols/<name>/context.md` | `specs/<branch>/_runtime/context.md` |
| `.protocols/<name>/log.md` | `specs/<branch>/_runtime/log.md` |
| `.protocols/<name>/01-step.md` | `specs/<branch>/tasks.md` (consolidated) |
| `.protocols/<name>/quality-report.md` | `specs/<branch>/_runtime/quality-report.md` |
| N/A (new) | `specs/<branch>/spec.md` |

### 1.4 Alignment Matrix

| TasksGodzilla Component | Spec-Kit Equivalent | Integration Strategy |
|------------------------|---------------------|---------------------|
| Protocol Planning Service | `/speckit.specify` + `/speckit.plan` | **REPLACE** |
| Step Decomposition | `/speckit.tasks` | **REPLACE** |
| Prompt Templates | spec-kit templates | **REPLACE** |
| Complexity Heuristics | `/speckit.analyze` | **ENHANCE** |
| Execution Service | `/speckit.implement` patterns | **INTEGRATE** |
| QA Service | `/speckit.checklist` | **ENHANCE** |
| Orchestrator Service | N/A (orchestration layer) | **PRESERVE** |
| Git Service | spec-kit branch naming | **INTEGRATE** |
| Engine Registry | Multi-agent support | **EXTEND** |

---

## 1.5 Onboarding: What Stays, What Changes

**Onboarding is still required.** Spec-kit does not replace project infrastructure setup.

| Onboarding Responsibility | Status | Notes |
|--------------------------|--------|-------|
| Project DB registration | **KEEP** | Spec-kit has no database |
| Repository clone/validate | **KEEP** | Spec-kit assumes repo exists |
| Git identity/remote config | **KEEP** | Infrastructure concern |
| CI provider detection | **KEEP** | Spec-kit doesn't handle CI |
| Codebase discovery | **KEEP** | Spec-kit has no discovery |
| Starter assets (prompts/, CI) | **KEEP** | Different from .specify/ |
| Infrastructure clarifications | **KEEP** | Git, SSH, models, secrets |
| Policy pack assignment | **MERGE** | → Constitution bidirectional |
| Worktree/.protocols setup | **REPLACE** | → Worktree/.specify setup |

**Onboarding changes for consolidated structure:**

```python
# In OnboardingService.run_project_setup_job():

def _finalize_setup(self, project_id, protocol_run_id, repo_path, base_branch):
    """Finalize setup with .specify/ instead of .protocols/"""

    # 1. Create worktree (unchanged)
    worktree_path = git_service.ensure_worktree(...)

    # 2. Initialize spec-kit (NEW - replaces .protocols/ creation)
    self._init_speckit(worktree_path, protocol_run_id)

    # 3. Create feature directory for this setup protocol
    feature_dir = worktree_path / ".specify" / "specs" / protocol_name
    feature_dir.mkdir(parents=True, exist_ok=True)

    # 4. Create runtime directory
    runtime_dir = feature_dir / "_runtime"
    runtime_dir.mkdir(exist_ok=True)

    # 5. Create initial plan.md (in spec-kit location)
    plan_file = feature_dir / "plan.md"
    if not plan_file.exists():
        plan_file.write_text(f"# Protocol: {protocol_name}\n\nSetup protocol.\n")

    # 6. Update DB paths to new structure
    self.db.update_protocol_paths(
        protocol_run_id,
        worktree_path=str(worktree_path),
        protocol_root=str(feature_dir),  # Now points to specs/<branch>
    )

def _init_speckit(self, repo_path: Path, protocol_run_id: int):
    """Initialize spec-kit in project during onboarding."""
    from specify import SpecifyEngine

    engine = SpecifyEngine()
    engine.init(repo_path)  # Library call, not subprocess

    # Generate constitution from policy pack if configured
    if settings.SPECKIT_SYNC_CONSTITUTION:
        self._sync_constitution_from_policy(repo_path, protocol_run_id)

    self.db.append_event(
        protocol_run_id,
        "setup_speckit_initialized",
        "Initialized spec-kit (.specify/ directory created).",
        metadata={"path": str(repo_path / ".specify")},
    )
```

**Path constants update:**

```python
# tasksgodzilla/constants.py (NEW)

# OLD (deprecated)
PROTOCOLS_DIR = ".protocols"

# NEW
SPECIFY_DIR = ".specify"
SPECS_DIR = "specs"
RUNTIME_DIR = "_runtime"
RUNS_DIR = "_runtime/runs"

def get_feature_dir(repo_root: Path, branch_name: str) -> Path:
    """Get feature directory for a branch."""
    return repo_root / SPECIFY_DIR / "specs" / branch_name

def get_runtime_dir(repo_root: Path, branch_name: str) -> Path:
    """Get runtime directory for execution artifacts."""
    return get_feature_dir(repo_root, branch_name) / RUNTIME_DIR

def get_run_dir(repo_root: Path, branch_name: str, run_id: str) -> Path:
    """Get directory for a specific run."""
    return get_runtime_dir(repo_root, branch_name) / "runs" / run_id
```

---

## 2. Integration Approach: Library vs CLI

### 2.1 The "Black Box" Dependency Risk

> ⚠️ **CRITICAL ARCHITECTURAL DECISION**

**Problem with CLI Subprocess Approach:**

Wrapping `specify-cli` via subprocess calls creates several serious issues:

| Issue | Impact | Severity |
|-------|--------|----------|
| **Latency** | Shelling out to CLI for every planning step adds I/O overhead | Medium |
| **Fragility** | If CLI changes markdown output format (e.g., `[DEPENDS]` tags), regex parsers silently break | High |
| **Error Handling** | CLI returns generic exit codes; no way to know if failure is context window, API error, or bad template | High |
| **Debugging** | Stack traces are lost; errors require scraping stderr | Medium |
| **Testing** | Can't mock internal components; must mock entire subprocess | Medium |

**Rejected Approach (DO NOT USE):**

```python
class PlanningService:
    def __init__(self, db):
        self._runner = SpecKitRunner()  # Subprocess wrapper - BAD

    def plan_protocol(self, ...):
        # Shells out to CLI - fragile, slow, opaque errors
        result = self._runner.specify(...)  # subprocess.run() under the hood
        self._parse_markdown_output(result.stdout)  # Regex parsing - breaks easily
```

### 2.2 Recommended Approach: Direct Library Import

**If spec-kit is Python:** Import and call internal classes directly.

**If spec-kit is not Python:** Build a JSON sidecar mode into CLI for structured output.

**Correct Implementation:**

```python
from specify import SpecifyEngine, PlanGenerator, TaskBreakdown
from specify.models import FeatureSpec, ImplementationPlan, TaskList
from specify.errors import ContextWindowError, TemplateError, APIError

class PlanningService:
    """Planning service using spec-kit as library, not subprocess."""

    def __init__(self, db: BaseDatabase):
        self.db = db
        # Direct library instantiation - no subprocess
        self._engine = SpecifyEngine(
            templates_dir=".specify/templates",
            constitution_path=".specify/memory/constitution.md"
        )
        self._planner = PlanGenerator(engine=self._engine)
        self._tasker = TaskBreakdown(engine=self._engine)

    def plan_protocol(
        self,
        project_id: int,
        task_description: str,
        branch_name: str,
    ) -> ProtocolRun:
        """Create protocol using spec-kit library calls."""
        project = self.db.get_project(project_id)
        repo_root = Path(project.local_path)

        try:
            # Step 1: Generate feature spec (typed return, not stdout)
            feature_spec: FeatureSpec = self._engine.specify(
                description=task_description,
                branch=branch_name,
                project_root=repo_root
            )

            # Step 2: Generate implementation plan (typed return)
            plan: ImplementationPlan = self._planner.generate(
                spec=feature_spec,
                project_root=repo_root
            )

            # Step 3: Break down into tasks (typed return with dependencies)
            tasks: TaskList = self._tasker.breakdown(
                plan=plan,
                project_root=repo_root
            )

            # Step 4: Convert to StepRuns (no regex parsing needed)
            steps = self._convert_tasks_to_steps(tasks)
            return self._create_protocol_run(project_id, branch_name, steps)

        except ContextWindowError as e:
            raise PlanningError(f"Context too large: {e.token_count} tokens") from e
        except TemplateError as e:
            raise PlanningError(f"Template error: {e.template_path}") from e
        except APIError as e:
            raise PlanningError(f"LLM API error: {e.status_code}") from e

    def _convert_tasks_to_steps(self, tasks: TaskList) -> list[StepSpec]:
        """Convert typed TaskList to StepSpecs - no regex needed."""
        steps = []
        for task in tasks.items:
            steps.append(StepSpec(
                id=task.id,
                name=task.description,
                depends_on=task.depends_on,  # Already parsed, typed list
                parallel_group=task.parallel_group,  # Already parsed
                estimated_complexity=task.complexity,
            ))
        return steps
```

**Benefits of Library Approach:**

| Benefit | Description |
|---------|-------------|
| **Type Safety** | `FeatureSpec`, `TaskList` are typed objects, not strings |
| **Error Granularity** | Catch `ContextWindowError` vs `TemplateError` vs `APIError` |
| **Performance** | In-process calls, no subprocess overhead |
| **Testability** | Mock `SpecifyEngine` directly in unit tests |
| **Debugging** | Full stack traces, proper exception chaining |
| **Stability** | No regex parsing of markdown output |

### 2.3 JSON Sidecar Mode (Fallback if not Python)

If spec-kit is not importable as a Python library, require JSON output mode:

```bash
# Instead of parsing markdown stdout:
specify plan --output-format json --spec-path specs/auth/spec.md

# Returns structured JSON:
{
  "plan": {
    "title": "Authentication Implementation",
    "phases": [...],
    "estimated_tokens": 15000
  },
  "tasks": [
    {
      "id": "task-001",
      "description": "Create user model",
      "depends_on": [],
      "parallel_group": null,
      "complexity": "low"
    },
    {
      "id": "task-002",
      "description": "Implement login endpoint",
      "depends_on": ["task-001"],
      "parallel_group": "auth-endpoints",
      "complexity": "medium"
    }
  ],
  "errors": [],
  "warnings": []
}
```

```python
class PlanningService:
    """Fallback: JSON sidecar mode if library import not possible."""

    def _call_specify_json(self, command: str, **kwargs) -> dict:
        """Call specify CLI with JSON output mode."""
        cmd = ["specify", command, "--output-format", "json"]
        for k, v in kwargs.items():
            cmd.extend([f"--{k.replace('_', '-')}", str(v)])

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            error_data = json.loads(result.stderr)
            raise self._map_error(error_data)

        return json.loads(result.stdout)

    def _map_error(self, error_data: dict) -> PlanningError:
        """Map JSON error response to typed exception."""
        error_type = error_data.get("error_type")
        if error_type == "context_window_exceeded":
            return ContextWindowError(error_data["token_count"])
        elif error_type == "template_error":
            return TemplateError(error_data["template_path"])
        elif error_type == "api_error":
            return APIError(error_data["status_code"], error_data["message"])
        return PlanningError(error_data.get("message", "Unknown error"))
```

### 2.4 Integration Priority

1. **Best:** Direct Python library import (no subprocess)
2. **Acceptable:** JSON sidecar mode (structured output, typed errors)
3. **Rejected:** Markdown stdout parsing via subprocess (fragile, opaque)

### 2.5 The "Waterfall" Trap: Feedback Loops Required

> ⚠️ **CRITICAL ARCHITECTURAL DECISION**

**Problem: Linear Workflow is Too Rigid**

The naive integration enforces a strict waterfall: `Specify → Plan → Tasks → Implement`

| Issue | Impact | Severity |
|-------|--------|----------|
| **No Feedback Loop** | Implementation failures can't trigger re-planning | Critical |
| **Upstream Blind Spot** | ExecutionService can't signal "plan is impossible" | Critical |
| **DAG Deadlocks** | Circular dependencies or hallucinated tasks crash orchestrator | High |
| **Human-Centric Assumption** | Spec-kit assumes human drives CLI, not automated system | High |

**Failure Scenarios Without Feedback:**

```
Scenario 1: Impossible Plan
  1. PlanningService generates tasks.md with "Create OAuth2 provider"
  2. ExecutionService attempts implementation
  3. Agent discovers: "No OAuth2 library exists for this framework"
  4. WITHOUT FEEDBACK: Step fails, protocol fails, no recovery
  5. WITH FEEDBACK: Raise SpecificationError → Re-plan with context

Scenario 2: Circular Dependency
  1. TaskBreakdown generates: Task A depends on B, B depends on C, C depends on A
  2. OrchestratorService builds DAG
  3. WITHOUT FEEDBACK: Deadlock - no task can start
  4. WITH FEEDBACK: Detect cycle → Raise SpecificationError → Re-generate tasks

Scenario 3: Hallucinated Task
  1. TaskBreakdown generates: "Update the FrobnicatorService"
  2. ExecutionService attempts implementation
  3. Agent discovers: "FrobnicatorService doesn't exist in codebase"
  4. WITHOUT FEEDBACK: Step fails with confusing error
  5. WITH FEEDBACK: Raise SpecificationError("Entity not found") → Clarify spec
```

**Solution: Feedback Loop Architecture**

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         Feedback Loop Architecture                       │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│    ┌──────────────┐                                                      │
│    │   Specify    │◄─────────────────────────────────────────┐          │
│    └──────┬───────┘                                          │          │
│           │                                                   │          │
│           ▼                                                   │          │
│    ┌──────────────┐     SpecificationError                   │          │
│    │     Plan     │◄──────────────────────────┐              │          │
│    └──────┬───────┘                           │              │          │
│           │                                    │              │          │
│           ▼                                    │              │          │
│    ┌──────────────┐     TaskGraphError        │              │          │
│    │    Tasks     │◄───────────────┐          │              │          │
│    └──────┬───────┘                │          │              │          │
│           │                         │          │              │          │
│           ▼                         │          │              │          │
│    ┌──────────────┐                │          │              │          │
│    │ Orchestrator │────────────────┘          │              │          │
│    │ (DAG Build)  │  Cycle/Invalid detected   │              │          │
│    └──────┬───────┘                           │              │          │
│           │                                    │              │          │
│           ▼                                    │              │          │
│    ┌──────────────┐                           │              │          │
│    │   Execute    │───────────────────────────┴──────────────┘          │
│    └──────┬───────┘  SpecificationError raised                          │
│           │                                                              │
│           ▼                                                              │
│    ┌──────────────┐                                                      │
│    │      QA      │                                                      │
│    └──────────────┘                                                      │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

**Error Types for Feedback:**

```python
# tasksgodzilla/errors.py

class SpecificationError(Exception):
    """Raised when execution reveals specification is invalid/impossible.

    Triggers re-planning via PlanningService.clarify() or re-specify.
    """
    def __init__(
        self,
        message: str,
        error_type: str,  # "impossible", "missing_entity", "ambiguous", "conflict"
        context: dict,    # Details for re-planning
        step_id: str | None = None,
        suggested_action: str = "clarify",  # "clarify", "re_plan", "re_specify"
    ):
        super().__init__(message)
        self.error_type = error_type
        self.context = context
        self.step_id = step_id
        self.suggested_action = suggested_action


class TaskGraphError(Exception):
    """Raised when task DAG is invalid (cycles, missing deps, etc.)."""
    def __init__(
        self,
        message: str,
        error_type: str,  # "cycle", "missing_dependency", "orphan_task"
        affected_tasks: list[str],
        graph_snapshot: dict,  # For debugging
    ):
        super().__init__(message)
        self.error_type = error_type
        self.affected_tasks = affected_tasks
        self.graph_snapshot = graph_snapshot
```

**ExecutionService with Feedback:**

```python
from specify import SpecifyEngine
from specify.errors import ExecutionBlockedError
from tasksgodzilla.errors import SpecificationError

class ExecutionService:
    """ExecutionService with feedback loop support."""

    def execute_step(self, step_run_id: int) -> StepResult:
        step = self.db.get_step_run(step_run_id)

        try:
            result = self._run_engine(step)
            return result

        except ExecutionBlockedError as e:
            # Engine reports it cannot proceed - specification issue
            raise SpecificationError(
                message=f"Step blocked: {e.reason}",
                error_type=self._classify_block_reason(e),
                context={
                    "step_id": step.id,
                    "step_name": step.name,
                    "block_reason": e.reason,
                    "attempted_actions": e.attempted_actions,
                    "missing_prerequisites": e.missing_prerequisites,
                },
                step_id=step.id,
                suggested_action="re_plan" if e.is_structural else "clarify",
            )

    def _classify_block_reason(self, error: ExecutionBlockedError) -> str:
        """Classify block reason for appropriate feedback action."""
        if "not found" in error.reason.lower():
            return "missing_entity"
        if "conflict" in error.reason.lower():
            return "conflict"
        if "ambiguous" in error.reason.lower():
            return "ambiguous"
        return "impossible"
```

**OrchestratorService with Cycle Detection:**

```python
from tasksgodzilla.errors import TaskGraphError

class OrchestratorService:
    """OrchestratorService with DAG validation and feedback."""

    def build_execution_dag(self, protocol_run_id: int) -> ExecutionDAG:
        steps = self.db.get_steps_for_protocol(protocol_run_id)

        # Build adjacency list
        graph = self._build_adjacency_list(steps)

        # Detect cycles BEFORE execution starts
        cycle = self._detect_cycle(graph)
        if cycle:
            raise TaskGraphError(
                message=f"Circular dependency detected: {' → '.join(cycle)}",
                error_type="cycle",
                affected_tasks=cycle,
                graph_snapshot=graph,
            )

        # Validate all dependencies exist
        missing = self._find_missing_dependencies(steps)
        if missing:
            raise TaskGraphError(
                message=f"Missing dependencies: {missing}",
                error_type="missing_dependency",
                affected_tasks=list(missing.keys()),
                graph_snapshot=graph,
            )

        return ExecutionDAG(steps=steps, graph=graph)

    def _detect_cycle(self, graph: dict) -> list[str] | None:
        """Tarjan's algorithm for cycle detection."""
        visited = set()
        rec_stack = set()
        path = []

        def dfs(node):
            visited.add(node)
            rec_stack.add(node)
            path.append(node)

            for neighbor in graph.get(node, []):
                if neighbor not in visited:
                    cycle = dfs(neighbor)
                    if cycle:
                        return cycle
                elif neighbor in rec_stack:
                    # Found cycle - return the cycle path
                    cycle_start = path.index(neighbor)
                    return path[cycle_start:] + [neighbor]

            path.pop()
            rec_stack.remove(node)
            return None

        for node in graph:
            if node not in visited:
                cycle = dfs(node)
                if cycle:
                    return cycle
        return None
```

**PlanningService with Feedback Handlers:**

```python
from specify import SpecifyEngine, Clarifier
from tasksgodzilla.errors import SpecificationError, TaskGraphError

class PlanningService:
    """PlanningService with feedback loop handlers."""

    def __init__(self, db: BaseDatabase):
        self.db = db
        self._engine = SpecifyEngine()
        self._clarifier = Clarifier(engine=self._engine)
        # ... other components

    def handle_specification_error(
        self,
        protocol_run_id: int,
        error: SpecificationError,
    ) -> ProtocolRun:
        """Handle feedback from ExecutionService."""
        protocol = self.db.get_protocol_run(protocol_run_id)

        if error.suggested_action == "clarify":
            return self._clarify_and_update(protocol, error)
        elif error.suggested_action == "re_plan":
            return self._replan_from_step(protocol, error)
        elif error.suggested_action == "re_specify":
            return self._respecify(protocol, error)
        else:
            raise ValueError(f"Unknown action: {error.suggested_action}")

    def _clarify_and_update(
        self,
        protocol: ProtocolRun,
        error: SpecificationError,
    ) -> ProtocolRun:
        """Use /speckit.clarify to refine spec based on error."""
        repo_root = Path(protocol.project.local_path)
        feature_dir = repo_root / ".specify" / "specs" / protocol.branch_name

        # Call clarify with error context
        clarification = self._clarifier.clarify(
            spec_path=feature_dir / "spec.md",
            issue=error.message,
            context=error.context,
        )

        # Re-generate affected tasks only
        if error.step_id:
            return self._regenerate_step(protocol, error.step_id, clarification)
        else:
            return self._regenerate_all_tasks(protocol, clarification)

    def _replan_from_step(
        self,
        protocol: ProtocolRun,
        error: SpecificationError,
    ) -> ProtocolRun:
        """Re-plan from the failed step onwards."""
        # Mark failed step and all dependents as "needs_replan"
        self._mark_for_replan(protocol.id, error.step_id)

        # Re-run task breakdown with error context
        repo_root = Path(protocol.project.local_path)
        tasks = self._tasker.breakdown(
            plan=self._load_plan(protocol),
            project_root=repo_root,
            error_context=error.context,  # Inform breakdown of what failed
            exclude_patterns=error.context.get("failed_approaches", []),
        )

        # Update only affected steps
        return self._update_protocol_steps(protocol, tasks, from_step=error.step_id)

    def handle_task_graph_error(
        self,
        protocol_run_id: int,
        error: TaskGraphError,
    ) -> ProtocolRun:
        """Handle DAG errors from OrchestratorService."""
        protocol = self.db.get_protocol_run(protocol_run_id)

        if error.error_type == "cycle":
            # Re-generate tasks with cycle-breaking hints
            return self._regenerate_tasks_breaking_cycle(protocol, error)
        elif error.error_type == "missing_dependency":
            # Add missing tasks or fix references
            return self._fix_missing_dependencies(protocol, error)
        else:
            raise ValueError(f"Unknown graph error: {error.error_type}")

    def _regenerate_tasks_breaking_cycle(
        self,
        protocol: ProtocolRun,
        error: TaskGraphError,
    ) -> ProtocolRun:
        """Re-generate tasks with instruction to avoid cycles."""
        repo_root = Path(protocol.project.local_path)

        tasks = self._tasker.breakdown(
            plan=self._load_plan(protocol),
            project_root=repo_root,
            constraints={
                "break_cycle": error.affected_tasks,
                "avoid_patterns": [
                    f"{a} -> {b}"
                    for a, b in zip(error.affected_tasks, error.affected_tasks[1:])
                ],
            },
        )

        return self._replace_protocol_steps(protocol, tasks)
```

**API Endpoints for Feedback:**

```python
# tasksgodzilla/api/feedback.py

@router.post("/protocols/{protocol_id}/feedback/specification-error")
async def handle_specification_error(
    protocol_id: int,
    body: SpecificationErrorRequest,
    planning: PlanningService = Depends(get_planning_service),
) -> ProtocolRunOut:
    """Handle specification error feedback from execution."""
    error = SpecificationError(
        message=body.message,
        error_type=body.error_type,
        context=body.context,
        step_id=body.step_id,
        suggested_action=body.suggested_action,
    )
    updated = planning.handle_specification_error(protocol_id, error)
    return ProtocolRunOut.from_orm(updated)


@router.post("/protocols/{protocol_id}/feedback/task-graph-error")
async def handle_task_graph_error(
    protocol_id: int,
    body: TaskGraphErrorRequest,
    planning: PlanningService = Depends(get_planning_service),
) -> ProtocolRunOut:
    """Handle task graph error feedback from orchestrator."""
    error = TaskGraphError(
        message=body.message,
        error_type=body.error_type,
        affected_tasks=body.affected_tasks,
        graph_snapshot=body.graph_snapshot,
    )
    updated = planning.handle_task_graph_error(protocol_id, error)
    return ProtocolRunOut.from_orm(updated)
```

**Feedback Loop Limits (Prevent Infinite Loops):**

```python
# tasksgodzilla/config.py

class FeedbackConfig:
    MAX_CLARIFY_ATTEMPTS: int = 3      # Max /speckit.clarify calls per step
    MAX_REPLAN_ATTEMPTS: int = 2       # Max re-planning attempts per protocol
    MAX_RESPECIFY_ATTEMPTS: int = 1    # Max full re-specification attempts
    FEEDBACK_COOLDOWN_SECONDS: int = 60  # Min time between feedback cycles
```

```python
# In PlanningService

def handle_specification_error(self, protocol_run_id: int, error: SpecificationError):
    protocol = self.db.get_protocol_run(protocol_run_id)

    # Check feedback limits
    feedback_count = self.db.count_feedback_events(
        protocol_run_id,
        error_type=error.error_type,
    )

    if error.suggested_action == "clarify" and feedback_count >= self.config.MAX_CLARIFY_ATTEMPTS:
        # Escalate to re-plan
        error.suggested_action = "re_plan"

    if error.suggested_action == "re_plan" and feedback_count >= self.config.MAX_REPLAN_ATTEMPTS:
        # Escalate to human intervention
        self._request_human_intervention(protocol, error)
        raise FeedbackLimitExceeded(
            f"Max re-plan attempts ({self.config.MAX_REPLAN_ATTEMPTS}) exceeded"
        )

    # ... proceed with feedback handling
```

**Event Logging for Feedback:**

```python
# Log all feedback events for debugging and improvement

def handle_specification_error(self, protocol_run_id: int, error: SpecificationError):
    # Log the feedback event
    self.db.append_event(
        protocol_run_id,
        event_type="feedback_specification_error",
        message=f"Specification error: {error.error_type}",
        metadata={
            "error_message": error.message,
            "error_type": error.error_type,
            "context": error.context,
            "step_id": error.step_id,
            "suggested_action": error.suggested_action,
            "attempt_number": self._get_attempt_number(protocol_run_id, error),
        },
    )

    # ... handle error
```

---

## 3. Integration Architecture

### 3.1 High-Level Architecture

> ⚠️ **Direct Library Integration** - No subprocess/CLI calls. See [Section 2](#2-integration-approach-library-vs-cli).

```
┌─────────────────────────────────────────────────────────────────────┐
│                        TasksGodzilla + Spec-Kit                      │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │              Spec-Kit Python Library (Direct Import)          │   │
│  │  ┌────────────────┐  ┌──────────────┐  ┌────────────────┐    │   │
│  │  │ SpecifyEngine  │  │ PlanGenerator│  │ TaskBreakdown  │    │   │
│  │  └────────────────┘  └──────────────┘  └────────────────┘    │   │
│  │  ┌────────────────────────────────────────────────────────┐  │   │
│  │  │ Typed Models: FeatureSpec, ImplementationPlan, TaskList│  │   │
│  │  └────────────────────────────────────────────────────────┘  │   │
│  │  ┌────────────────────────────────────────────────────────┐  │   │
│  │  │ Typed Errors: ContextWindowError, TemplateError, etc.  │  │   │
│  │  └────────────────────────────────────────────────────────┘  │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                       │                                              │
│                       │ In-process calls (no subprocess)            │
│                       ▼                                              │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │              Refactored Services                              │   │
│  │  PlanningService    - imports spec-kit library directly      │   │
│  │  ExecutionService   - writes to _runtime/                    │   │
│  │  QualityService     - adds constitutional gates              │   │
│  │  OrchestratorService - DAG-based step execution              │   │
│  │                                                               │   │
│  │  DELETED: SpecService, DecompositionService                  │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                       │                                              │
│                       ▼                                              │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │              Extended Engine Registry                         │   │
│  │  ┌────────┐ ┌──────────┐ ┌────────────┐ ┌──────────────────┐│   │
│  │  │ Codex  │ │ OpenCode │ │ Claude Code│ │ GitHub Copilot   ││   │
│  │  └────────┘ └──────────┘ └────────────┘ └──────────────────┘│   │
│  │  ┌────────┐ ┌──────────┐ ┌────────────┐ ┌──────────────────┐│   │
│  │  │ Cursor │ │ Gemini   │ │ Windsurf   │ │     ... etc      ││   │
│  │  └────────┘ └──────────┘ └────────────┘ └──────────────────┘│   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### 3.2 Data Flow (with Feedback Loops)

> See [Section 2.5](#25-the-waterfall-trap-feedback-loops-required) for feedback loop details.

```
                    ┌──────────────────────────────────┐
                    │        User/API Request          │
                    │   "Add user authentication"      │
                    └──────────────────┬───────────────┘
                                       │
          ┌────────────────────────────┼────────────────────────────┐
          │                            │                            │
          │  SpecificationError        │                            │
          │  (re_specify)              ▼                            │
          │           ┌──────────────────────────────────┐          │
          │           │    PlanningService.plan_protocol()│◄─────┐  │
          │           │  (uses spec-kit library directly)│      │  │
          │           │                                  │      │  │
          │           │  + handle_specification_error()  │      │  │
          │           │  + handle_task_graph_error()     │      │  │
          └──────────►└──────────────────┬───────────────┘      │  │
                                         │                       │  │
                      ┌──────────────────▼───────────────┐       │  │
                      │    OrchestratorService           │       │  │
                      │  - DAG-based step scheduling     │       │  │
                      │  - Cycle detection (TaskGraphError)      │  │
                      │  - Parallel group handling       │       │  │
                      └──────────────────┬───────────────┘       │  │
                                         │                       │  │
                         TaskGraphError  │                       │  │
                         (cycle/missing) │                       │  │
                              ┌──────────┘                       │  │
                              │                                  │  │
                              ▼                                  │  │
                      ┌──────────────────────────────────┐       │  │
                      │     ExecutionService             │       │  │
                      │  - Use engine registry           │       │  │
                      │  - Detect blocked execution      │       │  │
                      │  - Raise SpecificationError      │───────┘  │
                      └──────────────────┬───────────────┘          │
                                         │                          │
                         SpecificationError                         │
                         (clarify/re_plan)                          │
                              ┌──────────┘                          │
                              │                                     │
                              ▼                                     │
                      ┌──────────────────────────────────┐          │
                      │      QualityService              │          │
                      │  - Constitutional gates          │          │
                      │  - May trigger re-specify        │──────────┘
                      └──────────────────────────────────┘
```

**Feedback Actions:**

| Error Type | Source | Action | Target |
|------------|--------|--------|--------|
| `SpecificationError(clarify)` | ExecutionService | `_clarify_and_update()` | Update affected tasks |
| `SpecificationError(re_plan)` | ExecutionService | `_replan_from_step()` | Re-generate tasks from failure |
| `SpecificationError(re_specify)` | QualityService | `_respecify()` | Full re-specification |
| `TaskGraphError(cycle)` | OrchestratorService | `_regenerate_tasks_breaking_cycle()` | Re-generate with constraints |
| `TaskGraphError(missing_dependency)` | OrchestratorService | `_fix_missing_dependencies()` | Add/fix task references |

---

## 4. Component Refactoring Details

### 4.1 Rewrite: Planning Service

**Current Implementation:** `tasksgodzilla/services/planning.py`

```python
class PlanningService:
    def plan_protocol(self, project_id, task_description, ...):
        # Calls Codex LLM with planning prompt
        # Generates plan.md + step files
```

**Rewritten Implementation:** `tasksgodzilla/services/planning.py` (same file, new code)

> ⚠️ **IMPORTANT:** Uses direct library import, NOT subprocess. See [Section 2](#2-integration-approach-library-vs-cli).

```python
from specify import SpecifyEngine, PlanGenerator, TaskBreakdown
from specify.models import FeatureSpec, ImplementationPlan, TaskList
from specify.errors import ContextWindowError, TemplateError, APIError

class PlanningService:
    """Planning service - uses spec-kit as library (NOT subprocess).

    Same class name, same method signatures, new implementation.
    Absorbs SpecService and DecompositionService functionality.
    """

    def __init__(self, db: BaseDatabase):
        self.db = db
        # Direct library instantiation - NO subprocess
        self._engine = SpecifyEngine(
            templates_dir=".specify/templates",
            constitution_path=".specify/memory/constitution.md"
        )
        self._planner = PlanGenerator(engine=self._engine)
        self._tasker = TaskBreakdown(engine=self._engine)

    def plan_protocol(
        self,
        project_id: int,
        task_description: str,
        branch_name: str,
        **kwargs
    ) -> ProtocolRun:
        """Create protocol from task description.

        Same signature as before, but now uses spec-kit library internally.
        """
        project = self.db.get_project(project_id)
        repo_root = Path(project.local_path)

        try:
            # Step 1: Generate feature spec (typed return, not stdout)
            feature_spec: FeatureSpec = self._engine.specify(
                description=task_description,
                branch=branch_name,
                project_root=repo_root
            )

            # Step 2: Generate implementation plan (typed return)
            plan: ImplementationPlan = self._planner.generate(
                spec=feature_spec,
                project_root=repo_root
            )

            # Step 3: Break down into tasks (typed return with dependencies)
            # This replaces DecompositionService
            tasks: TaskList = self._tasker.breakdown(
                plan=plan,
                project_root=repo_root
            )

            # Step 4: Convert to StepRuns (no regex parsing - typed objects)
            steps = self._convert_tasks_to_steps(tasks)

            # Step 5: Create ProtocolRun with .specify/ paths
            feature_dir = repo_root / ".specify" / "specs" / branch_name
            return self._create_protocol_run(
                project_id=project_id,
                branch_name=branch_name,
                protocol_root=str(feature_dir),
                steps=steps,
            )

        except ContextWindowError as e:
            raise PlanningError(f"Context too large: {e.token_count} tokens") from e
        except TemplateError as e:
            raise PlanningError(f"Template error: {e.template_path}") from e
        except APIError as e:
            raise PlanningError(f"LLM API error: {e.status_code}") from e

    def _convert_tasks_to_steps(self, tasks: TaskList) -> list[StepSpec]:
        """Convert typed TaskList to StepSpecs - no regex needed."""
        steps = []
        for task in tasks.items:
            steps.append(StepSpec(
                id=task.id,
                name=task.description,
                depends_on=task.depends_on,      # Already parsed, typed list
                parallel_group=task.parallel_group,  # Already parsed
                estimated_complexity=task.complexity,
            ))
        return steps

    def _create_protocol_run(
        self,
        project_id: int,
        branch_name: str,
        protocol_root: str,
        steps: list[StepSpec]
    ) -> ProtocolRun:
        """Create protocol run and step runs from typed spec-kit output."""
        protocol_run = self.db.create_protocol_run(
            project_id=project_id,
            branch_name=branch_name,
            protocol_root=protocol_root,
            status="planned",
        )

        for i, step in enumerate(steps):
            self.db.create_step_run(
                protocol_run_id=protocol_run.id,
                order=i + 1,
                name=step.name,
                depends_on=step.depends_on,
                parallel_group=step.parallel_group,
                status="pending",
            )

        return protocol_run
```

**Migration Path:**
1. Install spec-kit as dependency
2. **REWRITE** `tasksgodzilla/services/planning.py` (same file name)
3. **DELETE** `tasksgodzilla/services/decomposition.py` (merged into PlanningService)
4. **DELETE** `tasksgodzilla/pipeline.py` LLM prompts (spec-kit has templates)
5. No API changes needed - same method signatures

### 4.2 Merge: Decomposition Service → Planning Service

**Current Implementation:** `tasksgodzilla/services/decomposition.py`

```python
def decompose_step(self, step_content: str) -> str:
    # LLM-based step refinement
    # Uses complexity heuristics
```

**After Migration:** File deleted, functionality merged into `PlanningService`

The `/speckit.tasks` command (called within `PlanningService.plan_protocol()`) handles decomposition:
- Parallel task detection
- Dependency inference
- Granular subtask generation

**Key Mapping:**

| Spec-Kit Tasks Output | TasksGodzilla StepSpec |
|----------------------|------------------------|
| `- [ ] Task description` | `step.name` |
| `[PARALLEL]` marker | `step.parallel_group` |
| `[DEPENDS: task-id]` | `step.depends_on` |
| Priority markers | `step.order` |

**Callers to update:**
```python
# Before:
planning_service.plan_protocol(...)
decomposition_service.decompose_step(...)  # Separate call

# After:
planning_service.plan_protocol(...)  # Decomposition included
# No separate call needed
```

### 4.3 Replace: Prompt Templates

**Current Location:** `tasksgodzilla/pipeline.py` (hardcoded prompts)

**New Location:** `.specify/templates/`

| Current Prompt | Spec-Kit Template |
|---------------|-------------------|
| `PLANNING_PROMPT` | `templates/spec-template.md` |
| `DECOMPOSITION_PROMPT` | `templates/tasks-template.md` |
| `EXECUTION_PROMPT` | `templates/plan-template.md` |
| `QA_PROMPT` | `templates/checklist-template.md` |

**Migration:**
1. Copy spec-kit templates to project `.specify/templates/`
2. Customize for TasksGodzilla conventions
3. Update `PlanningService` to read templates from `.specify/templates/`
4. **DELETE** `tasksgodzilla/pipeline.py` (no longer needed)

### 4.4 Rewrite: Quality Service

**Current Implementation:** `tasksgodzilla/services/quality.py` - Pattern matching on outputs

**Rewritten Implementation:** `tasksgodzilla/services/quality.py` (same file, enhanced)

> ⚠️ **IMPORTANT:** Uses library import, NOT subprocess. See [Section 2](#2-integration-approach-library-vs-cli).

```python
from specify import ChecklistValidator
from specify.models import ChecklistResult
from specify.errors import ValidationError

class QualityService:
    """Quality service - rewritten with constitutional gates.

    Same class name, enhanced with spec-kit checklist and gates.
    Uses library import, not subprocess.
    """

    def __init__(self, db: BaseDatabase):
        self.db = db
        self._validator = ChecklistValidator()  # Library, not subprocess

    def run_qa(self, step_run_id: int) -> QAVerdict:
        """Run QA on step - same method signature, enhanced implementation."""
        step = self.db.get_step_run(step_run_id)
        feature_dir = Path(step.protocol_run.protocol_root)

        try:
            # Run spec-kit checklist (library call, returns typed result)
            checklist_result: ChecklistResult = self._validator.validate(
                feature_dir=feature_dir
            )

            # Apply constitutional gates
            gates = self._check_constitutional_gates(step, feature_dir)

            # Engine-based QA (existing logic, kept)
            engine_verdict = self._run_engine_qa(step)

            return self._combine_verdicts(engine_verdict, checklist_result, gates)

        except ValidationError as e:
            return QAVerdict(status="error", message=str(e))

    def _check_constitutional_gates(self, step: StepRun, feature_dir: Path) -> list[GateResult]:
        """Check Article compliance from constitution.md"""
        constitution_path = feature_dir.parent.parent.parent / "memory" / "constitution.md"
        if not constitution_path.exists():
            return []

        return [
            self._check_simplicity_gate(step),       # Article VII
            self._check_anti_abstraction_gate(step), # Article VIII
            self._check_test_first_gate(step),       # Article III
        ]
```

### 4.5 Extend: Engine Registry

**Current Engines:** Codex, OpenCode

**Extended Engines:** All 18+ spec-kit supported agents

```python
# tasksgodzilla/engines_registry_extended.py

SPECKIT_AGENT_MAPPING = {
    "claude-code": {
        "command_dir": ".claude/commands/",
        "format": "markdown",
        "cli_command": "claude",
    },
    "github-copilot": {
        "command_dir": ".github/agents/",
        "format": "markdown",
        "cli_command": None,  # IDE-based
    },
    "cursor": {
        "command_dir": ".cursor/commands/",
        "format": "markdown",
        "cli_command": "cursor",
    },
    "gemini-cli": {
        "command_dir": ".gemini/commands/",
        "format": "toml",
        "cli_command": "gemini",
    },
    # ... etc for all 18 agents
}

class SpecKitAgentEngine:
    def __init__(self, agent_name: str):
        self.config = SPECKIT_AGENT_MAPPING[agent_name]
        self.metadata = EngineMetadata(
            id=agent_name,
            display_name=f"Spec-Kit: {agent_name}",
            kind="cli" if self.config["cli_command"] else "ide",
            default_model=None
        )

    def execute(self, req: EngineRequest) -> EngineResult:
        # Use spec-kit's agent command format
        pass
```

---

## 5. Schema and Data Model Changes

### 5.1 Extended ProtocolSpec Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "source": {
      "enum": ["speckit", "codex", "codemachine", "manual"]
    },
    "speckit_metadata": {
      "type": "object",
      "properties": {
        "constitution_version": { "type": "string" },
        "feature_spec_path": { "type": "string" },
        "plan_path": { "type": "string" },
        "tasks_path": { "type": "string" },
        "branch_name": { "type": "string" }
      }
    },
    "steps": {
      "type": "array",
      "items": {
        "$ref": "#/definitions/StepSpec"
      }
    }
  },
  "definitions": {
    "StepSpec": {
      "type": "object",
      "properties": {
        "id": { "type": "string" },
        "name": { "type": "string" },
        "depends_on": {
          "type": "array",
          "items": { "type": "string" }
        },
        "parallel_group": { "type": "string" },
        "speckit_task_marker": { "type": "string" }
      }
    }
  }
}
```

### 5.2 Database Migrations

```python
# alembic/versions/xxx_add_speckit_fields.py

def upgrade():
    # Add speckit source tracking
    op.add_column('protocol_runs',
        sa.Column('speckit_metadata', sa.JSON, nullable=True))

    # Add DAG support for steps
    op.add_column('step_runs',
        sa.Column('depends_on', sa.JSON, nullable=True))
    op.add_column('step_runs',
        sa.Column('parallel_group', sa.String(100), nullable=True))

    # Add constitution tracking
    op.add_column('projects',
        sa.Column('constitution_version', sa.String(50), nullable=True))
```

---

## 6. API Changes

### 6.1 New Endpoints

```python
# POST /projects/{id}/speckit/init
# Initialize spec-kit in project
@router.post("/projects/{project_id}/speckit/init")
async def init_speckit(project_id: int):
    """Run 'specify init' in project directory"""
    pass

# POST /projects/{id}/speckit/specify
# Create feature specification
@router.post("/projects/{project_id}/speckit/specify")
async def create_feature_spec(
    project_id: int,
    body: FeatureSpecRequest
):
    """Run /speckit.specify and create protocol run"""
    pass

# POST /projects/{id}/speckit/plan
# Create implementation plan from spec
@router.post("/projects/{project_id}/speckit/plan")
async def create_implementation_plan(
    project_id: int,
    spec_path: str
):
    """Run /speckit.plan"""
    pass

# POST /projects/{id}/speckit/tasks
# Generate tasks from plan
@router.post("/projects/{project_id}/speckit/tasks")
async def generate_tasks(
    project_id: int,
    plan_path: str
):
    """Run /speckit.tasks"""
    pass

# POST /protocols/{id}/speckit/implement
# Execute implementation
@router.post("/protocols/{protocol_id}/speckit/implement")
async def implement_step(
    protocol_id: int,
    step_id: str,
    agent: str = "codex"
):
    """Run /speckit.implement with specified agent"""
    pass
```

### 6.2 Schema Additions

```python
# tasksgodzilla/api/schemas.py

class FeatureSpecRequest(BaseModel):
    description: str
    branch_name: Optional[str] = None
    use_constitution: bool = True

class SpecKitMetadata(BaseModel):
    constitution_version: Optional[str]
    feature_spec_path: Optional[str]
    plan_path: Optional[str]
    tasks_path: Optional[str]
    branch_name: Optional[str]

class ProtocolRunOut(BaseModel):
    # ... existing fields
    speckit_metadata: Optional[SpecKitMetadata] = None
    source: str = "codex"  # "speckit" | "codex" | "codemachine"
```

---

## 7. CLI Integration

### 7.1 New CLI Commands

```bash
# Initialize spec-kit in project
tasksgodzilla speckit init <project-id>

# Create feature specification
tasksgodzilla speckit specify <project-id> --description "Add authentication"

# Generate implementation plan
tasksgodzilla speckit plan <project-id> --spec-path specs/auth/spec.md

# Generate tasks
tasksgodzilla speckit tasks <project-id> --plan-path specs/auth/plan.md

# Run full workflow
tasksgodzilla speckit workflow <project-id> \
  --description "Add user authentication" \
  --agent codex \
  --auto-execute
```

### 7.2 Slash Command Integration

Create TasksGodzilla-specific slash commands in `.claude/commands/`:

```markdown
<!-- .claude/commands/tg-specify.md -->
Run the TasksGodzilla specify workflow:
1. Call /speckit.specify with: $ARGUMENTS
2. Parse the generated spec.md
3. Create a ProtocolRun via API
4. Return the protocol URL
```

---

## 8. Constitution Integration

### 8.1 Mapping to Policy Packs

Spec-kit's constitution maps to TasksGodzilla's policy pack system:

| Constitution Article | Policy Pack Equivalent |
|---------------------|----------------------|
| Article I: Library-First | `requirements.architecture.library_first` |
| Article III: Test-First | `requirements.testing.test_first` |
| Article VII: Simplicity | `requirements.complexity.max_projects: 3` |
| Article VIII: Anti-Abstraction | `requirements.patterns.no_unnecessary_wrappers` |
| Article IX: Integration Testing | `defaults.qa.prefer_real_services` |

### 8.2 Constitution-to-PolicyPack Converter

```python
# tasksgodzilla/services/constitution_adapter.py

class ConstitutionAdapter:
    def convert_to_policy_pack(self, constitution_path: str) -> PolicyPack:
        """Convert .specify/memory/constitution.md to PolicyPack"""
        constitution = self._parse_constitution(constitution_path)

        return PolicyPack(
            meta=PolicyPackMeta(
                key=f"speckit-{constitution.version}",
                name="Spec-Kit Constitution",
                version=constitution.version,
            ),
            requirements={
                "step_sections": self._extract_required_sections(constitution),
                "protocol_files": ["spec.md", "plan.md", "tasks.md"],
            },
            enforcement={
                "mode": "block",
                "gates": self._extract_gates(constitution),
            },
            defaults={
                "qa": {"policy": "full"},
                "models": {},
            }
        )
```

---

## 9. Implementation Phases

### Phase 1: Foundation (Week 1-2)

**Objective:** Install spec-kit as Python library and verify direct imports work

> ⚠️ **IMPORTANT:** Direct library import, NOT subprocess wrapper. See [Section 2](#2-integration-approach-library-vs-cli).

**Tasks:**
- [ ] Add spec-kit as Python library dependency via `uv add specify`
- [ ] Verify library imports work: `from specify import SpecifyEngine, PlanGenerator, TaskBreakdown`
- [ ] Verify typed models: `from specify.models import FeatureSpec, ImplementationPlan, TaskList`
- [ ] Verify typed errors: `from specify.errors import ContextWindowError, TemplateError, APIError`
- [ ] Create integration test verifying library calls return typed objects
- [ ] Add basic CLI command `tasksgodzilla speckit init` (uses library, not CLI)

**Validation Script:**
```python
# scripts/validate_speckit_library.py
from specify import SpecifyEngine, PlanGenerator, TaskBreakdown
from specify.models import FeatureSpec, ImplementationPlan, TaskList
from specify.errors import ContextWindowError, TemplateError, APIError

# Verify classes are importable and have expected methods
engine = SpecifyEngine(templates_dir=".specify/templates")
assert hasattr(engine, 'specify'), "Missing specify method"

planner = PlanGenerator(engine=engine)
assert hasattr(planner, 'generate'), "Missing generate method"

tasker = TaskBreakdown(engine=engine)
assert hasattr(tasker, 'breakdown'), "Missing breakdown method"

print("✅ All spec-kit library imports validated")
```

**Success Criteria:**
- Library imports work without errors
- Typed objects are returned (not strings)
- Typed exceptions can be caught
- No subprocess calls needed

### Phase 2: Planning Refactoring (Week 3-4)

**Objective:** Rewrite PlanningService to use spec-kit library directly (no parsing needed)

> ⚠️ **IMPORTANT:** Library returns typed objects. No regex/markdown parsing required.

**Tasks:**
- [ ] Rewrite `PlanningService.__init__()` to instantiate `SpecifyEngine`, `PlanGenerator`, `TaskBreakdown`
- [ ] Rewrite `PlanningService.plan_protocol()` to call library methods directly
- [ ] Add `_convert_tasks_to_steps()` to convert typed `TaskList` to `StepSpec` list
- [ ] Add proper error handling for `ContextWindowError`, `TemplateError`, `APIError`
- [ ] **DELETE** `tasksgodzilla/services/decomposition.py`
- [ ] **DELETE** `tasksgodzilla/services/spec.py` (merged into planning)
- [ ] **DELETE** `tasksgodzilla/pipeline.py` LLM prompts
- [ ] Update callers that used `SpecService` to use `PlanningService`
- [ ] Write integration tests

**Files Changed:**
```
tasksgodzilla/services/planning.py      ← REWRITE (uses library, absorbs spec + decomposition)
tasksgodzilla/services/decomposition.py ← DELETE
tasksgodzilla/services/spec.py          ← DELETE (merged into planning.py)
tasksgodzilla/pipeline.py               ← DELETE
```

**Key Code Change:**
```python
# Before (REJECTED - subprocess):
result = subprocess.run(["specify", "plan", ...])
steps = self._parse_markdown(result.stdout)  # Fragile regex

# After (CORRECT - library):
plan: ImplementationPlan = self._planner.generate(spec=feature_spec)
tasks: TaskList = self._tasker.breakdown(plan=plan)
steps = [StepSpec(id=t.id, name=t.description, depends_on=t.depends_on) for t in tasks.items]
```

**Success Criteria:**
- `PlanningService` handles everything via library calls
- No subprocess calls
- No regex/markdown parsing
- Typed exceptions properly handled
- No separate `SpecService`
- Same external API, simplified internals

### Phase 3: Execution, Orchestration & Feedback Loops (Week 5-6)

**Objective:** Rewrite ExecutionService for `_runtime/` paths, add DAG to OrchestratorService, implement feedback loops

> ⚠️ **CRITICAL:** This phase implements feedback loops. See [Section 2.5](#25-the-waterfall-trap-feedback-loops-required).

**Tasks:**

*Execution & Paths:*
- [ ] Rewrite `ExecutionService` to write outputs to `_runtime/runs/<id>/`
- [ ] Add `SpecificationError` detection and raising in `ExecutionService`
- [ ] Create `tasksgodzilla/paths.py` for path utilities

*Orchestration & DAG:*
- [ ] Rewrite `OrchestratorService` for DAG-based execution
- [ ] Implement cycle detection with Tarjan's algorithm
- [ ] Add `TaskGraphError` for cycle/missing dependency detection
- [ ] Validate DAG BEFORE execution starts (fail fast)

*Feedback Loops:*
- [ ] Create `tasksgodzilla/errors.py` with `SpecificationError`, `TaskGraphError`
- [ ] Add `handle_specification_error()` to `PlanningService`
- [ ] Add `handle_task_graph_error()` to `PlanningService`
- [ ] Add feedback API endpoints (`/protocols/{id}/feedback/*`)
- [ ] Implement feedback limits (prevent infinite loops)
- [ ] Add feedback event logging

*Database:*
- [ ] Add database migrations for new path fields
- [ ] Add `feedback_events` table for tracking re-planning attempts
- [ ] Update StepSpec schema for dependencies

**Files Changed:**
```
tasksgodzilla/services/execution.py     ← REWRITE (_runtime/ paths + SpecificationError)
tasksgodzilla/services/orchestrator.py  ← REWRITE (DAG + cycle detection + TaskGraphError)
tasksgodzilla/services/planning.py      ← ADD feedback handlers
tasksgodzilla/errors.py                 ← NEW (SpecificationError, TaskGraphError)
tasksgodzilla/paths.py                  ← NEW (path utilities)
tasksgodzilla/api/feedback.py           ← NEW (feedback endpoints)
tasksgodzilla/config.py                 ← ADD FeedbackConfig
```

**Key Changes in OrchestratorService:**
```python
class OrchestratorService:
    """Same class, enhanced with DAG support and cycle detection."""

    def build_execution_dag(self, protocol_run_id: int) -> ExecutionDAG:
        steps = self.db.get_steps_for_protocol(protocol_run_id)
        graph = self._build_adjacency_list(steps)

        # Detect cycles BEFORE execution starts
        cycle = self._detect_cycle(graph)
        if cycle:
            raise TaskGraphError(
                message=f"Circular dependency: {' → '.join(cycle)}",
                error_type="cycle",
                affected_tasks=cycle,
                graph_snapshot=graph,
            )

        return ExecutionDAG(steps=steps, graph=graph)

    def enqueue_next_step(self, protocol_run_id: int):
        ready_steps = self._get_ready_steps(protocol_run_id)
        for step in ready_steps:
            if step.parallel_group:
                self._enqueue_parallel_group(step.parallel_group)
            else:
                self._enqueue_step(step)
```

**Key Changes in ExecutionService:**
```python
class ExecutionService:
    """Same class, enhanced with feedback loop support."""

    def execute_step(self, step_run_id: int) -> StepResult:
        try:
            result = self._run_engine(step)
            return result
        except ExecutionBlockedError as e:
            raise SpecificationError(
                message=f"Step blocked: {e.reason}",
                error_type=self._classify_block_reason(e),
                context={"step_id": step.id, "block_reason": e.reason},
                suggested_action="re_plan" if e.is_structural else "clarify",
            )
```

**Success Criteria:**
- Tasks with dependencies execute in correct order
- Parallel tasks can run concurrently
- All paths point to `specs/<branch>/_runtime/`
- Circular dependencies detected BEFORE execution (fail fast)
- `SpecificationError` triggers re-planning, not hard failure
- Feedback loops have attempt limits (no infinite loops)
- All feedback events logged for debugging

### Phase 4: Quality Service Refactoring (Week 7-8)

**Objective:** Rewrite QualityService with spec-kit checklist and constitutional gates

**Tasks:**
- [ ] Rewrite `QualityService.run_qa()` to include spec-kit checklist
- [ ] Add constitutional gate checks to `QualityService`
- [ ] Update QA verdict logic to combine engine + checklist + gates
- [ ] Rewrite `PolicyService` to read from `constitution.md`

**Files Changed:**
```
tasksgodzilla/services/quality.py  ← REWRITE (same name)
tasksgodzilla/services/policy.py   ← REWRITE (same name, reads constitution)
```

**Success Criteria:**
- `QualityService` runs checklist and gates
- Same method signatures, enhanced output
- Constitutional gates integrated into verdict

### Phase 5: Multi-Agent Support (Week 9-10)

**Objective:** Extend engine registry with spec-kit agents

**Tasks:**
- [ ] Create `SpecKitAgentEngine` class
- [ ] Register all 18 supported agents
- [ ] Implement agent command generation
- [ ] Add agent selection to API/CLI
- [ ] Test with multiple agents (Claude, Cursor, Gemini)

**Configuration:**
```yaml
# config/agents.yaml
agents:
  claude-code:
    enabled: true
    default_model: claude-sonnet-4-20250514
  cursor:
    enabled: true
    default_model: gpt-4
  gemini-cli:
    enabled: false
```

**Success Criteria:**
- Can execute steps with any supported agent
- Agent-specific commands work correctly
- Configuration allows enabling/disabling agents

### Phase 6: Web Console Integration (Week 11-12)

**Objective:** Update React console for spec-kit workflows

**Tasks:**
- [ ] Add "Spec-Kit" workflow option in protocol creation
- [ ] Create specification editor component
- [ ] Add plan visualization
- [ ] Show task dependencies as DAG
- [ ] Display constitution compliance status

**Components:**
```
frontend/src/features/speckit/
├── SpecifyForm.tsx       # Feature specification input
├── PlanViewer.tsx        # Implementation plan display
├── TasksDAG.tsx          # Dependency graph visualization
├── ConstitutionBadge.tsx # Compliance status indicator
└── AgentSelector.tsx     # Multi-agent dropdown
```

**Success Criteria:**
- Full spec-kit workflow accessible from UI
- Visual representation of task dependencies
- Clear indication of workflow source (spec-kit vs legacy)

---

## 10. Configuration

### 10.1 Environment Variables

```bash
# NO FEATURE FLAGS - spec-kit is always enabled after migration
# These are removed:
# - TASKSGODZILLA_USE_SPECKIT (removed - always on)
# - TASKSGODZILLA_SPECKIT_PLANNING (removed - always on)
# - TASKSGODZILLA_SPECKIT_DECOMPOSITION (removed - always on)

# Default agent for execution
TASKSGODZILLA_DEFAULT_AGENT=codex

# Template paths (override defaults)
TASKSGODZILLA_TEMPLATES_PATH=.specify/templates

# Constitution settings
TASKSGODZILLA_ENFORCE_CONSTITUTION=true
TASKSGODZILLA_CONSTITUTION_PATH=.specify/memory/constitution.md

# QA gates (always enabled, can configure strictness)
TASKSGODZILLA_QA_GATE_MODE=strict  # strict | warn
```

### 10.2 Project-Level Configuration

```json
// .tasksgodzilla.json
{
  // NO "enabled" flag - spec-kit is always the only option
  "default_agent": "claude-code",
  "enforce_constitution": true,
  "templates": {
    "spec": ".specify/templates/spec-template.md",
    "plan": ".specify/templates/plan-template.md",
    "tasks": ".specify/templates/tasks-template.md"
  },
  "agents": {
    "claude-code": { "enabled": true },
    "cursor": { "enabled": true },
    "codex": { "enabled": true }
  },
  "qa_gate_mode": "strict"
}
```

---

## 11. Testing Strategy

### 11.1 Unit Tests

```python
# tests/test_planning_service.py

class TestPlanningService:
    def test_plan_protocol_creates_specify_structure(self):
        """plan_protocol() creates specs/<branch>/ structure"""
        pass

    def test_plan_protocol_runs_speckit_commands(self):
        """plan_protocol() runs specify, plan, tasks commands"""
        pass

    def test_plan_protocol_parses_tasks_with_dependencies(self):
        """Parse tasks.md with PARALLEL/DEPENDS markers"""
        pass

# tests/test_policy_service.py

class TestPolicyService:
    def test_reads_constitution_md(self):
        """PolicyService reads from constitution.md"""
        pass
```

### 11.2 Integration Tests

```python
# tests/integration/test_speckit_workflow.py

class TestSpecKitWorkflow:
    def test_full_specify_plan_tasks_flow(self, project):
        """Complete workflow from specify to tasks"""
        pass

    def test_dag_execution_order(self, protocol_with_deps):
        """Verify DAG respects dependencies"""
        pass

    def test_parallel_step_execution(self, protocol_with_parallel):
        """Verify parallel groups execute together"""
        pass
```

### 11.3 E2E Tests

```bash
# scripts/test_speckit_e2e.sh

# Full workflow test
tasksgodzilla speckit workflow test-project \
  --description "Add user login" \
  --agent codex \
  --dry-run

# Verify artifacts created
ls specs/*/
```

---

## 12. Migration Guide

### 12.1 Mandatory `.protocols/` Migration

> ⚠️ **MANDATORY**: All `.protocols/` data MUST be migrated before deployment.
> There is NO backward compatibility. The migration is a prerequisite, not optional.

**Timeline:**
- **Pre-deployment**: Run mandatory migration for ALL existing projects
- **Deployment**: Only `.specify/` structure supported
- **Post-deployment**: `.protocols/` directories are deleted

**Migration script:**

```bash
# Migrate existing .protocols/ to .specify/
tasksgodzilla migrate-to-speckit <project-id> [--dry-run]

# What it does:
# 1. Creates .specify/ structure if not exists
# 2. For each .protocols/<name>/:
#    - Creates specs/<name>/
#    - Moves plan.md → specs/<name>/plan.md
#    - Moves context.md, log.md, quality-report.md → _runtime/
#    - Consolidates NN-step.md files → tasks.md (or preserves as _runtime/legacy/)
# 3. Updates DB protocol_root paths
# 4. Optionally removes .protocols/ after verification
```

**Migration implementation:**

```python
# tasksgodzilla/services/migration.py

class MigrationService:
    def migrate_protocols_to_specify(
        self,
        project_id: int,
        dry_run: bool = False
    ) -> MigrationReport:
        """Migrate .protocols/ to .specify/ structure."""
        project = self.db.get_project(project_id)
        repo_path = Path(project.local_path)

        protocols_dir = repo_path / ".protocols"
        specify_dir = repo_path / ".specify"

        if not protocols_dir.exists():
            return MigrationReport(status="skipped", reason="No .protocols/ found")

        # Ensure .specify/ exists
        if not dry_run:
            self._init_speckit_if_needed(repo_path)

        migrated = []
        for protocol_dir in protocols_dir.iterdir():
            if not protocol_dir.is_dir():
                continue

            branch_name = protocol_dir.name
            target_dir = specify_dir / "specs" / branch_name
            runtime_dir = target_dir / "_runtime"

            if not dry_run:
                target_dir.mkdir(parents=True, exist_ok=True)
                runtime_dir.mkdir(exist_ok=True)

                # Move spec files
                self._move_if_exists(protocol_dir / "plan.md", target_dir / "plan.md")

                # Move runtime files
                for runtime_file in ["context.md", "log.md", "quality-report.md"]:
                    self._move_if_exists(
                        protocol_dir / runtime_file,
                        runtime_dir / runtime_file
                    )

                # Handle step files → consolidate or preserve
                self._migrate_step_files(protocol_dir, target_dir, runtime_dir)

                # Update DB
                self._update_protocol_paths(branch_name, str(target_dir))

            migrated.append(branch_name)

        return MigrationReport(
            status="success",
            migrated_protocols=migrated,
            dry_run=dry_run
        )

    def _migrate_step_files(self, src_dir: Path, target_dir: Path, runtime_dir: Path):
        """Handle NN-step.md files."""
        step_files = sorted(src_dir.glob("[0-9][0-9]-*.md"))

        if not step_files:
            return

        # Option 1: Preserve as legacy in _runtime
        legacy_dir = runtime_dir / "legacy"
        legacy_dir.mkdir(exist_ok=True)
        for f in step_files:
            shutil.copy2(f, legacy_dir / f.name)

        # Option 2: Generate tasks.md stub pointing to legacy
        tasks_content = "# Tasks\n\n"
        tasks_content += "<!-- Migrated from .protocols/ - original step files in _runtime/legacy/ -->\n\n"
        for f in step_files:
            tasks_content += f"- [ ] {f.stem.replace('-', ' ').title()}\n"
        (target_dir / "tasks.md").write_text(tasks_content)
```

### 12.2 Services Changes Summary

| Service | Change | Details |
|---------|--------|---------|
| `PlanningService` | **REWRITE** | Absorbs SpecService, calls spec-kit, parses output |
| `SpecService` | **DELETE** | Merged into PlanningService |
| `DecompositionService` | **DELETE** | Merged into PlanningService |
| `ExecutionService` | **REWRITE** | Output paths to `_runtime/runs/<run-id>/` |
| `QualityService` | **REWRITE** | QA report to `_runtime/`, add gates |
| `PolicyService` | **REWRITE** | Read `constitution.md` |
| `GitService` | **REWRITE** | Create `.specify/` structure |
| `OnboardingService` | **REWRITE** | Init `.specify/` during setup |
| `OrchestratorService` | **REWRITE** | DAG execution, new path resolution |

**PlanningService now uses spec-kit library directly (SpecService deleted):**

> ⚠️ **Uses library import, NOT subprocess.** See [Section 2](#2-integration-approach-library-vs-cli).

```python
# tasksgodzilla/services/planning.py
from specify import SpecifyEngine, PlanGenerator, TaskBreakdown
from specify.models import FeatureSpec, ImplementationPlan, TaskList

class PlanningService:
    """Planning service - uses spec-kit library directly.

    SpecService functionality absorbed. No separate spec service.
    No subprocess calls. No markdown parsing.
    """

    def __init__(self, db: BaseDatabase):
        self.db = db
        self._engine = SpecifyEngine()
        self._planner = PlanGenerator(engine=self._engine)
        self._tasker = TaskBreakdown(engine=self._engine)

    def plan_protocol(self, project_id: int, description: str, branch: str) -> ProtocolRun:
        """Create protocol - uses spec-kit library (typed returns)."""
        project = self.db.get_project(project_id)
        repo_root = Path(project.local_path)

        # Library calls return typed objects (no parsing needed)
        feature_spec: FeatureSpec = self._engine.specify(description, branch, repo_root)
        plan: ImplementationPlan = self._planner.generate(spec=feature_spec)
        tasks: TaskList = self._tasker.breakdown(plan=plan)

        # Convert typed TaskList to StepSpecs (no regex)
        steps = [
            StepSpec(id=t.id, name=t.description, depends_on=t.depends_on)
            for t in tasks.items
        ]

        feature_dir = repo_root / ".specify" / "specs" / branch
        return self._create_protocol_run(project_id, branch, feature_dir, steps)

    def _create_protocol_run(self, ...) -> ProtocolRun:
        """Create ProtocolRun and StepRun entries."""
        pass
```

**DELETE `tasksgodzilla/services/spec.py` entirely.**

**ExecutionService changes (complete replacement):**

```python
# tasksgodzilla/services/execution.py

# DELETE: _get_legacy_output_paths() - no longer needed
# DELETE: _is_speckit_structure() - no longer needed (always speckit)

def get_output_paths(self, step_run: StepRun, run_id: str) -> OutputPaths:
    """Get output paths for step execution.

    Only .specify/ structure supported. No legacy fallback.
    """
    feature_dir = Path(step_run.protocol_run.protocol_root)

    # Validate structure (fail fast, no fallback)
    if "_runtime" not in str(feature_dir) and not (feature_dir / "_runtime").exists():
        (feature_dir / "_runtime").mkdir(exist_ok=True)

    run_dir = feature_dir / "_runtime" / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "step-outputs").mkdir(exist_ok=True)
    (run_dir / "qa").mkdir(exist_ok=True)

    return OutputPaths(
        step_output=run_dir / "step-outputs" / f"{step_run.order:02d}-output.md",
        log=feature_dir / "_runtime" / "log.md",
        context=feature_dir / "_runtime" / "context.md",
    )
```

### 12.3 Mandatory Pre-Deployment Steps

> ⚠️ **ALL steps below are MANDATORY before deployment**

```bash
# Step 1: Migrate ALL existing projects (REQUIRED)
for project_id in $(tasksgodzilla projects list --ids); do
    tasksgodzilla migrate-to-speckit $project_id --dry-run
    tasksgodzilla migrate-to-speckit $project_id
done

# Step 2: Verify migration (REQUIRED)
tasksgodzilla verify-migration --all-projects

# Step 3: Generate constitutions from policy packs (REQUIRED)
for project_id in $(tasksgodzilla projects list --ids); do
    tasksgodzilla speckit sync-constitution $project_id
done

# Step 4: Delete old .protocols/ directories (REQUIRED)
for project_id in $(tasksgodzilla projects list --ids); do
    tasksgodzilla cleanup-legacy $project_id --delete-protocols
done

# Step 5: Update database paths (automatic during migration)
# All protocol_root paths now point to specs/<branch>/
```

### 12.4 No Backward Compatibility

> **There is NO backward compatibility.** The system will fail if it encounters
> `.protocols/` paths after migration.

| Scenario | Behavior |
|----------|----------|
| ProtocolRun with `.protocols/` path | **ERROR** - migration required |
| Missing `.specify/` structure | **ERROR** - fail fast |
| Mixed project (both dirs) | **NOT ALLOWED** - cleanup required |

**Validation on startup:**

```python
# tasksgodzilla/startup.py

def validate_no_legacy_structures():
    """Fail startup if any legacy structures exist.

    Called during application initialization.
    """
    projects = db.list_all_projects()

    for project in projects:
        repo_path = Path(project.local_path)
        protocols_dir = repo_path / ".protocols"

        if protocols_dir.exists():
            raise StartupError(
                f"Legacy .protocols/ found in project {project.id}. "
                f"Run 'tasksgodzilla migrate-to-speckit {project.id}' first."
            )

        # Validate all protocol runs point to .specify/
        for run in db.list_protocol_runs(project_id=project.id):
            if run.protocol_root and ".protocols" in run.protocol_root:
                raise StartupError(
                    f"ProtocolRun {run.id} has legacy path. "
                    f"Database migration required."
                )
```

### 12.5 Files to DELETE vs REWRITE

**DELETE entirely:**
```
tasksgodzilla/services/decomposition.py  # Merged into planning.py
tasksgodzilla/pipeline.py                # LLM prompts replaced by templates
```

**REWRITE (same file name, new implementation):**
```
tasksgodzilla/services/planning.py       # Uses spec-kit internally
tasksgodzilla/services/spec.py           # Reads .specify/ structure
tasksgodzilla/services/execution.py      # Writes to _runtime/
tasksgodzilla/services/quality.py        # Adds constitutional gates
tasksgodzilla/services/policy.py         # Reads constitution.md
tasksgodzilla/services/orchestrator.py   # Adds DAG execution
tasksgodzilla/services/onboarding.py     # Creates .specify/ structure
```

**REMOVE from rewritten files:**
```
- build_spec_from_protocol_files()
- _parse_protocol_files()
- _get_legacy_output_paths()
- _is_speckit_structure()
- detect_artifact_structure()
- Any "if .protocols" conditions
```

**REMOVE ENV VARS:**
```
- TASKSGODZILLA_USE_SPECKIT (no toggle, always on)
- TASKSGODZILLA_USE_SPECKIT_PLANNING (no toggle)
- Any feature flags
```

---

## 13. Risks and Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Spec-kit API changes | High | Medium | Pin version, abstract through adapter |
| Agent compatibility issues | Medium | Medium | Test matrix, default to Codex |
| Performance regression | Medium | Low | Benchmark, async execution |
| Migration data loss | High | Low | Dry-run first, backup before migration |
| Incomplete migration | High | Medium | Startup validation fails fast |
| Constitution conflicts with policies | Medium | Medium | Policy packs converted to constitution |

**Clean Cut Specific Risks:**

| Risk | Mitigation |
|------|------------|
| Missed migration step | Startup validation blocks launch |
| Legacy code paths remain | Code review checklist, grep for ".protocols" |
| Database paths not updated | Migration script updates all paths |
| Tests reference old paths | All tests rewritten for new structure |

---

## 14. Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Planning quality improvement | 20% fewer revisions | Compare revision counts |
| Spec completeness | 90% pass rate on checklist | Automated checks |
| Multi-agent usage | 3+ agents in use | Telemetry |
| User adoption | 50% of new protocols use spec-kit | API metrics |
| Execution time | No regression | Benchmark suite |

---

## 15. Open Questions

1. ~~**Directory Structure:** Use `.protocols/` or `.specify/` or both?~~
   **RESOLVED:** Consolidate to `.specify/` with `_runtime/` extension. No `.protocols/`.

2. ~~**Backward Compatibility:** Support both old and new structure?~~
   **RESOLVED:** No backward compatibility. Clean cut migration required.

3. **Template Customization:** Should we maintain TasksGodzilla-specific templates or fully adopt spec-kit's?

4. ~~**Constitution vs Policy Packs:** Merge into unified system or keep separate?~~
   **RESOLVED:** Policy packs converted to constitution during migration. Single system.

5. **Agent Priority:** When multiple agents are available, how to select?

6. **Offline Mode:** Spec-kit requires agents - how to handle offline scenarios?

7. **Version Sync:** How to keep spec-kit CLI version in sync with templates?

8. **Git Ignore:** Should `_runtime/runs/` be gitignored?
   - **Decision needed**: `runs/` is ephemeral, but `context.md`/`log.md` might be useful

---

## 16. Post-Migration Architecture (No Redundancy)

After migration, the system has a single, clean architecture with no redundant services:

### 16.1 Services: Before → After

| Service | Change | Implementation |
|---------|--------|----------------|
| `PlanningService` | **REWRITE** | Calls spec-kit + parses output (absorbs SpecService) |
| `DecompositionService` | **DELETE** | Merged into `PlanningService` |
| `SpecService` | **DELETE** | Merged into `PlanningService` |
| `ExecutionService` | **REWRITE** | Writes to `_runtime/`, same interface |
| `QualityService` | **REWRITE** | Adds constitutional gates, same interface |
| `PolicyService` | **REWRITE** | Reads constitution.md, same interface |
| `OrchestratorService` | **REWRITE** | Adds DAG support, same interface |
| `pipeline.py` | **DELETE** | Templates moved to `.specify/templates/` |

### 16.2 Directory Structure: Before → After

| Before (DELETED) | After (ONLY) |
|------------------|--------------|
| `.protocols/<name>/` | `specs/<branch>/` |
| `.protocols/<name>/plan.md` | `specs/<branch>/plan.md` |
| `.protocols/<name>/context.md` | `specs/<branch>/_runtime/context.md` |
| `.protocols/<name>/NN-step.md` | `specs/<branch>/tasks.md` |
| N/A | `specs/<branch>/spec.md` (new) |

### 16.3 Code Paths: Before → After

```
BEFORE (multiple paths):                 AFTER (single path):

┌─────────────────────┐                 ┌─────────────────────┐
│ PlanningService     │                 │ PlanningService     │
│   if USE_SPECKIT:   │                 │   (rewritten)       │
│     use speckit     │        →        │   uses spec-kit     │
│   else:             │                 │   internally        │
│     use legacy LLM  │                 │                     │
└─────────────────────┘                 └─────────────────────┘

┌─────────────────────┐                 ┌─────────────────────┐
│ ExecutionService    │                 │ ExecutionService    │
│   if .protocols:    │                 │   (rewritten)       │
│     legacy paths    │        →        │   always uses       │
│   else:             │                 │   specs/   │
│     .specify paths  │                 │   └── _runtime/     │
└─────────────────────┘                 └─────────────────────┘
```

**Key Point:** Same service names, same method signatures, new implementation.

### 16.4 Files Changed (Complete List)

```
tasksgodzilla/
├── services/
│   ├── planning.py           ← REWRITE (absorbs spec.py + decomposition.py)
│   ├── decomposition.py      ← DELETE
│   ├── spec.py               ← DELETE (merged into planning.py)
│   ├── execution.py          ← REWRITE (_runtime/ paths)
│   ├── quality.py            ← REWRITE (add gates)
│   ├── policy.py             ← REWRITE (read constitution)
│   ├── orchestrator.py       ← REWRITE (add DAG)
│   ├── onboarding.py         ← REWRITE (init .specify/)
│   └── git.py                ← REWRITE (.specify/ structure)
├── pipeline.py               ← DELETE
└── paths.py                  ← NEW (path utilities)

# DELETED FILES:
- tasksgodzilla/services/spec.py
- tasksgodzilla/services/decomposition.py
- tasksgodzilla/pipeline.py

# Functions to REMOVE from rewritten services:
- _get_legacy_output_paths()           # execution.py
- _is_speckit_structure()              # execution.py
- detect_artifact_structure()          # anywhere
- Any "if .protocols" conditions       # everywhere
- Any USE_SPECKIT env checks           # everywhere
```

### 16.5 Verification Commands

```bash
# Verify no legacy code remains
grep -r "\.protocols" tasksgodzilla/ --include="*.py"
# Expected: 0 results

grep -r "USE_SPECKIT" tasksgodzilla/ --include="*.py"
# Expected: 0 results

grep -r "legacy" tasksgodzilla/ --include="*.py"
# Expected: 0 results (or only in migration script)

grep -r "build_spec_from_protocol" tasksgodzilla/ --include="*.py"
# Expected: 0 results

# Verify startup validation passes
tasksgodzilla validate-migration --all-projects
# Expected: "All projects migrated successfully"
```

---

## 17. References

- [GitHub spec-kit Repository](https://github.com/github/spec-kit)
- [Spec-Driven Development Methodology](https://github.com/github/spec-kit/blob/main/spec-driven.md)
- [TasksGodzilla Architecture (CLAUDE.md)](/home/ilya/Documents/dev-pipeline/CLAUDE.md)
- [Protocol Spec Schema](/home/ilya/Documents/dev-pipeline/schemas/protocol-spec.schema.json)

---

## Appendix A: Spec-Kit Command Reference

| Command | Purpose | Output |
|---------|---------|--------|
| `specify init <name>` | Bootstrap project | `.specify/` directory |
| `/speckit.constitution` | Create governance | `memory/constitution.md` |
| `/speckit.specify` | Feature specification | `specs/<branch>/spec.md` |
| `/speckit.plan` | Implementation plan | `specs/<branch>/plan.md` |
| `/speckit.tasks` | Task breakdown | `specs/<branch>/tasks.md` |
| `/speckit.implement` | Execute tasks | Code changes |
| `/speckit.clarify` | Refine requirements | Updated spec |
| `/speckit.analyze` | Consistency check | Analysis report |
| `/speckit.checklist` | Quality validation | Checklist results |

## Appendix B: Supported Agents

| Agent | CLI | Format | Command Dir |
|-------|-----|--------|-------------|
| Claude Code | `claude` | Markdown | `.claude/commands/` |
| GitHub Copilot | IDE | Markdown | `.github/agents/` |
| Cursor | `cursor` | Markdown | `.cursor/commands/` |
| Gemini CLI | `gemini` | TOML | `.gemini/commands/` |
| Codex CLI | `codex` | Markdown | `.codex/commands/` |
| OpenCode | `opencode` | Markdown | `.opencode/command/` |
| Windsurf | IDE | Markdown | `.windsurf/workflows/` |
| Amazon Q | `q` | Markdown | `.amazonq/prompts/` |
| Qoder CLI | `qoder` | Markdown | `.qoder/commands/` |
| Qwen Code | `qwen` | TOML | `.qwen/commands/` |
| Auggie CLI | `auggie` | Markdown | `.augment/rules/` |
| CodeBuddy | `codebuddy` | Markdown | `.codebuddy/commands/` |
| Amp | `amp` | Markdown | `.agents/commands/` |
| SHAI | `shai` | Markdown | `.shai/commands/` |
| Kilo Code | IDE | Markdown | `.kilocode/rules/` |
| Roo Code | IDE | Markdown | `.roo/rules/` |
| IBM Bob | IDE | Markdown | `.bob/commands/` |

## Appendix C: Consolidated Directory Structure Reference

### Complete Structure

```
project-root/
├── .specify/                                    # ROOT (replaces .protocols/)
│   │
│   ├── memory/                                  # Project-level governance
│   │   ├── constitution.md                      # From spec-kit constitution
│   │   └── principles.md                        # Additional principles (optional)
│   │
│   ├── templates/                               # Shared templates
│   │   ├── spec-template.md                     # Feature specification template
│   │   ├── plan-template.md                     # Implementation plan template
│   │   ├── tasks-template.md                    # Task breakdown template
│   │   └── checklist-template.md                # QA checklist template
│   │
│   └── specs/                                   # Per-feature specifications
│       │
│       ├── 0001-user-auth/                      # Feature branch: 0001-user-auth
│       │   ├── spec.md                  # SPEC-KIT: What to build
│       │   ├── plan.md                          # SPEC-KIT: How to build
│       │   ├── tasks.md                         # SPEC-KIT: Task breakdown
│       │   │
│       │   └── _runtime/                        # TASKSGODZILLA: Execution layer
│       │       ├── context.md                   # Execution context
│       │       ├── log.md                       # Execution log (appended)
│       │       ├── quality-report.md            # Latest QA summary
│       │       │
│       │       ├── runs/                        # Per-execution history
│       │       │   ├── run-001/
│       │       │   │   ├── metadata.json        # { started, ended, status, ... }
│       │       │   │   ├── step-outputs/
│       │       │   │   │   ├── 01-setup.md
│       │       │   │   │   ├── 02-impl.md
│       │       │   │   │   └── 03-test.md
│       │       │   │   └── qa/
│       │       │   │       ├── checklist.md
│       │       │   │       └── gate-results.json
│       │       │   │
│       │       │   └── run-002/                 # Retry run
│       │       │       └── ...
│       │       │
│       │       └── legacy/                      # Migrated from .protocols/ (if any)
│       │           ├── 01-step.md
│       │           └── 02-step.md
│       │
│       ├── 0002-payment-flow/                   # Another feature
│       │   ├── spec.md
│       │   ├── plan.md
│       │   ├── tasks.md
│       │   └── _runtime/
│       │       └── ...
│       │
│       └── setup-1/                             # Onboarding protocol
│           ├── plan.md
│           └── _runtime/
│               └── ...
│
├── .gitignore                                   # Should include: specs/*/_runtime/runs/
│
└── ... (rest of project)
```

### Path Resolution Functions

```python
# tasksgodzilla/paths.py

from pathlib import Path
from typing import Optional

SPECIFY_ROOT = ".specify"
SPECS_DIR = "specs"
RUNTIME_DIR = "_runtime"
RUNS_DIR = "runs"

class SpecifyPaths:
    """Path resolution for .specify/ structure."""

    def __init__(self, repo_root: Path):
        self.repo_root = repo_root
        self.specify_root = repo_root / SPECIFY_ROOT

    # === Project-level paths ===

    @property
    def memory_dir(self) -> Path:
        return self.specify_root / "memory"

    @property
    def constitution_path(self) -> Path:
        return self.memory_dir / "constitution.md"

    @property
    def templates_dir(self) -> Path:
        return self.specify_root / "templates"

    @property
    def specs_dir(self) -> Path:
        return self.specify_root / SPECS_DIR

    # === Feature-level paths ===

    def feature_dir(self, branch_name: str) -> Path:
        return self.specs_dir / branch_name

    def feature_spec_path(self, branch_name: str) -> Path:
        return self.feature_dir(branch_name) / "spec.md"

    def plan_path(self, branch_name: str) -> Path:
        return self.feature_dir(branch_name) / "plan.md"

    def tasks_path(self, branch_name: str) -> Path:
        return self.feature_dir(branch_name) / "tasks.md"

    # === Runtime paths ===

    def runtime_dir(self, branch_name: str) -> Path:
        return self.feature_dir(branch_name) / RUNTIME_DIR

    def context_path(self, branch_name: str) -> Path:
        return self.runtime_dir(branch_name) / "context.md"

    def log_path(self, branch_name: str) -> Path:
        return self.runtime_dir(branch_name) / "log.md"

    def quality_report_path(self, branch_name: str) -> Path:
        return self.runtime_dir(branch_name) / "quality-report.md"

    # === Run-level paths ===

    def runs_dir(self, branch_name: str) -> Path:
        return self.runtime_dir(branch_name) / RUNS_DIR

    def run_dir(self, branch_name: str, run_id: str) -> Path:
        return self.runs_dir(branch_name) / run_id

    def run_metadata_path(self, branch_name: str, run_id: str) -> Path:
        return self.run_dir(branch_name, run_id) / "metadata.json"

    def step_outputs_dir(self, branch_name: str, run_id: str) -> Path:
        return self.run_dir(branch_name, run_id) / "step-outputs"

    def step_output_path(self, branch_name: str, run_id: str, step_order: int) -> Path:
        return self.step_outputs_dir(branch_name, run_id) / f"{step_order:02d}-output.md"

    def qa_dir(self, branch_name: str, run_id: str) -> Path:
        return self.run_dir(branch_name, run_id) / "qa"

    # === Utilities ===

    def ensure_feature_structure(self, branch_name: str) -> Path:
        """Create feature directory with runtime subdirs."""
        feature = self.feature_dir(branch_name)
        runtime = self.runtime_dir(branch_name)
        runs = self.runs_dir(branch_name)

        feature.mkdir(parents=True, exist_ok=True)
        runtime.mkdir(exist_ok=True)
        runs.mkdir(exist_ok=True)

        return feature

    def ensure_run_structure(self, branch_name: str, run_id: str) -> Path:
        """Create run directory with subdirs."""
        run = self.run_dir(branch_name, run_id)
        step_outputs = self.step_outputs_dir(branch_name, run_id)
        qa = self.qa_dir(branch_name, run_id)

        run.mkdir(parents=True, exist_ok=True)
        step_outputs.mkdir(exist_ok=True)
        qa.mkdir(exist_ok=True)

        return run

    @classmethod
    def from_protocol_run(cls, protocol_run) -> "SpecifyPaths":
        """Create paths helper from ProtocolRun."""
        # Extract repo root from protocol_root
        protocol_root = Path(protocol_run.protocol_root)

        # protocol_root is specs/<branch>, so repo_root is 3 levels up
        if "specs" in str(protocol_root):
            repo_root = protocol_root.parent.parent.parent
        else:
            # Legacy .protocols/ structure - use worktree path
            repo_root = Path(protocol_run.worktree_path)

        return cls(repo_root)
```

### Recommended .gitignore additions

```gitignore
# Spec-kit runtime artifacts (execution-specific, stored in DB)
specs/*/_runtime/runs/

# Keep these tracked:
# specs/*/_runtime/context.md   (useful for debugging)
# specs/*/_runtime/log.md       (useful for history)
# specs/*/_runtime/quality-report.md (useful for review)
```
