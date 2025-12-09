from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from tasksgodzilla.logging import get_logger
from tasksgodzilla.storage import BaseDatabase
from tasksgodzilla.workers import codemachine_worker

log = get_logger(__name__)


@dataclass
class CodeMachineService:
    """Service for CodeMachine workspace import and management.
    
    This service handles CodeMachine workspace operations, providing a stable
    service API for CodeMachine-based protocol execution.
    
    Responsibilities:
    - Import CodeMachine workspaces into protocol runs
    - Parse CodeMachine configuration files
    - Create protocol specs from CodeMachine agents
    - Handle CodeMachine-specific execution workflows
    
    CodeMachine vs Codex:
    - CodeMachine: Agent-based execution with .codemachine/ directory structure
    - Codex: Traditional protocol-based execution with .protocols/ directory
    
    CodeMachine Structure:
    - config.json: Defines agents, placeholders, and workflow
    - agents/: Agent definitions with prompts and configurations
    - .codemachine/: Execution workspace
    
    Usage:
        codemachine_service = CodeMachineService(db)
        
        # Import a CodeMachine workspace
        codemachine_service.import_workspace(
            project_id=1,
            protocol_run_id=123,
            workspace_path="/path/to/.codemachine",
            job_id="job-123"
        )
    """
    
    db: BaseDatabase
    
    def import_workspace(
        self,
        project_id: int,
        protocol_run_id: int,
        workspace_path: str,
        *,
        job_id: Optional[str] = None
    ) -> None:
        """Import a CodeMachine workspace and create protocol spec.
        
        Delegates to the existing worker implementation while providing a
        service-level API for callers.
        """
        log.info(
            "codemachine_import_workspace",
            extra={
                "project_id": project_id,
                "protocol_run_id": protocol_run_id,
                "workspace_path": workspace_path,
                "job_id": job_id,
            }
        )
        codemachine_worker.import_codemachine_workspace(
            project_id,
            protocol_run_id,
            workspace_path,
            self.db,
            job_id=job_id
        )
