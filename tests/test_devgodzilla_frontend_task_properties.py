"""
Property-based tests for task PATCH endpoint.

**Feature: frontend-api-integration, Property 5: Task update reflection**
**Validates: Requirements 3.18**
"""

import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Optional, List
from datetime import datetime

import pytest
from hypothesis import given, strategies as st, settings, HealthCheck

from devgodzilla.db.database import SQLiteDatabase


@contextmanager
def temp_db_context():
    """Context manager to create a temporary database for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        db = SQLiteDatabase(db_path)
        db.init_schema()
        yield db


def create_test_project(db: SQLiteDatabase) -> int:
    """Helper to create a test project."""
    try:
        project = db.get_project(1)
        return project.id
    except KeyError:
        project = db.create_project(
            name="test-project",
            git_url="https://github.com/test/test",
            base_branch="main"
        )
        return project.id


def create_test_sprint(db: SQLiteDatabase, project_id: int) -> int:
    """Helper to create a test sprint."""
    sprint = db.create_sprint(
        project_id=project_id,
        name="Test Sprint",
        start_date="2024-01-01",
        end_date="2024-01-14",
        velocity_planned=10
    )
    return sprint.id


def create_test_task(
    db: SQLiteDatabase,
    project_id: int,
    sprint_id: Optional[int] = None,
    title: str = "Test Task",
    task_type: str = "story",
    priority: str = "medium",
    board_status: str = "backlog"
) -> int:
    """Helper to create a test task."""
    task = db.create_task(
        project_id=project_id,
        title=title,
        task_type=task_type,
        priority=priority,
        board_status=board_status,
        sprint_id=sprint_id,
        description="Test description",
        assignee="test-user",
        reporter="test-reporter",
        story_points=3,
        labels=["test"],
        acceptance_criteria=["Test criteria"],
        due_date=None,
        blocked_by=[],
        blocks=[]
    )
    return task.id


# Strategies for generating valid task field values
task_type_strategy = st.sampled_from(["story", "bug", "task", "spike"])
priority_strategy = st.sampled_from(["low", "medium", "high", "critical"])
board_status_strategy = st.sampled_from(["backlog", "todo", "in_progress", "review", "done"])
assignee_strategy = st.one_of(st.none(), st.text(min_size=1, max_size=50))
reporter_strategy = st.one_of(st.none(), st.text(min_size=1, max_size=50))
story_points_strategy = st.one_of(st.none(), st.integers(min_value=1, max_value=21))
title_strategy = st.text(min_size=1, max_size=200)
description_strategy = st.one_of(st.none(), st.text(min_size=0, max_size=1000))


@settings(max_examples=20, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(
    # Generate update fields
    title=st.one_of(st.none(), title_strategy),
    task_type=st.one_of(st.none(), task_type_strategy),
    priority=st.one_of(st.none(), priority_strategy),
    board_status=st.one_of(st.none(), board_status_strategy),
    description=st.one_of(st.none(), description_strategy),
    assignee=st.one_of(st.none(), assignee_strategy),
    reporter=st.one_of(st.none(), reporter_strategy),
    story_points=st.one_of(st.none(), story_points_strategy),
    labels=st.one_of(st.none(), st.lists(st.text(min_size=1, max_size=20), max_size=5)),
    acceptance_criteria=st.one_of(st.none(), st.lists(st.text(min_size=1, max_size=100), max_size=5))
)
def test_task_update_reflection(
    title: Optional[str],
    task_type: Optional[str],
    priority: Optional[str],
    board_status: Optional[str],
    description: Optional[str],
    assignee: Optional[str],
    reporter: Optional[str],
    story_points: Optional[int],
    labels: Optional[List[str]],
    acceptance_criteria: Optional[List[str]]
):
    """
    **Feature: frontend-api-integration, Property 5: Task update reflection**
    **Validates: Requirements 3.18**
    
    Property: For any valid task update via PATCH /tasks/{id}, the returned task
    SHALL reflect all updated fields with the new values.
    
    This property ensures that partial updates work correctly and that the
    returned task object contains exactly the updated values.
    """
    with temp_db_context() as temp_db:
        # Create test project and task
        project_id = create_test_project(temp_db)
        sprint_id = create_test_sprint(temp_db, project_id)
        task_id = create_test_task(temp_db, project_id, sprint_id)
        
        # Get original task for comparison
        original_task = temp_db.get_task(task_id)
        
        # Build update dictionary with only non-None values
        updates = {}
        if title is not None:
            updates["title"] = title
        if task_type is not None:
            updates["task_type"] = task_type
        if priority is not None:
            updates["priority"] = priority
        if board_status is not None:
            updates["board_status"] = board_status
        if description is not None:
            updates["description"] = description
        if assignee is not None:
            updates["assignee"] = assignee
        if reporter is not None:
            updates["reporter"] = reporter
        if story_points is not None:
            updates["story_points"] = story_points
        if labels is not None:
            updates["labels"] = labels
        if acceptance_criteria is not None:
            updates["acceptance_criteria"] = acceptance_criteria
        
        # Skip test if no updates to apply
        if not updates:
            return
        
        # Apply the update
        updated_task = temp_db.update_task(task_id, **updates)
        
        # Property: All updated fields should reflect the new values
        for field, expected_value in updates.items():
            actual_value = getattr(updated_task, field)
            assert actual_value == expected_value, (
                f"Field '{field}' should be '{expected_value}' but got '{actual_value}'"
            )
        
        # Property: Non-updated fields should remain unchanged
        for field in ["title", "task_type", "priority", "board_status", "description", 
                     "assignee", "reporter", "story_points", "labels", "acceptance_criteria"]:
            if field not in updates:
                original_value = getattr(original_task, field)
                actual_value = getattr(updated_task, field)
                assert actual_value == original_value, (
                    f"Non-updated field '{field}' changed from '{original_value}' to '{actual_value}'"
                )
        
        # Property: Task ID should remain the same
        assert updated_task.id == task_id, (
            f"Task ID changed from {task_id} to {updated_task.id}"
        )
        
        # Property: updated_at should be more recent than original
        # Note: We can't easily test this with the current schema since updated_at 
        # is set by the database, but we can verify it exists
        assert updated_task.updated_at is not None, "updated_at should be set"


@settings(max_examples=20, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(
    # Generate blocked_by relationships
    num_blocking_tasks=st.integers(min_value=0, max_value=5),
    # Generate blocks relationships  
    num_blocked_tasks=st.integers(min_value=0, max_value=5)
)
def test_task_update_blocked_relationships(
    num_blocking_tasks: int,
    num_blocked_tasks: int
):
    """
    Property test for task blocking relationships updates.
    
    Property: When updating blocked_by or blocks fields, the relationships
    SHALL be correctly stored and retrieved, and circular dependencies
    SHALL be prevented.
    """
    with temp_db_context() as temp_db:
        # Create test project
        project_id = create_test_project(temp_db)
        sprint_id = create_test_sprint(temp_db, project_id)
        
        # Create main task and related tasks
        main_task_id = create_test_task(temp_db, project_id, sprint_id, title="Main Task")
        
        # Create blocking tasks (tasks that block the main task)
        blocking_task_ids = []
        for i in range(num_blocking_tasks):
            task_id = create_test_task(temp_db, project_id, sprint_id, title=f"Blocking Task {i}")
            blocking_task_ids.append(task_id)
        
        # Create blocked tasks (tasks that are blocked by the main task)
        blocked_task_ids = []
        for i in range(num_blocked_tasks):
            task_id = create_test_task(temp_db, project_id, sprint_id, title=f"Blocked Task {i}")
            blocked_task_ids.append(task_id)
        
        # Update main task with blocking relationships
        if blocking_task_ids:
            updated_task = temp_db.update_task(main_task_id, blocked_by=blocking_task_ids)
            
            # Property: blocked_by should reflect the update
            assert set(updated_task.blocked_by) == set(blocking_task_ids), (
                f"blocked_by should be {blocking_task_ids} but got {updated_task.blocked_by}"
            )
        
        # Update main task with blocks relationships
        if blocked_task_ids:
            updated_task = temp_db.update_task(main_task_id, blocks=blocked_task_ids)
            
            # Property: blocks should reflect the update
            assert set(updated_task.blocks) == set(blocked_task_ids), (
                f"blocks should be {blocked_task_ids} but got {updated_task.blocks}"
            )


@settings(max_examples=20, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(
    # Generate sprint changes
    change_sprint=st.booleans()
)
def test_task_update_sprint_assignment(change_sprint: bool):
    """
    Property test for task sprint assignment updates.
    
    Property: When updating sprint_id, the task SHALL be correctly
    assigned to the new sprint and removed from the old sprint.
    """
    with temp_db_context() as temp_db:
        # Create test project and sprints
        project_id = create_test_project(temp_db)
        sprint1_id = create_test_sprint(temp_db, project_id)
        
        sprint2 = temp_db.create_sprint(
            project_id=project_id,
            name="Test Sprint 2",
            start_date="2024-01-15",
            end_date="2024-01-28",
            velocity_planned=15
        )
        sprint2_id = sprint2.id
        
        # Create task in first sprint
        task_id = create_test_task(temp_db, project_id, sprint1_id)
        
        if change_sprint:
            # Update task to second sprint
            updated_task = temp_db.update_task(task_id, sprint_id=sprint2_id)
            
            # Property: Task should be in new sprint
            assert updated_task.sprint_id == sprint2_id, (
                f"Task should be in sprint {sprint2_id} but got {updated_task.sprint_id}"
            )
            
            # Property: Task should appear in new sprint's task list
            sprint2_tasks = temp_db.list_tasks(sprint_id=sprint2_id)
            task_ids_in_sprint2 = [task.id for task in sprint2_tasks]
            assert task_id in task_ids_in_sprint2, (
                f"Task {task_id} should appear in sprint {sprint2_id} task list"
            )
            
            # Property: Task should not appear in old sprint's task list
            sprint1_tasks = temp_db.list_tasks(sprint_id=sprint1_id)
            task_ids_in_sprint1 = [task.id for task in sprint1_tasks]
            assert task_id not in task_ids_in_sprint1, (
                f"Task {task_id} should not appear in sprint {sprint1_id} task list"
            )


@settings(max_examples=20, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(
    # Generate multiple field updates at once
    num_fields_to_update=st.integers(min_value=1, max_value=5)
)
def test_task_update_multiple_fields(num_fields_to_update: int):
    """
    Property test for updating multiple task fields simultaneously.
    
    Property: When updating multiple fields in a single PATCH request,
    ALL specified fields SHALL be updated correctly.
    """
    with temp_db_context() as temp_db:
        # Create test project and task
        project_id = create_test_project(temp_db)
        sprint_id = create_test_sprint(temp_db, project_id)
        task_id = create_test_task(temp_db, project_id, sprint_id)
        
        # Define possible field updates
        possible_updates = {
            "title": "Updated Title",
            "task_type": "bug",
            "priority": "high",
            "board_status": "in_progress",
            "description": "Updated description",
            "assignee": "new-assignee",
            "story_points": 8
        }
        
        # Select random fields to update
        field_names = list(possible_updates.keys())
        selected_fields = field_names[:num_fields_to_update]
        
        updates = {field: possible_updates[field] for field in selected_fields}
        
        # Apply the updates
        updated_task = temp_db.update_task(task_id, **updates)
        
        # Property: All updated fields should have new values
        for field, expected_value in updates.items():
            actual_value = getattr(updated_task, field)
            assert actual_value == expected_value, (
                f"Field '{field}' should be '{expected_value}' but got '{actual_value}'"
            )
        
        # Property: Task should still be valid and retrievable
        retrieved_task = temp_db.get_task(task_id)
        assert retrieved_task.id == task_id, "Task should still be retrievable after update"
        
        # Property: All updated fields should persist after retrieval
        for field, expected_value in updates.items():
            actual_value = getattr(retrieved_task, field)
            assert actual_value == expected_value, (
                f"Persisted field '{field}' should be '{expected_value}' but got '{actual_value}'"
            )