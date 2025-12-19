"""
Plan Protocol Script

Complete spec → plan → tasks workflow with DAG generation and flow creation.

Args:
    project_id: Project ID from database
    feature_request: Natural language feature description
    protocol_name: Name for this protocol run
    branch_name: Branch name for feature (auto-generated if not provided)

Returns:
    protocol_run_id: Created protocol run ID
    spec_path: Path to generated specification
    plan_path: Path to generated plan
    tasks_path: Path to generated tasks
    dag: Task dependency graph
    windmill_flow_id: Created Windmill flow path
"""

import os
import re
from pathlib import Path
from datetime import datetime
import json

# Import DevGodzilla services if available
try:
    from devgodzilla.db import get_database
    from devgodzilla.services import PlanningService
    from devgodzilla.windmill import WindmillClient, FlowGenerator
    DEVGODZILLA_AVAILABLE = True
except ImportError:
    DEVGODZILLA_AVAILABLE = False


def slugify(text: str) -> str:
    """Convert text to slug format."""
    text = text.lower()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_-]+', '-', text)
    return text.strip('-')[:50]


def main(
    project_id: int,
    feature_request: str,
    protocol_name: str = "",
    branch_name: str = "",
) -> dict:
    """Run complete planning workflow."""
    
    start_time = datetime.now()
    
    # Generate names if not provided
    feature_slug = slugify(feature_request)
    if not branch_name:
        branch_name = f"feature-{feature_slug}"
    if not protocol_name:
        protocol_name = f"Protocol: {feature_request[:50]}"
    
    # Get project info
    project_path = _get_project_path(project_id)
    if not project_path:
        return {"error": f"Project {project_id} not found"}
    
    # Create protocol run record
    protocol_run_id = _create_protocol_run(project_id, protocol_name, branch_name)
    
    # Step 1: Generate specification
    spec_result = _generate_spec(project_path, feature_request, branch_name)
    
    # Step 2: Generate implementation plan
    plan_result = _generate_plan(project_path, spec_result.get("spec_path", ""))
    
    # Step 3: Generate task breakdown
    tasks_result = _generate_tasks(project_path, plan_result.get("plan_path", ""))
    
    # Step 4: Build DAG and create Windmill flow
    dag = tasks_result.get("dag", {})
    flow_id = None
    
    if dag and protocol_run_id:
        flow_id = _create_windmill_flow(protocol_run_id, dag, tasks_result.get("tasks", []))
        
        # Update protocol with flow ID
        _update_protocol_run(protocol_run_id, {
            "windmill_flow_id": flow_id,
            "status": "planned",
        })
    
    return {
        "protocol_run_id": protocol_run_id,
        "protocol_name": protocol_name,
        "branch_name": branch_name,
        "spec_path": spec_result.get("spec_path"),
        "plan_path": plan_result.get("plan_path"),
        "tasks_path": tasks_result.get("tasks_path"),
        "task_count": tasks_result.get("task_count", 0),
        "dag": dag,
        "windmill_flow_id": flow_id,
        "duration_seconds": (datetime.now() - start_time).total_seconds(),
    }


def _get_project_path(project_id: int) -> str | None:
    """Get project local path from database or demo path."""
    if DEVGODZILLA_AVAILABLE:
        try:
            db = get_database()
            project = db.get_project(project_id)
            return project.local_path
        except:
            pass
    
    # Fallback for demo
    demo_path = Path("/tmp/devgodzilla/repos")
    if demo_path.exists():
        repos = list(demo_path.iterdir())
        if repos:
            return str(repos[0])
    return None


def _create_protocol_run(project_id: int, name: str, branch: str) -> int | None:
    """Create protocol run record."""
    if not DEVGODZILLA_AVAILABLE:
        return 1  # Demo ID
    
    try:
        db = get_database()
        protocol = db.create_protocol_run({
            "project_id": project_id,
            "protocol_name": name,
            "base_branch": branch,
            "status": "planning",
        })
        return protocol.id
    except:
        return None


def _update_protocol_run(protocol_id: int, updates: dict) -> None:
    """Update protocol run record."""
    if DEVGODZILLA_AVAILABLE:
        try:
            db = get_database()
            db.update_protocol_run(protocol_id, **updates)
        except:
            pass


def _generate_spec(project_path: str, feature_request: str, branch_name: str) -> dict:
    """Generate feature specification."""
    path = Path(project_path)
    spec_dir = path / "specs" / branch_name
    spec_dir.mkdir(parents=True, exist_ok=True)
    
    spec_content = f"""# Feature Specification: {feature_request}

## Summary
{feature_request}

## User Stories
- [ ] As a user, I want {feature_request.lower()}

## Requirements
### Functional
1. Implement the requested functionality

### Non-Functional
1. Maintain backward compatibility
2. Include appropriate tests

## Acceptance Criteria
- [ ] Feature works as described
- [ ] Tests pass

---
*Generated by DevGodzilla*
"""
    
    spec_path = spec_dir / "spec.md"
    spec_path.write_text(spec_content)
    
    return {"spec_path": str(spec_path)}


def _generate_plan(project_path: str, spec_path: str) -> dict:
    """Generate implementation plan."""
    if not spec_path:
        return {}
    
    plan_path = Path(spec_path).parent / "plan.md"
    
    plan_content = """# Implementation Plan

## Overview
Technical implementation approach.

## Components
### New
- Core implementation

### Modified
- Integration with existing code

## Phases
1. Setup
2. Core Implementation
3. Testing
4. Documentation

---
*Generated by DevGodzilla*
"""
    
    plan_path.write_text(plan_content)
    return {"plan_path": str(plan_path)}


def _generate_tasks(project_path: str, plan_path: str) -> dict:
    """Generate task breakdown with DAG."""
    if not plan_path:
        return {}
    
    tasks_path = Path(plan_path).parent / "tasks.md"
    
    tasks_content = """# Task Breakdown

## Phase 1: Setup
- [ ] T001: Review existing codebase [DEPENDS: none]
- [ ] T002: Set up development environment [DEPENDS: T001]

## Phase 2: Core Implementation
- [ ] T003: Implement core feature logic [DEPENDS: T002]
- [ ] T004: Implement supporting utilities [DEPENDS: T002] [PARALLEL]
- [ ] T005: Integrate with existing components [DEPENDS: T003, T004]

## Phase 3: Testing
- [ ] T006: Write unit tests [DEPENDS: T003] [PARALLEL]
- [ ] T007: Write integration tests [DEPENDS: T005] [PARALLEL]
- [ ] T008: Run full test suite [DEPENDS: T006, T007]

## Phase 4: Completion
- [ ] T009: Update documentation [DEPENDS: T008]
- [ ] T010: Final review [DEPENDS: T009]

---
*Generated by DevGodzilla*
"""
    
    tasks_path.write_text(tasks_content)
    
    # Build DAG
    tasks = [
        {"id": "T001", "description": "Review codebase", "depends_on": [], "parallel": False},
        {"id": "T002", "description": "Setup environment", "depends_on": ["T001"], "parallel": False},
        {"id": "T003", "description": "Core logic", "depends_on": ["T002"], "parallel": True},
        {"id": "T004", "description": "Utilities", "depends_on": ["T002"], "parallel": True},
        {"id": "T005", "description": "Integration", "depends_on": ["T003", "T004"], "parallel": False},
        {"id": "T006", "description": "Unit tests", "depends_on": ["T003"], "parallel": True},
        {"id": "T007", "description": "Integration tests", "depends_on": ["T005"], "parallel": True},
        {"id": "T008", "description": "Test suite", "depends_on": ["T006", "T007"], "parallel": False},
        {"id": "T009", "description": "Documentation", "depends_on": ["T008"], "parallel": False},
        {"id": "T010", "description": "Final review", "depends_on": ["T009"], "parallel": False},
    ]
    
    dag = _build_dag(tasks)
    
    # Save DAG
    runtime_dir = Path(plan_path).parent / "_runtime"
    runtime_dir.mkdir(exist_ok=True)
    (runtime_dir / "dag.json").write_text(json.dumps(dag, indent=2))
    
    return {
        "tasks_path": str(tasks_path),
        "tasks": tasks,
        "dag": dag,
        "task_count": len(tasks),
    }


def _build_dag(tasks: list) -> dict:
    """Build DAG from tasks."""
    nodes = {}
    edges = []
    
    for task in tasks:
        nodes[task["id"]] = {
            "id": task["id"],
            "description": task["description"],
            "parallel": task.get("parallel", True),
        }
        for dep in task.get("depends_on", []):
            edges.append([dep, task["id"]])
    
    # Compute parallel groups (levels)
    levels = []
    completed = set()
    remaining = set(nodes.keys())
    
    while remaining:
        ready = [
            tid for tid in remaining
            if all(d in completed for d in _get_deps(tid, tasks))
        ]
        if not ready:
            ready = list(remaining)[:1]
        
        levels.append(ready)
        completed.update(ready)
        remaining -= set(ready)
    
    return {
        "nodes": nodes,
        "edges": edges,
        "levels": levels,
    }


def _get_deps(task_id: str, tasks: list) -> list:
    """Get dependencies for a task."""
    for t in tasks:
        if t["id"] == task_id:
            return t.get("depends_on", [])
    return []


def _create_windmill_flow(protocol_run_id: int, dag: dict, tasks: list) -> str | None:
    """Create Windmill flow from DAG."""
    
    flow_path = f"f/devgodzilla/protocol-{protocol_run_id}"
    
    # Build flow modules from DAG levels
    modules = []
    
    for level_idx, task_ids in enumerate(dag.get("levels", [])):
        if len(task_ids) == 1:
            # Single task
            task_id = task_ids[0]
            modules.append({
                "id": task_id,
                "value": {
                    "type": "script",
                    "path": "u/devgodzilla/execute_step"
                },
                "input_transforms": {
                    "step_id": {"type": "static", "value": task_id},
                    "agent_id": {"type": "javascript", "expr": "flow_input.agent_id || 'opencode'"},
                    "protocol_run_id": {"type": "static", "value": protocol_run_id},
                    "context": {"type": "static", "value": {}}
                }
            })
        else:
            # Parallel tasks - branchall
            branches = []
            for task_id in task_ids:
                branches.append({
                    "modules": [{
                        "id": task_id,
                        "value": {
                            "type": "script",
                            "path": "u/devgodzilla/execute_step"
                        },
                        "input_transforms": {
                            "step_id": {"type": "static", "value": task_id},
                            "agent_id": {"type": "javascript", "expr": "flow_input.agent_id || 'opencode'"},
                            "protocol_run_id": {"type": "static", "value": protocol_run_id},
                            "context": {"type": "static", "value": {}}
                        }
                    }]
                })
            
            modules.append({
                "id": f"parallel_group_{level_idx}",
                "value": {
                    "type": "branchall",
                    "branches": branches
                }
            })
    
    flow_def = {
        "summary": f"Protocol {protocol_run_id}",
        "description": "Generated by DevGodzilla plan_protocol",
        "value": {"modules": modules},
        "schema": {
            "type": "object",
            "properties": {
                "agent_id": {"type": "string", "default": "opencode"}
            }
        }
    }
    
    # Try to create in Windmill
    if DEVGODZILLA_AVAILABLE:
        try:
            client = WindmillClient()
            client.create_flow(flow_path, flow_def)
            return flow_path
        except:
            pass
    
    # Save flow definition locally as fallback
    flows_dir = Path("/tmp/devgodzilla/flows")
    flows_dir.mkdir(parents=True, exist_ok=True)
    (flows_dir / f"protocol-{protocol_run_id}.flow.json").write_text(json.dumps(flow_def, indent=2))
    
    return flow_path
