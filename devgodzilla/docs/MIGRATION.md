# TasksGodzilla to DevGodzilla Migration Guide

> Guide for migrating from TasksGodzilla to DevGodzilla

---

## Overview

DevGodzilla is the next-generation evolution of TasksGodzilla, featuring:

- **SpecKit Integration** - Spec-driven development workflow
- **Windmill Orchestration** - Industrial-grade workflow management
- **Multi-Agent Execution** - 18+ AI coding agent support
- **DAG-based Execution** - Parallel step execution with dependencies

---

## Key Differences

| Feature | TasksGodzilla | DevGodzilla |
|---------|---------------|-------------|
| Workflow Engine | Custom | Windmill |
| Spec Format | Ad-hoc | SpecKit (.specify/) |
| Agents | Codex only | 18+ agents |
| Execution | Sequential | DAG-parallel |
| CLI | Basic | Full Click-based |
| API | Partial | Full REST API |

---

## Migration Steps

### 1. Database Migration

DevGodzilla uses an enhanced schema. Run the Alembic migration:

```bash
cd devgodzilla
alembic upgrade head
```

**New Tables:**
- `feedback_events` - Tracks retry/replan events

**New Columns:**
- `protocol_runs.windmill_flow_id` - Windmill integration
- `protocol_runs.speckit_metadata` - SpecKit tracking
- `step_runs.depends_on` - DAG dependencies
- `step_runs.parallel_group` - Parallel execution groups
- `projects.constitution_version` - Constitution tracking
- `projects.constitution_hash` - Constitution integrity

### 2. Configuration Migration

Move from environment variables to YAML configuration:

```bash
# Old (TasksGodzilla)
export CODEX_MODEL=gpt-4

# New (DevGodzilla)
# Edit devgodzilla/config/agents.yaml
```

### 3. CLI Command Changes

| Old Command | New Command |
|-------------|-------------|
| `tasksgodzilla run` | `devgodzilla protocol start` |
| `tasksgodzilla status` | `devgodzilla protocol status` |
| N/A | `devgodzilla spec init` |
| N/A | `devgodzilla spec specify` |

### 4. API Endpoint Changes

| Old Endpoint | New Endpoint |
|--------------|--------------|
| `/runs` | `/protocols` |
| `/runs/{id}/start` | `/protocols/{id}/actions/start` |
| N/A | `/speckit/init` |
| N/A | `/speckit/specify` |

### 5. SpecKit Initialization

Initialize SpecKit for each project:

```bash
cd your-project
devgodzilla spec init .
```

This creates:
```
.specify/
├── memory/
│   └── constitution.md
├── templates/
│   ├── spec-template.md
│   ├── plan-template.md
│   └── tasks-template.md
└── specs/
```

### 6. Constitution Setup

Edit `.specify/memory/constitution.md` with your project rules:

```markdown
# Project Constitution

## Core Values
1. Safety First
2. Library First
3. Test Driven

## Quality Gates
- All code must pass linting
- Tests must pass before merge
```

---

## Rollback Plan

If you need to rollback:

```bash
# Downgrade database
alembic downgrade -1

# Use old CLI (if still installed)
tasksgodzilla run
```

---

## Support

For migration issues:
1. Check logs: `~/.devgodzilla/logs/`
2. Create an issue on GitHub
3. Contact the DevGodzilla team
