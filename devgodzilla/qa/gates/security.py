"""
DevGodzilla Security Gate

QA gate for security vulnerability scanning using bandit.
"""

import json
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from devgodzilla.qa.gates.interface import (
    Finding,
    Gate,
    GateContext,
    GateResult,
    GateVerdict,
)


@dataclass
class SecurityFinding:
    """A security vulnerability finding."""
    issue_text: str
    severity: str  # LOW, MEDIUM, HIGH
    confidence: str  # LOW, MEDIUM, HIGH
    filename: str
    lineno: int
    test_id: str
    test_name: str
    code: Optional[str] = None


class SecurityGate(Gate):
    """
    Security scanning gate using bandit (Python) or npm audit (JS).
    
    Runs security scanners on the codebase and fails if high-severity
    vulnerabilities are found.
    """
    
    NAME = "security"
    DESCRIPTION = "Security vulnerability scanning"
    
    def __init__(
        self,
        fail_on_high: bool = True,
        fail_on_medium: bool = False,
        exclude_dirs: Optional[List[str]] = None,
        timeout: int = 120,
    ) -> None:
        self.fail_on_high = fail_on_high
        self.fail_on_medium = fail_on_medium
        self.exclude_dirs = exclude_dirs or [".venv", "venv", "node_modules", "__pycache__"]
        self.timeout = timeout
    
    @property
    def gate_id(self) -> str:
        return self.NAME

    @property
    def gate_name(self) -> str:
        return "Security Gate"

    def run(self, context: GateContext) -> GateResult:
        """Run security scan on workspace."""
        start = time.time()
        workspace_path = Path(context.workspace_root)
        
        # Detect project type
        has_python = (workspace_path / "pyproject.toml").exists() or \
                     (workspace_path / "setup.py").exists() or \
                     list(workspace_path.glob("*.py"))
        has_node = (workspace_path / "package.json").exists()
        
        findings: List[SecurityFinding] = []
        errors: List[str] = []
        
        # Run bandit for Python
        if has_python:
            python_findings, python_error = self._run_bandit(workspace_path)
            findings.extend(python_findings)
            if python_error:
                errors.append(python_error)
        
        # Run npm audit for Node.js
        if has_node:
            node_findings, node_error = self._run_npm_audit(workspace_path)
            findings.extend(node_findings)
            if node_error:
                errors.append(node_error)
        
        # Evaluate results
        high_count = sum(1 for f in findings if f.severity == "HIGH")
        medium_count = sum(1 for f in findings if f.severity == "MEDIUM")
        low_count = sum(1 for f in findings if f.severity == "LOW")
        
        passed = True
        if self.fail_on_high and high_count > 0:
            passed = False
        if self.fail_on_medium and medium_count > 0:
            passed = False
        
        # Build summary
        if not findings and not errors:
            summary = "No security vulnerabilities found"
        elif high_count > 0:
            summary = f"Found {high_count} HIGH severity issues"
        elif medium_count > 0:
            summary = f"Found {medium_count} MEDIUM severity issues"
        else:
            summary = f"Found {low_count} low severity issues"

        result_findings = [self._finding_to_result(f) for f in findings]
        duration = time.time() - start
        verdict = GateVerdict.PASS if passed else GateVerdict.FAIL

        return GateResult(
            gate_id=self.gate_id,
            gate_name=self.gate_name,
            verdict=verdict,
            findings=result_findings,
            duration_seconds=duration,
            metadata={
                "summary": summary,
                "high_count": high_count,
                "medium_count": medium_count,
                "low_count": low_count,
                "errors": errors,
            },
        )

    def evaluate(
        self,
        workspace: str,
        step_name: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> GateResult:
        """Backwards-compatible wrapper for legacy callers."""
        gate_context = GateContext(
            workspace_root=workspace,
            step_name=step_name,
            metadata=context or {},
        )
        return self.run(gate_context)
    
    def _run_bandit(self, workspace: Path) -> tuple[List[SecurityFinding], Optional[str]]:
        """Run bandit security scanner for Python."""
        try:
            exclude = ",".join(self.exclude_dirs)
            cmd = [
                "bandit",
                "-r",
                str(workspace),
                "-f", "json",
                "--exclude", exclude,
                "-ll",  # Only medium and high severity
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )
            
            # Bandit returns 1 if issues found, 0 if clean
            if result.stdout:
                try:
                    data = json.loads(result.stdout)
                    findings = []
                    for issue in data.get("results", []):
                        findings.append(SecurityFinding(
                            issue_text=issue.get("issue_text", ""),
                            severity=issue.get("issue_severity", "LOW").upper(),
                            confidence=issue.get("issue_confidence", "LOW").upper(),
                            filename=issue.get("filename", ""),
                            lineno=issue.get("line_number", 0),
                            test_id=issue.get("test_id", ""),
                            test_name=issue.get("test_name", ""),
                            code=issue.get("code", ""),
                        ))
                    return findings, None
                except json.JSONDecodeError as e:
                    return [], f"Failed to parse bandit output: {e}"
            
            return [], None
            
        except FileNotFoundError:
            return [], "bandit not installed. Install with: pip install bandit"
        except subprocess.TimeoutExpired:
            return [], f"bandit timed out after {self.timeout}s"
        except Exception as e:
            return [], f"bandit error: {e}"
    
    def _run_npm_audit(self, workspace: Path) -> tuple[List[SecurityFinding], Optional[str]]:
        """Run npm audit for Node.js projects."""
        try:
            cmd = ["npm", "audit", "--json"]
            
            result = subprocess.run(
                cmd,
                cwd=workspace,
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )
            
            if result.stdout:
                try:
                    data = json.loads(result.stdout)
                    findings = []
                    
                    for vuln_id, vuln in data.get("vulnerabilities", {}).items():
                        severity = vuln.get("severity", "low").upper()
                        findings.append(SecurityFinding(
                            issue_text=vuln.get("title", vuln_id),
                            severity=severity,
                            confidence="HIGH",
                            filename="package.json",
                            lineno=0,
                            test_id=vuln_id,
                            test_name=vuln.get("name", vuln_id),
                        ))
                    
                    return findings, None
                except json.JSONDecodeError:
                    return [], None  # No vulnerabilities found
            
            return [], None
            
        except FileNotFoundError:
            return [], "npm not installed"
        except subprocess.TimeoutExpired:
            return [], f"npm audit timed out after {self.timeout}s"
        except Exception as e:
            return [], f"npm audit error: {e}"
    
    def _finding_to_result(self, finding: SecurityFinding) -> Finding:
        """Convert a security finding into a QA Finding."""
        severity_map = {
            "HIGH": "critical",
            "MEDIUM": "warning",
            "LOW": "info",
        }
        return Finding(
            gate_id=self.gate_id,
            severity=severity_map.get(finding.severity.upper(), "warning"),
            message=finding.issue_text,
            file_path=finding.filename,
            line_number=finding.lineno,
            rule_id=finding.test_id,
            metadata={
                "confidence": finding.confidence,
                "test_name": finding.test_name,
                "code": finding.code,
            },
        )
