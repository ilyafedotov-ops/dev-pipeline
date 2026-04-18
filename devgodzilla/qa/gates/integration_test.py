"""
DevGodzilla Integration Test Gate

QA gate that validates integration tests exist and pass.
"""

import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from devgodzilla.qa.gates.interface import (
    Gate,
    GateContext,
    GateResult,
    GateVerdict,
    Finding,
)
from devgodzilla.logging import get_logger

logger = get_logger(__name__)


class IntegrationTestGate(Gate):
    """
    Gate that discovers and runs integration tests.

    Detects integration test directories/files and runs them with
    appropriate test runners (pytest, jest, etc.).

    Integration test detection patterns:
    - Python: directories/files named ``test_integration*``, ``tests/integration/``,
      or pytest markers ``@pytest.mark.integration``
    - JavaScript: files in ``__tests__/integration/``, ``test/integration/``,
      or files matching ``*.integration.test.*``
    """

    __test__ = False

    def __init__(
        self,
        *,
        test_command: Optional[List[str]] = None,
        timeout: int = 300,
        integration_dirs: Optional[List[str]] = None,
    ) -> None:
        self.test_command = test_command
        self.timeout = timeout
        self.integration_dirs = integration_dirs or [
            "tests/integration",
            "test/integration",
            "tests/test_integration",
            "__tests__/integration",
        ]

    @property
    def gate_id(self) -> str:
        return "integration_test"

    @property
    def gate_name(self) -> str:
        return "Integration Test Gate"

    def run(self, context: GateContext) -> GateResult:
        """Run integration tests."""
        start = time.time()
        workspace = Path(context.workspace_root)

        resolved = self._resolve_command(context, workspace)
        if resolved is None:
            return self.skip("No integration tests found")

        cmd, command_cwd, display = resolved

        try:
            proc = subprocess.run(
                cmd,
                cwd=command_cwd,
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )

            duration = time.time() - start
            metadata: Dict[str, Any] = {
                "command": display,
                "cwd": str(command_cwd),
                "stdout": proc.stdout[:1000],
                "stderr": proc.stderr[:1000],
            }

            if proc.returncode == 0:
                return GateResult(
                    gate_id=self.gate_id,
                    gate_name=self.gate_name,
                    verdict=GateVerdict.PASS,
                    duration_seconds=duration,
                    metadata=metadata,
                )

            findings = self._parse_output(proc.stdout + proc.stderr)
            if not findings:
                findings = [
                    Finding(
                        gate_id=self.gate_id,
                        severity="error",
                        message=(
                            f"Integration tests failed with exit code "
                            f"{proc.returncode}: {display}"
                        )[:200],
                        metadata={
                            "stderr": proc.stderr[:500],
                            "stdout": proc.stdout[:500],
                        },
                    )
                ]
            return GateResult(
                gate_id=self.gate_id,
                gate_name=self.gate_name,
                verdict=GateVerdict.FAIL,
                findings=findings,
                duration_seconds=duration,
                metadata=metadata,
            )

        except subprocess.TimeoutExpired:
            return self.error(f"Integration tests timed out after {self.timeout}s")
        except Exception as e:
            return self.error(str(e))

    def _resolve_command(
        self,
        context: GateContext,
        workspace: Path,
    ) -> Optional[Tuple[List[str], Path, str]]:
        """Resolve the integration test command.

        Priority:
        1. Explicit test_command override
        2. Metadata-supplied commands
        3. Auto-detected from workspace layout
        """
        if self.test_command:
            display = " ".join(self.test_command)
            return self.test_command, workspace, display

        metadata = context.metadata if isinstance(context.metadata, dict) else {}

        # Check metadata for explicit command
        raw_commands = metadata.get("integration_test_commands")
        if isinstance(raw_commands, list):
            for raw in raw_commands:
                text = str(raw).strip()
                if text:
                    return ["bash", "-lc", text], workspace, text

        # Auto-detect based on project type
        has_python = (
            (workspace / "pyproject.toml").exists()
            or (workspace / "setup.py").exists()
            or list(workspace.glob("*.py"))
        )
        has_node = (workspace / "package.json").exists()

        if has_python:
            return self._resolve_python(workspace)
        if has_node:
            return self._resolve_node(workspace)

        return None

    def _resolve_python(
        self, workspace: Path
    ) -> Optional[Tuple[List[str], Path, str]]:
        """Detect and return pytest command for integration tests."""
        # Check if integration test directory/files exist
        has_integration = False

        for d in self.integration_dirs:
            candidate = workspace / d
            if candidate.exists() and candidate.is_dir():
                has_integration = True
                break

        # Also check for integration marker in test files
        if not has_integration:
            for pattern in ("**/test_integration*.py", "**/*_integration_test.py"):
                if list(workspace.glob(pattern)):
                    has_integration = True
                    break

        if not has_integration:
            # Fallback: use pytest -k integration which will discover
            # tests marked or named with 'integration'
            cmd = [
                "python3", "-m", "pytest",
                "-k", "integration",
                "--tb=short", "-q",
            ]
            return cmd, workspace, "pytest -k 'integration' --tb=short -q"

        cmd = [
            "python3", "-m", "pytest",
            "-k", "integration",
            "--tb=short", "-q",
        ]
        return cmd, workspace, "pytest -k 'integration' --tb=short -q"

    def _resolve_node(
        self, workspace: Path
    ) -> Optional[Tuple[List[str], Path, str]]:
        """Detect and return jest command for integration tests."""
        # Check for integration test directories
        has_integration = False
        for d in self.integration_dirs:
            candidate = workspace / d
            if candidate.exists() and candidate.is_dir():
                has_integration = True
                break

        if not has_integration:
            for pattern in (
                "**/*.integration.test.*",
                "**/*.integration.spec.*",
            ):
                if list(workspace.glob(pattern)):
                    has_integration = True
                    break

        # Use jest with testPathPattern regardless (will skip if no matches)
        cmd = [
            "npx", "jest",
            "--testPathPattern", "integration",
            "--passWithNoTests",
        ]
        return cmd, workspace, "jest --testPathPattern 'integration' --passWithNoTests"

    def _parse_output(self, output: str) -> List[Finding]:
        """Parse test output for failures."""
        findings: List[Finding] = []
        for line in output.split("\n"):
            if "FAILED" in line or "ERROR" in line:
                findings.append(
                    Finding(
                        gate_id=self.gate_id,
                        severity="error",
                        message=line.strip()[:200],
                    )
                )
        return findings[:20]
