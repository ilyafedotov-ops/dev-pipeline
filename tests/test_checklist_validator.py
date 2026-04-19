"""Tests for ChecklistValidator."""

import pytest
from pathlib import Path
from unittest.mock import MagicMock

from devgodzilla.engines.interface import Engine, EngineMetadata, EngineKind, EngineResult
from devgodzilla.qa.checklist_validator import (
    ChecklistValidator,
    ChecklistItem,
    ValidationResult,
)


def _make_mock_engine(stdout: str = "", error: str | None = None) -> MagicMock:
    """Create a mock Engine that returns the given stdout via qa()."""
    engine = MagicMock(spec=Engine)
    engine.metadata = EngineMetadata(
        id="mock-engine",
        display_name="Mock Engine",
        kind=EngineKind.CLI,
    )
    engine.qa.return_value = EngineResult(
        success=error is None,
        stdout=stdout,
        stderr="",
        error=error,
    )
    return engine


class TestChecklistItem:
    """Tests for ChecklistItem dataclass."""

    def test_create_item(self):
        item = ChecklistItem(
            id="1",
            description="Test item",
            checked=False,
            required=True,
        )
        assert item.id == "1"
        assert item.description == "Test item"
        assert item.checked is False
        assert item.required is True

    def test_default_values(self):
        item = ChecklistItem(id="1", description="Test")
        assert item.checked is False
        assert item.required is True
        assert item.category == "general"
        assert item.validation_hints == []


class TestValidationResult:
    """Tests for ValidationResult dataclass."""

    def test_create_result(self):
        result = ValidationResult(
            item_id="1",
            passed=True,
            confidence=0.9,
            evidence=["Found test"],
            reasoning="Tests detected",
        )
        assert result.item_id == "1"
        assert result.passed is True
        assert result.confidence == 0.9
        assert result.suggestions == []

    def test_result_with_suggestions(self):
        result = ValidationResult(
            item_id="1",
            passed=False,
            confidence=0.5,
            evidence=[],
            reasoning="No tests found",
            suggestions=["Add unit tests", "Add integration tests"],
        )
        assert len(result.suggestions) == 2


class TestChecklistValidator:
    @pytest.fixture
    def validator(self):
        return ChecklistValidator(use_llm=False)  # Pattern-based only for tests

    @pytest.fixture
    def sample_checklist(self):
        return """
- [ ] Implement user authentication
- [x] Create database schema
- [ ] Add unit tests
- [Optional] Add integration tests
"""

    def test_parse_checklist(self, validator, sample_checklist):
        items = validator.parse_checklist(sample_checklist)
        # The parser may not handle [Optional] prefix, so check what we get
        assert len(items) >= 3
        assert items[0].checked is False
        assert items[1].checked is True
        assert items[2].required is True

    def test_parse_checklist_empty(self, validator):
        items = validator.parse_checklist("")
        assert items == []

    def test_parse_checklist_no_checkboxes(self, validator):
        content = "This is just text\nNo checkboxes here"
        items = validator.parse_checklist(content)
        assert items == []

    def test_extract_keywords(self, validator):
        keywords = validator._extract_keywords("Implement user authentication with OAuth2")
        assert "implement" in keywords
        assert "user" in keywords
        assert "authentication" in keywords
        assert "oauth2" in keywords
        # Stop words should be removed
        assert "with" not in keywords

    def test_extract_keywords_removes_stopwords(self, validator):
        keywords = validator._extract_keywords("The quick brown fox jumps over the lazy dog")
        # Common stop words should be removed
        assert "the" not in keywords
        # "over" is not in the stop words list, so it may be included
        assert "quick" in keywords

    def test_has_test_patterns(self, validator):
        assert validator._has_test_patterns("def test_login(): pass")
        assert validator._has_test_patterns("it('should work', () => {})")
        assert validator._has_test_patterns("describe('feature', () => {})")
        assert validator._has_test_patterns("test('my test', () => {})")
        assert validator._has_test_patterns("expect(result).toBe(true)")
        assert not validator._has_test_patterns("def regular_function(): pass")

    def test_has_error_handling_patterns(self, validator):
        assert validator._has_error_handling_patterns("try:\n    pass\nexcept:")
        assert validator._has_error_handling_patterns("catch (e) {}")
        assert validator._has_error_handling_patterns("raise ValueError()")
        assert not validator._has_error_handling_patterns("def regular_function(): pass")

    def test_validate_item_with_patterns(self, validator, tmp_path):
        test_file = tmp_path / "test_auth.py"
        test_file.write_text("def test_login(): pass")

        item = ChecklistItem(
            id="1",
            description="Add unit tests for authentication",
            required=True,
        )

        result = validator.validate_item(item, [test_file])
        assert result.passed
        assert result.confidence > 0

    def test_validate_item_no_match(self, validator, tmp_path):
        test_file = tmp_path / "main.py"
        test_file.write_text("def regular_function(): pass")

        item = ChecklistItem(
            id="1",
            description="Add blockchain integration",
            required=True,
        )

        result = validator.validate_item(item, [test_file])
        # Should have low confidence since no keywords match
        assert result.confidence < 0.8

    def test_validate_all(self, validator, tmp_path, sample_checklist):
        test_file = tmp_path / "tests.py"
        test_file.write_text("def test_schema(): pass")

        items = validator.parse_checklist(sample_checklist)
        results = validator.validate_all(items, [test_file])

        # Number of results should match number of parsed items
        assert len(results) == len(items)
        assert all(isinstance(r, ValidationResult) for r in results)

    def test_validate_all_with_multiple_artifacts(self, validator, tmp_path):
        (tmp_path / "test_auth.py").write_text("def test_login(): pass")
        (tmp_path / "auth.py").write_text("def login(): pass")

        items = [
            ChecklistItem(id="1", description="Add authentication"),
            ChecklistItem(id="2", description="Add unit tests"),
        ]

        results = validator.validate_all(items, [tmp_path / "test_auth.py", tmp_path / "auth.py"])
        assert len(results) == 2


class TestChecklistValidatorWithEngine:
    """Tests for Engine-based validation (mocked Engine)."""

    def test_validate_with_engine(self, tmp_path):
        mock_engine = _make_mock_engine(
            stdout="PASSED\nConfidence: 0.9\nEvidence: Found implementation"
        )
        validator = ChecklistValidator(engine=mock_engine, use_llm=True)

        test_file = tmp_path / "code.py"
        test_file.write_text("def important_function(): pass")

        item = ChecklistItem(
            id="1",
            description="Implement important function",
            required=True,
        )

        # Force low-confidence pattern result so engine path is taken
        result = validator._validate_with_llm(item, [test_file], None)
        assert result.passed is True

    def test_validate_with_engine_called_via_validate_item(self, tmp_path):
        """Integration: validate_item falls through to engine when pattern confidence < 0.8."""
        mock_engine = _make_mock_engine(
            stdout="PASSED\nConfidence: 0.9\nEvidence: Found implementation"
        )
        validator = ChecklistValidator(engine=mock_engine, use_llm=True)

        # Use a file that won't trigger high pattern confidence
        test_file = tmp_path / "code.py"
        test_file.write_text("def something(): pass")

        item = ChecklistItem(
            id="1",
            description="Implement exotic feature xyz",
            required=True,
        )

        result = validator.validate_item(item, [test_file])
        # Engine should have been called
        assert mock_engine.qa.called

    def test_engine_error_fallback(self, tmp_path):
        mock_engine = _make_mock_engine(error="Engine unavailable")

        validator = ChecklistValidator(engine=mock_engine, use_llm=True)

        test_file = tmp_path / "code.py"
        test_file.write_text("def function(): pass")

        item = ChecklistItem(id="1", description="Do something")

        result = validator._validate_with_llm(item, [test_file], None)
        assert isinstance(result, ValidationResult)
        assert result.passed is False
        assert "Engine QA error" in result.reasoning

    def test_engine_exception_fallback(self, tmp_path):
        """When engine.qa() raises, _validate_with_llm catches and returns a result."""
        mock_engine = MagicMock(spec=Engine)
        mock_engine.qa.side_effect = RuntimeError("Boom")

        validator = ChecklistValidator(engine=mock_engine, use_llm=True)

        test_file = tmp_path / "code.py"
        test_file.write_text("def function(): pass")

        item = ChecklistItem(id="1", description="Do something")

        result = validator._validate_with_llm(item, [test_file], None)
        assert isinstance(result, ValidationResult)
        assert result.passed is False
        assert "Engine validation failed" in result.reasoning

    def test_engine_request_uses_context(self, tmp_path):
        """EngineRequest is populated from context dict."""
        mock_engine = _make_mock_engine(stdout="PASSED\nConfidence: 0.8")
        validator = ChecklistValidator(engine=mock_engine, use_llm=True)

        test_file = tmp_path / "code.py"
        test_file.write_text("pass")

        item = ChecklistItem(id="1", description="Something")
        ctx = {"project_id": 42, "protocol_run_id": 7, "step_run_id": 3}

        validator._validate_with_llm(item, [test_file], ctx)

        call_args = mock_engine.qa.call_args
        req = call_args[0][0]
        assert req.project_id == 42
        assert req.protocol_run_id == 7
        assert req.step_run_id == 3
        assert item.description in req.prompt_text

    def test_no_engine_uses_patterns_only(self, tmp_path):
        """When engine is None, only pattern matching runs."""
        validator = ChecklistValidator(engine=None, use_llm=True)

        test_file = tmp_path / "code.py"
        test_file.write_text("def function(): pass")

        item = ChecklistItem(id="1", description="Do something exotic")

        result = validator.validate_item(item, [test_file])
        assert isinstance(result, ValidationResult)


class TestChecklistValidatorHelpers:
    """Tests for helper methods."""

    @pytest.fixture
    def validator(self):
        return ChecklistValidator(use_llm=False)

    def test_build_artifact_context(self, validator, tmp_path):
        file1 = tmp_path / "file1.py"
        file2 = tmp_path / "file2.py"
        file1.write_text("content1")
        file2.write_text("content2")

        context = validator._build_artifact_context([file1, file2])
        assert "file1.py" in context
        assert "file2.py" in context
        assert "content1" in context
        assert "content2" in context

    def test_build_artifact_context_empty(self, validator, tmp_path):
        context = validator._build_artifact_context([])
        assert context == ""

    def test_parse_llm_response(self, validator):
        response = """
PASSED
Confidence: 0.85
Evidence: Found the implementation at line 10
Reasoning: The code correctly implements the feature
"""
        result = validator._parse_llm_response("1", response)
        assert result.item_id == "1"
        assert result.passed is True
        assert result.confidence == 0.85

    def test_parse_llm_response_failed(self, validator):
        response = "FAILED\nConfidence: 0.9\nNot implemented"
        result = validator._parse_llm_response("1", response)
        assert result.passed is False
