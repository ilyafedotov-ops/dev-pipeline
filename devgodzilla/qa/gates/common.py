"""
DevGodzilla Common QA Gates

Standard gate implementations for common QA checks.
"""

import subprocess
import time
from pathlib import Path
from typing import List, Optional

from devgodzilla.qa.gates.interface import (
    Gate,
    GateContext,
    GateResult,
    GateVerdict,
    Finding,
)
from devgodzilla.logging import get_logger

logger = get_logger(__name__)


class TestGate(Gate):
    """
    Gate that runs tests.
    
    Supports pytest, npm test, and other test frameworks.
    """

    def __init__(
        self,
        *,
        test_command: Optional[List[str]] = None,
        timeout: int = 300,
    ) -> None:
        self.test_command = test_command
        self.timeout = timeout

    @property
    def gate_id(self) -> str:
        return "test"

    @property
    def gate_name(self) -> str:
        return "Test Gate"

    def run(self, context: GateContext) -> GateResult:
        """Run tests."""
        start = time.time()
        workspace = Path(context.workspace_root)
        
        # Detect test command
        cmd = self.test_command
        if not cmd:
            if (workspace / "pytest.ini").exists() or (workspace / "pyproject.toml").exists():
                cmd = ["pytest", "--tb=short", "-q"]
            elif (workspace / "package.json").exists():
                cmd = ["npm", "test"]
            else:
                return self.skip("No test configuration found")
        
        try:
            proc = subprocess.run(
                cmd,
                cwd=workspace,
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )
            
            duration = time.time() - start
            
            if proc.returncode == 0:
                return GateResult(
                    gate_id=self.gate_id,
                    gate_name=self.gate_name,
                    verdict=GateVerdict.PASS,
                    duration_seconds=duration,
                    metadata={"stdout": proc.stdout[:1000]},
                )
            else:
                findings = self._parse_test_output(proc.stdout + proc.stderr)
                return GateResult(
                    gate_id=self.gate_id,
                    gate_name=self.gate_name,
                    verdict=GateVerdict.FAIL,
                    findings=findings,
                    duration_seconds=duration,
                    metadata={"stdout": proc.stdout[:1000], "stderr": proc.stderr[:1000]},
                )
                
        except subprocess.TimeoutExpired:
            return self.error(f"Tests timed out after {self.timeout}s")
        except Exception as e:
            return self.error(str(e))

    def _parse_test_output(self, output: str) -> List[Finding]:
        """Parse test output for failures."""
        findings = []
        # Simple parsing - could be enhanced with pytest JSON output
        for line in output.split("\n"):
            if "FAILED" in line or "ERROR" in line:
                findings.append(Finding(
                    gate_id=self.gate_id,
                    severity="error",
                    message=line.strip()[:200],
                ))
        return findings[:20]  # Limit findings


class LintGate(Gate):
    """
    Gate that runs linters.
    
    Supports ruff, eslint, and other linters.
    """

    def __init__(
        self,
        *,
        lint_command: Optional[List[str]] = None,
        timeout: int = 120,
    ) -> None:
        self.lint_command = lint_command
        self.timeout = timeout

    @property
    def gate_id(self) -> str:
        return "lint"

    @property
    def gate_name(self) -> str:
        return "Lint Gate"

    @property
    def blocking(self) -> bool:
        return False  # Lint warnings don't block by default

    def run(self, context: GateContext) -> GateResult:
        """Run linter."""
        start = time.time()
        workspace = Path(context.workspace_root)
        
        # Detect linter
        cmd = self.lint_command
        if not cmd:
            if (workspace / "pyproject.toml").exists() or (workspace / "ruff.toml").exists():
                cmd = ["ruff", "check", "."]
            elif (workspace / ".eslintrc.js").exists() or (workspace / ".eslintrc.json").exists():
                cmd = ["eslint", ".", "--format", "compact"]
            else:
                return self.skip("No linter configuration found")
        
        try:
            proc = subprocess.run(
                cmd,
                cwd=workspace,
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )
            
            duration = time.time() - start
            findings = self._parse_lint_output(proc.stdout + proc.stderr)
            
            if proc.returncode == 0 and not findings:
                verdict = GateVerdict.PASS
            elif findings:
                # Check if any are errors
                has_errors = any(f.severity == "error" for f in findings)
                verdict = GateVerdict.FAIL if has_errors else GateVerdict.WARN
            else:
                verdict = GateVerdict.FAIL
            
            return GateResult(
                gate_id=self.gate_id,
                gate_name=self.gate_name,
                verdict=verdict,
                findings=findings,
                duration_seconds=duration,
            )
            
        except subprocess.TimeoutExpired:
            return self.error(f"Linting timed out after {self.timeout}s")
        except FileNotFoundError:
            return self.skip("Linter not installed")
        except Exception as e:
            return self.error(str(e))

    def _parse_lint_output(self, output: str) -> List[Finding]:
        """Parse linter output."""
        findings = []
        for line in output.split("\n"):
            if ":" in line and any(x in line.lower() for x in ["error", "warning", "e", "w"]):
                severity = "error" if "error" in line.lower() else "warning"
                findings.append(Finding(
                    gate_id=self.gate_id,
                    severity=severity,
                    message=line.strip()[:200],
                ))
        return findings[:50]


class TypeGate(Gate):
    """
    Gate that runs type checkers.
    
    Supports mypy, pyright, tsc.
    """

    def __init__(
        self,
        *,
        type_command: Optional[List[str]] = None,
        timeout: int = 180,
    ) -> None:
        self.type_command = type_command
        self.timeout = timeout

    @property
    def gate_id(self) -> str:
        return "type"

    @property
    def gate_name(self) -> str:
        return "Type Check Gate"

    @property
    def blocking(self) -> bool:
        return False  # Type errors usually warnings

    def run(self, context: GateContext) -> GateResult:
        """Run type checker."""
        start = time.time()
        workspace = Path(context.workspace_root)
        
        # Detect type checker
        cmd = self.type_command
        if not cmd:
            if (workspace / "mypy.ini").exists() or (workspace / "pyproject.toml").exists():
                cmd = ["mypy", "."]
            elif (workspace / "tsconfig.json").exists():
                cmd = ["tsc", "--noEmit"]
            else:
                return self.skip("No type checker configuration found")
        
        try:
            proc = subprocess.run(
                cmd,
                cwd=workspace,
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )
            
            duration = time.time() - start
            findings = self._parse_type_output(proc.stdout + proc.stderr)
            
            if proc.returncode == 0:
                verdict = GateVerdict.PASS
            elif findings:
                verdict = GateVerdict.WARN
            else:
                verdict = GateVerdict.FAIL
            
            return GateResult(
                gate_id=self.gate_id,
                gate_name=self.gate_name,
                verdict=verdict,
                findings=findings,
                duration_seconds=duration,
            )
            
        except subprocess.TimeoutExpired:
            return self.error(f"Type checking timed out after {self.timeout}s")
        except FileNotFoundError:
            return self.skip("Type checker not installed")
        except Exception as e:
            return self.error(str(e))

    def _parse_type_output(self, output: str) -> List[Finding]:
        """Parse type checker output."""
        findings = []
        for line in output.split("\n"):
            if "error:" in line.lower() or "warning:" in line.lower():
                severity = "error" if "error:" in line.lower() else "warning"
                findings.append(Finding(
                    gate_id=self.gate_id,
                    severity=severity,
                    message=line.strip()[:200],
                ))
        return findings[:50]


class ChecklistGate(Gate):
    """
    Gate that validates against a checklist.
    
    Checks that expected files and patterns exist.
    """

    def __init__(
        self,
        *,
        required_files: Optional[List[str]] = None,
        required_patterns: Optional[List[str]] = None,
    ) -> None:
        self.required_files = required_files or []
        self.required_patterns = required_patterns or []

    @property
    def gate_id(self) -> str:
        return "checklist"

    @property
    def gate_name(self) -> str:
        return "Checklist Gate"

    def run(self, context: GateContext) -> GateResult:
        """Validate checklist items."""
        start = time.time()
        workspace = Path(context.workspace_root)
        findings = []
        
        # Check required files
        for file_path in self.required_files:
            full_path = workspace / file_path
            if not full_path.exists():
                findings.append(Finding(
                    gate_id=self.gate_id,
                    severity="error",
                    message=f"Missing required file: {file_path}",
                    file_path=file_path,
                ))
        
        # Check required patterns (simple glob)
        for pattern in self.required_patterns:
            matches = list(workspace.glob(pattern))
            if not matches:
                findings.append(Finding(
                    gate_id=self.gate_id,
                    severity="error",
                    message=f"No files matching pattern: {pattern}",
                ))
        
        duration = time.time() - start
        
        if not findings:
            verdict = GateVerdict.PASS
        elif any(f.severity == "error" for f in findings):
            verdict = GateVerdict.FAIL
        else:
            verdict = GateVerdict.WARN
        
        return GateResult(
            gate_id=self.gate_id,
            gate_name=self.gate_name,
            verdict=verdict,
            findings=findings,
            duration_seconds=duration,
        )
