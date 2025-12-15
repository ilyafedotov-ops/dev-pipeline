"""
DevGodzilla Worker Entry Point

Windmill worker script entry point for executing DevGodzilla jobs.
This module provides the functions that Windmill scripts call.
"""

import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

# Ensure devgodzilla is in the path
sys.path.insert(0, str(Path(__file__).parent.parent))

from devgodzilla.config import get_config
from devgodzilla.db import get_database
from devgodzilla.logging import get_logger
from devgodzilla.services.base import ServiceContext

logger = get_logger(__name__)


def get_context() -> ServiceContext:
    """Get service context for worker jobs."""
    config = get_config()
    return ServiceContext(config=config)


def get_db():
    """Get database instance for worker jobs."""
    config = get_config()
    return get_database(
        db_url=config.database.url if config.database.url else None,
        db_path=Path(config.database.path) if config.database.path else None,
    )


def plan_protocol(protocol_run_id: int) -> Dict[str, Any]:
    """
    Plan a protocol run.
    
    Windmill script entry point for protocol planning.
    
    Args:
        protocol_run_id: Protocol run ID
        
    Returns:
        Dict with planning result
    """
    from devgodzilla.services.planning import PlanningService
    
    context = get_context()
    db = get_db()
    
    planning = PlanningService(context, db)
    result = planning.plan_protocol(protocol_run_id)
    
    return {
        "success": result.success,
        "steps_created": result.steps_created,
        "spec_hash": result.spec_hash,
        "error": result.error,
        "warnings": result.warnings,
    }


def execute_step(
    step_run_id: int,
    agent_id: str = "codex",
    protocol_run_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Execute a step using the specified agent.
    
    Windmill script entry point for step execution.
    
    Args:
        step_run_id: Step run ID
        agent_id: Agent to use for execution
        protocol_run_id: Optional protocol run ID (for context)
        
    Returns:
        Dict with execution result
    """
    context = get_context()
    db = get_db()
    
    # Get step and update status
    step = db.get_step_run(step_run_id)
    
    logger.info(
        "execute_step_started",
        extra={
            "step_run_id": step_run_id,
            "step_name": step.step_name,
            "agent_id": agent_id,
        },
    )
    
    try:
        # TODO: Import and use ExecutionService when available
        # For now, simulate execution
        from devgodzilla.models.domain import StepStatus
        
        db.update_step_status(step_run_id, StepStatus.COMPLETED, summary="Step executed")
        
        return {
            "success": True,
            "step_run_id": step_run_id,
            "agent_id": agent_id,
        }
    except Exception as e:
        from devgodzilla.models.domain import StepStatus
        
        db.update_step_status(step_run_id, StepStatus.FAILED, summary=str(e))
        
        logger.error(
            "execute_step_failed",
            extra={
                "step_run_id": step_run_id,
                "error": str(e),
            },
        )
        
        return {
            "success": False,
            "step_run_id": step_run_id,
            "error": str(e),
        }


def run_qa(
    step_run_id: int,
    protocol_run_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Run QA validation on a step.
    
    Windmill script entry point for QA.
    
    Args:
        step_run_id: Step run ID
        protocol_run_id: Optional protocol run ID
        
    Returns:
        Dict with QA result
    """
    context = get_context()
    db = get_db()
    
    step = db.get_step_run(step_run_id)
    
    logger.info(
        "run_qa_started",
        extra={
            "step_run_id": step_run_id,
            "step_name": step.step_name,
        },
    )
    
    try:
        # TODO: Import and use QualityService when available
        # For now, mark as completed
        from devgodzilla.models.domain import StepStatus
        
        db.update_step_status(step_run_id, StepStatus.COMPLETED)
        
        return {
            "success": True,
            "passed": True,
            "step_run_id": step_run_id,
        }
    except Exception as e:
        logger.error(
            "run_qa_failed",
            extra={
                "step_run_id": step_run_id,
                "error": str(e),
            },
        )
        
        return {
            "success": False,
            "passed": False,
            "step_run_id": step_run_id,
            "error": str(e),
        }


def open_pr(protocol_run_id: int) -> Dict[str, Any]:
    """
    Open a PR/MR for a protocol.
    
    Windmill script entry point for PR creation.
    
    Args:
        protocol_run_id: Protocol run ID
        
    Returns:
        Dict with PR details
    """
    from devgodzilla.services.git import GitService
    
    context = get_context()
    db = get_db()
    
    run = db.get_protocol_run(protocol_run_id)
    project = db.get_project(run.project_id)
    
    git = GitService(context)
    
    logger.info(
        "open_pr_started",
        extra={
            "protocol_run_id": protocol_run_id,
            "protocol_name": run.protocol_name,
        },
    )
    
    try:
        pr_info = git.open_pr(
            project_id=run.project_id,
            branch_name=run.protocol_name,
            title=f"[DevGodzilla] {run.protocol_name}",
            description=run.description or "Automated changes from DevGodzilla",
        )
        
        return {
            "success": True,
            "protocol_run_id": protocol_run_id,
            "pr_url": pr_info.get("url"),
        }
    except Exception as e:
        logger.error(
            "open_pr_failed",
            extra={
                "protocol_run_id": protocol_run_id,
                "error": str(e),
            },
        )
        
        return {
            "success": False,
            "protocol_run_id": protocol_run_id,
            "error": str(e),
        }


# CLI entry point for testing
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="DevGodzilla Worker")
    parser.add_argument("command", choices=["plan", "execute", "qa", "pr"])
    parser.add_argument("--protocol-run-id", type=int)
    parser.add_argument("--step-run-id", type=int)
    parser.add_argument("--agent-id", default="codex")
    
    args = parser.parse_args()
    
    if args.command == "plan":
        result = plan_protocol(args.protocol_run_id)
    elif args.command == "execute":
        result = execute_step(args.step_run_id, args.agent_id)
    elif args.command == "qa":
        result = run_qa(args.step_run_id)
    elif args.command == "pr":
        result = open_pr(args.protocol_run_id)
    
    import json
    print(json.dumps(result, indent=2))
