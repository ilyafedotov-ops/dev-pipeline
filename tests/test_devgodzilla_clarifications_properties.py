"""
Property-based tests for clarifications endpoints.

**Feature: frontend-api-integration, Property 2: Project clarifications scope**
**Feature: frontend-api-integration, Property 3: Protocol clarifications scope**
**Validates: Requirements 3.9, 3.10**
"""

import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import List, Optional

from hypothesis import given, strategies as st, settings

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


def create_test_protocol(db: SQLiteDatabase, project_id: int, name: str = "test-protocol") -> int:
    """Helper to create a test protocol."""
    protocol = db.create_protocol_run(
        project_id=project_id,
        protocol_name=name,
        status="pending",
        base_branch="main"
    )
    return protocol.id


def create_test_clarification(
    db: SQLiteDatabase,
    project_id: int,
    key: str,
    protocol_run_id: Optional[int] = None,
    question: str = "Test question?"
):
    """Helper to create a test clarification."""
    scope = f"protocol:{protocol_run_id}" if protocol_run_id else f"project:{project_id}"
    
    db.upsert_clarification(
        scope=scope,
        project_id=project_id,
        protocol_run_id=protocol_run_id,
        key=key,
        question=question
    )


# Strategy for generating clarification keys
clarification_key_strategy = st.text(
    alphabet=st.characters(min_codepoint=97, max_codepoint=122),  # a-z
    min_size=1,
    max_size=20
)


@settings(max_examples=100, deadline=None)
@given(
    # Number of projects to create
    num_projects=st.integers(min_value=1, max_value=5),
    # Number of clarifications per project
    clarifications_per_project=st.integers(min_value=0, max_value=10),
    # Which project to query
    query_project_index=st.integers(min_value=0, max_value=4)
)
def test_project_clarifications_scope(
    num_projects: int,
    clarifications_per_project: int,
    query_project_index: int
):
    """
    **Feature: frontend-api-integration, Property 2: Project clarifications scope**
    **Validates: Requirements 3.9**
    
    Property: For any project ID, all clarifications returned from 
    /projects/{id}/clarifications SHALL have project_id equal to the 
    requested ID or be null (project-level).
    
    This property ensures that project clarifications are properly scoped
    and don't leak across project boundaries.
    """
    with temp_db_context() as temp_db:
        # Ensure query_project_index is valid
        query_project_index = query_project_index % num_projects
        
        # Create projects and their clarifications
        project_ids = []
        for i in range(num_projects):
            project_id = create_test_project(temp_db, f"project-{i}")
            project_ids.append(project_id)
            
            # Create clarifications for this project
            for j in range(clarifications_per_project):
                create_test_clarification(
                    temp_db,
                    project_id=project_id,
                    key=f"clarification-{i}-{j}",
                    protocol_run_id=None,  # Project-level clarification
                    question=f"Question {i}-{j}?"
                )
        
        # Query clarifications for a specific project
        query_project_id = project_ids[query_project_index]
        clarifications = temp_db.list_clarifications(
            project_id=query_project_id,
            limit=100
        )
        
        # Property: All returned clarifications must belong to the queried project
        for clarification in clarifications:
            assert clarification.project_id == query_project_id, (
                f"Clarification {clarification.id} has project_id {clarification.project_id} "
                f"but query was for project_id {query_project_id}"
            )
        
        # Property: Count should match what we created for this project
        assert len(clarifications) == clarifications_per_project, (
            f"Expected {clarifications_per_project} clarifications for project {query_project_id}, "
            f"got {len(clarifications)}"
        )


@settings(max_examples=100, deadline=None)
@given(
    # Number of protocols to create
    num_protocols=st.integers(min_value=1, max_value=5),
    # Number of clarifications per protocol
    clarifications_per_protocol=st.integers(min_value=0, max_value=10),
    # Which protocol to query
    query_protocol_index=st.integers(min_value=0, max_value=4)
)
def test_protocol_clarifications_scope(
    num_protocols: int,
    clarifications_per_protocol: int,
    query_protocol_index: int
):
    """
    **Feature: frontend-api-integration, Property 3: Protocol clarifications scope**
    **Validates: Requirements 3.10**
    
    Property: For any protocol ID, all clarifications returned from 
    /protocols/{id}/clarifications SHALL have protocol_run_id equal to 
    the requested ID.
    
    This property ensures that protocol clarifications are properly scoped
    and don't leak across protocol boundaries.
    """
    with temp_db_context() as temp_db:
        # Ensure query_protocol_index is valid
        query_protocol_index = query_protocol_index % num_protocols
        
        # Create a project first
        project_id = create_test_project(temp_db, "test-project")
        
        # Create protocols and their clarifications
        protocol_ids = []
        for i in range(num_protocols):
            protocol_id = create_test_protocol(temp_db, project_id, f"protocol-{i}")
            protocol_ids.append(protocol_id)
            
            # Create clarifications for this protocol
            for j in range(clarifications_per_protocol):
                create_test_clarification(
                    temp_db,
                    project_id=project_id,
                    key=f"clarification-{i}-{j}",
                    protocol_run_id=protocol_id,
                    question=f"Question {i}-{j}?"
                )
        
        # Query clarifications for a specific protocol
        query_protocol_id = protocol_ids[query_protocol_index]
        clarifications = temp_db.list_clarifications(
            protocol_run_id=query_protocol_id,
            limit=100
        )
        
        # Property: All returned clarifications must belong to the queried protocol
        for clarification in clarifications:
            assert clarification.protocol_run_id == query_protocol_id, (
                f"Clarification {clarification.id} has protocol_run_id {clarification.protocol_run_id} "
                f"but query was for protocol_run_id {query_protocol_id}"
            )
        
        # Property: Count should match what we created for this protocol
        assert len(clarifications) == clarifications_per_protocol, (
            f"Expected {clarifications_per_protocol} clarifications for protocol {query_protocol_id}, "
            f"got {len(clarifications)}"
        )


@settings(max_examples=100, deadline=None)
@given(
    # Number of project-level clarifications
    project_clarifications=st.integers(min_value=0, max_value=10),
    # Number of protocol-level clarifications
    protocol_clarifications=st.integers(min_value=0, max_value=10),
    # Status filter to apply
    status_filter=st.one_of(st.none(), st.sampled_from(["open", "answered"]))
)
def test_clarifications_status_filter(
    project_clarifications: int,
    protocol_clarifications: int,
    status_filter: Optional[str]
):
    """
    Property test for clarifications status filtering.
    
    Property: When a status filter is applied, all returned clarifications
    SHALL have that status.
    """
    with temp_db_context() as temp_db:
        # Create a project and protocol
        project_id = create_test_project(temp_db, "test-project")
        protocol_id = create_test_protocol(temp_db, project_id, "test-protocol")
        
        # Create project-level clarifications with alternating statuses
        for i in range(project_clarifications):
            status = "open" if i % 2 == 0 else "answered"
            key = f"project-clarification-{i}"
            create_test_clarification(
                temp_db,
                project_id=project_id,
                key=key,
                protocol_run_id=None,
                question=f"Project question {i}?"
            )
            # Answer half of them
            if status == "answered":
                temp_db.answer_clarification(
                    scope=f"project:{project_id}",
                    key=key,
                    answer={"text": "Test answer"},
                    status="answered"
                )
        
        # Create protocol-level clarifications with alternating statuses
        for i in range(protocol_clarifications):
            status = "open" if i % 2 == 0 else "answered"
            key = f"protocol-clarification-{i}"
            create_test_clarification(
                temp_db,
                project_id=project_id,
                key=key,
                protocol_run_id=protocol_id,
                question=f"Protocol question {i}?"
            )
            # Answer half of them
            if status == "answered":
                temp_db.answer_clarification(
                    scope=f"protocol:{protocol_id}",
                    key=key,
                    answer={"text": "Test answer"},
                    status="answered"
                )
        
        # Query with status filter
        clarifications = temp_db.list_clarifications(
            project_id=project_id,
            status=status_filter,
            limit=100
        )
        
        # Property: If filter is specified, all results must match
        if status_filter is not None:
            for clarification in clarifications:
                assert clarification.status == status_filter, (
                    f"Clarification {clarification.id} has status '{clarification.status}' "
                    f"but filter was '{status_filter}'"
                )
        
        # Property: Count should match expected
        if status_filter is not None:
            # Count how many we created with this status
            total_created = project_clarifications + protocol_clarifications
            # Half are open, half are answered (with rounding)
            expected_open = (project_clarifications + 1) // 2 + (protocol_clarifications + 1) // 2
            expected_answered = project_clarifications // 2 + protocol_clarifications // 2
            
            if status_filter == "open":
                assert len(clarifications) == expected_open, (
                    f"Expected {expected_open} open clarifications, got {len(clarifications)}"
                )
            elif status_filter == "answered":
                assert len(clarifications) == expected_answered, (
                    f"Expected {expected_answered} answered clarifications, got {len(clarifications)}"
                )
        else:
            # No filter means all clarifications
            expected_total = project_clarifications + protocol_clarifications
            assert len(clarifications) == expected_total, (
                f"Expected {expected_total} total clarifications, got {len(clarifications)}"
            )


@settings(max_examples=50, deadline=None)
@given(
    # Number of clarifications to create
    num_clarifications=st.integers(min_value=1, max_value=50),
    # Limit to apply
    limit=st.integers(min_value=1, max_value=100)
)
def test_clarifications_limit_respected(num_clarifications: int, limit: int):
    """
    Property test for clarifications limit parameter.
    
    Property: The list_clarifications method SHALL return at most 'limit' 
    clarifications, regardless of how many exist in the database.
    """
    with temp_db_context() as temp_db:
        # Create a project
        project_id = create_test_project(temp_db, "test-project")
        
        # Create clarifications
        for i in range(num_clarifications):
            create_test_clarification(
                temp_db,
                project_id=project_id,
                key=f"clarification-{i}",
                protocol_run_id=None,
                question=f"Question {i}?"
            )
        
        # Query with limit
        clarifications = temp_db.list_clarifications(
            project_id=project_id,
            limit=limit
        )
        
        # Property: Result count should not exceed limit
        assert len(clarifications) <= limit, (
            f"Expected at most {limit} clarifications, got {len(clarifications)}"
        )
        
        # Property: Result count should be min(num_clarifications, limit)
        expected_count = min(num_clarifications, limit)
        assert len(clarifications) == expected_count, (
            f"Expected {expected_count} clarifications, got {len(clarifications)}"
        )
