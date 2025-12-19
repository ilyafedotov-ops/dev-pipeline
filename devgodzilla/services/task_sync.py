"""
Task Sync Service

Synchronizes SpecKit markdown task files with database AgileTask records.
"""

import re
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from devgodzilla.db.database import Database
from devgodzilla.logging import get_logger
from devgodzilla.models.domain import AgileTask

logger = get_logger(__name__)


class TaskSyncService:
    """Service for synchronizing tasks between markdown files and the database."""

    def __init__(self, db: Database):
        self.db = db

    async def import_speckit_tasks(
        self,
        project_id: int,
        spec_path: str,
        sprint_id: int,
        overwrite_existing: bool = False,
    ) -> List[AgileTask]:
        """
        Parse a SpecKit tasks.md file and create database tasks.

        Args:
            project_id: Project ID
            spec_path: Absolute path to the tasks.md file
            sprint_id: Sprint to import tasks into
            overwrite_existing: If True, delete existing tasks in the sprint before importing

        Returns:
            List of created tasks
        """
        if not os.path.exists(spec_path):
            raise FileNotFoundError(f"Task file not found: {spec_path}")

        with open(spec_path, "r", encoding="utf-8") as f:
            content = f.read()

        parsed_tasks = self.parse_task_markdown(content)
        spec_label = None
        try:
            spec_label = f"spec:{Path(spec_path).parent.name}"
        except Exception:
            spec_label = None

        if overwrite_existing:
            # Delete existing tasks in the sprint
            existing_tasks = self.db.list_tasks(sprint_id=sprint_id)
            for task in existing_tasks:
                # Only delete tasks that look like they came from import (optional check?)
                # For now, simplistic approach: wipe the sprint if overwrite requested
                self.db.delete_task(task.id)
            logger.info(
                f"Deleted {len(existing_tasks)} tasks from sprint {sprint_id} (overwrite=True)",
                extra={"sprint_id": sprint_id},
            )

        created_tasks: List[AgileTask] = []

        for item in parsed_tasks:
            
            # Check for duplicates if not overwriting
            if not overwrite_existing:
                existing = self.db.list_tasks(sprint_id=sprint_id)
                if any(t.title == item["title"] for t in existing):
                    continue

            labels = [label for label in [spec_label, "speckit"] if label]
            task = self.db.create_task(
                project_id=project_id,
                sprint_id=sprint_id,
                title=item["title"],
                description=item.get("description"),
                task_type="story",
                priority="medium",
                board_status=item["board_status"],
                story_points=item.get("story_points"),
                labels=labels,
            )
            created_tasks.append(task)

        logger.info(
            f"Imported {len(created_tasks)} tasks to sprint {sprint_id} from {spec_path}",
            extra={"sprint_id": sprint_id, "file": spec_path},
        )

        # Update sprint velocity
        self._update_sprint_velocity(sprint_id)

        return created_tasks

    def parse_task_markdown(self, content: str) -> List[Dict[str, Any]]:
        """
        Parse task markdown format (checkbox lists).

        Supported formats:
        - [ ] Task Title
        - [x] Completed Task
        - [ ] Task with points (3 pts)
        - [ ] Task with points (5)
        """
        tasks = []
        lines = content.splitlines()
        
        # Regex for task line: - [x] Title (3 pts)
        # Group 1: x or space (status)
        # Group 2: Title (including points)
        task_pattern = re.compile(r"^\s*-\s*\[([ xX])\]\s*(.+)$")
        
        # Regex for points at end of title: (3 pts) or (5) or (1 pt)
        points_pattern = re.compile(r"\s*\((\d+)\s*(?:pts?|points?)?\)\s*$")

        for line in lines:
            match = task_pattern.match(line)
            if match:
                status_char = match.group(1).lower()
                full_title = match.group(2).strip()
                
                # Extract points
                points = None
                title = full_title
                points_match = points_pattern.search(full_title)
                if points_match:
                    points = int(points_match.group(1))
                    title = full_title[:points_match.start()].strip()
                
                board_status = "done" if status_char == "x" else "todo"
                
                tasks.append({
                    "title": title,
                    "board_status": board_status,
                    "story_points": points,
                    "description": None # Could support extracting nested bullets as description later
                })
                
        return tasks

    def _update_sprint_velocity(self, sprint_id: int):
        """Recalculate velocity for the sprint."""
        sprint = self.db.get_sprint(sprint_id)
        tasks = self.db.list_tasks(sprint_id=sprint_id)
        
        completed_points = sum(
            t.story_points or 0 
            for t in tasks 
            if t.board_status == "done"
        )
        
        self.db.update_sprint(sprint_id, velocity_actual=completed_points)
