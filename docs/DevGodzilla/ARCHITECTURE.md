# DevGodzilla: Integrated Architecture Design

> **Speckit + Windmill + DevGodzilla**
> 
> A unified AI-driven development platform combining specification-driven development, industrial-grade workflow orchestration, and multi-agent code execution.
>
> **Open Source • Python Library • CLI**

---

## Design Principles

> [!IMPORTANT]
> **Core Design Decisions**
> - **Open Source**: Fully open source solution
> - **Distribution**: Available as both Python library and CLI
> - **Agent Assignment**: Users can assign specific agents to specific steps
> - **No Offline Mode**: System requires online AI agent access
> - **No Fallbacks**: Clean-cut implementation, no backward compatibility layers
> - **Gitignore Runtime**: `_runtime/runs/` is gitignored (ephemeral execution data)
> - **Frontend**: Extend existing Windmill frontend (Svelte) with DevGodzilla-specific features

**Current-state reference (what actually runs today):** `docs/DevGodzilla/CURRENT_STATE.md`

## Executive Summary

This document defines the architecture for **DevGodzilla**, a new integrated platform combining:

| Component | Role | Source |
|-----------|------|--------|
| **Speckit** | Spec-style artifacts (`.specify/`) + API/CLI surface | `devgodzilla/services/specification.py` |
| **Windmill** | Workflow engine + UI (flows/scripts execute DevGodzilla jobs) | `Origins/Windmill/`, `windmill/` |
| **DevGodzilla** | FastAPI API + services + agent execution | `devgodzilla/` |

> Notes:
> - The upstream SpecKit project is vendored under `Origins/spec-kit/` for reference, but the current implementation generates `.specify/` artifacts directly (no external `specify` CLI/library dependency).
> - The legacy TasksGodzilla stack lives under `archive/` and is not part of the main DevGodzilla runtime.

## 0. Current Runtime Workflow (Headless SWE-agent)

DevGodzilla’s primary workflow is **agent-driven**: a headless SWE-agent runs prompt(s), writes artifacts into the repo/worktree, and DevGodzilla validates/records those artifacts.

High-level flow:
1. **Onboard repo**: ensure repo exists locally and initialize `.specify/` (`POST /projects/{id}/actions/onboard`).
2. **Discovery (optional)**: run headless discovery agent (writes `tasksgodzilla/*`).
3. **Plan protocol**: ensure a git worktree, then read `.protocols/<protocol_name>/step-*.md` to create `StepRun` rows.
   - If protocol files are missing and `DEVGODZILLA_AUTO_GENERATE_PROTOCOL=true` (default), generate `.protocols/<protocol_name>/plan.md` + `step-*.md` via headless agent.
4. **Execute step**: engine runs inside the protocol worktree; DevGodzilla writes execution artifacts (“git report”) under `.protocols/<protocol_name>/.devgodzilla/steps/<step_run_id>/artifacts/*`.
5. **QA**: QA gates run on step output; `"gates": []` skips QA and still completes the step (useful for E2E/system tests). After QA, DevGodzilla best-effort updates protocol status to `completed` / `failed` when all steps are terminal.

Default engine/model for headless workflows:
- Engine: `opencode` (`DEVGODZILLA_DEFAULT_ENGINE_ID`)
- Model: `zai-coding-plan/glm-4.6` (`DEVGODZILLA_OPENCODE_MODEL`)

---

## 1. High-Level Architecture

```mermaid
graph TB
    subgraph UserLayer["👤 User Layer"]
        CLI[CLI - Click-based]
        Console[Windmill UI + Extensions]
        API[REST API - FastAPI]
    end

    subgraph SpecificationEngine["📋 Specification Engine"]
        direction TB
        SpecKit[SpecKit Library]
        SpecParser[Specification Parser]
        TaskBreakdown[Task Breakdown Engine]
    end

    subgraph OrchestrationCore["⚙️ Orchestration Core"]
        direction TB
        Windmill[Windmill Engine]
        DAGScheduler[DAG Scheduler]
        JobQueue[Job Queue - Postgres]
        WorkerPool[Worker Pool]
    end

    subgraph ExecutionLayer["🚀 Execution Layer"]
        direction TB
        EngineRegistry[Engine Registry]
        Codex[Codex Engine]
        OpenCode[OpenCode Engine]
        ClaudeCode[Claude Code]
        OtherAgents[15+ More Agents]
    end

    subgraph CrossCutting["🔄 Cross-Cutting Services"]
        direction TB
        Constitution[Constitution Manager]
        Clarifier[Clarifier Service]
        QAGates[QA Gates]
        FeedbackLoop[Feedback Loop]
    end

    subgraph PlatformServices["🔧 Platform Services"]
        direction TB
        GitService[Git Service]
        CIService[CI Integration]
        StorageService[Storage - PostgreSQL]
        EventBus[Event Bus]
    end

    %% User Layer connections
    CLI --> API
    Console --> API
    API --> SpecificationEngine
    API --> OrchestrationCore

    %% Specification flow
    SpecificationEngine --> OrchestrationCore
    SpecKit --> SpecParser
    SpecParser --> TaskBreakdown

    %% Cross-cutting integration with Specification
    Constitution -->|governs| SpecKit
    Constitution -->|governs| QAGates
    SpecKit -->|ambiguity| Clarifier
    Clarifier -->|resolved| SpecKit

    %% Orchestration flow
    OrchestrationCore --> ExecutionLayer
    Windmill --> DAGScheduler
    DAGScheduler --> JobQueue
    JobQueue --> WorkerPool
    WorkerPool --> EngineRegistry

    %% Execution connections
    EngineRegistry --> Codex
    EngineRegistry --> OpenCode
    EngineRegistry --> ClaudeCode
    EngineRegistry --> OtherAgents

    %% QA integration with Execution
    ExecutionLayer -->|output| QAGates
    QAGates -->|passed| OrchestrationCore
    QAGates -->|failed| FeedbackLoop
    
    %% Feedback loop connections
    FeedbackLoop -->|clarify| Clarifier
    FeedbackLoop -->|re-plan| SpecificationEngine
    FeedbackLoop -->|re-schedule| OrchestrationCore
    Clarifier -->|user answer| FeedbackLoop

    %% Platform services
    OrchestrationCore --> PlatformServices
    ExecutionLayer --> PlatformServices
    CrossCutting --> PlatformServices

    style UserLayer fill:#e1f5fe
    style SpecificationEngine fill:#f3e5f5
    style OrchestrationCore fill:#fff3e0
    style ExecutionLayer fill:#e8f5e9
    style CrossCutting fill:#fce4ec
    style PlatformServices fill:#f5f5f5
```

---

## 2. Subsystem Architecture

> [!TIP]
> **Detailed Documentation Available**
> Each subsystem has its own detailed architecture document in [subsystems/](./subsystems/):
> - [01-SPECIFICATION-ENGINE.md](./subsystems/01-SPECIFICATION-ENGINE.md) - SpecKit integration, typed models
> - [02-ORCHESTRATION-CORE.md](./subsystems/02-ORCHESTRATION-CORE.md) - Windmill DAG execution
> - [03-EXECUTION-LAYER.md](./subsystems/03-EXECUTION-LAYER.md) - Multi-agent execution (18+ agents)
> - [04-QUALITY-ASSURANCE.md](./subsystems/04-QUALITY-ASSURANCE.md) - Constitutional QA gates
> - [05-PLATFORM-SERVICES.md](./subsystems/05-PLATFORM-SERVICES.md) - Database, Git, Events
> - [06-USER-INTERFACE.md](./subsystems/06-USER-INTERFACE.md) - Svelte extensions, CLI

### 2.1 Specification Engine (SpecKit Integration)

The Specification Engine manages the spec-driven development workflow, providing structured planning before code execution.

```mermaid
graph LR
    subgraph SpecificationEngine["Specification Engine"]
        direction TB
        
        subgraph Commands["Slash Commands"]
            Const["/speckit.constitution"]
            Spec["/speckit.specify"]
            Plan["/speckit.plan"]
            Tasks["/speckit.tasks"]
            Impl["/speckit.implement"]
        end

        subgraph Core["Core Components"]
            SpecifyEngine[SpecifyEngine]
            PlanGenerator[PlanGenerator]
            TaskBreakdown[TaskBreakdown]
            Clarifier[Clarifier]
        end

        subgraph Models["Typed Models"]
            FeatureSpec[FeatureSpec]
            ImplPlan[ImplementationPlan]
            TaskList[TaskList]
            Clarifications[Clarifications]
        end

        subgraph Storage["Artifact Storage"]
            SpecDir[".specify/"]
            Memory["memory/constitution.md"]
            Specs["specs/<branch>/"]
            Templates["templates/"]
            Runtime["_runtime/"]
        end
    end

    Const --> SpecifyEngine
    Spec --> SpecifyEngine
    Plan --> PlanGenerator
    Tasks --> TaskBreakdown

    SpecifyEngine -->|ambiguity| Clarifier
    PlanGenerator -->|ambiguity| Clarifier
    TaskBreakdown -->|ambiguity| Clarifier
    Clarifier --> Clarifications
    Clarifications -->|answered| SpecifyEngine
    Clarifications -->|answered| PlanGenerator
    Clarifications -->|answered| TaskBreakdown

    SpecifyEngine --> FeatureSpec
    PlanGenerator --> ImplPlan
    TaskBreakdown --> TaskList

    FeatureSpec --> Specs
    ImplPlan --> Specs
    TaskList --> Specs
    
    style Commands fill:#e8f5e9
    style Core fill:#fff3e0
    style Models fill:#e3f2fd
    style Storage fill:#f5f5f5
```

**Key Responsibilities:**
- **Constitution Management**: Project governance principles that guide all development
- **Specification Generation**: Structured feature specs with user stories
- **Planning**: Technical implementation plans with tech stack decisions
- **Task Decomposition**: Parallel-aware task breakdown with dependencies

**Directory Structure:**
```
.specify/
├── memory/
│   └── constitution.md          # Governance principles
├── templates/
│   ├── spec-template.md
│   ├── plan-template.md
│   └── tasks-template.md
└── specs/<feature-branch>/
    ├── spec.md          # Requirements
    ├── plan.md                  # Architecture
    ├── tasks.md                 # Task breakdown
    └── _runtime/                # Execution artifacts
        ├── context.md
        ├── log.md
        ├── quality-report.md
        └── runs/<run-id>/       # ⚠️ GITIGNORED
```

**Gitignore Entry:**
```gitignore
# DevGodzilla runtime artifacts (ephemeral)
specs/*/_runtime/runs/
```

---

### 2.2 Orchestration Core (WindMill-Based)

The Orchestration Core replaces Redis/RQ with Windmill's industrial-grade workflow engine.

```mermaid
graph TB
    subgraph OrchestrationCore["Orchestration Core"]
        direction TB

        subgraph WindmillEngine["Windmill Engine"]
            Server[Windmill Server - Rust]
            Workers[Worker Pool]
            Scheduler[Job Scheduler]
        end

        subgraph DAGExecution["DAG Execution"]
            DAGBuilder[DAG Builder]
            CycleDetector[Cycle Detector]
            ParallelScheduler[Parallel Scheduler]
            DependencyResolver[Dependency Resolver]
        end

        subgraph JobManagement["Job Management"]
            JobQueue[(PostgreSQL Job Queue)]
            JobTypes{{"Job Types"}}
            plan_job["plan_protocol_job"]
            exec_job["execute_step_job"]
            qa_job["run_quality_job"]
            setup_job["project_setup_job"]
            pr_job["open_pr_job"]
        end

        subgraph StateManagement["State Management"]
            ProtocolState["Protocol State"]
            StepState["Step State"]
            RunState["Run State"]
        end
    end

    Server --> Scheduler
    Scheduler --> JobQueue
    Workers --> JobQueue
    
    DAGBuilder --> CycleDetector
    CycleDetector --> ParallelScheduler
    ParallelScheduler --> DependencyResolver
    DependencyResolver --> Scheduler

    JobTypes --> plan_job
    JobTypes --> exec_job
    JobTypes --> qa_job
    JobTypes --> setup_job
    JobTypes --> pr_job

    ProtocolState --> StepState
    StepState --> RunState

    style WindmillEngine fill:#fff3e0
    style DAGExecution fill:#e8f5e9
    style JobManagement fill:#e3f2fd
    style StateManagement fill:#fce4ec
```

**Key Improvements over Redis/RQ:**
| Aspect | Redis/RQ (Current) | Windmill (New) |
|--------|-------------------|----------------|
| **Job Queue** | Redis-based | PostgreSQL-native |
| **Scalability** | Manual worker scaling | Horizontal auto-scaling |
| **Visibility** | Limited job inspection | Full job history + logs |
| **Language Support** | Python-only workers | Multi-language (Python, TS, Go, Bash) |
| **DAG Support** | Manual implementation | Native flow DAG support |
| **UI** | None (CLI only) | Built-in web UI |

**Job Status Transitions:**
```mermaid
stateDiagram-v2
    [*] --> pending: Created
    pending --> planning: start_protocol
    planning --> planned: PlanningService completes
    planned --> running: execute_next_step
    running --> running: step completed, more steps
    running --> needs_qa: step needs QA
    needs_qa --> running: QA passed
    needs_qa --> blocked: QA failed
    blocked --> running: retry/fix
    running --> completed: all steps done
    running --> failed: unrecoverable error
    planned --> cancelled: user cancels
    running --> cancelled: user cancels
    running --> paused: user pauses
    paused --> running: user resumes
```

---

### 2.3 Execution Layer (Multi-Agent Engine)

The Execution Layer manages 18+ AI coding agents with unified interface.

```mermaid
graph TB
    subgraph ExecutionLayer["Execution Layer"]
        direction TB

        subgraph EngineRegistry["Engine Registry"]
            Registry[Engine Registry]
            Resolver[Engine Resolver]
            ConfigLoader[Config Loader]
        end

        subgraph CoreEngines["Core Engines"]
            Codex[Codex Engine]
            OpenCode[OpenCode Engine]
        end

        subgraph SpecKitAgents["SpecKit Agents"]
            Claude[Claude Code]
            Gemini[Gemini CLI]
            Cursor[Cursor]
            Copilot[GitHub Copilot]
            Windsurf[Windsurf]
            Jules[Jules]
            Qoder[Qoder]
            Others[12+ More Agents]
        end

        subgraph ExecutionRuntime["Execution Runtime"]
            StepExecutor[Step Executor]
            SandboxManager[Sandbox Manager]
            OutputCapture[Output Capture]
            ArtifactWriter[Artifact Writer]
        end

        subgraph ErrorHandling["Error Handling"]
            BlockDetector[Block Detector]
            SpecError[SpecificationError]
            RetryManager[Retry Manager]
        end
    end

    Registry --> Resolver
    Resolver --> ConfigLoader
    
    Registry --> Codex
    Registry --> OpenCode
    Registry --> Claude
    Registry --> Gemini
    Registry --> Cursor
    Registry --> Copilot
    Registry --> Windsurf
    Registry --> Jules
    Registry --> Qoder
    Registry --> Others

    StepExecutor --> SandboxManager
    StepExecutor --> OutputCapture
    OutputCapture --> ArtifactWriter

    StepExecutor --> BlockDetector
    BlockDetector --> SpecError
    SpecError --> RetryManager

    style EngineRegistry fill:#e3f2fd
    style CoreEngines fill:#e8f5e9
    style SpecKitAgents fill:#fff3e0
    style ExecutionRuntime fill:#f3e5f5
    style ErrorHandling fill:#ffebee
```

**Engine Interface:**
```python
class EngineInterface(Protocol):
    """Unified interface for all AI coding agents."""
    
    @property
    def metadata(self) -> EngineMetadata:
        """Engine identification and capabilities."""
        ...
    
    def execute(self, request: EngineRequest) -> EngineResult:
        """Execute a coding task."""
        ...
    
    def check_availability(self) -> bool:
        """Check if engine is available."""
        ...
```

**Supported Agents Configuration:**
```yaml
# config/agents.yaml
agents:
  codex:
    kind: cli
    default_model: gpt-4.1
    sandbox: workspace-write
    
  opencode:
    kind: cli
    default_model: zai-coding-plan/glm-4.6
    sandbox: workspace-write
    
  claude-code:
    kind: cli
    command_dir: .claude/commands/
    default_model: claude-sonnet-4-20250514
    
  gemini-cli:
    kind: cli
    command_dir: .gemini/commands/
    format: toml
    
  cursor:
    kind: ide
    command_dir: .cursor/commands/
```

**Per-Step Agent Assignment:**
```yaml
# tasks.md or protocol config
steps:
  - name: "Create data models"
    agent: opencode        # User assigns agent
    
  - name: "Implement API routes"
    agent: claude-code     # Different agent for this step
    
  - name: "Write unit tests"
    agent: opencode        # User choice per step
```

---

### 2.4 Quality Assurance Subsystem

Constitutional QA with spec-kit checklist integration.

```mermaid
graph TB
    subgraph QASubsystem["Quality Assurance Subsystem"]
        direction TB

        subgraph QAInputs["QA Inputs"]
            StepOutput[Step Output]
            FeatureSpec[Feature Spec]
            Constitution[Constitution]
            Checklist[Checklist Template]
        end

        subgraph QAEngine["QA Engine"]
            ChecklistValidator[Checklist Validator]
            ConstitutionalGates[Constitutional Gates]
            EngineQA[Engine-based QA]
            VerdictCombiner[Verdict Combiner]
        end

        subgraph ConstitutionalArticles["Constitutional Articles"]
            Art1[Article I: Library-First]
            Art3[Article III: Test-First]
            Art7[Article VII: Simplicity]
            Art8[Article VIII: Anti-Abstraction]
            Art9[Article IX: Integration Testing]
        end

        subgraph FeedbackLoop["Feedback Loop"]
            ErrorClassifier[Error Classifier]
            ClarifyAction[Clarify Action]
            RePlanAction[Re-Plan Action]
            ReSpecifyAction[Re-Specify Action]
        end

        subgraph QAOutputs["QA Outputs"]
            QAVerdict[QA Verdict]
            QualityReport[Quality Report]
            GateResults[Gate Results]
        end
    end

    StepOutput --> ChecklistValidator
    FeatureSpec --> ChecklistValidator
    Constitution --> ConstitutionalGates
    Checklist --> ChecklistValidator

    ChecklistValidator --> VerdictCombiner
    ConstitutionalGates --> VerdictCombiner
    EngineQA --> VerdictCombiner

    ConstitutionalGates --> Art1
    ConstitutionalGates --> Art3
    ConstitutionalGates --> Art7
    ConstitutionalGates --> Art8
    ConstitutionalGates --> Art9

    VerdictCombiner --> QAVerdict
    QAVerdict -->|failed| ErrorClassifier
    QAVerdict -->|passed| QualityReport

    ErrorClassifier --> ClarifyAction
    ErrorClassifier --> RePlanAction
    ErrorClassifier --> ReSpecifyAction

    ClarifyAction -.-> SpecificationEngine
    RePlanAction -.-> OrchestrationCore
    ReSpecifyAction -.-> SpecificationEngine

    style QAInputs fill:#e3f2fd
    style QAEngine fill:#e8f5e9
    style ConstitutionalArticles fill:#fff3e0
    style FeedbackLoop fill:#ffebee
    style QAOutputs fill:#f3e5f5
```

**Feedback Loop Flow:**
```mermaid
sequenceDiagram
    participant Exec as ExecutionService
    participant QA as QualityService
    participant Plan as PlanningService
    participant Orch as OrchestratorService

    Exec->>QA: Run QA on step output
    
    alt QA Passed
        QA->>Orch: Step completed
        Orch->>Orch: Schedule next step
    else QA Failed - Clarify
        QA->>Plan: SpecificationError(clarify)
        Plan->>Plan: _clarify_and_update()
        Plan->>Orch: Updated tasks
        Orch->>Exec: Re-execute step
    else QA Failed - Re-Plan
        QA->>Plan: SpecificationError(re_plan)
        Plan->>Plan: _replan_from_step()
        Plan->>Orch: New task DAG
        Orch->>Orch: Rebuild schedule
    else QA Failed - Re-Specify
        QA->>Plan: SpecificationError(re_specify)
        Plan->>Plan: _respecify()
        Note over Plan: Requires user input
    end
```

---

### 2.5 Platform Services

Core infrastructure services for storage, Git, CI/CD, and events.

```mermaid
graph TB
    subgraph PlatformServices["Platform Services"]
        direction TB

        subgraph Storage["Storage Layer"]
            PostgreSQL[(PostgreSQL)]
            FileStorage[File Storage]
            ArtifactStore[Artifact Store]
        end

        subgraph GitIntegration["Git Integration"]
            GitService[Git Service]
            WorktreeManager[Worktree Manager]
            BranchManager[Branch Manager]
            PRService[PR Service]
        end

        subgraph CIIntegration["CI/CD Integration"]
            GitHubWebhook[GitHub Webhooks]
            GitLabWebhook[GitLab Webhooks]
            CIReporter[CI Reporter]
            AutoQA[Auto-QA Trigger]
        end

        subgraph EventSystem["Event System"]
            EventBus[Event Bus]
            EventStore[Event Store]
            Subscribers[Event Subscribers]
        end

        subgraph Observability["Observability"]
            Metrics[Prometheus Metrics]
            Logging[Structured Logging]
            Tracing[Distributed Tracing]
        end
    end

    PostgreSQL --> FileStorage
    FileStorage --> ArtifactStore

    GitService --> WorktreeManager
    GitService --> BranchManager
    BranchManager --> PRService

    GitHubWebhook --> CIReporter
    GitLabWebhook --> CIReporter
    CIReporter --> AutoQA

    EventBus --> EventStore
    EventBus --> Subscribers

    Metrics --> Logging
    Logging --> Tracing

    style Storage fill:#e3f2fd
    style GitIntegration fill:#e8f5e9
    style CIIntegration fill:#fff3e0
    style EventSystem fill:#f3e5f5
    style Observability fill:#fce4ec
```

**Database Schema Extensions:**
```sql
-- Extended for Windmill integration
ALTER TABLE protocol_runs ADD COLUMN windmill_flow_id UUID;
ALTER TABLE protocol_runs ADD COLUMN speckit_metadata JSONB;

-- DAG support for steps
ALTER TABLE step_runs ADD COLUMN depends_on JSONB DEFAULT '[]';
ALTER TABLE step_runs ADD COLUMN parallel_group VARCHAR(100);

-- Constitution tracking
ALTER TABLE projects ADD COLUMN constitution_version VARCHAR(50);
ALTER TABLE projects ADD COLUMN constitution_hash VARCHAR(64);

-- Feedback tracking
CREATE TABLE feedback_events (
    id SERIAL PRIMARY KEY,
    protocol_run_id INTEGER REFERENCES protocol_runs(id),
    step_run_id INTEGER REFERENCES step_runs(id),
    error_type VARCHAR(50),
    action_taken VARCHAR(50),
    attempt_number INTEGER,
    context JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);
```

---

### 2.6 User Interface Layer

Extends Windmill's existing Svelte frontend with DevGodzilla-specific features.

```mermaid
graph TB
    subgraph UILayer["User Interface Layer"]
        direction TB

        subgraph WindmillBase["Windmill Frontend (Base)"]
            WMDashboard[Dashboard]
            WMFlows[Flow Editor]
            WMScripts[Script Editor]
            WMJobs[Job Viewer]
            WMLogs[Log Viewer]
        end

        subgraph CoreExtensions["Core DevGodzilla Extensions"]
            SpecEditor[Specification Editor]
            ConstitutionEditor[Constitution Editor]
            DAGViewer[Task DAG Viewer]
            QADashboard[QA Dashboard]
        end

        subgraph WorkflowExtensions["Workflow Extensions"]
            AgentSelector[Agent Selector]
            FeedbackPanel[Feedback Panel]
            UserStoryTracker[User Story Tracker]
            ClarificationChat[Clarification Chat]
            ChecklistViewer[Checklist Viewer]
            RunArtifactViewer[Run Artifact Viewer]
        end

        subgraph ConfigExtensions["Config & Setup Extensions"]
            ProjectOnboarding[Project Onboarding]
            AgentConfigMgr[Agent Config Manager]
            TemplateManager[Template Manager]
        end

        subgraph CLI["CLI (Click-based)"]
            MainCLI[Main CLI Entry]
            ProjectCmds[Project Commands]
            ProtocolCmds[Protocol Commands]
            SpecKitCmds[SpecKit Commands]
        end

        subgraph RESTAPI["REST API (FastAPI)"]
            ProjectsAPI["/projects"]
            ProtocolsAPI["/protocols"]
            StepsAPI["/steps"]
            SpecKitAPI["/speckit"]
            AgentsAPI["/agents"]
        end
    end

    WindmillBase --> CoreExtensions
    WindmillBase --> WorkflowExtensions
    
    WMFlows --> DAGViewer
    WMFlows --> AgentSelector
    WMScripts --> SpecEditor
    WMScripts --> TemplateManager
    WMJobs --> QADashboard
    WMJobs --> RunArtifactViewer
    WMLogs --> FeedbackPanel
    WMDashboard --> ProjectOnboarding
    WMDashboard --> UserStoryTracker

    MainCLI --> ProjectCmds
    MainCLI --> ProtocolCmds
    MainCLI --> SpecKitCmds

    style WindmillBase fill:#fff3e0
    style CoreExtensions fill:#e8f5e9
    style WorkflowExtensions fill:#e3f2fd
    style ConfigExtensions fill:#f3e5f5
    style CLI fill:#fce4ec
    style RESTAPI fill:#fffde7
```

**Windmill Frontend Extensions:**

| Extension | Purpose | Integrates With |
|-----------|---------|----------------|
| **Specification Editor** | Edit spec.md, plan.md, tasks.md | Script Editor |
| **Constitution Editor** | Manage project governance rules | Settings |
| **Agent Selector** | Assign AI agents per step | Flow Editor |
| **Task DAG Viewer** | Visualize step dependencies | Flow Editor |
| **QA Dashboard** | View constitutional gate results | Job Viewer |
| **Feedback Panel** | Handle SpecificationError loops | Job Viewer |

**Additional Extensions (from codebase analysis):**

| Extension | Purpose | Source |
|-----------|---------|--------|
| **User Story Tracker** | Track [US1], [US2] phases from tasks.md template | SpecKit tasks-template.md |
| **Clarification Chat** | Protocol Q&A interface | Existing TasksGodzilla |
| **Project Onboarding** | Wizard for project setup + .specify/ init | Existing OnboardingService |
| **Agent Config Manager** | Configure 18+ agent integrations | SpecKit AGENTS.md |
| **Checklist Viewer** | Display /speckit.checklist results | SpecKit checklist-template.md |
| **Run Artifact Viewer** | View step run logs, outputs, diffs | Existing runs/steps features |
| **Template Manager** | Manage spec-template.md, plan-template.md | SpecKit templates/ |

**Extension Architecture:**
```
windmill/frontend/src/
├── lib/
│   └── devgodzilla/                    # DevGodzilla extension modules
│       ├── SpecificationEditor.svelte
│       ├── ConstitutionEditor.svelte
│       ├── AgentSelector.svelte
│       ├── TaskDAGViewer.svelte
│       ├── QADashboard.svelte
│       ├── FeedbackPanel.svelte
│       ├── UserStoryTracker.svelte  # NEW: Phase/story progress
│       ├── ClarificationChat.svelte  # NEW: Q&A interface
│       ├── ProjectOnboarding.svelte  # NEW: Setup wizard
│       ├── AgentConfigManager.svelte # NEW: 18+ agents config
│       ├── ChecklistViewer.svelte    # NEW: QA checklists
│       ├── RunArtifactViewer.svelte  # NEW: Logs/outputs/diffs
│       └── TemplateManager.svelte    # NEW: Template editing
├── routes/
│   └── devgodzilla/                    # DevGodzilla routes
│       ├── +page.svelte             # DevGodzilla dashboard
│       ├── specifications/
│       ├── protocols/
│       ├── quality/
│       ├── onboarding/              # NEW: /devgodzilla/onboarding
│       └── agents/                  # NEW: /devgodzilla/agents
└── stores/
    └── devgodzilla.ts                  # DevGodzilla state management
```

**UI Feature Mapping (Existing → New):**

| Existing React Feature | New Svelte Extension |
|------------------------|---------------------|
| `ProtocolDetailPage.tsx` tabs (Steps, Events, Runs, Spec, Policy, Clarifications) | Integrated into Windmill Flow Viewer with DevGodzilla tabs |
| `StepDetailPage.tsx` (Run Step, Run QA, Approve) | AgentSelector + QADashboard actions |
| `ProtocolsNewPage.tsx` (create protocol) | ProjectOnboarding + SpecificationEditor |
| Steps list with dependencies | TaskDAGViewer |
| Policy findings | ConstitutionEditor + QADashboard |

---

## 3. End-to-End Workflow

### 3.1 Complete Development Workflow

```mermaid
sequenceDiagram
    participant User
    participant CLI/Console
    participant API
    participant SpecEngine as Specification Engine
    participant Windmill as Windmill Orchestrator
    participant Executor as Execution Layer
    participant QA as Quality Service
    participant Git as Git Service

    rect rgb(230, 245, 255)
        Note over User,Git: Phase 1: Project Setup
        User->>CLI/Console: Create project
        CLI/Console->>API: POST /projects
        API->>Git: Clone/init repository
        API->>SpecEngine: Initialize .specify/
        SpecEngine->>SpecEngine: Create constitution.md
        API-->>User: Project created
    end

    rect rgb(255, 243, 224)
        Note over User,Git: Phase 2: Specification
        User->>CLI/Console: /speckit.specify "Add auth feature"
        CLI/Console->>SpecEngine: Generate specification
        SpecEngine->>SpecEngine: Create spec.md
        User->>CLI/Console: /speckit.plan "Use FastAPI + PostgreSQL"
        CLI/Console->>SpecEngine: Generate plan
        SpecEngine->>SpecEngine: Create plan.md
        User->>CLI/Console: /speckit.tasks
        CLI/Console->>SpecEngine: Generate task breakdown
        SpecEngine->>SpecEngine: Create tasks.md with deps
    end

    rect rgb(232, 245, 233)
        Note over User,Git: Phase 3: Orchestration
        User->>CLI/Console: Start protocol
        CLI/Console->>API: POST /protocols/{id}/actions/start
        API->>Windmill: Create workflow from tasks.md
        Windmill->>Windmill: Build execution DAG
        Windmill->>Windmill: Validate (no cycles)
        Windmill-->>API: DAG ready
    end

    rect rgb(243, 229, 245)
        Note over User,Git: Phase 4: Execution
        loop For each ready step
            Windmill->>Executor: Execute step
            Executor->>Executor: Select engine
            Executor->>Executor: Run code generation
            Executor->>QA: Run quality checks
            alt QA Passed
                QA->>Windmill: Step completed
                Windmill->>Windmill: Mark dependencies satisfied
            else QA Failed
                QA->>SpecEngine: Feedback loop
                SpecEngine->>Windmill: Updated tasks
            end
        end
    end

    rect rgb(252, 228, 236)
        Note over User,Git: Phase 5: Completion
        Windmill->>Git: Commit changes
        Windmill->>Git: Create PR
        Git-->>User: PR ready for review
    end
```

### 3.2 DAG Execution Flow

```mermaid
graph LR
    subgraph DAGExecution["DAG Execution Example"]
        T1[Task 1: Create Models]
        T2[Task 2: Create Services]
        T3[Task 3: Create API Routes]
        T4[Task 4: Write Unit Tests]
        T5[Task 5: Integration Tests]
        T6[Task 6: Documentation]
        
        T1 --> T2
        T1 --> T4
        T2 --> T3
        T2 --> T5
        T3 --> T5
        T4 --> T5
        T5 --> T6
    end

    subgraph ParallelGroups["Parallel Execution Groups"]
        G1["Group 1: T1"]
        G2["Group 2: T2, T4 (parallel)"]
        G3["Group 3: T3"]
        G4["Group 4: T5"]
        G5["Group 5: T6"]
        
        G1 --> G2
        G2 --> G3
        G3 --> G4
        G4 --> G5
    end
```

### 3.3 Cross-Cutting Services Integration

The Constitution Manager, Clarifier Service, and QA Gates form an integrated loop that operates across all phases:

```mermaid
graph TB
    subgraph CrossCuttingFlow["Cross-Cutting Services Workflow"]
        direction TB
        
        subgraph Constitution["Constitution Manager"]
            ConstitutionFile[constitution.md]
            PolicyPack[Policy Pack]
            ArticleGates[Article Gates]
        end

        subgraph Clarifier["Clarifier Service"]
            AmbiguityDetector[Ambiguity Detector]
            QuestionGenerator[Question Generator]
            AnswerStore[Answer Store]
        end

        subgraph QA["Quality Assurance"]
            GateRunner[Gate Runner]
            ChecklistValidator[Checklist Validator]
            VerdictEngine[Verdict Engine]
        end

        subgraph Feedback["Feedback Loop"]
            ErrorClassifier[Error Classifier]
            ActionRouter[Action Router]
        end
    end

    ConstitutionFile --> ArticleGates
    PolicyPack --> ArticleGates
    ArticleGates -->|enforce| GateRunner

    AmbiguityDetector --> QuestionGenerator
    QuestionGenerator --> AnswerStore
    AnswerStore -->|context| AmbiguityDetector

    GateRunner --> ChecklistValidator
    ChecklistValidator --> VerdictEngine
    VerdictEngine -->|passed| Done[Continue Workflow]
    VerdictEngine -->|failed| ErrorClassifier

    ErrorClassifier --> ActionRouter
    ActionRouter -->|clarify| AmbiguityDetector
    ActionRouter -->|re-plan| ReSpec[Re-Specification]
    ActionRouter -->|retry| Retry[Retry Step]

    style Constitution fill:#e8f5e9
    style Clarifier fill:#e3f2fd
    style QA fill:#fce4ec
    style Feedback fill:#fff3e0
```

**Integration Points by Phase:**

| Phase | Constitution | Clarifier | QA |
|-------|--------------|-----------|-----|
| **Specify** | Validates spec against articles | Resolves ambiguous requirements | Pre-validates spec structure |
| **Plan** | Checks tech decisions against policies | Resolves technical choices | Validates plan completeness |
| **Tasks** | Ensures task structure compliance | Resolves scope questions | Validates task dependencies |
| **Execute** | N/A (already validated) | N/A (execution phase) | Validates step output |
| **QA** | Enforces constitutional gates | Generates clarification for failures | Full quality assessment |
| **Feedback** | Guides re-planning constraints | Handles user clarification answers | Triggers based on QA verdict |

**Detailed Workflow:**

```mermaid
sequenceDiagram
    participant User
    participant Spec as Specification Engine
    participant Const as Constitution Manager
    participant Clarify as Clarifier Service
    participant Orch as Orchestrator
    participant Exec as Execution Layer
    participant QA as QA Gates

    Note over User,QA: Phase: Specification with Constitution + Clarification
    
    User->>Spec: /speckit.specify "Add OAuth login"
    Spec->>Const: Load constitution.md
    Const-->>Spec: Articles I-X
    Spec->>Spec: Generate spec with constraints
    
    alt Ambiguity Detected
        Spec->>Clarify: detect_ambiguity(context)
        Clarify->>User: "OAuth provider: Google, GitHub, or both?"
        User->>Clarify: "Both"
        Clarify->>Spec: inject_answer(provider=both)
    end
    
    Spec->>Const: validate_spec(spec)
    alt Article Violation
        Const-->>Spec: Warning: Article VII (complexity)
        Spec->>User: Show warning, continue
    end
    
    Spec-->>User: FeatureSpec created

    Note over User,QA: Phase: Execution with QA + Feedback Loop
    
    User->>Orch: Start protocol
    Orch->>Exec: Execute step T001
    Exec-->>QA: Step output
    
    QA->>Const: Load constitutional gates
    Const-->>QA: Active gates (III, IV, IX)
    
    QA->>QA: Run gates + checklist
    
    alt QA Passed
        QA-->>Orch: Step completed
        Orch->>Orch: Mark T001 done, schedule T002
    else QA Failed (needs clarification)
        QA->>Clarify: generate_question(failure_context)
        Clarify->>User: "Missing tests - defer or block?"
        User->>Clarify: "Block"
        Clarify->>Orch: Update step policy
        Orch->>Exec: Retry with updated context
    else QA Failed (needs re-plan)
        QA->>Spec: trigger_replan(step, error)
        Spec->>Spec: Generate updated tasks
        Spec->>Orch: Replace remaining DAG
        Orch->>Exec: Continue with new plan
    end
```

---

## 4. Integration Points

### 4.1 SpecKit ↔ Windmill Integration

```mermaid
graph LR
    subgraph SpecKit["SpecKit Output"]
        TasksMD["tasks.md"]
        Dependencies["[DEPENDS: task-id]"]
        Parallel["[PARALLEL] markers"]
    end

    subgraph Adapter["Integration Adapter"]
        Parser["Task Parser"]
        DAGBuilder["DAG Builder"]
        FlowGenerator["Windmill Flow Generator"]
    end

    subgraph Windmill["Windmill Input"]
        Flow["Windmill Flow"]
        Steps["Flow Steps"]
        Branches["Parallel Branches"]
    end

    TasksMD --> Parser
    Dependencies --> DAGBuilder
    Parallel --> DAGBuilder
    Parser --> DAGBuilder
    DAGBuilder --> FlowGenerator
    FlowGenerator --> Flow
    Flow --> Steps
    Flow --> Branches
```

### 4.2 Service Layer Mapping

| Current Service | Role (current) | Integration |
|-----------------|----------|-------------|
| `SpecificationService` | Speckit-style artifacts | Writes `.specify/` (constitution, templates, spec/plan/tasks markdown) |
| `PlanningService` | Protocol planning | Parses protocol specs and creates step DAG; can generate Windmill flows |
| `ExecutionService` | Uses Engine Registry | Multi-agent dispatch |
| `QualityService` | Constitutional QA | Constitution + gates (lint/type/tests today; checklist integration is planned) |
| `OrchestratorService` | Windmill adapter | DAG → Flow conversion |
| `OnboardingService` | Project setup | `.specify/` initialization (when onboarding is enabled) |
| `PolicyService` | Constitution reader | Bidirectional sync |

---

## 5. Technology Stack

```mermaid
graph TB
    subgraph Frontend["Frontend (Windmill + Extensions)"]
        Svelte[Svelte]
        WindmillUI[Windmill UI Components]
        DevGodzillaExt[DevGodzilla Extensions]
    end

    subgraph Backend["Backend"]
        FastAPI[FastAPI - Python]
        Windmill[Windmill Server - Rust]
        Workers[Python Workers]
    end

    subgraph Storage["Storage"]
        PostgreSQL[(PostgreSQL)]
        FileSystem[Local File System]
    end

    subgraph AIEngines["AI Engines"]
        SpecKit[SpecKit Library]
        Codex[OpenAI Codex]
        Claude[Anthropic Claude]
        OpenCode[OpenCode]
    end

    subgraph Infrastructure["Infrastructure"]
        Docker[Docker Compose]
        K8s[Kubernetes]
        Caddy[Caddy Reverse Proxy]
    end

    Frontend --> Backend
    Backend --> Storage
    Backend --> AIEngines
    Backend --> Infrastructure
```

---

## 6. Migration Strategy

### Phase 1: Foundation (Week 1-2)
- [ ] Add SpecKit as Python library dependency
- [ ] Verify library imports and typed models
- [ ] Set up Windmill infrastructure

### Phase 2: Planning Refactoring (Week 3-4)
- [ ] Rewrite `PlanningService` with SpecKit library
- [ ] Delete `DecompositionService` (merged)
- [ ] Delete `SpecService` (merged)

### Phase 3: Orchestration Migration (Week 5-6)
- [ ] Implement Windmill adapter in `OrchestratorService`
- [ ] Migrate from Redis/RQ to Windmill job queue
- [ ] Implement DAG execution with cycle detection

### Phase 4: Execution & QA (Week 7-8)
- [ ] Extend Engine Registry with SpecKit agents
- [ ] Implement Constitutional QA gates
- [ ] Add feedback loop handlers

### Phase 5: UI & Polish (Week 9-10)
- [ ] Update Web Console for new workflow
- [ ] Add DAG visualization
- [ ] Create integrated documentation

---

## 7. Verification Plan

### Automated Tests
```bash
# Unit tests
pytest tests/services/test_planning.py -v
pytest tests/services/test_orchestrator.py -v
pytest tests/services/test_quality.py -v

# Integration tests
pytest tests/integration/test_speckit_workflow.py -v
pytest tests/integration/test_windmill_dag.py -v

# E2E tests
./scripts/test_e2e.sh
```

### Manual Verification
1. Create new project via CLI
2. Run `/speckit.specify`, `/speckit.plan`, `/speckit.tasks`
3. Start protocol and observe DAG execution
4. Verify feedback loops work on intentional failures
5. Check Windmill UI for job visibility

---

## Open Questions

~~1. WindMill's AGPLv3 license - any concerns for your use case?~~
   **RESOLVED**: Open source solution, license compatible.

~~2. Is SpecKit available as a Python library, or CLI only?~~
   **RESOLVED**: DevGodzilla will be available as both Python library AND CLI.

~~3. Preferred agent selection priority when multiple are available?~~
   **RESOLVED**: User explicitly assigns agent per step. No auto-selection priority.

~~4. Should `_runtime/runs/` be gitignored?~~
   **RESOLVED**: Yes, `_runtime/runs/` is gitignored (ephemeral execution data).

~~5. Offline mode / fallbacks?~~
   **RESOLVED**: No offline mode. No fallbacks. No backward compatibility.

---

## Summary

This architecture combines:

- **SpecKit's specification-driven methodology** for structured, AI-assisted planning
- **Windmill's industrial workflow engine** for scalable, observable job execution
- **TasksGodzilla's multi-agent execution layer** with feedback loops

The result is **DevGodzilla**: a unified platform for AI-driven software development with proper orchestration, quality gates, and self-healing capabilities through specification feedback loops.

---

## Related Documentation

| Document | Description |
|----------|-------------|
| [API-ARCHITECTURE.md](./API-ARCHITECTURE.md) | Detailed REST API specification |
| [subsystems/README.md](./subsystems/README.md) | Subsystem documentation index |
| [subsystems/01-SPECIFICATION-ENGINE.md](./subsystems/01-SPECIFICATION-ENGINE.md) | SpecKit integration details |
| [subsystems/02-ORCHESTRATION-CORE.md](./subsystems/02-ORCHESTRATION-CORE.md) | Windmill workflow engine |
| [subsystems/03-EXECUTION-LAYER.md](./subsystems/03-EXECUTION-LAYER.md) | Multi-agent execution (18+ agents) |
| [subsystems/04-QUALITY-ASSURANCE.md](./subsystems/04-QUALITY-ASSURANCE.md) | Constitutional QA gates |
| [subsystems/05-PLATFORM-SERVICES.md](./subsystems/05-PLATFORM-SERVICES.md) | Database, Git, Events |
| [subsystems/06-USER-INTERFACE.md](./subsystems/06-USER-INTERFACE.md) | Svelte UI + CLI |
