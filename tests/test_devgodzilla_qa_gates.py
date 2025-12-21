"""
Tests for DevGodzilla QA Gates.

Tests the composable QA gate implementations including TestGate, LintGate,
TypeGate, ChecklistGate, and ConstitutionalGate.
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from devgodzilla.qa.gates.interface import (
    Gate,
    GateContext,
    GateResult,
    GateVerdict,
    Finding,
)
from devgodzilla.qa.gates.common import (
    TestGate,
    LintGate,
    TypeGate,
    ChecklistGate,
    FormatGate,
    CoverageGate,
)
from devgodzilla.qa.gates.constitutional import (
    ConstitutionalGate,
    ConstitutionalSummaryGate,
)
from devgodzilla.services.constitution import Constitution, Article


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def workspace(tmp_path):
    """Create a minimal workspace for testing."""
    # Create basic structure
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("# Main module\n")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_main.py").write_text("def test_pass(): pass\n")
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'\n")
    return tmp_path


@pytest.fixture
def gate_context(workspace):
    """Create a basic gate context."""
    return GateContext(
        workspace_root=str(workspace),
        step_name="test-step",
    )


@pytest.fixture
def mock_constitution():
    """Create a mock constitution for testing."""
    articles = [
        Article(
            number="III",
            title="Test-First Development",
            content="All features must have tests.",
            blocking=True,
        ),
        Article(
            number="IV",
            title="Security Requirements",
            content="No secrets in repo.",
            blocking=True,
        ),
        Article(
            number="IX",
            title="Integration Testing",
            content="Integration tests required.",
            blocking=False,
        ),
    ]
    constitution_content = """# Test Constitution

## Article III: Test-First Development
All features must have tests.

## Article IV: Security Requirements
No secrets in repo.

## Article IX: Integration Testing
Integration tests required.
"""
    return Constitution(
        version="1.0",
        content=constitution_content,
        articles=articles,
        hash="test-hash-123",
    )


# =============================================================================
# Test Gate Interface
# =============================================================================

class TestGateInterface:
    """Test Gate base class and interface."""

    def test_gate_result_passed_for_pass_verdict(self):
        """Test GateResult.passed property for PASS verdict."""
        result = GateResult(
            gate_id="test",
            gate_name="Test Gate",
            verdict=GateVerdict.PASS,
        )
        assert result.passed is True
        assert result.blocking is False

    def test_gate_result_passed_for_warn_verdict(self):
        """Test GateResult.passed property for WARN verdict."""
        result = GateResult(
            gate_id="test",
            gate_name="Test Gate",
            verdict=GateVerdict.WARN,
        )
        assert result.passed is True
        assert result.blocking is False

    def test_gate_result_not_passed_for_fail_verdict(self):
        """Test GateResult.passed property for FAIL verdict."""
        result = GateResult(
            gate_id="test",
            gate_name="Test Gate",
            verdict=GateVerdict.FAIL,
        )
        assert result.passed is False
        assert result.blocking is True

    def test_gate_result_blocking_for_error_verdict(self):
        """Test GateResult.blocking property for ERROR verdict."""
        result = GateResult(
            gate_id="test",
            gate_name="Test Gate",
            verdict=GateVerdict.ERROR,
            error="Something went wrong",
        )
        assert result.passed is False
        assert result.blocking is True

    def test_finding_dataclass(self):
        """Test Finding dataclass creation."""
        finding = Finding(
            gate_id="lint",
            severity="error",
            message="Missing docstring",
            file_path="src/main.py",
            line_number=1,
            rule_id="D100",
        )
        assert finding.gate_id == "lint"
        assert finding.severity == "error"
        assert finding.line_number == 1

    def test_gate_context_creation(self, workspace):
        """Test GateContext dataclass creation."""
        context = GateContext(
            workspace_root=str(workspace),
            step_name="step-1",
            step_run_id=123,
            protocol_run_id=456,
        )
        assert context.workspace_root == str(workspace)
        assert context.step_name == "step-1"
        assert context.step_run_id == 123


# =============================================================================
# Test TestGate
# =============================================================================

class TestTestGateImplementation:
    """Test TestGate implementation."""

    def test_gate_id(self):
        """Test TestGate.gate_id property."""
        gate = TestGate()
        assert gate.gate_id == "test"

    def test_gate_name(self):
        """Test TestGate.gate_name property."""
        gate = TestGate()
        assert gate.gate_name == "Test Gate"

    def test_run_with_no_pytest(self, gate_context, workspace):
        """Test running when pytest is not found."""
        gate = TestGate()
        
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError()
            result = gate.run(gate_context)
            
        # Should skip or error gracefully
        assert result.verdict in (GateVerdict.SKIP, GateVerdict.ERROR)


class TestFormatGateImplementation:
    """Test FormatGate implementation."""

    def test_format_gate_warns_on_issues(self, gate_context, workspace):
        gate = FormatGate(format_command=["ruff", "format", "--check", "."])

        mock_proc = Mock()
        mock_proc.returncode = 1
        mock_proc.stdout = "Formatting needed"
        mock_proc.stderr = ""

        with patch("shutil.which") as mock_which, patch("subprocess.run") as mock_run:
            mock_which.return_value = "/usr/bin/ruff"
            mock_run.return_value = mock_proc

            result = gate.run(gate_context)

        assert result.verdict == GateVerdict.WARN
        assert result.findings


class TestCoverageGateImplementation:
    """Test CoverageGate implementation."""

    def test_coverage_gate_passes_on_threshold(self, gate_context, workspace):
        coverage_xml = workspace / "coverage.xml"
        coverage_xml.write_text(
            """<?xml version="1.0" ?>
<coverage line-rate="0.85"></coverage>
""",
            encoding="utf-8",
        )
        gate = CoverageGate(minimum=80.0)
        result = gate.run(gate_context)
        assert result.verdict == GateVerdict.PASS

    def test_coverage_gate_fails_below_threshold(self, gate_context, workspace):
        coverage_xml = workspace / "coverage.xml"
        coverage_xml.write_text(
            """<?xml version="1.0" ?>
<coverage line-rate="0.50"></coverage>
""",
            encoding="utf-8",
        )
        gate = CoverageGate(minimum=80.0)
        result = gate.run(gate_context)
        assert result.verdict == GateVerdict.FAIL
        assert result.findings

    def test_run_with_passing_tests(self, gate_context, workspace):
        """Test running with passing tests."""
        gate = TestGate()
        
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="1 passed",
                stderr="",
            )
            result = gate.run(gate_context)
            
        assert result.verdict == GateVerdict.PASS
        assert len(result.findings) == 0

    def test_run_with_failing_tests(self, gate_context, workspace):
        """Test running with failing tests."""
        gate = TestGate()
        
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1,
                stdout="1 failed",
                stderr="FAILED tests/test_main.py::test_fail",
            )
            result = gate.run(gate_context)
            
        assert result.verdict == GateVerdict.FAIL
        assert len(result.findings) > 0

    def test_custom_test_command(self, gate_context):
        """Test using custom test command."""
        gate = TestGate(test_command=["npm", "test"])
        
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="All tests passed",
                stderr="",
            )
            result = gate.run(gate_context)
            
        mock_run.assert_called_once()
        call_args = mock_run.call_args
        assert call_args[0][0] == ["npm", "test"]


# =============================================================================
# Test LintGate
# =============================================================================

class TestLintGateImplementation:
    """Test LintGate implementation."""

    def test_gate_id(self):
        """Test LintGate.gate_id property."""
        gate = LintGate()
        assert gate.gate_id == "lint"

    def test_gate_name(self):
        """Test LintGate.gate_name property."""
        gate = LintGate()
        assert gate.gate_name == "Lint Gate"

    def test_non_blocking_by_default(self):
        """Test that LintGate is non-blocking by default."""
        gate = LintGate()
        assert gate.blocking is False

    def test_run_with_clean_code(self, gate_context):
        """Test running on code with no lint issues."""
        gate = LintGate()
        
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="",
                stderr="",
            )
            result = gate.run(gate_context)
            
        assert result.verdict == GateVerdict.PASS

    def test_run_with_lint_warnings(self, gate_context):
        """Test running on code with lint warnings."""
        gate = LintGate()
        
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1,
                stdout="src/main.py:1:1: W291 trailing whitespace",
                stderr="",
            )
            result = gate.run(gate_context)
            
        assert result.verdict in (GateVerdict.WARN, GateVerdict.FAIL)
        assert len(result.findings) > 0


# =============================================================================
# Test TypeGate
# =============================================================================

class TestTypeGateImplementation:
    """Test TypeGate implementation."""

    def test_gate_id(self):
        """Test TypeGate.gate_id property."""
        gate = TypeGate()
        assert gate.gate_id == "type"

    def test_gate_name(self):
        """Test TypeGate.gate_name property."""
        gate = TypeGate()
        assert gate.gate_name == "Type Check Gate"

    def test_non_blocking_by_default(self):
        """Test that TypeGate is non-blocking by default."""
        gate = TypeGate()
        assert gate.blocking is False

    def test_run_with_no_type_errors(self, gate_context):
        """Test running on well-typed code."""
        gate = TypeGate()
        
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="Success: no issues found",
                stderr="",
            )
            result = gate.run(gate_context)
            
        assert result.verdict == GateVerdict.PASS


# =============================================================================
# Test ChecklistGate
# =============================================================================

class TestChecklistGateImplementation:
    """Test ChecklistGate implementation."""

    def test_gate_id(self):
        """Test ChecklistGate.gate_id property."""
        gate = ChecklistGate()
        assert gate.gate_id == "checklist"

    def test_gate_name(self):
        """Test ChecklistGate.gate_name property."""
        gate = ChecklistGate()
        assert gate.gate_name == "Checklist Gate"

    def test_run_with_all_required_files(self, workspace):
        """Test when all required files exist."""
        gate = ChecklistGate(required_files=["src/main.py", "pyproject.toml"])
        context = GateContext(workspace_root=str(workspace))
        
        result = gate.run(context)
        
        assert result.verdict == GateVerdict.PASS

    def test_run_with_missing_required_file(self, workspace):
        """Test when a required file is missing."""
        gate = ChecklistGate(required_files=["src/main.py", "missing.txt"])
        context = GateContext(workspace_root=str(workspace))
        
        result = gate.run(context)
        
        assert result.verdict == GateVerdict.FAIL
        assert any("missing.txt" in f.message for f in result.findings)

    def test_run_with_empty_requirements(self, workspace):
        """Test with no required files specified."""
        gate = ChecklistGate()
        context = GateContext(workspace_root=str(workspace))
        
        result = gate.run(context)
        
        assert result.verdict == GateVerdict.PASS


# =============================================================================
# Test ConstitutionalGate
# =============================================================================

class TestConstitutionalGateImplementation:
    """Test ConstitutionalGate implementation."""

    def test_gate_id(self, mock_constitution):
        """Test ConstitutionalGate.gate_id property."""
        gate = ConstitutionalGate(mock_constitution)
        assert gate.gate_id == "constitutional"

    def test_gate_name(self, mock_constitution):
        """Test ConstitutionalGate.gate_name property."""
        gate = ConstitutionalGate(mock_constitution)
        assert gate.gate_name == "Constitutional Gate"

    def test_run_with_test_directory(self, workspace, mock_constitution):
        """Test Article III passes when tests directory exists."""
        gate = ConstitutionalGate(mock_constitution)
        context = GateContext(workspace_root=str(workspace))
        
        result = gate.run(context)
        
        # Should not have Article III violation (tests dir exists)
        article_iii_findings = [
            f for f in result.findings 
            if f.rule_id == "article-III"
        ]
        assert len(article_iii_findings) == 0

    def test_run_without_test_directory(self, tmp_path, mock_constitution):
        """Test Article III fails when no tests directory."""
        # Create workspace without tests
        workspace = tmp_path / "no_tests"
        workspace.mkdir()
        (workspace / "src").mkdir()
        
        gate = ConstitutionalGate(mock_constitution)
        context = GateContext(workspace_root=str(workspace))
        
        result = gate.run(context)
        
        # Should have Article III violation
        article_iii_findings = [
            f for f in result.findings 
            if f.rule_id == "article-III"
        ]
        assert len(article_iii_findings) > 0

    def test_blocking_only_mode(self, mock_constitution, workspace):
        """Test check_blocking_only flag."""
        gate = ConstitutionalGate(mock_constitution, check_blocking_only=True)
        context = GateContext(workspace_root=str(workspace))
        
        result = gate.run(context)
        
        # Metadata should show only blocking articles checked
        assert result.metadata.get("articles_checked") == 2  # III and IV are blocking

    def test_result_includes_constitution_version(self, mock_constitution, workspace):
        """Test that result includes constitution version."""
        gate = ConstitutionalGate(mock_constitution)
        context = GateContext(workspace_root=str(workspace))
        
        result = gate.run(context)
        
        assert result.metadata.get("constitution_version") == "1.0"


class TestConstitutionalSummaryGateImplementation:
    """Test ConstitutionalSummaryGate implementation."""

    def test_gate_id(self, mock_constitution):
        """Test ConstitutionalSummaryGate.gate_id property."""
        gate = ConstitutionalSummaryGate(mock_constitution)
        assert gate.gate_id == "constitutional-summary"

    def test_non_blocking(self, mock_constitution):
        """Test that summary gate is non-blocking."""
        gate = ConstitutionalSummaryGate(mock_constitution)
        assert gate.blocking is False

    def test_run_returns_pass(self, mock_constitution, workspace):
        """Test run returns PASS (advisory only)."""
        gate = ConstitutionalSummaryGate(mock_constitution)
        context = GateContext(workspace_root=str(workspace))
        
        result = gate.run(context)
        
        assert result.verdict == GateVerdict.PASS
        assert result.metadata.get("articles_count") == 3


# =============================================================================
# Test Gate Base Class Methods
# =============================================================================

class TestGateBaseMethods:
    """Test Gate base class convenience methods."""

    def test_skip_method(self, mock_constitution):
        """Test Gate.skip() method."""
        gate = ConstitutionalGate(mock_constitution)
        result = gate.skip("Not applicable")
        
        assert result.verdict == GateVerdict.SKIP
        assert result.metadata.get("skip_reason") == "Not applicable"

    def test_error_method(self, mock_constitution):
        """Test Gate.error() method."""
        gate = ConstitutionalGate(mock_constitution)
        result = gate.error("Something broke")
        
        assert result.verdict == GateVerdict.ERROR
        assert result.error == "Something broke"
