# DevGodzilla Architecture Review Report

> **Date**: 2025-12-15
> **Status**: Review Completed
> **Scope**: `docs/newTasksGodzilla/` (Implementation Plan, API Architecture, Subsystems 01-06)

---

## 1. Executive Summary

The proposed DevGodzilla architecture is robust, well-structured, and leverages modern patterns (Spec-Driven Development, Constitutional AI, Windmill Orchestration). The integration of SpecKit for requirements and Windmill for execution is a strong design choice.

However, several critical gaps exist in **security (secrets management)**, **state synchronization**, **agent networking**, and **scalability (QA context limits)**. Addressing these before full implementation will prevent significant technical debt.

---

## 2. Identified Gaps & "Missings"

### 2.1 Security & Secrets Management
- **Issue**: The data model (`05-PLATFORM-SERVICES`) mentions an `encrypted` secrets column in the `projects` table, but the implementation detail is missing.
- **Risk**: Storing secrets (API keys, GitHub tokens) without a defined encryption strategy (e.g., KMS, Vault, or Fernet) is a security vulnerability.
- **Missing**: A dedicated `SecretManager` service or integration with Windmill's secret management.

### 2.2 State Synchronization (Split-Brain Risk)
- **Issue**: There are two sources of truth for execution state:
    1.  **DevGodzilla DB** (`protocol_runs`, `step_runs`)
    2.  **Windmill DB** (Flow runs, Job status)
- **Risk**: If a Windmill job completes but the callback/update to DevGodzilla fails, the system enters an inconsistent state.
- **Missing**: A defined reconciliation mechanism (e.g., periodic sync job) or a strictly event-driven state machine that handles idempotency.

### 2.3 Agent Sandbox & Networking
- **Issue**: `nsjail` is proposed for sandboxing.
    1.  **Complexity**: `nsjail` configuration is non-trivial and OS-specific.
    2.  **Dependencies**: Agents often need to download libraries (`pip install`, `npm install`). The "network-restricted" mode might break this.
- **Missing**: A clear "Pre-flight" phase for dependency resolution with network access before entering the restricted execution sandbox. Alternatively, considered `Docker` based sandboxing for better isolation and ease of use.

### 2.4 QA Context Limits
- **Issue**: The QA subsystem (`04-QUALITY-ASSURANCE`) sends "Artifacts + Step Output" to the LLM.
- **Risk**: For large files or large projects, this will rapidly exceed token limits (8k/32k/128k), causing QA failures or huge costs.
- **Missing**: A Context Pruning / RAG strategy for QA to select only relevant code snippets for the specific checklist item being validated.

### 2.5 Authentication & UI Integration
- **Issue**: `API-ARCHITECTURE.md` describes a standalone FastAPI app (port 8011), while `06-USER-INTERFACE` describes Svelte components within Windmill.
- **Gap**: How does the Windmill frontend authenticate with the DevGodzilla API? Cross-Origin Resource Sharing (CORS) and shared session management are not detailed.

---

## 3. Recommended Improvements

### 3.1 Architecture Refinements

#### Use Windmill for Secrets
Instead of building a custom `secrets` column, leverage Windmill's built-in **Variables & Secrets** management.
- **Change**: `AgentAdapter` should pull secrets via Windmill's hook rather than DevGodzilla DB.

#### "Smart" Context for QA
Implement a lightweight RAG (Retrieval-Augmented Generation) for the QA layer.
- **Change**: Instead of dumping `artifact.read_text()`, index artifacts (e.g., using `chromadb` or simple vector search) and retrieve top-k chunks relevant to the Checklist Item description.

#### Hybrid Sandboxing
Relax `nsjail` strictness for a "Setup" phase.
- **Change**:
    1.  **Setup Phase** (Network: ON, FS: Write): Install dependencies.
    2.  **Execution Phase** (Network: OFF/Whitelisted, FS: Write): Run agent code generation.

### 3.2 Missing Components to Add

1.  **`ReconciliationService`**: A background worker that compares Windmill Job statuses with DevGodzilla `step_runs` and fixes inconsistencies.
2.  **`TelemetryService`**: Explicit OpenTelemetry integration (traces) to visualize the flow across API -> Orchestrator -> Windmill -> Agent.
3.  **`DependencyManager`**: A platform service to detect and install project dependencies before agents run, ensuring the environment is "primed".

---

## 4. Documentation Inconsistencies

- **Port Numbers**: `API-ARCHITECTURE.md` mentions port `8011`, but Windmill usually runs on `8000`. Need to clarify if DevGodzilla runs *inside* Windmill workers or as a sidecar.
- **Clarification Flow**: `01-SPECIFICATION` mentions `ClarifierService` store, `04-QUALITY` mentions `FeedbackRouter`. Ensure circular dependencies between Planning and Quality services are handled (e.g., via Event Bus decoupling).

---

## 5. Conclusion

The foundation is solid. Prioritize **Secrets Management** and **State Reconciliation** in Phase 1 to avoid rewriting the core later. The **QA Context** issue can be addressed in Phase 5 but should be designed for (RAG) now.
