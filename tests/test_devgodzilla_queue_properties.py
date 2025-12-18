"""
Property-based tests for queue statistics endpoints.

**Feature: frontend-api-integration, Property 1: Queue jobs filter consistency**
**Validates: Requirements 3.2**
"""

import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import List

import pytest
from hypothesis import given, strategies as st, settings

from devgodzilla.db.database import SQLiteDatabase


# Strategy for generating valid job statuses
job_status_strategy = st.sampled_from([
    "queued",
    "running",
    "started",
    "completed",
    "failed",
    "cancelled"
])

# Strategy for generating job types
job_type_strategy = st.sampled_from([
    "plan_protocol_job",
    "execute_step_job",
    "qa_gate_job",
    "discovery_job"
])


@contextmanager
def temp_db_context():
    """Context manager to create a temporary database for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        db = SQLiteDatabase(db_path)
        db.init_schema()
        yield db


def create_test_job_run(db: SQLiteDatabase, run_id: str, status: str, job_type: str, queue: str = "default"):
    """Helper to create a job run for testing."""
    # First create a project
    try:
        project = db.get_project(1)
    except KeyError:
        project = db.create_project(
            name="test-project",
            git_url="https://github.com/test/test",
            base_branch="main"
        )
    
    # Create the job run
    db.create_job_run(
        run_id=run_id,
        job_type=job_type,
        status=status,
        queue=queue,
        project_id=project.id
    )


@settings(max_examples=100, deadline=None)
@given(
    # Generate a list of job statuses to create
    job_statuses=st.lists(
        job_status_strategy,
        min_size=0,
        max_size=20
    ),
    # Generate a filter status (or None for no filter)
    filter_status=st.one_of(st.none(), job_status_strategy)
)
def test_queue_jobs_filter_consistency(job_statuses: List[str], filter_status: str):
    """
    **Feature: frontend-api-integration, Property 1: Queue jobs filter consistency**
    **Validates: Requirements 3.2**
    
    Property: For any status filter applied to list_queue_jobs, all returned jobs
    SHALL have a status matching the filter value.
    
    This property ensures that the queue jobs filtering works correctly across
    all possible combinations of job statuses and filter values.
    """
    with temp_db_context() as temp_db:
        # Create job runs with the generated statuses
        for i, status in enumerate(job_statuses):
            create_test_job_run(
                temp_db,
                run_id=f"test-run-{i}",
                status=status,
                job_type="plan_protocol_job",
                queue="default"
            )
        
        # Query with the filter
        jobs = temp_db.list_queue_jobs(status=filter_status, limit=100)
        
        # Property: If a filter is specified, all returned jobs must match that status
        if filter_status is not None:
            for job in jobs:
                assert job["status"] == filter_status, (
                    f"Job {job['job_id']} has status '{job['status']}' "
                    f"but filter was '{filter_status}'"
                )
        
        # Property: If no filter is specified, we should get all jobs
        if filter_status is None:
            assert len(jobs) == len(job_statuses), (
                f"Expected {len(job_statuses)} jobs without filter, got {len(jobs)}"
            )
        
        # Property: If filter is specified, count should match expected
        if filter_status is not None:
            expected_count = job_statuses.count(filter_status)
            assert len(jobs) == expected_count, (
                f"Expected {expected_count} jobs with status '{filter_status}', got {len(jobs)}"
            )


@settings(max_examples=100, deadline=None)
@given(
    # Generate jobs with different statuses
    queued_count=st.integers(min_value=0, max_value=10),
    running_count=st.integers(min_value=0, max_value=10),
    failed_count=st.integers(min_value=0, max_value=10),
    completed_count=st.integers(min_value=0, max_value=10)
)
def test_queue_stats_accuracy(
    queued_count: int,
    running_count: int,
    failed_count: int,
    completed_count: int
):
    """
    Property test for queue statistics accuracy.
    
    Property: The queue statistics SHALL accurately reflect the count of jobs
    in each status category.
    """
    with temp_db_context() as temp_db:
        # Create jobs with specific statuses
        job_id = 0
        
        for _ in range(queued_count):
            create_test_job_run(temp_db, f"run-{job_id}", "queued", "plan_protocol_job")
            job_id += 1
        
        for _ in range(running_count):
            create_test_job_run(temp_db, f"run-{job_id}", "running", "execute_step_job")
            job_id += 1
        
        for _ in range(failed_count):
            create_test_job_run(temp_db, f"run-{job_id}", "failed", "qa_gate_job")
            job_id += 1
        
        for _ in range(completed_count):
            create_test_job_run(temp_db, f"run-{job_id}", "completed", "discovery_job")
            job_id += 1
        
        # Get queue stats
        stats = temp_db.get_queue_stats()
        
        # Should have exactly one queue (default) if we have any jobs
        if queued_count + running_count + failed_count + completed_count > 0:
            assert len(stats) == 1, f"Expected 1 queue, got {len(stats)}"
            
            queue_stat = stats[0]
            
            # Verify counts match what we created
            assert queue_stat["queued"] == queued_count, (
                f"Expected {queued_count} queued jobs, got {queue_stat['queued']}"
            )
            
            assert queue_stat["started"] == running_count, (
                f"Expected {running_count} running jobs, got {queue_stat['started']}"
            )
            
            assert queue_stat["failed"] == failed_count, (
                f"Expected {failed_count} failed jobs, got {queue_stat['failed']}"
            )
        else:
            # No jobs means no queue stats
            assert len(stats) == 0, f"Expected 0 queues with no jobs, got {len(stats)}"


@settings(max_examples=50, deadline=None)
@given(
    # Generate a limit value
    limit=st.integers(min_value=1, max_value=500),
    # Generate more jobs than the limit
    job_count=st.integers(min_value=1, max_value=100)
)
def test_queue_jobs_limit_respected(limit: int, job_count: int):
    """
    Property test for queue jobs limit parameter.
    
    Property: The list_queue_jobs method SHALL return at most 'limit' jobs,
    regardless of how many jobs exist in the database.
    """
    with temp_db_context() as temp_db:
        # Create the specified number of jobs
        for i in range(job_count):
            create_test_job_run(
                temp_db,
                run_id=f"run-{i}",
                status="queued",
                job_type="plan_protocol_job"
            )
        
        # Query with the limit
        jobs = temp_db.list_queue_jobs(status=None, limit=limit)
        
        # Property: Result count should not exceed limit
        assert len(jobs) <= limit, (
            f"Expected at most {limit} jobs, got {len(jobs)}"
        )
        
        # Property: Result count should be min(job_count, limit)
        expected_count = min(job_count, limit)
        assert len(jobs) == expected_count, (
            f"Expected {expected_count} jobs, got {len(jobs)}"
        )
