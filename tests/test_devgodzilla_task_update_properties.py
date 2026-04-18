"""
Property-based tests for task update endpoint.

**Feature: frontend-api-integration, Property 5: Task update reflection**
**Validates: Requirements 3.18**
"""

import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Optional, List

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


def create_test_project(db: SQLiteDatabase, name: str = "test-project") -> int:
    """Helper to create a test project."""
    project = db.create_project(
        name=name,
        git_url="https://github.com/test/test",
        base_branch="main"
    )
    return project.id


def create_test_task(
    db: SQLiteDatabase,
    project_id: int,
    title: str = "Test task",
    task_type: str = "story",
    priority: str = "medium",
    board_status: str = "backlog",
    description: Optional[str] = None,
    assignee: Optional[str] = None,
    reporter: Optional[str] = None,
    story_points: Optional[int] = None,
    labels: Optional[List[str]] = None,
    acceptance_criteria: Optional[List[str]] = None,
):
    """Helper to create a test task."""
    task = db.create_task(
        project_id=project_id,
        title=title,
        task_type=task_type,
        priority=priority,
        board_status=board_status,
        description=description,
        assignee=assignee,
        reporter=reporter,
        story_points=story_points,
        labels=labels or [],
        acceptance_criteria=acceptance_criteria or [],
    )
    return task


# Strategies for generating valid task field values
title_strategy = st.text(
    alphabet=st.characters(whitelist_categories=('L', 'N', 'P', 'S'), whitelist_characters=' '),
    min_size=1,
    max_size=100
).filter(lambda x: x.strip())  # Ensure non-empty after stripping

task_type_strategy = st.sampled_from(["story", "bug", "task", "spike"])

priority_strategy = st.sampled_from(["low", "medium", "high", "critical"])

board_status_strategy = st.sampled_from([
    "backlog", "todo", "in_progress", "review", "done"
])

description_strategy = st.one_of(
    st.none(),
    st.text(min_size=0, max_size=500)
)

assignee_strategy = st.one_of(
    st.none(),
    st.text(
        alphabet=st.characters(whitelist_categories=('L', 'N'), whitelist_characters='_-'),
        min_size=1,
        max_size=50
    ).filter(lambda x: x.strip())
)

story_points_strategy = st.one_of(
    st.none(),
    st.integers(min_value=1, max_value=13)  # Fibonacci-like points
)

labels_strategy = st.lists(
    st.text(
        alphabet=st.characters(whitelist_categories=('L', 'N'), whitelist_characters='-_'),
        min_size=1,
        max_size=20
    ).filter(lambda x: x.strip()),
    min_size=0,
    max_size=5
)


@settings(max_examples=20, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(
    # Fields to update
    new_title=st.one_of(st.none(), title_strategy),
    new_task_type=st.one_of(st.none(), task_type_strategy),
    new_priority=st.one_of(st.none(), priority_strategy),
    new_board_status=st.one_of(st.none(), board_status_strategy),
    new_description=st.one_of(st.none(), description_strategy),
    new_assignee=st.one_of(st.none(), assignee_strategy),
    new_story_points=st.one_of(st.none(), story_points_strategy),
)
def test_task_update_reflection(
    new_title: Optional[str],
    new_task_type: Optional[str],
    new_priority: Optional[str],
    new_board_status: Optional[str],
    new_description: Optional[str],
    new_assignee: Optional[str],
    new_story_points: Optional[int],
):
    """
    **Feature: frontend-api-integration, Property 5: Task update reflection**
    **Validates: Requirements 3.18**
    
    Property: For any valid task update via PATCH /tasks/{id}, the returned task 
    SHALL reflect all updated fields with the new values.
    
    This property ensures that when a task is updated via the PATCH endpoint,
    all specified fields are correctly updated and reflected in the returned task.
    """
    with temp_db_context() as temp_db:
        # Create a project and initial task
        project_id = create_test_project(temp_db, "test-project")
        initial_task = create_test_task(
            temp_db,
            project_id=project_id,
            title="Initial Task",
            task_type="story",
            priority="medium",
            board_status="backlog",
            description="Initial description",
            assignee="initial_user",
            story_points=3,
        )
        task_id = initial_task.id
        
        # Build update kwargs - only include non-None values
        updates = {}
        if new_title is not None:
            updates["title"] = new_title
        if new_task_type is not None:
            updates["task_type"] = new_task_type
        if new_priority is not None:
            updates["priority"] = new_priority
        if new_board_status is not None:
            updates["board_status"] = new_board_status
        if new_description is not None:
            updates["description"] = new_description
        if new_assignee is not None:
            updates["assignee"] = new_assignee
        if new_story_points is not None:
            updates["story_points"] = new_story_points
        
        # Skip if no updates to apply
        if not updates:
            return
        
        # Apply the update
        updated_task = temp_db.update_task(task_id, **updates)
        
        # Property: All updated fields should reflect the new values
        if new_title is not None:
            assert updated_task.title == new_title, (
                f"Expected title to be '{new_title}', got '{updated_task.title}'"
            )
        
        if new_task_type is not None:
            assert updated_task.task_type == new_task_type, (
                f"Expected task_type to be '{new_task_type}', got '{updated_task.task_type}'"
            )
        
        if new_priority is not None:
            assert updated_task.priority == new_priority, (
                f"Expected priority to be '{new_priority}', got '{updated_task.priority}'"
            )
        
        if new_board_status is not None:
            assert updated_task.board_status == new_board_status, (
                f"Expected board_status to be '{new_board_status}', got '{updated_task.board_status}'"
            )
        
        if new_description is not None:
            assert updated_task.description == new_description, (
                f"Expected description to be '{new_description}', got '{updated_task.description}'"
            )
        
        if new_assignee is not None:
            assert updated_task.assignee == new_assignee, (
                f"Expected assignee to be '{new_assignee}', got '{updated_task.assignee}'"
            )
        
        if new_story_points is not None:
            assert updated_task.story_points == new_story_points, (
                f"Expected story_points to be {new_story_points}, got {updated_task.story_points}"
            )
        
        # Property: Non-updated fields should retain their original values
        if new_title is None:
            assert updated_task.title == "Initial Task", (
                f"Expected title to remain 'Initial Task', got '{updated_task.title}'"
            )
        
        # Property: The task ID should remain unchanged
        assert updated_task.id == task_id, (
            f"Expected task ID to remain {task_id}, got {updated_task.id}"
        )
        
        # Property: The project_id should remain unchanged
        assert updated_task.project_id == project_id, (
            f"Expected project_id to remain {project_id}, got {updated_task.project_id}"
        )


@settings(max_examples=20, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(
    # Labels to update
    new_labels=labels_strategy,
)
def test_task_update_labels_reflection(new_labels: List[str]):
    """
    **Feature: frontend-api-integration, Property 5: Task update reflection**
    **Validates: Requirements 3.18**
    
    Property: For any valid labels update via PATCH /tasks/{id}, the returned task 
    SHALL reflect the new labels list.
    
    This property specifically tests the labels field which is a JSON array.
    """
    with temp_db_context() as temp_db:
        # Create a project and initial task with some labels
        project_id = create_test_project(temp_db, "test-project")
        initial_task = create_test_task(
            temp_db,
            project_id=project_id,
            title="Task with labels",
            labels=["initial", "labels"],
        )
        task_id = initial_task.id
        
        # Apply the labels update
        updated_task = temp_db.update_task(task_id, labels=new_labels)
        
        # Property: Labels should be updated to the new list
        assert updated_task.labels == new_labels, (
            f"Expected labels to be {new_labels}, got {updated_task.labels}"
        )
        
        # Property: Labels should be a list
        assert isinstance(updated_task.labels, list), (
            f"Expected labels to be a list, got {type(updated_task.labels)}"
        )


@settings(max_examples=20, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(
    # Multiple sequential updates
    updates_sequence=st.lists(
        st.fixed_dictionaries({
            "board_status": board_status_strategy,
            "priority": priority_strategy,
        }),
        min_size=1,
        max_size=5
    )
)
def test_task_sequential_updates_reflection(updates_sequence: List[dict]):
    """
    **Feature: frontend-api-integration, Property 5: Task update reflection**
    **Validates: Requirements 3.18**
    
    Property: For any sequence of valid task updates, each update SHALL correctly
    reflect the new values, and the final state SHALL match the last update.
    
    This property tests that sequential updates work correctly and don't
    interfere with each other.
    """
    with temp_db_context() as temp_db:
        # Create a project and initial task
        project_id = create_test_project(temp_db, "test-project")
        initial_task = create_test_task(
            temp_db,
            project_id=project_id,
            title="Sequential Update Task",
            board_status="backlog",
            priority="low",
        )
        task_id = initial_task.id
        
        # Apply each update in sequence
        for update in updates_sequence:
            updated_task = temp_db.update_task(task_id, **update)
            
            # Property: Each update should be reflected immediately
            assert updated_task.board_status == update["board_status"], (
                f"Expected board_status to be '{update['board_status']}', "
                f"got '{updated_task.board_status}'"
            )
            assert updated_task.priority == update["priority"], (
                f"Expected priority to be '{update['priority']}', "
                f"got '{updated_task.priority}'"
            )
        
        # Property: Final state should match the last update
        final_task = temp_db.get_task(task_id)
        last_update = updates_sequence[-1]
        
        assert final_task.board_status == last_update["board_status"], (
            f"Expected final board_status to be '{last_update['board_status']}', "
            f"got '{final_task.board_status}'"
        )
        assert final_task.priority == last_update["priority"], (
            f"Expected final priority to be '{last_update['priority']}', "
            f"got '{final_task.priority}'"
        )
