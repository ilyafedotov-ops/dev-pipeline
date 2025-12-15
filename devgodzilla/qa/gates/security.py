"""
DevGodzilla Security Gate

QA gate for security vulnerability scanning using bandit.
"""

import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from devgodzilla.qa.gates.interface import Gate, GateResult, Severity


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
    
    def evaluate(
        self,
        workspace: str,
        step_name: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> GateResult:
        """Run security scan on workspace."""
        workspace_path = Path(workspace)
        
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
        
        # Build message
        if not findings and not errors:
            message = "No security vulnerabilities found"
            severity = Severity.INFO
        elif high_count > 0:
            message = f"Found {high_count} HIGH severity issues"
            severity = Severity.ERROR
        elif medium_count > 0:
            message = f"Found {medium_count} MEDIUM severity issues"
            severity = Severity.WARNING
        else:
            message = f"Found {low_count} low severity issues"
            severity = Severity.INFO
        
        return GateResult(
            gate_name=self.NAME,
            passed=passed,
            message=message,
            severity=severity,
            details={
                "high_count": high_count,
                "medium_count": medium_count,
                "low_count": low_count,
                "findings": [self._finding_to_dict(f) for f in findings],
                "errors": errors,
            },
        )
    
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
    
    def _finding_to_dict(self, finding: SecurityFinding) -> Dict[str, Any]:
        """Convert finding to dictionary."""
        return {
            "issue_text": finding.issue_text,
            "severity": finding.severity,
            "confidence": finding.confidence,
            "filename": finding.filename,
            "lineno": finding.lineno,
            "test_id": finding.test_id,
            "test_name": finding.test_name,
        }
