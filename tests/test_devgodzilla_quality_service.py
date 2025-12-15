"""
Tests for DevGodzilla Quality Service.

Tests the QualityService including gate orchestration, verdict aggregation,
and database integration for step quality assessment.
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
from dataclasses import dataclass
from typing import Optional

from devgodzilla.services.quality import (
    QualityService,
    QAResult,
    QAVerdict,
)
from devgodzilla.qa.gates.interface import (
    Gate,
    GateContext,
    GateResult,
    GateVerdict,
    Finding,
)
from devgodzilla.qa.gates.common import TestGate, LintGate
from devgodzilla.services.base import ServiceContext


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def workspace(tmp_path):
    """Create a minimal workspace for testing."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("# Main\n")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_main.py").write_text("def test_pass(): pass\n")
    return tmp_path


@pytest.fixture
def service_context():
    """Create a mock service context."""
    config = Mock()
    config.engine_defaults = {}
    return ServiceContext(config=config)


@pytest.fixture
def mock_db():
    """Create a mock database."""
    db = Mock()
    
    # Mock project
    mock_project = Mock()
    mock_project.id = 1
    mock_project.repo_path = "/tmp/repo"
    mock_project.local_path = "/tmp/repo"  # Used by QualityService._get_workspace
    mock_project.default_branch = "main"
    
    # Mock protocol run
    mock_run = Mock()
    mock_run.id = 100
    mock_run.project_id = 1
    mock_run.worktree_path = None
    mock_run.protocol_root = ".protocols/test"
    
    # Mock step run
    mock_step = Mock()
    mock_step.id = 1000
    mock_step.run_id = 100
    mock_step.step_name = "step-1"
    mock_step.status = "completed"
    
    db.get_step_run.return_value = mock_step
    db.get_protocol_run.return_value = mock_run
    db.get_project.return_value = mock_project
    
    return db


class PassingGate(Gate):
    """A gate that always passes."""
    
    @property
    def gate_id(self):
        return "passing"
    
    @property
    def gate_name(self):
        return "Passing Gate"
    
    def run(self, context: GateContext) -> GateResult:
        return GateResult(
            gate_id=self.gate_id,
            gate_name=self.gate_name,
            verdict=GateVerdict.PASS,
        )


class FailingGate(Gate):
    """A gate that always fails."""
    
    @property
    def gate_id(self):
        return "failing"
    
    @property
    def gate_name(self):
        return "Failing Gate"
    
    def run(self, context: GateContext) -> GateResult:
        return GateResult(
            gate_id=self.gate_id,
            gate_name=self.gate_name,
            verdict=GateVerdict.FAIL,
            findings=[
                Finding(
                    gate_id=self.gate_id,
                    severity="error",
                    message="Always fails",
                )
            ],
        )


class WarningGate(Gate):
    """A gate that always warns."""
    
    @property
    def gate_id(self):
        return "warning"
    
    @property
    def gate_name(self):
        return "Warning Gate"
    
    @property
    def blocking(self):
        return False
    
    def run(self, context: GateContext) -> GateResult:
        return GateResult(
            gate_id=self.gate_id,
            gate_name=self.gate_name,
            verdict=GateVerdict.WARN,
            findings=[
                Finding(
                    gate_id=self.gate_id,
                    severity="warning",
                    message="This is a warning",
                )
            ],
        )


# =============================================================================
# Test QualityService Instantiation
# =============================================================================

class TestQualityServiceInstantiation:
    """Test service creation with gates."""

    def test_create_with_context_and_db(self, service_context, mock_db):
        """Test creating QualityService with context and database."""
        service = QualityService(context=service_context, db=mock_db)
        assert service is not None

    def test_create_with_default_gates(self, service_context, mock_db):
        """Test that default gates are set."""
        service = QualityService(context=service_context, db=mock_db)
        # Default gates should include TestGate and LintGate
        assert hasattr(service, 'default_gates') or hasattr(service, '_default_gates')

    def test_create_with_custom_gates(self, service_context, mock_db):
        """Test creating with custom gates."""
        custom_gates = [PassingGate(), WarningGate()]
        service = QualityService(
            context=service_context,
            db=mock_db,
            default_gates=custom_gates,
        )
        assert service is not None


# =============================================================================
# Test QAResult
# =============================================================================

class TestQAResult:
    """Test QAResult dataclass."""

    def test_qa_result_pass(self):
        """Test QAResult with pass verdict."""
        result = QAResult(
            step_run_id=1,
            verdict=QAVerdict.PASS,
        )
        assert result.passed is True

    def test_qa_result_fail(self):
        """Test QAResult with fail verdict."""
        result = QAResult(
            step_run_id=1,
            verdict=QAVerdict.FAIL,
        )
        assert result.passed is False

    def test_qa_result_warn(self):
        """Test QAResult with warn verdict."""
        result = QAResult(
            step_run_id=1,
            verdict=QAVerdict.WARN,
        )
        assert result.passed is True  # Warnings still pass

    def test_all_findings_aggregation(self):
        """Test all_findings property aggregates gate results."""
        gate_results = [
            GateResult(
                gate_id="gate1",
                gate_name="Gate 1",
                verdict=GateVerdict.FAIL,
                findings=[
                    Finding(gate_id="gate1", severity="error", message="Error 1"),
                    Finding(gate_id="gate1", severity="error", message="Error 2"),
                ],
            ),
            GateResult(
                gate_id="gate2",
                gate_name="Gate 2",
                verdict=GateVerdict.WARN,
                findings=[
                    Finding(gate_id="gate2", severity="warning", message="Warning 1"),
                ],
            ),
        ]
        
        result = QAResult(
            step_run_id=1,
            verdict=QAVerdict.FAIL,
            gate_results=gate_results,
        )
        
        all_findings = result.all_findings
        assert len(all_findings) == 3

    def test_blocking_findings(self):
        """Test blocking_findings filters correctly."""
        gate_results = [
            GateResult(
                gate_id="gate1",
                gate_name="Gate 1",
                verdict=GateVerdict.FAIL,
                findings=[
                    Finding(gate_id="gate1", severity="error", message="Error"),
                    Finding(gate_id="gate1", severity="warning", message="Warning"),
                ],
            ),
        ]
        
        result = QAResult(
            step_run_id=1,
            verdict=QAVerdict.FAIL,
            gate_results=gate_results,
        )
        
        blocking = result.blocking_findings
        # Only error severity should be blocking
        assert all(f.severity == "error" for f in blocking)


# =============================================================================
# Test Verdict Aggregation
# =============================================================================

class TestVerdictAggregation:
    """Test _aggregate_verdict logic."""

    def test_all_pass_returns_pass(self, service_context, mock_db):
        """Test aggregation when all gates pass."""
        service = QualityService(
            context=service_context,
            db=mock_db,
            default_gates=[PassingGate()],
        )
        
        gate_results = [
            GateResult(gate_id="g1", gate_name="G1", verdict=GateVerdict.PASS),
            GateResult(gate_id="g2", gate_name="G2", verdict=GateVerdict.PASS),
        ]
        
        verdict = service._aggregate_verdict(gate_results)
        assert verdict == QAVerdict.PASS

    def test_any_fail_returns_fail(self, service_context, mock_db):
        """Test aggregation when any gate fails."""
        service = QualityService(
            context=service_context,
            db=mock_db,
        )
        
        gate_results = [
            GateResult(gate_id="g1", gate_name="G1", verdict=GateVerdict.PASS),
            GateResult(gate_id="g2", gate_name="G2", verdict=GateVerdict.FAIL),
        ]
        
        verdict = service._aggregate_verdict(gate_results)
        assert verdict == QAVerdict.FAIL

    def test_warn_with_no_fail_returns_warn(self, service_context, mock_db):
        """Test aggregation with only warnings."""
        service = QualityService(
            context=service_context,
            db=mock_db,
        )
        
        gate_results = [
            GateResult(gate_id="g1", gate_name="G1", verdict=GateVerdict.PASS),
            GateResult(gate_id="g2", gate_name="G2", verdict=GateVerdict.WARN),
        ]
        
        verdict = service._aggregate_verdict(gate_results)
        assert verdict == QAVerdict.WARN

    def test_error_verdict_returns_error(self, service_context, mock_db):
        """Test aggregation when gate errors."""
        service = QualityService(
            context=service_context,
            db=mock_db,
        )
        
        gate_results = [
            GateResult(gate_id="g1", gate_name="G1", verdict=GateVerdict.PASS),
            GateResult(gate_id="g2", gate_name="G2", verdict=GateVerdict.ERROR, error="Crashed"),
        ]
        
        verdict = service._aggregate_verdict(gate_results)
        assert verdict in (QAVerdict.FAIL, QAVerdict.ERROR)

    def test_empty_results_returns_pass(self, service_context, mock_db):
        """Test aggregation with no gate results."""
        service = QualityService(
            context=service_context,
            db=mock_db,
        )
        
        verdict = service._aggregate_verdict([])
        assert verdict in (QAVerdict.PASS, QAVerdict.SKIP)


# =============================================================================
# Test Evaluate Step (Standalone)
# =============================================================================

class TestEvaluateStep:
    """Test standalone evaluate_step."""

    def test_evaluate_step_with_passing_gates(self, service_context, mock_db, workspace):
        """Test evaluate_step with all passing gates."""
        service = QualityService(
            context=service_context,
            db=mock_db,
            default_gates=[PassingGate()],
        )
        
        result = service.evaluate_step(
            workspace_root=workspace,
            step_name="test-step",
        )
        
        assert result.verdict == QAVerdict.PASS
        assert len(result.gate_results) == 1

    def test_evaluate_step_with_failing_gates(self, service_context, mock_db, workspace):
        """Test evaluate_step with failing gates."""
        service = QualityService(
            context=service_context,
            db=mock_db,
            default_gates=[FailingGate()],
        )
        
        result = service.evaluate_step(
            workspace_root=workspace,
            step_name="test-step",
        )
        
        assert result.verdict == QAVerdict.FAIL

    def test_evaluate_step_custom_gates(self, service_context, mock_db, workspace):
        """Test evaluate_step with custom gates override."""
        service = QualityService(
            context=service_context,
            db=mock_db,
            default_gates=[FailingGate()],  # Default fails
        )
        
        # Override with passing gate
        result = service.evaluate_step(
            workspace_root=workspace,
            step_name="test-step",
            gates=[PassingGate()],
        )
        
        assert result.verdict == QAVerdict.PASS

    def test_evaluate_step_returns_duration(self, service_context, mock_db, workspace):
        """Test that evaluate_step includes duration."""
        service = QualityService(
            context=service_context,
            db=mock_db,
            default_gates=[PassingGate()],
        )
        
        result = service.evaluate_step(
            workspace_root=workspace,
            step_name="test-step",
        )
        
        # Duration might be in result or metadata
        assert result.duration_seconds is not None or "duration" in str(result.metadata)


# =============================================================================
# Test Run QA (Database Integration)
# =============================================================================

class TestRunQA:
    """Test run_qa with mock database."""

    def test_run_qa_fetches_step(self, service_context, mock_db, workspace, tmp_path):
        """Test that run_qa fetches step from database."""
        # Setup mock to return proper paths
        mock_db.get_project.return_value.local_path = str(workspace)
        
        service = QualityService(
            context=service_context,
            db=mock_db,
            default_gates=[PassingGate()],
        )
        
        result = service.run_qa(step_run_id=1000)
        
        mock_db.get_step_run.assert_called_with(1000)

    def test_run_qa_returns_qa_result(self, service_context, mock_db, workspace):
        """Test that run_qa returns QAResult."""
        mock_db.get_project.return_value.local_path = str(workspace)
        
        service = QualityService(
            context=service_context,
            db=mock_db,
            default_gates=[PassingGate()],
        )
        
        result = service.run_qa(step_run_id=1000)
        
        assert isinstance(result, QAResult)
        assert result.step_run_id == 1000

    def test_run_qa_with_skip_gates(self, service_context, mock_db, workspace):
        """Test run_qa with skip_gates parameter."""
        mock_db.get_project.return_value.local_path = str(workspace)
        
        service = QualityService(
            context=service_context,
            db=mock_db,
            default_gates=[PassingGate(), FailingGate()],
        )
        
        result = service.run_qa(
            step_run_id=1000,
            skip_gates=["failing"],
        )
        
        # Should only have one gate result (the passing one)
        gate_ids = [g.gate_id for g in result.gate_results]
        assert "failing" not in gate_ids


# =============================================================================
# Test Inline QA
# =============================================================================

class TestRunInlineQA:
    """Test run_inline_qa for quick feedback."""

    def test_run_inline_qa_uses_fewer_gates(self, service_context, mock_db, workspace):
        """Test that inline QA uses a lighter gate set."""
        mock_db.get_project.return_value.local_path = str(workspace)
        
        service = QualityService(
            context=service_context,
            db=mock_db,
            default_gates=[PassingGate(), WarningGate()],
        )
        
        result = service.run_inline_qa(step_run_id=1000)
        
        assert isinstance(result, QAResult)

    def test_run_inline_qa_with_custom_gates(self, service_context, mock_db, workspace):
        """Test inline QA with custom gates."""
        mock_db.get_project.return_value.local_path = str(workspace)
        
        service = QualityService(
            context=service_context,
            db=mock_db,
        )
        
        result = service.run_inline_qa(
            step_run_id=1000,
            gates=[PassingGate()],
        )
        
        assert result.verdict == QAVerdict.PASS
