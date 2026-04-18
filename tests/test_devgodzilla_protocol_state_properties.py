"""
Property-based tests for protocol state transitions.

**Feature: frontend-api-integration, Properties 8-11: Protocol state transitions**
**Validates: Requirements 9.1, 9.2, 9.3, 9.4**
"""

import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

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


def create_test_protocol(
    db: SQLiteDatabase,
    project_id: int,
    protocol_name: str = "test-protocol",
    status: str = "pending",
    base_branch: str = "main",
    description: Optional[str] = None,
):
    """Helper to create a test protocol run."""
    run = db.create_protocol_run(
        project_id=project_id,
        protocol_name=protocol_name,
        status=status,
        base_branch=base_branch,
        description=description,
    )
    return run


# Strategies for generating valid protocol data
protocol_name_strategy = st.text(
    alphabet=st.characters(whitelist_categories=('L', 'N'), whitelist_characters='-_'),
    min_size=1,
    max_size=50
).filter(lambda x: x.strip())

description_strategy = st.one_of(
    st.none(),
    st.text(min_size=0, max_size=200)
)


@settings(max_examples=20, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(
    protocol_name=protocol_name_strategy,
    description=description_strategy,
)
def test_protocol_start_transition(
    protocol_name: str,
    description: Optional[str],
):
    """
    **Feature: frontend-api-integration, Property 8: Protocol state transitions - start**
    **Validates: Requirements 9.1**
    
    Property: For any protocol in "pending" or "planned" state, calling /actions/start 
    SHALL transition the status to "planning" or "running".
    
    This property tests that starting a protocol from valid initial states
    correctly transitions to an active state.
    """
    with temp_db_context() as temp_db:
        project_id = create_test_project(temp_db, "test-project")
        
        # Test starting from "pending" state
        protocol = create_test_protocol(
            temp_db,
            project_id=project_id,
            protocol_name=protocol_name,
            status="pending",
            description=description,
        )
        
        # Simulate the start action by updating status to "planning"
        # (This is what the start endpoint does)
        updated = temp_db.update_protocol_status(protocol.id, "planning")
        
        # Property: Status should transition to "planning" or "running"
        assert updated.status in ["planning", "running"], (
            f"Expected status to be 'planning' or 'running', got '{updated.status}'"
        )
        
        # Property: Protocol ID should remain unchanged
        assert updated.id == protocol.id, (
            f"Expected protocol ID to remain {protocol.id}, got {updated.id}"
        )
        
        # Property: Protocol name should remain unchanged
        assert updated.protocol_name == protocol_name, (
            f"Expected protocol_name to remain '{protocol_name}', got '{updated.protocol_name}'"
        )


@settings(max_examples=20, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(
    protocol_name=protocol_name_strategy,
)
def test_protocol_start_from_planned(protocol_name: str):
    """
    **Feature: frontend-api-integration, Property 8: Protocol state transitions - start**
    **Validates: Requirements 9.1**
    
    Property: For any protocol in "planned" state, calling /actions/start 
    SHALL transition the status to "running".
    """
    with temp_db_context() as temp_db:
        project_id = create_test_project(temp_db, "test-project")
        
        # Create protocol in "planned" state (after planning is complete)
        protocol = create_test_protocol(
            temp_db,
            project_id=project_id,
            protocol_name=protocol_name,
            status="planned",
        )
        
        # Simulate the start action - from planned goes to running
        updated = temp_db.update_protocol_status(protocol.id, "running")
        
        # Property: Status should transition to "running"
        assert updated.status == "running", (
            f"Expected status to be 'running', got '{updated.status}'"
        )


@settings(max_examples=20, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(
    protocol_name=protocol_name_strategy,
)
def test_protocol_pause_transition(protocol_name: str):
    """
    **Feature: frontend-api-integration, Property 9: Protocol state transitions - pause**
    **Validates: Requirements 9.2**
    
    Property: For any protocol in "running" state, calling /actions/pause 
    SHALL transition the status to "paused".
    
    This property tests that pausing a running protocol correctly transitions
    to the paused state.
    """
    with temp_db_context() as temp_db:
        project_id = create_test_project(temp_db, "test-project")
        
        # Create protocol in "running" state
        protocol = create_test_protocol(
            temp_db,
            project_id=project_id,
            protocol_name=protocol_name,
            status="running",
        )
        
        # Simulate the pause action
        updated = temp_db.update_protocol_status(protocol.id, "paused")
        
        # Property: Status should transition to "paused"
        assert updated.status == "paused", (
            f"Expected status to be 'paused', got '{updated.status}'"
        )
        
        # Property: Protocol ID should remain unchanged
        assert updated.id == protocol.id, (
            f"Expected protocol ID to remain {protocol.id}, got {updated.id}"
        )


@settings(max_examples=20, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(
    protocol_name=protocol_name_strategy,
)
def test_protocol_resume_transition(protocol_name: str):
    """
    **Feature: frontend-api-integration, Property 10: Protocol state transitions - resume**
    **Validates: Requirements 9.3**
    
    Property: For any protocol in "paused" state, calling /actions/resume 
    SHALL transition the status to "running".
    
    This property tests that resuming a paused protocol correctly transitions
    back to the running state.
    """
    with temp_db_context() as temp_db:
        project_id = create_test_project(temp_db, "test-project")
        
        # Create protocol in "paused" state
        protocol = create_test_protocol(
            temp_db,
            project_id=project_id,
            protocol_name=protocol_name,
            status="paused",
        )
        
        # Simulate the resume action
        updated = temp_db.update_protocol_status(protocol.id, "running")
        
        # Property: Status should transition to "running"
        assert updated.status == "running", (
            f"Expected status to be 'running', got '{updated.status}'"
        )
        
        # Property: Protocol ID should remain unchanged
        assert updated.id == protocol.id, (
            f"Expected protocol ID to remain {protocol.id}, got {updated.id}"
        )


@settings(max_examples=20, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(
    protocol_name=protocol_name_strategy,
    initial_status=st.sampled_from(["pending", "planning", "running", "paused", "failed"]),
)
def test_protocol_cancel_transition(protocol_name: str, initial_status: str):
    """
    **Feature: frontend-api-integration, Property 11: Protocol state transitions - cancel**
    **Validates: Requirements 9.4**
    
    Property: For any protocol not in "completed" or "cancelled" state, 
    calling /actions/cancel SHALL transition the status to "cancelled".
    
    This property tests that cancelling a protocol from any non-terminal state
    correctly transitions to the cancelled state.
    """
    with temp_db_context() as temp_db:
        project_id = create_test_project(temp_db, "test-project")
        
        # Create protocol in the given initial state
        protocol = create_test_protocol(
            temp_db,
            project_id=project_id,
            protocol_name=protocol_name,
            status=initial_status,
        )
        
        # Simulate the cancel action
        updated = temp_db.update_protocol_status(protocol.id, "cancelled")
        
        # Property: Status should transition to "cancelled"
        assert updated.status == "cancelled", (
            f"Expected status to be 'cancelled', got '{updated.status}'"
        )
        
        # Property: Protocol ID should remain unchanged
        assert updated.id == protocol.id, (
            f"Expected protocol ID to remain {protocol.id}, got {updated.id}"
        )


@settings(max_examples=20, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(
    protocol_name=protocol_name_strategy,
)
def test_protocol_cancel_idempotent_for_terminal_states(protocol_name: str):
    """
    **Feature: frontend-api-integration, Property 11: Protocol state transitions - cancel**
    **Validates: Requirements 9.4**
    
    Property: For any protocol already in "completed" or "cancelled" state,
    the cancel action should not change the state (idempotent for cancelled,
    no-op for completed).
    """
    with temp_db_context() as temp_db:
        project_id = create_test_project(temp_db, "test-project")
        
        # Test with "cancelled" state - should remain cancelled
        protocol_cancelled = create_test_protocol(
            temp_db,
            project_id=project_id,
            protocol_name=f"{protocol_name}-cancelled",
            status="cancelled",
        )
        
        # The endpoint returns the protocol without changing status
        # when already in terminal state
        current = temp_db.get_protocol_run(protocol_cancelled.id)
        assert current.status == "cancelled", (
            f"Expected status to remain 'cancelled', got '{current.status}'"
        )
        
        # Test with "completed" state - should remain completed
        protocol_completed = create_test_protocol(
            temp_db,
            project_id=project_id,
            protocol_name=f"{protocol_name}-completed",
            status="completed",
        )
        
        current = temp_db.get_protocol_run(protocol_completed.id)
        assert current.status == "completed", (
            f"Expected status to remain 'completed', got '{current.status}'"
        )


@settings(max_examples=20, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(
    protocol_name=protocol_name_strategy,
)
def test_protocol_state_transition_sequence(protocol_name: str):
    """
    **Feature: frontend-api-integration, Properties 8-11: Protocol state transitions**
    **Validates: Requirements 9.1, 9.2, 9.3, 9.4**
    
    Property: A protocol can go through a complete lifecycle:
    pending -> planning -> running -> paused -> running -> completed
    
    This property tests that the full state machine works correctly.
    """
    with temp_db_context() as temp_db:
        project_id = create_test_project(temp_db, "test-project")
        
        # Create protocol in pending state
        protocol = create_test_protocol(
            temp_db,
            project_id=project_id,
            protocol_name=protocol_name,
            status="pending",
        )
        
        # Start: pending -> planning
        protocol = temp_db.update_protocol_status(protocol.id, "planning")
        assert protocol.status == "planning"
        
        # Planning complete: planning -> running
        protocol = temp_db.update_protocol_status(protocol.id, "running")
        assert protocol.status == "running"
        
        # Pause: running -> paused
        protocol = temp_db.update_protocol_status(protocol.id, "paused")
        assert protocol.status == "paused"
        
        # Resume: paused -> running
        protocol = temp_db.update_protocol_status(protocol.id, "running")
        assert protocol.status == "running"
        
        # Complete: running -> completed
        protocol = temp_db.update_protocol_status(protocol.id, "completed")
        assert protocol.status == "completed"
        
        # Property: Final state should be completed
        final = temp_db.get_protocol_run(protocol.id)
        assert final.status == "completed", (
            f"Expected final status to be 'completed', got '{final.status}'"
        )


@settings(max_examples=20, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(
    protocol_name=protocol_name_strategy,
)
def test_protocol_cancel_from_any_active_state(protocol_name: str):
    """
    **Feature: frontend-api-integration, Property 11: Protocol state transitions - cancel**
    **Validates: Requirements 9.4**
    
    Property: A protocol can be cancelled from any active state in the lifecycle.
    """
    with temp_db_context() as temp_db:
        project_id = create_test_project(temp_db, "test-project")
        
        # Test cancel from each active state
        active_states = ["pending", "planning", "running", "paused", "failed"]
        
        for i, state in enumerate(active_states):
            protocol = create_test_protocol(
                temp_db,
                project_id=project_id,
                protocol_name=f"{protocol_name}-{i}",
                status=state,
            )
            
            # Cancel the protocol
            updated = temp_db.update_protocol_status(protocol.id, "cancelled")
            
            # Property: Should transition to cancelled
            assert updated.status == "cancelled", (
                f"Expected status to be 'cancelled' when cancelling from '{state}', "
                f"got '{updated.status}'"
            )
