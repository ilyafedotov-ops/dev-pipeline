"""
Tests for SPEX-002 (LLM-based ambiguity detection in ClarifierService)
and SPEX-003 (clarifier integration at tasks stage).

These tests exercise the new detect_ambiguities() method and the
_detect_tasks_ambiguities integration point without requiring a real LLM.
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from devgodzilla.config import Config
from devgodzilla.db.database import SQLiteDatabase
from devgodzilla.engines.interface import Engine, EngineMetadata, EngineKind, EngineRequest, EngineResult
from devgodzilla.models.domain import Clarification
from devgodzilla.services.base import ServiceContext
from devgodzilla.services.clarifier import ClarifierService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _FakeEngine(Engine):
    """A minimal fake engine that returns a canned response."""

    def __init__(self, response_json: str = "[]"):
        self._response = response_json

    @property
    def metadata(self) -> EngineMetadata:
        return EngineMetadata(
            id="fake-engine",
            display_name="Fake Engine",
            kind=EngineKind.API,
            default_model="fake-model",
        )

    def plan(self, req: EngineRequest) -> EngineResult:
        return EngineResult(success=True, stdout=self._response)

    def execute(self, req: EngineRequest) -> EngineResult:
        return EngineResult(success=True, stdout=self._response)

    def qa(self, req: EngineRequest) -> EngineResult:
        return EngineResult(success=True, stdout=self._response)


def _make_context() -> ServiceContext:
    cfg = MagicMock(spec=Config)
    return ServiceContext(config=cfg, request_id="test-req")


def _make_db():
    """Create a temp SQLite database for testing."""
    tmpdir = tempfile.mkdtemp()
    db_path = Path(tmpdir) / "test.db"
    db = SQLiteDatabase(db_path)
    db.init_schema()
    return db


def _make_service(db=None, fake_engine_response="[]"):
    """Create a ClarifierService with a patched engine registry."""
    ctx = _make_context()
    svc = ClarifierService(ctx, db)
    return svc, _FakeEngine(fake_engine_response)


# ---------------------------------------------------------------------------
# SPEX-002 Tests: detect_ambiguities()
# ---------------------------------------------------------------------------

class TestParseAmbiguityResponse:
    """Tests for _parse_ambiguity_response."""

    def test_empty_input(self):
        svc, _ = _make_service()
        assert svc._parse_ambiguity_response("") == []
        assert svc._parse_ambiguity_response("  ") == []

    def test_valid_json_array(self):
        svc, _ = _make_service()
        raw = json.dumps([
            {"key": "missing_auth", "question": "What auth method?", "blocking": True},
            {"key": "vague_error", "question": "How are errors handled?", "blocking": False},
        ])
        result = svc._parse_ambiguity_response(raw)
        assert len(result) == 2
        assert result[0]["key"] == "missing_auth"
        assert result[0]["blocking"] is True
        assert result[1]["key"] == "vague_error"

    def test_json_in_markdown_fences(self):
        svc, _ = _make_service()
        inner = json.dumps([{"key": "test", "question": "Q?", "blocking": False}])
        raw = f"```json\n{inner}\n```"
        result = svc._parse_ambiguity_response(raw)
        assert len(result) == 1
        assert result[0]["key"] == "test"

    def test_empty_array(self):
        svc, _ = _make_service()
        assert svc._parse_ambiguity_response("[]") == []

    def test_invalid_json(self):
        svc, _ = _make_service()
        assert svc._parse_ambiguity_response("not json at all") == []

    def test_json_array_embedded_in_text(self):
        svc, _ = _make_service()
        arr = json.dumps([{"key": "x", "question": "Q?", "blocking": True}])
        raw = f"Here is the result: {arr} and that's it."
        result = svc._parse_ambiguity_response(raw)
        assert len(result) == 1

    def test_missing_key_skipped(self):
        svc, _ = _make_service()
        raw = json.dumps([{"question": "Q?"}])
        assert svc._parse_ambiguity_response(raw) == []

    def test_missing_question_skipped(self):
        svc, _ = _make_service()
        raw = json.dumps([{"key": "k"}])
        assert svc._parse_ambiguity_response(raw) == []

    def test_non_dict_entries_skipped(self):
        svc, _ = _make_service()
        raw = json.dumps(["string", 42, {"key": "k", "question": "Q?"}])
        result = svc._parse_ambiguity_response(raw)
        assert len(result) == 1

    def test_blocking_defaults_false(self):
        svc, _ = _make_service()
        raw = json.dumps([{"key": "k", "question": "Q?"}])
        result = svc._parse_ambiguity_response(raw)
        assert result[0]["blocking"] is False


class TestMakeTransientClarifications:
    """Tests for _make_transient_clarifications."""

    def test_creates_clarifications(self):
        items = [
            {"key": "a", "question": "QA?", "blocking": True},
            {"key": "b", "question": "QB?", "blocking": False},
        ]
        result = ClarifierService._make_transient_clarifications(items, project_id=5)
        assert len(result) == 2
        assert all(isinstance(c, Clarification) for c in result)
        assert result[0].key == "ambiguity_a"
        assert result[0].project_id == 5
        assert result[0].blocking is True
        assert result[1].blocking is False

    def test_empty_items(self):
        assert ClarifierService._make_transient_clarifications([]) == []


class TestDetectAmbiguities:
    """Tests for detect_ambiguities() with mocked engine registry."""

    @patch("devgodzilla.services.clarifier.get_registry")
    def test_empty_content_returns_empty(self, mock_get_registry):
        svc, fake_engine = _make_service()
        result = svc.detect_ambiguities("")
        assert result == []
        mock_get_registry.assert_not_called()

    @patch("devgodzilla.services.clarifier.get_registry")
    def test_whitespace_content_returns_empty(self, mock_get_registry):
        svc, _ = _make_service()
        result = svc.detect_ambiguities("   \n\t  ")
        assert result == []

    @patch("devgodzilla.services.clarifier.get_registry")
    def test_no_ambiguities_found(self, mock_get_registry):
        fake_engine = _FakeEngine("[]")
        mock_registry = MagicMock()
        mock_registry.list_ids.return_value = ["fake-engine"]
        mock_registry.get.return_value = fake_engine
        mock_get_registry.return_value = mock_registry

        svc = ClarifierService(_make_context(), db=None)
        result = svc.detect_ambiguities("Clear spec content", persist=False)
        assert result == []

    @patch("devgodzilla.services.clarifier.get_registry")
    def test_detects_ambiguities_transient(self, mock_get_registry):
        response = json.dumps([
            {"key": "missing_error_handling", "question": "How should errors be handled?", "blocking": True},
            {"key": "vague_perf_req", "question": "What is the target response time?", "blocking": False},
        ])
        fake_engine = _FakeEngine(response)
        mock_registry = MagicMock()
        mock_registry.list_ids.return_value = ["fake-engine"]
        mock_registry.get.return_value = fake_engine
        mock_get_registry.return_value = mock_registry

        svc = ClarifierService(_make_context(), db=None)
        result = svc.detect_ambiguities("# Tasks\n- [ ] Do something", persist=False)
        assert len(result) == 2
        assert result[0].key == "ambiguity_missing_error_handling"
        assert result[0].blocking is True
        assert result[1].key == "ambiguity_vague_perf_req"

    @patch("devgodzilla.services.clarifier.get_registry")
    def test_detects_with_context(self, mock_get_registry):
        response = json.dumps([
            {"key": "ctx_issue", "question": "Context Q?", "blocking": False},
        ])
        fake_engine = _FakeEngine(response)
        mock_registry = MagicMock()
        mock_registry.list_ids.return_value = ["fake-engine"]
        mock_registry.get.return_value = fake_engine
        mock_get_registry.return_value = mock_registry

        svc = ClarifierService(_make_context(), db=None)
        result = svc.detect_ambiguities(
            "Tasks content",
            context="Additional spec context",
            persist=False,
        )
        assert len(result) == 1

    @patch("devgodzilla.services.clarifier.get_registry")
    def test_engine_resolve_failure_returns_empty(self, mock_get_registry):
        mock_registry = MagicMock()
        mock_registry.list_ids.return_value = []
        mock_registry.default_id = property(lambda self: (_ for _ in ()).throw(RuntimeError("no default")))
        del mock_registry.default_id  # Remove the property entirely
        mock_get_registry.return_value = mock_registry

        svc = ClarifierService(_make_context(), db=None)
        result = svc.detect_ambiguities("Some content", persist=False)
        assert result == []

    @patch("devgodzilla.services.clarifier.get_registry")
    def test_llm_call_failure_returns_empty(self, mock_get_registry):
        fake_engine = MagicMock()
        fake_engine.metadata = EngineMetadata(
            id="fake", display_name="Fake", kind=EngineKind.API, default_model="m"
        )
        fake_engine.qa.side_effect = RuntimeError("LLM crashed")
        mock_registry = MagicMock()
        mock_registry.list_ids.return_value = ["fake"]
        mock_registry.get.return_value = fake_engine
        mock_get_registry.return_value = mock_registry

        svc = ClarifierService(_make_context(), db=None)
        result = svc.detect_ambiguities("Content", persist=False)
        assert result == []

    @patch("devgodzilla.services.clarifier.get_registry")
    def test_unsuccessful_result_returns_empty(self, mock_get_registry):
        fake_engine = MagicMock()
        fake_engine.metadata = EngineMetadata(
            id="fake", display_name="Fake", kind=EngineKind.API, default_model="m"
        )
        fake_engine.qa.return_value = EngineResult(success=False, error="timeout")
        mock_registry = MagicMock()
        mock_registry.list_ids.return_value = ["fake"]
        mock_registry.get.return_value = fake_engine
        mock_get_registry.return_value = mock_registry

        svc = ClarifierService(_make_context(), db=None)
        result = svc.detect_ambiguities("Content", persist=False)
        assert result == []

    @patch("devgodzilla.services.clarifier.get_registry")
    def test_persist_to_db(self, mock_get_registry):
        db = _make_db()
        project_id = db.create_project(
            name="test-project", git_url="https://x.com/test/test", base_branch="main"
        ).id

        response = json.dumps([
            {"key": "auth_method", "question": "Which auth method to use?", "blocking": True},
        ])
        fake_engine = _FakeEngine(response)
        mock_registry = MagicMock()
        mock_registry.list_ids.return_value = ["fake-engine"]
        mock_registry.get.return_value = fake_engine
        mock_get_registry.return_value = mock_registry

        svc = ClarifierService(_make_context(), db=db)
        result = svc.detect_ambiguities(
            "# Tasks\n- [ ] Implement auth",
            project_id=project_id,
            persist=True,
        )
        assert len(result) == 1
        assert result[0].key == "ambiguity_auth_method"
        assert result[0].project_id == project_id
        assert result[0].blocking is True
        assert result[0].status == "open"

        # Verify it's in the DB
        open_clarifications = svc.list_open(project_id=project_id)
        assert len(open_clarifications) >= 1
        keys = [c.key for c in open_clarifications]
        assert "ambiguity_auth_method" in keys


class TestDetectAmbiguitiesBackwardCompatibility:
    """Ensure existing policy-based methods still work after SPEX-002 changes."""

    def test_ensure_from_policy_still_works(self):
        db = _make_db()
        project_id = db.create_project(
            name="compat-test", git_url="https://x.com/test/test", base_branch="main"
        ).id
        svc = ClarifierService(_make_context(), db=db)

        policy = {
            "clarifications": [
                {"key": "data_classification", "question": "What data classification?", "blocking": True},
            ]
        }
        result = svc.ensure_from_policy(
            project_id=project_id, policy=policy, applies_to="onboarding"
        )
        assert len(result) == 1
        assert result[0].key == "data_classification"

    def test_list_open_still_works(self):
        db = _make_db()
        project_id = db.create_project(
            name="list-test", git_url="https://x.com/test/test", base_branch="main"
        ).id
        svc = ClarifierService(_make_context(), db=db)
        result = svc.list_open(project_id=project_id)
        assert isinstance(result, list)

    def test_answer_still_works(self):
        db = _make_db()
        project_id = db.create_project(
            name="answer-test", git_url="https://x.com/test/test", base_branch="main"
        ).id
        svc = ClarifierService(_make_context(), db=db)

        svc.ensure_from_policy(
            project_id=project_id,
            policy={"clarifications": [{"key": "k1", "question": "Q?"}]},
            applies_to="test",
        )
        answered = svc.answer(project_id=project_id, key="k1", answer={"value": "A"})
        assert answered.status == "answered"

    def test_has_blocking_open_still_works(self):
        db = _make_db()
        project_id = db.create_project(
            name="blocking-test", git_url="https://x.com/test/test", base_branch="main"
        ).id
        svc = ClarifierService(_make_context(), db=db)
        assert not svc.has_blocking_open(project_id=project_id)

        svc.ensure_from_policy(
            project_id=project_id,
            policy={"clarifications": [{"key": "b1", "question": "Q?", "blocking": True}]},
            applies_to="test",
        )
        assert svc.has_blocking_open(project_id=project_id)


# ---------------------------------------------------------------------------
# SPEX-003 Tests: _detect_tasks_ambiguities integration in SpecificationService
# ---------------------------------------------------------------------------

class TestDetectTasksAmbiguitiesIntegration:
    """Tests for _detect_tasks_ambiguities in SpecificationService."""

    @patch("devgodzilla.services.clarifier.get_registry")
    def test_detect_tasks_ambiguities_calls_clarifier(self, mock_get_registry):
        from devgodzilla.services.specification import SpecificationService

        response = json.dumps([
            {"key": "task_ambiguity", "question": "What does task 1 mean?", "blocking": False},
        ])
        fake_engine = _FakeEngine(response)
        mock_registry = MagicMock()
        mock_registry.list_ids.return_value = ["fake-engine"]
        mock_registry.get.return_value = fake_engine
        mock_get_registry.return_value = mock_registry

        db = _make_db()
        project_id = db.create_project(
            name="spec-test", git_url="https://x.com/test/test", base_branch="main"
        ).id

        svc = SpecificationService(_make_context(), db=db)
        # Call the method directly
        svc._detect_tasks_ambiguities(
            tasks_content="# Tasks\n- [ ] Do something vague",
            project_path="/tmp/fake",
            project_id=project_id,
        )

        # Verify clarification was persisted
        clarifier = ClarifierService(_make_context(), db=db)
        open_items = clarifier.list_open(project_id=project_id, applies_to="tasks")
        assert any("ambiguity_task_ambiguity" == c.key for c in open_items)

    def test_detect_tasks_ambiguities_no_db_noop(self):
        from devgodzilla.services.specification import SpecificationService

        svc = SpecificationService(_make_context(), db=None)
        # Should not raise
        svc._detect_tasks_ambiguities(
            tasks_content="content",
            project_path="/tmp",
            project_id=None,
        )

    def test_detect_tasks_ambiguities_exception_logged_not_raised(self):
        from devgodzilla.services.specification import SpecificationService

        db = _make_db()
        project_id = db.create_project(
            name="exc-test", git_url="https://x.com/test/test", base_branch="main"
        ).id

        svc = SpecificationService(_make_context(), db=db)

        with patch(
            "devgodzilla.services.specification.ClarifierService.detect_ambiguities",
            side_effect=RuntimeError("boom"),
        ):
            # Should not raise
            svc._detect_tasks_ambiguities(
                tasks_content="content",
                project_path="/tmp",
                project_id=project_id,
            )
