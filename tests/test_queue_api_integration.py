"""
Integration test for queue API endpoints.
"""

import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from devgodzilla.api.app import app
from devgodzilla.db.database import SQLiteDatabase


@pytest.fixture
def test_client():
    """Create a test client with a temporary database."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        db = SQLiteDatabase(db_path)
        db.init_schema()
        
        # Override the database dependency
        from devgodzilla.api.dependencies import get_db
        
        def override_get_db():
            return db
        
        app.dependency_overrides[get_db] = override_get_db
        
        client = TestClient(app)
        
        # Create a test project and some job runs
        project = db.create_project(
            name="test-project",
            git_url="https://github.com/test/test",
            base_branch="main"
        )
        
        # Create some test job runs
        db.create_job_run(
            run_id="run-1",
            job_type="plan_protocol_job",
            status="queued",
            queue="default",
            project_id=project.id
        )
        
        db.create_job_run(
            run_id="run-2",
            job_type="execute_step_job",
            status="running",
            queue="default",
            project_id=project.id
        )
        
        db.create_job_run(
            run_id="run-3",
            job_type="qa_gate_job",
            status="failed",
            queue="default",
            project_id=project.id
        )
        
        yield client
        
        # Clean up
        app.dependency_overrides.clear()


def test_get_queue_stats(test_client):
    """Test GET /queues endpoint."""
    response = test_client.get("/queues")
    
    assert response.status_code == 200
    stats = response.json()
    
    assert len(stats) == 1
    assert stats[0]["name"] == "default"
    assert stats[0]["queued"] == 1
    assert stats[0]["started"] == 1
    assert stats[0]["failed"] == 1


def test_list_queue_jobs_no_filter(test_client):
    """Test GET /queues/jobs without filter."""
    response = test_client.get("/queues/jobs")
    
    assert response.status_code == 200
    jobs = response.json()
    
    assert len(jobs) == 3
    assert all("job_id" in job for job in jobs)
    assert all("job_type" in job for job in jobs)
    assert all("status" in job for job in jobs)


def test_list_queue_jobs_with_status_filter(test_client):
    """Test GET /queues/jobs with status filter."""
    response = test_client.get("/queues/jobs?status=queued")
    
    assert response.status_code == 200
    jobs = response.json()
    
    assert len(jobs) == 1
    assert jobs[0]["status"] == "queued"
    assert jobs[0]["job_type"] == "plan_protocol_job"


def test_list_queue_jobs_with_limit(test_client):
    """Test GET /queues/jobs with limit parameter."""
    response = test_client.get("/queues/jobs?limit=2")
    
    assert response.status_code == 200
    jobs = response.json()
    
    assert len(jobs) == 2
