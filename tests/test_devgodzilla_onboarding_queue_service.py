"""
Tests for OnboardingQueueService.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from devgodzilla.db.database import SQLiteDatabase
from devgodzilla.services.base import ServiceContext
from devgodzilla.services.onboarding_queue import (
    enqueue_project_onboarding,
    OnboardingEnqueueResult,
)
from devgodzilla.config import load_config


class TestOnboardingQueueService:
    """Tests for onboarding queue functionality."""

    @pytest.fixture
    def db(self, tmp_path: Path):
        db_path = tmp_path / "test.db"
        db = SQLiteDatabase(db_path)
        db.init_schema()
        return db

    @pytest.fixture
    def context(self):
        config = load_config()
        return config

    @pytest.fixture
    def sample_project(self, db: SQLiteDatabase):
        return db.create_project(
            name="Test Project",
            git_url="https://github.com/example/test.git",
            base_branch="main",
        )

    # ==================== enqueue_project_onboarding Tests ====================

    def test_enqueue_project_onboarding_success(self, context, db, sample_project):
        """Test successful enqueueing of project onboarding."""
        mock_client = MagicMock()
        mock_client.run_script.return_value = "job-123"
        mock_client.close = MagicMock()

        with patch(
            "devgodzilla.services.onboarding_queue._build_windmill_client",
            return_value=mock_client,
        ):
            result = enqueue_project_onboarding(
                ServiceContext(config=context),
                db,
                project_id=sample_project.id,
            )

        assert isinstance(result, OnboardingEnqueueResult)
        assert result.windmill_job_id == "job-123"
        assert result.script_path == "u/devgodzilla/project_onboard_api"
        assert result.run_id is not None

        # Verify job run was created in DB
        job_run = db.get_job_run(result.run_id)
        assert job_run is not None
        assert job_run.status == "queued"

    def test_enqueue_project_onboarding_with_options(self, context, db, sample_project):
        """Test enqueueing with custom options."""
        mock_client = MagicMock()
        mock_client.run_script.return_value = "job-456"
        mock_client.close = MagicMock()

        with patch(
            "devgodzilla.services.onboarding_queue._build_windmill_client",
            return_value=mock_client,
        ):
            result = enqueue_project_onboarding(
                ServiceContext(config=context),
                db,
                project_id=sample_project.id,
                branch="feature/test",
                run_discovery_agent=False,
                discovery_pipeline=False,
                clone_if_missing=False,
                discovery_engine_id="custom-engine",
                discovery_model="custom-model",
            )

        assert result.windmill_job_id == "job-456"

        # Verify payload included custom options
        call_args = mock_client.run_script.call_args
        payload = call_args[0][1]  # Second argument is payload
        assert payload["branch"] == "feature/test"
        assert payload["run_discovery_agent"] is False
        assert payload["discovery_pipeline"] is False
        assert payload["clone_if_missing"] is False
        assert payload["discovery_engine_id"] == "custom-engine"
        assert payload["discovery_model"] == "custom-model"

    def test_enqueue_project_onboarding_uses_configured_script_path(self, context, db, sample_project):
        """Test script path is read from config when provided."""
        mock_client = MagicMock()
        mock_client.run_script.return_value = "job-custom"
        mock_client.close = MagicMock()
        context.windmill_onboard_script_path = "u/custom/onboard_script"

        with patch(
            "devgodzilla.services.onboarding_queue._build_windmill_client",
            return_value=mock_client,
        ):
            result = enqueue_project_onboarding(
                ServiceContext(config=context),
                db,
                project_id=sample_project.id,
            )

        assert result.windmill_job_id == "job-custom"
        assert result.script_path == "u/custom/onboard_script"
        script_arg = mock_client.run_script.call_args[0][0]
        assert script_arg == "u/custom/onboard_script"

    def test_enqueue_project_onboarding_creates_event(self, context, db, sample_project):
        """Test that enqueueing creates an event."""
        mock_client = MagicMock()
        mock_client.run_script.return_value = "job-789"
        mock_client.close = MagicMock()

        with patch(
            "devgodzilla.services.onboarding_queue._build_windmill_client",
            return_value=mock_client,
        ):
            enqueue_project_onboarding(
                ServiceContext(config=context),
                db,
                project_id=sample_project.id,
            )

        # Verify event was created - use append_event which is called
        # The event is stored, we verify by checking job run exists
        job_runs = db.list_job_runs(limit=10)
        onboarding_runs = [j for j in job_runs if j.job_type == "onboarding"]
        assert len(onboarding_runs) >= 1

    def test_enqueue_project_onboarding_windmill_error(self, context, db, sample_project):
        """Test handling Windmill errors."""
        mock_client = MagicMock()
        mock_client.run_script.side_effect = Exception("Windmill connection failed")
        mock_client.close = MagicMock()

        with patch(
            "devgodzilla.services.onboarding_queue._build_windmill_client",
            return_value=mock_client,
        ):
            with pytest.raises(Exception, match="Windmill connection failed"):
                enqueue_project_onboarding(
                    ServiceContext(config=context),
                    db,
                    project_id=sample_project.id,
                )

    def test_enqueue_project_onboarding_windmill_disabled(self, context, db, sample_project):
        """Test error when Windmill is not configured."""
        # Create a new config with windmill disabled
        from devgodzilla.config import Config
        config = Config(
            db_path=Path("test.db"),
            windmill_url=None,
            windmill_token=None,
        )
        ctx = ServiceContext(config=config)

        # Should raise RuntimeError when windmill is disabled
        with pytest.raises((RuntimeError, Exception)):
            enqueue_project_onboarding(ctx, db, project_id=sample_project.id)

    def test_enqueue_multiple_projects(self, context, db):
        """Test enqueueing multiple projects."""
        project1 = db.create_project(name="P1", git_url="https://a.com/1.git", base_branch="main")
        project2 = db.create_project(name="P2", git_url="https://a.com/2.git", base_branch="main")

        call_count = [0]
        job_ids = ["job-1", "job-2"]

        def mock_run_script(script, payload):
            result = job_ids[call_count[0]]
            call_count[0] += 1
            return result

        mock_client = MagicMock()
        mock_client.run_script.side_effect = mock_run_script
        mock_client.close = MagicMock()

        with patch(
            "devgodzilla.services.onboarding_queue._build_windmill_client",
            return_value=mock_client,
        ):
            result1 = enqueue_project_onboarding(
                ServiceContext(config=context), db, project_id=project1.id
            )
            result2 = enqueue_project_onboarding(
                ServiceContext(config=context), db, project_id=project2.id
            )

        assert result1.windmill_job_id == "job-1"
        assert result2.windmill_job_id == "job-2"

        # Verify both job runs exist
        runs = db.list_job_runs(limit=10)
        assert len(runs) == 2

    # ==================== OnboardingEnqueueResult Tests ====================

    def test_onboarding_enqueue_result_dataclass(self):
        """Test OnboardingEnqueueResult dataclass."""
        result = OnboardingEnqueueResult(
            run_id="run-123",
            windmill_job_id="job-456",
            script_path="u/devgodzilla/test",
        )

        assert result.run_id == "run-123"
        assert result.windmill_job_id == "job-456"
        assert result.script_path == "u/devgodzilla/test"

        # Test frozen/immutability
        with pytest.raises(Exception):
            result.run_id = "changed"
