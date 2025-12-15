"""
DevGodzilla Feedback Router

Routes QA feedback to appropriate handlers for auto-fix or escalation.
"""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable

from devgodzilla.logging import get_logger
from devgodzilla.qa.gates import Finding, GateResult, GateVerdict

logger = get_logger(__name__)


class FeedbackAction(str, Enum):
    """Action to take for feedback."""
    AUTO_FIX = "auto_fix"    # Attempt automatic fix
    RETRY = "retry"          # Retry the step
    ESCALATE = "escalate"    # Escalate to human
    IGNORE = "ignore"        # Ignore the feedback
    BLOCK = "block"          # Block and wait


class ErrorCategory(str, Enum):
    """Category of error for routing."""
    SYNTAX = "syntax"
    LINT = "lint"
    FORMAT = "format"
    TYPE_CHECK = "typecheck"
    TEST = "test"
    SECURITY = "security"
    LOGIC = "logic"
    OTHER = "other"


@dataclass
class FeedbackRoute:
    """A route for handling feedback."""
    category: ErrorCategory
    action: FeedbackAction
    max_attempts: int = 3
    handler: Optional[Callable] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RoutedFeedback:
    """Feedback with routing decision."""
    finding: Finding
    route: FeedbackRoute
    attempt: int = 0
    resolved: bool = False
    resolution: Optional[str] = None


# Auto-fixable error categories
AUTO_FIXABLE_CATEGORIES = {
    ErrorCategory.SYNTAX,
    ErrorCategory.LINT,
    ErrorCategory.FORMAT,
}


def classify_error(finding: Finding) -> ErrorCategory:
    """Classify a finding into an error category."""
    message = finding.message.lower()
    rule_id = (finding.rule_id or "").lower()
    
    # Syntax errors
    if any(x in message for x in ["syntax", "parse", "unexpected token", "unterminated"]):
        return ErrorCategory.SYNTAX
    
    # Lint errors
    if any(x in message for x in ["lint", "ruff", "eslint", "pylint"]):
        return ErrorCategory.LINT
    # Use startswith for standard rule prefixes to avoid false positives
    if any(rule_id.startswith(x) for x in ["e", "f", "w", "c", "n"]):
        return ErrorCategory.LINT
    
    # Format errors
    if any(x in message for x in ["format", "black", "prettier", "indent"]):
        return ErrorCategory.FORMAT
    
    # Type check errors
    if any(x in message for x in ["type", "mypy", "pyright", "tsc", "undefined"]):
        return ErrorCategory.TYPE_CHECK
    
    # Test failures
    if any(x in message for x in ["test", "assert", "failed", "pytest"]):
        return ErrorCategory.TEST
    
    # Security issues
    if any(x in message for x in ["security", "vulnerability", "secret", "credential", "password", "unsafe"]):
        return ErrorCategory.SECURITY
    if rule_id.startswith("s"): # Bandit rules
        return ErrorCategory.SECURITY
    
    return ErrorCategory.OTHER


class FeedbackRouter:
    """
    Routes QA feedback to appropriate handlers.
    
    Responsibilities:
    - Classify errors by category
    - Decide routing action (auto-fix, retry, escalate)
    - Track fix attempts
    - Invoke handlers for auto-fix
    
    Example:
        router = FeedbackRouter()
        
        for finding in qa_result.all_findings:
            routed = router.route(finding)
            
            if routed.route.action == FeedbackAction.AUTO_FIX:
                # Attempt auto-fix
                success = router.attempt_fix(routed, context)
    """

    def __init__(
        self,
        *,
        default_routes: Optional[Dict[ErrorCategory, FeedbackRoute]] = None,
        max_auto_fix_attempts: int = 3,
    ) -> None:
        self.max_auto_fix_attempts = max_auto_fix_attempts
        self.default_routes = default_routes or self._build_default_routes()
        self._attempt_counts: Dict[str, int] = {}

    def _build_default_routes(self) -> Dict[ErrorCategory, FeedbackRoute]:
        """Build default routing table."""
        return {
            ErrorCategory.SYNTAX: FeedbackRoute(
                category=ErrorCategory.SYNTAX,
                action=FeedbackAction.AUTO_FIX,
                max_attempts=3,
            ),
            ErrorCategory.LINT: FeedbackRoute(
                category=ErrorCategory.LINT,
                action=FeedbackAction.AUTO_FIX,
                max_attempts=3,
            ),
            ErrorCategory.FORMAT: FeedbackRoute(
                category=ErrorCategory.FORMAT,
                action=FeedbackAction.AUTO_FIX,
                max_attempts=2,
            ),
            ErrorCategory.TYPE_CHECK: FeedbackRoute(
                category=ErrorCategory.TYPE_CHECK,
                action=FeedbackAction.AUTO_FIX,
                max_attempts=2,
            ),
            ErrorCategory.TEST: FeedbackRoute(
                category=ErrorCategory.TEST,
                action=FeedbackAction.RETRY,
                max_attempts=2,
            ),
            ErrorCategory.SECURITY: FeedbackRoute(
                category=ErrorCategory.SECURITY,
                action=FeedbackAction.BLOCK,
                max_attempts=1,
            ),
            ErrorCategory.LOGIC: FeedbackRoute(
                category=ErrorCategory.LOGIC,
                action=FeedbackAction.ESCALATE,
                max_attempts=1,
            ),
            ErrorCategory.OTHER: FeedbackRoute(
                category=ErrorCategory.OTHER,
                action=FeedbackAction.ESCALATE,
                max_attempts=1,
            ),
        }

    def route(self, finding: Finding) -> RoutedFeedback:
        """Route a finding to appropriate action."""
        category = classify_error(finding)
        route = self.default_routes.get(category)
        
        if not route:
            route = FeedbackRoute(
                category=category,
                action=FeedbackAction.ESCALATE,
            )
        
        # Get attempt count for this finding
        finding_key = f"{finding.gate_id}:{finding.file_path}:{finding.message[:50]}"
        attempt = self._attempt_counts.get(finding_key, 0)
        
        # Check if max attempts exceeded
        if attempt >= route.max_attempts:
            route = FeedbackRoute(
                category=category,
                action=FeedbackAction.ESCALATE,
                metadata={"reason": "max_attempts_exceeded"},
            )
        
        return RoutedFeedback(
            finding=finding,
            route=route,
            attempt=attempt,
        )

    def route_all(self, findings: List[Finding]) -> List[RoutedFeedback]:
        """Route all findings."""
        return [self.route(f) for f in findings]

    def increment_attempt(self, routed: RoutedFeedback) -> None:
        """Increment attempt count for a finding."""
        finding_key = f"{routed.finding.gate_id}:{routed.finding.file_path}:{routed.finding.message[:50]}"
        new_count = routed.attempt + 1
        self._attempt_counts[finding_key] = new_count
        routed.attempt = new_count  # Update object state

    def mark_resolved(self, routed: RoutedFeedback, resolution: str = "Fixed") -> None:
        """Mark a finding as resolved."""
        routed.resolved = True
        routed.resolution = resolution

    def get_auto_fixable(self, findings: List[Finding]) -> List[RoutedFeedback]:
        """Get findings that can be auto-fixed."""
        routed = self.route_all(findings)
        return [r for r in routed if r.route.action == FeedbackAction.AUTO_FIX]

    def get_blocking(self, findings: List[Finding]) -> List[RoutedFeedback]:
        """Get findings that block progress."""
        routed = self.route_all(findings)
        return [r for r in routed if r.route.action == FeedbackAction.BLOCK]

    def build_fix_prompt(
        self,
        routed: RoutedFeedback,
        *,
        context: Optional[str] = None,
        file_content: Optional[str] = None,
    ) -> str:
        """Build a prompt for auto-fix agent."""
        finding = routed.finding
        category = routed.route.category
        
        prompt_parts = [
            f"# Auto-Fix Request (Attempt {routed.attempt + 1})",
            "",
            f"## Error Category: {category.value}",
            "",
            f"## Error Details:",
            f"- Message: {finding.message}",
        ]
        
        if finding.file_path:
            prompt_parts.append(f"- File: {finding.file_path}")
        if finding.line_number:
            prompt_parts.append(f"- Line: {finding.line_number}")
        if finding.rule_id:
            prompt_parts.append(f"- Rule: {finding.rule_id}")
        if finding.suggestion:
            prompt_parts.append(f"- Suggestion: {finding.suggestion}")
        
        if file_content:
            prompt_parts.extend([
                "",
                "## File Content:",
                "```",
                file_content[:3000],
                "```",
            ])
        
        if context:
            prompt_parts.extend([
                "",
                "## Additional Context:",
                context,
            ])
        
        prompt_parts.extend([
            "",
            "## Instructions:",
            "Fix the error described above. Make minimal changes to resolve the issue.",
            "If the error cannot be fixed automatically, explain why.",
        ])
        
        return "\n".join(prompt_parts)

    def reset_attempts(self) -> None:
        """Reset all attempt counts."""
        self._attempt_counts.clear()
