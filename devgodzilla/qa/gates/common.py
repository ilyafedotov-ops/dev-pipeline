"""
DevGodzilla Common QA Gates

Standard gate implementations for common QA checks.
"""

import re
import shutil
import subprocess
import time
import xml.etree.ElementTree as ET
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
    __test__ = False

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
        for line in output.splitlines():
            line = line.strip()
            if not line:
                continue

            ruff_match = re.match(r"^(?P<path>.+):(?P<line>\d+):(?P<col>\d+):\s+(?P<code>[A-Z]\d+)\s+(?P<msg>.+)$", line)
            if ruff_match:
                findings.append(Finding(
                    gate_id=self.gate_id,
                    severity="error",
                    message=f"{ruff_match.group('code')} {ruff_match.group('msg')}".strip()[:200],
                    file_path=ruff_match.group("path"),
                    line_number=int(ruff_match.group("line")),
                ))
                continue

            eslint_match = re.match(
                r"^(?P<path>.+):\s*(?P<line>\d+):(?P<col>\d+):\s*(?P<msg>.+?)\s*(\[(?P<severity>error|warning)\])?$",
                line,
                re.IGNORECASE,
            )
            if eslint_match:
                severity = (eslint_match.group("severity") or "warning").lower()
                findings.append(Finding(
                    gate_id=self.gate_id,
                    severity="error" if severity == "error" else "warning",
                    message=eslint_match.group("msg").strip()[:200],
                    file_path=eslint_match.group("path"),
                    line_number=int(eslint_match.group("line")),
                ))
                continue

            lower = line.lower()
            if ":" in line and ("error" in lower or "warning" in lower):
                severity = "error" if "error" in lower else "warning"
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


class FormatGate(Gate):
    """
    Gate that checks formatting without modifying files.

    Supports ruff format (Python) and prettier (JS).
    """

    def __init__(
        self,
        *,
        format_command: Optional[List[str]] = None,
        timeout: int = 120,
    ) -> None:
        self.format_command = format_command
        self.timeout = timeout

    @property
    def gate_id(self) -> str:
        return "format"

    @property
    def gate_name(self) -> str:
        return "Formatting Gate"

    @property
    def blocking(self) -> bool:
        return False

    def run(self, context: GateContext) -> GateResult:
        """Check formatting."""
        start = time.time()
        workspace = Path(context.workspace_root)

        cmd = self.format_command
        if not cmd:
            if (workspace / "pyproject.toml").exists() or (workspace / "ruff.toml").exists():
                cmd = ["ruff", "format", "--check", "."]
            elif (workspace / "package.json").exists():
                cmd = ["prettier", "--check", "."]
            else:
                return self.skip("No formatter configuration found")

        if not shutil.which(cmd[0]):
            return self.skip("Formatter not installed")

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
                )

            output = (proc.stdout or proc.stderr or "").strip()
            findings = [
                Finding(
                    gate_id=self.gate_id,
                    severity="warning",
                    message=output[:200] if output else "Formatting issues detected",
                )
            ]
            return GateResult(
                gate_id=self.gate_id,
                gate_name=self.gate_name,
                verdict=GateVerdict.WARN,
                findings=findings,
                duration_seconds=duration,
            )
        except subprocess.TimeoutExpired:
            return self.error(f"Formatting timed out after {self.timeout}s")
        except FileNotFoundError:
            return self.skip("Formatter not installed")
        except Exception as e:
            return self.error(str(e))


class CoverageGate(Gate):
    """
    Gate that checks coverage.xml against a minimum line coverage threshold.
    """

    def __init__(
        self,
        *,
        minimum: float = 80.0,
        coverage_paths: Optional[List[Path]] = None,
    ) -> None:
        self.minimum = float(minimum)
        self.coverage_paths = coverage_paths

    @property
    def gate_id(self) -> str:
        return "coverage"

    @property
    def gate_name(self) -> str:
        return "Coverage Gate"

    def run(self, context: GateContext) -> GateResult:
        workspace = Path(context.workspace_root)
        candidates = self.coverage_paths or [
            workspace / "coverage.xml",
            workspace / "coverage" / "coverage.xml",
        ]

        coverage_path = next((p for p in candidates if p.exists()), None)
        if not coverage_path:
            return self.skip("coverage.xml not found")

        try:
            tree = ET.parse(coverage_path)
            root = tree.getroot()
            line_rate = root.attrib.get("line-rate")
            if line_rate is None:
                return self.error("coverage.xml missing line-rate")
            percent = float(line_rate) * 100.0
        except Exception as e:
            return self.error(f"Failed to parse coverage.xml: {e}")

        verdict = GateVerdict.PASS if percent >= self.minimum else GateVerdict.FAIL
        findings = []
        if verdict == GateVerdict.FAIL:
            findings.append(
                Finding(
                    gate_id=self.gate_id,
                    severity="error",
                    message=f"Coverage {percent:.1f}% below minimum {self.minimum:.1f}%",
                    file_path=str(coverage_path),
                )
            )

        return GateResult(
            gate_id=self.gate_id,
            gate_name=self.gate_name,
            verdict=verdict,
            findings=findings,
            metadata={
                "coverage_percent": percent,
                "minimum_percent": self.minimum,
                "coverage_path": str(coverage_path),
            },
        )
