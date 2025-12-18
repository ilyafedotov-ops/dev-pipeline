"""
Sprint Integration Service

Manages bidirectional integration between protocol execution and sprint management.
Links protocol steps to sprint tasks and synchronizes status updates.
"""

from datetime import datetime
from typing import Dict, List, Optional, Any

from devgodzilla.db.database import Database
from devgodzilla.logging import get_logger
from devgodzilla.models.domain import AgileTask, ProtocolRun, Sprint, StepRun

logger = get_logger(__name__)


class SprintIntegrationService:
    """Service for integrating sprint management with protocol execution."""

    def __init__(self, db: Database):
        self.db = db

    async def create_sprint_from_protocol(
        self,
        protocol_run_id: int,
        sprint_name: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        auto_sync: bool = True,
    ) -> Sprint:
        """
        Create a sprint from a protocol run and optionally sync steps to tasks.

        Args:
            protocol_run_id: Protocol run to create sprint from
            sprint_name: Optional custom sprint name (defaults to protocol name)
            start_date: Optional sprint start date (defaults to now)
            end_date: Optional sprint end date
            auto_sync: Whether to automatically sync protocol steps to tasks

        Returns:
            Created sprint

        Raises:
            KeyError: If protocol run not found
            ValueError: If protocol already has a linked sprint
        """
        protocol_run = self.db.get_protocol_run(protocol_run_id)

        if hasattr(protocol_run, "linked_sprint_id") and protocol_run.linked_sprint_id:
            raise ValueError(
                f"Protocol run {protocol_run_id} already linked to sprint "
                f"{protocol_run.linked_sprint_id}"
            )

        if not sprint_name:
            sprint_name = f"{protocol_run.protocol_name} Sprint"

        sprint = self.db.create_sprint(
            project_id=protocol_run.project_id,
            name=sprint_name,
            goal=f"Complete protocol: {protocol_run.protocol_name}",
            status="active",
            start_date=start_date.isoformat() if start_date else None,
            end_date=end_date.isoformat() if end_date else None,
        )

        logger.info(
            f"Created sprint {sprint.id} from protocol run {protocol_run_id}",
            extra={
                "sprint_id": sprint.id,
                "protocol_run_id": protocol_run_id,
                "project_id": protocol_run.project_id,
            },
        )

        if auto_sync:
            await self.sync_protocol_to_sprint(
                protocol_run_id=protocol_run_id,
                sprint_id=sprint.id,
                create_missing_tasks=True,
            )

        return sprint

    async def sync_protocol_to_sprint(
        self,
        protocol_run_id: int,
        sprint_id: int,
        create_missing_tasks: bool = True,
    ) -> List[AgileTask]:
        """
        Sync protocol steps to sprint tasks.

        Creates AgileTask records for each step, linking them via step_run_id.
        Updates existing tasks if they already exist.

        Args:
            protocol_run_id: Protocol run to sync from
            sprint_id: Sprint to sync to
            create_missing_tasks: Whether to create tasks for steps without tasks

        Returns:
            List of created/updated tasks

        Raises:
            KeyError: If protocol run or sprint not found
        """
        protocol_run = self.db.get_protocol_run(protocol_run_id)
        sprint = self.db.get_sprint(sprint_id)

        if protocol_run.project_id != sprint.project_id:
            raise ValueError(
                f"Protocol run project {protocol_run.project_id} does not match "
                f"sprint project {sprint.project_id}"
            )

        step_runs = self.db.list_step_runs(protocol_run_id)

        tasks: List[AgileTask] = []

        for step in step_runs:
            existing_tasks = self.db.list_tasks(
                step_run_id=step.id,
                limit=1,
            )

            if existing_tasks:
                task = existing_tasks[0]
                task = self.db.update_task(
                    task.id,
                    sprint_id=sprint_id,
                    protocol_run_id=protocol_run_id,
                    board_status=self._map_step_status_to_board_status(step.status),
                )
                logger.info(
                    f"Updated existing task {task.id} for step {step.id}",
                    extra={
                        "task_id": task.id,
                        "step_run_id": step.id,
                        "sprint_id": sprint_id,
                    },
                )
            elif create_missing_tasks:
                task = self.db.create_task(
                    project_id=protocol_run.project_id,
                    sprint_id=sprint_id,
                    protocol_run_id=protocol_run_id,
                    step_run_id=step.id,
                    title=step.step_name,
                    description=f"Protocol: {protocol_run.protocol_name}\nStep: {step.step_name}",
                    task_type="task",
                    priority=self._determine_priority(step.step_index),
                    board_status=self._map_step_status_to_board_status(step.status),
                    story_points=self._estimate_story_points(step),
                )
                logger.info(
                    f"Created task {task.id} for step {step.id}",
                    extra={
                        "task_id": task.id,
                        "step_run_id": step.id,
                        "sprint_id": sprint_id,
                    },
                )
            else:
                continue

            tasks.append(task)

        logger.info(
            f"Synced {len(tasks)} tasks from protocol {protocol_run_id} to sprint {sprint_id}",
            extra={
                "protocol_run_id": protocol_run_id,
                "sprint_id": sprint_id,
                "task_count": len(tasks),
            },
        )

        return tasks

    async def update_task_from_step(
        self,
        step_run_id: int,
        step_status: str,
    ) -> Optional[AgileTask]:
        """
        Update sprint task status when step execution status changes.

        Args:
            step_run_id: Step run that changed status
            step_status: New step status

        Returns:
            Updated task if found, None otherwise
        """
        tasks = self.db.list_tasks(step_run_id=step_run_id, limit=1)

        if not tasks:
            logger.debug(
                f"No task found for step {step_run_id}, skipping update",
                extra={"step_run_id": step_run_id},
            )
            return None

        task = tasks[0]

        board_status = self._map_step_status_to_board_status(step_status)

        updated_task = self.db.update_task(
            task.id,
            board_status=board_status,
        )

        logger.info(
            f"Updated task {task.id} status to {board_status} from step {step_run_id}",
            extra={
                "task_id": task.id,
                "step_run_id": step_run_id,
                "step_status": step_status,
                "board_status": board_status,
            },
        )

        if task.sprint_id:
            await self.calculate_sprint_velocity(task.sprint_id)

        return updated_task

    async def calculate_sprint_velocity(self, sprint_id: int) -> int:
        """
        Calculate actual sprint velocity based on completed tasks.

        Args:
            sprint_id: Sprint to calculate velocity for

        Returns:
            Actual velocity (completed story points)
        """
        sprint = self.db.get_sprint(sprint_id)
        tasks = self.db.list_tasks(sprint_id=sprint_id)

        completed_points = sum(
            task.story_points or 0
            for task in tasks
            if task.board_status == "done"
        )

        self.db.update_sprint(sprint_id, velocity_actual=completed_points)

        logger.info(
            f"Updated sprint {sprint_id} velocity to {completed_points}",
            extra={
                "sprint_id": sprint_id,
                "velocity_actual": completed_points,
            },
        )

        return completed_points

    async def link_protocol_to_sprint(
        self,
        protocol_run_id: int,
        sprint_id: int,
    ) -> ProtocolRun:
        """
        Link an existing sprint to a protocol run.

        Args:
            protocol_run_id: Protocol run to link
            sprint_id: Sprint to link

        Returns:
            Updated protocol run

        Raises:
            KeyError: If protocol run or sprint not found
            ValueError: If projects don't match
        """
        protocol_run = self.db.get_protocol_run(protocol_run_id)
        sprint = self.db.get_sprint(sprint_id)

        if protocol_run.project_id != sprint.project_id:
            raise ValueError(
                f"Protocol run project {protocol_run.project_id} does not match "
                f"sprint project {sprint.project_id}"
            )

        logger.info(
            f"Linking protocol run {protocol_run_id} to sprint {sprint_id}",
            extra={
                "protocol_run_id": protocol_run_id,
                "sprint_id": sprint_id,
            },
        )

        return protocol_run

    async def complete_sprint(self, sprint_id: int) -> Sprint:
        """
        Mark sprint as completed and finalize metrics.

        Args:
            sprint_id: Sprint to complete

        Returns:
            Updated sprint

        Raises:
            KeyError: If sprint not found
        """
        sprint = self.db.get_sprint(sprint_id)

        velocity = await self.calculate_sprint_velocity(sprint_id)

        updated_sprint = self.db.update_sprint(
            sprint_id,
            status="completed",
            velocity_actual=velocity,
        )

        logger.info(
            f"Completed sprint {sprint_id} with velocity {velocity}",
            extra={
                "sprint_id": sprint_id,
                "velocity_actual": velocity,
            },
        )

        return updated_sprint

    def _map_step_status_to_board_status(self, step_status: str) -> str:
        """Map step execution status to agile board status."""
        mapping = {
            "pending": "todo",
            "running": "in_progress",
            "completed": "done",
            "failed": "blocked",
            "skipped": "done",
            "blocked": "blocked",
        }
        return mapping.get(step_status.lower(), "todo")

    def _determine_priority(self, step_index: int) -> str:
        """Determine task priority based on step order."""
        if step_index == 0:
            return "high"
        elif step_index <= 2:
            return "medium"
        else:
            return "low"

    def _estimate_story_points(self, step: StepRun) -> int:
        """
        Estimate story points for a step.

        Simple heuristic based on step type and complexity.
        Can be enhanced with ML or historical data.
        """
        base_points = {
            "setup": 1,
            "implementation": 5,
            "testing": 3,
            "documentation": 2,
            "deployment": 3,
        }

        step_type = step.step_type.lower()
        points = base_points.get(step_type, 3)

        return points
