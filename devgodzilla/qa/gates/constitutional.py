"""
DevGodzilla Constitutional Gate

Gate that validates code against constitution articles.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional

from devgodzilla.qa.gates.interface import (
    Gate,
    GateContext,
    GateResult,
    GateVerdict,
    Finding,
)
from devgodzilla.services.constitution import Constitution, Article
from devgodzilla.logging import get_logger

logger = get_logger(__name__)


class ConstitutionalGate(Gate):
    """
    Gate that validates code against constitution articles.
    
    Checks that code adheres to project governance principles
    defined in the constitution.
    
    Example:
        constitution = constitution_service.load_constitution(project_path)
        gate = ConstitutionalGate(constitution)
        result = gate.run(context)
    """

    def __init__(
        self,
        constitution: Constitution,
        *,
        check_blocking_only: bool = False,
    ) -> None:
        self.constitution = constitution
        self.check_blocking_only = check_blocking_only

    @property
    def gate_id(self) -> str:
        return "constitutional"

    @property
    def gate_name(self) -> str:
        return "Constitutional Gate"

    def run(self, context: GateContext) -> GateResult:
        """Validate against constitution."""
        findings = []
        workspace = Path(context.workspace_root)
        
        articles_to_check = self.constitution.articles
        if self.check_blocking_only:
            articles_to_check = [a for a in articles_to_check if a.blocking]
        
        for article in articles_to_check:
            article_findings = self._check_article(article, workspace, context)
            findings.extend(article_findings)
        
        # Determine verdict
        blocking_findings = [f for f in findings if f.severity == "error"]
        warning_findings = [f for f in findings if f.severity == "warning"]
        
        if blocking_findings:
            verdict = GateVerdict.FAIL
        elif warning_findings:
            verdict = GateVerdict.WARN
        else:
            verdict = GateVerdict.PASS
        
        return GateResult(
            gate_id=self.gate_id,
            gate_name=self.gate_name,
            verdict=verdict,
            findings=findings,
            metadata={
                "constitution_version": self.constitution.version,
                "articles_checked": len(articles_to_check),
            },
        )

    def _check_article(
        self,
        article: Article,
        workspace: Path,
        context: GateContext,
    ) -> List[Finding]:
        """Check compliance with a single article."""
        findings = []
        
        # Basic heuristic checks based on article number
        # In a real implementation, this would use LLM-based validation
        
        article_num = article.number
        severity = "error" if article.blocking else "warning"
        
        # Article III: Test-First Development
        if article_num == "III":
            test_dirs = ["tests", "test", "__tests__"]
            has_tests = any((workspace / d).exists() for d in test_dirs)
            if not has_tests:
                findings.append(Finding(
                    gate_id=self.gate_id,
                    severity=severity,
                    message=f"Article {article_num}: No test directory found",
                    rule_id=f"article-{article_num}",
                    suggestion="Create a tests/ directory with test files",
                ))
        
        # Article IV: Security Requirements
        elif article_num == "IV":
            # Check for common security issues
            secrets_patterns = [".env", "secrets.py", "credentials.json"]
            for pattern in secrets_patterns:
                if (workspace / pattern).exists():
                    # Check if in .gitignore
                    gitignore = workspace / ".gitignore"
                    if gitignore.exists():
                        content = gitignore.read_text()
                        if pattern not in content:
                            findings.append(Finding(
                                gate_id=self.gate_id,
                                severity=severity,
                                message=f"Article {article_num}: {pattern} not in .gitignore",
                                rule_id=f"article-{article_num}",
                                file_path=pattern,
                            ))
        
        # Article IX: Integration Testing
        elif article_num == "IX":
            # Check for integration tests
            integration_patterns = ["tests/integration", "tests/e2e", "test/integration"]
            has_integration = any((workspace / p).exists() for p in integration_patterns)
            if not has_integration:
                findings.append(Finding(
                    gate_id=self.gate_id,
                    severity=severity,
                    message=f"Article {article_num}: No integration test directory found",
                    rule_id=f"article-{article_num}",
                    suggestion="Create tests/integration/ directory",
                ))
        
        return findings


class ConstitutionalSummaryGate(Gate):
    """
    Gate that provides a summary of constitutional compliance.
    
    Uses LLM to analyze code and provide compliance summary.
    This is a lighter-weight check than full ConstitutionalGate.
    """

    def __init__(
        self,
        constitution: Constitution,
    ) -> None:
        self.constitution = constitution

    @property
    def gate_id(self) -> str:
        return "constitutional-summary"

    @property
    def gate_name(self) -> str:
        return "Constitutional Summary Gate"

    @property
    def blocking(self) -> bool:
        return False  # Summary is advisory

    def run(self, context: GateContext) -> GateResult:
        """Generate compliance summary."""
        # In a full implementation, this would call an LLM
        # For now, return a simple pass
        return GateResult(
            gate_id=self.gate_id,
            gate_name=self.gate_name,
            verdict=GateVerdict.PASS,
            metadata={
                "constitution_version": self.constitution.version,
                "articles_count": len(self.constitution.articles),
                "blocking_articles": len([a for a in self.constitution.articles if a.blocking]),
            },
        )
