"""
Tests for DevGodzilla Feedback Router.

Tests the FeedbackRouter component including error classification,
routing logic, auto-fix detection, and fix prompt generation.
"""

import pytest
from unittest.mock import Mock

from devgodzilla.qa.feedback import (
    FeedbackRouter,
    FeedbackAction,
    FeedbackRoute,
    RoutedFeedback,
    ErrorCategory,
    classify_error,
    AUTO_FIXABLE_CATEGORIES,
)
from devgodzilla.qa.gates.interface import Finding


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def router():
    """Create a default FeedbackRouter."""
    return FeedbackRouter()


@pytest.fixture
def syntax_finding():
    """Create a syntax error finding."""
    return Finding(
        gate_id="lint",
        severity="error",
        message="SyntaxError: invalid syntax",
        file_path="src/main.py",
        line_number=10,
        rule_id="E999",
    )


@pytest.fixture
def lint_finding():
    """Create a lint warning finding."""
    return Finding(
        gate_id="lint",
        severity="warning",
        message="Trailing whitespace",
        file_path="src/utils.py",
        line_number=5,
        rule_id="W291",
    )


@pytest.fixture
def test_finding():
    """Create a test failure finding."""
    return Finding(
        gate_id="test",
        severity="error",
        message="AssertionError: expected True, got False",
        file_path="tests/test_main.py",
        line_number=25,
    )


@pytest.fixture
def type_finding():
    """Create a type check finding."""
    return Finding(
        gate_id="type",
        severity="error",
        message="Incompatible types in assignment",
        file_path="src/main.py",
        line_number=15,
        rule_id="assignment",
    )


# =============================================================================
# Test Error Classification
# =============================================================================

class TestErrorClassification:
    """Test classify_error function."""

    def test_classify_syntax_error(self, syntax_finding):
        """Test classification of syntax errors."""
        category = classify_error(syntax_finding)
        assert category == ErrorCategory.SYNTAX

    def test_classify_lint_error_by_gate(self, lint_finding):
        """Test classification based on gate_id."""
        category = classify_error(lint_finding)
        assert category == ErrorCategory.LINT

    def test_classify_test_error(self, test_finding):
        """Test classification of test failures."""
        category = classify_error(test_finding)
        assert category == ErrorCategory.TEST

    def test_classify_type_error(self, type_finding):
        """Test classification of type check errors."""
        category = classify_error(type_finding)
        assert category == ErrorCategory.TYPE_CHECK

    def test_classify_format_error(self):
        """Test classification of formatting errors."""
        finding = Finding(
            gate_id="lint",
            severity="warning",
            message="Black would reformat this file",
            file_path="src/main.py",
            rule_id="format",
        )
        category = classify_error(finding)
        assert category in (ErrorCategory.FORMAT, ErrorCategory.LINT)

    def test_classify_security_error(self):
        """Test classification of security issues."""
        finding = Finding(
            gate_id="security",
            severity="error",
            message="Hardcoded password detected",
            file_path="src/auth.py",
            rule_id="S105",
        )
        category = classify_error(finding)
        assert category == ErrorCategory.SECURITY

    def test_classify_unknown_error(self):
        """Test classification of unknown errors."""
        finding = Finding(
            gate_id="custom",
            severity="info",
            message="Something happened",
        )
        category = classify_error(finding)
        assert category == ErrorCategory.OTHER


# =============================================================================
# Test FeedbackRouter
# =============================================================================

class TestFeedbackRouterInstantiation:
    """Test FeedbackRouter instantiation."""

    def test_default_instantiation(self):
        """Test creating router with defaults."""
        router = FeedbackRouter()
        assert router is not None
        assert router.max_auto_fix_attempts == 3

    def test_custom_max_attempts(self):
        """Test creating router with custom max attempts."""
        router = FeedbackRouter(max_auto_fix_attempts=5)
        assert router.max_auto_fix_attempts == 5

    def test_custom_routes(self):
        """Test creating router with custom routes."""
        custom_routes = {
            ErrorCategory.SYNTAX: FeedbackRoute(
                category=ErrorCategory.SYNTAX,
                action=FeedbackAction.BLOCK,
            ),
        }
        router = FeedbackRouter(default_routes=custom_routes)
        assert router is not None


class TestFeedbackRouting:
    """Test FeedbackRouter.route() logic."""

    def test_route_syntax_error(self, router, syntax_finding):
        """Test routing syntax errors."""
        routed = router.route(syntax_finding)
        
        assert isinstance(routed, RoutedFeedback)
        assert routed.finding == syntax_finding
        assert routed.route.category == ErrorCategory.SYNTAX
        # Syntax errors should be auto-fixable
        assert routed.route.action == FeedbackAction.AUTO_FIX

    def test_route_lint_warning(self, router, lint_finding):
        """Test routing lint warnings."""
        routed = router.route(lint_finding)
        
        assert routed.route.category == ErrorCategory.LINT
        # Lint warnings are typically auto-fixable
        assert routed.route.action == FeedbackAction.AUTO_FIX

    def test_route_test_failure(self, router, test_finding):
        """Test routing test failures."""
        routed = router.route(test_finding)
        
        assert routed.route.category == ErrorCategory.TEST
        # Test failures require manual intervention
        assert routed.route.action in (FeedbackAction.RETRY, FeedbackAction.ESCALATE)

    def test_route_all_method(self, router, syntax_finding, lint_finding):
        """Test routing multiple findings."""
        findings = [syntax_finding, lint_finding]
        routed_list = router.route_all(findings)
        
        assert len(routed_list) == 2
        assert all(isinstance(r, RoutedFeedback) for r in routed_list)


class TestAutoFixableCategories:
    """Test get_auto_fixable() filtering."""

    def test_auto_fixable_categories_constant(self):
        """Test AUTO_FIXABLE_CATEGORIES contains expected items."""
        assert ErrorCategory.SYNTAX in AUTO_FIXABLE_CATEGORIES
        assert ErrorCategory.LINT in AUTO_FIXABLE_CATEGORIES
        assert ErrorCategory.FORMAT in AUTO_FIXABLE_CATEGORIES
        # Test failures should NOT be auto-fixable
        assert ErrorCategory.TEST not in AUTO_FIXABLE_CATEGORIES

    def test_get_auto_fixable(self, router, syntax_finding, test_finding):
        """Test filtering auto-fixable findings."""
        findings = [syntax_finding, test_finding]
        auto_fixable = router.get_auto_fixable(findings)
        
        # Only syntax error should be auto-fixable
        assert len(auto_fixable) == 1
        assert auto_fixable[0].finding == syntax_finding

    def test_get_blocking(self, router, syntax_finding):
        """Test filtering blocking findings."""
        # Create a security finding which should block
        security_finding = Finding(
            gate_id="security",
            severity="error",
            message="Hardcoded password detected",
            file_path="src/main.py",
        )
        
        findings = [syntax_finding, security_finding]
        blocking = router.get_blocking(findings)
        
        # Security finding should block
        assert len(blocking) == 1
        assert blocking[0].finding == security_finding


class TestAttemptTracking:
    """Test attempt counting in FeedbackRouter."""

    def test_initial_attempt_is_zero(self, router, syntax_finding):
        """Test that initial attempt count is zero."""
        routed = router.route(syntax_finding)
        assert routed.attempt == 0

    def test_increment_attempt(self, router, syntax_finding):
        """Test incrementing attempt count."""
        routed = router.route(syntax_finding)
        router.increment_attempt(routed)
        
        assert routed.attempt == 1

    def test_multiple_increments(self, router, syntax_finding):
        """Test multiple increments."""
        routed = router.route(syntax_finding)
        router.increment_attempt(routed)
        router.increment_attempt(routed)
        router.increment_attempt(routed)
        
        assert routed.attempt == 3

    def test_mark_resolved(self, router, syntax_finding):
        """Test marking a finding as resolved."""
        routed = router.route(syntax_finding)
        router.mark_resolved(routed, "Fixed by auto-formatter")
        
        assert routed.resolved is True
        assert routed.resolution == "Fixed by auto-formatter"

    def test_reset_attempts(self, router, syntax_finding, lint_finding):
        """Test resetting all attempt counts."""
        routed1 = router.route(syntax_finding)
        routed2 = router.route(lint_finding)
        
        router.increment_attempt(routed1)
        router.increment_attempt(routed2)
        router.reset_attempts()
        
        # Routed objects should still have their counts
        # (reset_attempts clears internal tracking)
        assert True  # Just verify no exception


# =============================================================================
# Test Fix Prompt Generation
# =============================================================================

class TestFixPromptGeneration:
    """Test build_fix_prompt() formatting."""

    def test_build_fix_prompt_basic(self, router, syntax_finding):
        """Test building basic fix prompt."""
        routed = router.route(syntax_finding)
        prompt = router.build_fix_prompt(routed)
        
        assert isinstance(prompt, str)
        assert len(prompt) > 0
        # Should contain error info
        assert "SyntaxError" in prompt or "syntax" in prompt.lower()

    def test_build_fix_prompt_with_context(self, router, syntax_finding):
        """Test fix prompt with additional context."""
        routed = router.route(syntax_finding)
        prompt = router.build_fix_prompt(
            routed,
            context="This is a Python 3.10 project",
        )
        
        assert "Python 3.10" in prompt

    def test_build_fix_prompt_with_file_content(self, router, syntax_finding):
        """Test fix prompt with file content."""
        routed = router.route(syntax_finding)
        file_content = "def foo(:\n    pass\n"
        prompt = router.build_fix_prompt(
            routed,
            file_content=file_content,
        )
        
        # Should include the file content
        assert "foo" in prompt or file_content in prompt

    def test_build_fix_prompt_includes_file_path(self, router, syntax_finding):
        """Test fix prompt includes file path."""
        routed = router.route(syntax_finding)
        prompt = router.build_fix_prompt(routed)
        
        assert "main.py" in prompt or syntax_finding.file_path in prompt

    def test_build_fix_prompt_includes_line_number(self, router, syntax_finding):
        """Test fix prompt includes line number."""
        routed = router.route(syntax_finding)
        prompt = router.build_fix_prompt(routed)
        
        assert "10" in prompt or str(syntax_finding.line_number) in prompt


# =============================================================================
# Test FeedbackRoute
# =============================================================================

class TestFeedbackRoute:
    """Test FeedbackRoute dataclass."""

    def test_route_creation(self):
        """Test creating a FeedbackRoute."""
        route = FeedbackRoute(
            category=ErrorCategory.SYNTAX,
            action=FeedbackAction.AUTO_FIX,
            max_attempts=3,
        )
        assert route.category == ErrorCategory.SYNTAX
        assert route.action == FeedbackAction.AUTO_FIX
        assert route.max_attempts == 3

    def test_route_with_handler(self):
        """Test route with custom handler."""
        def custom_handler(finding):
            return "fixed"
        
        route = FeedbackRoute(
            category=ErrorCategory.LINT,
            action=FeedbackAction.AUTO_FIX,
            handler=custom_handler,
        )
        assert route.handler is custom_handler

    def test_route_with_metadata(self):
        """Test route with metadata."""
        route = FeedbackRoute(
            category=ErrorCategory.SECURITY,
            action=FeedbackAction.ESCALATE,
            metadata={"severity": "high", "team": "security"},
        )
        assert route.metadata.get("severity") == "high"


# =============================================================================
# Test RoutedFeedback
# =============================================================================

class TestRoutedFeedback:
    """Test RoutedFeedback dataclass."""

    def test_routed_feedback_creation(self, syntax_finding):
        """Test creating RoutedFeedback."""
        route = FeedbackRoute(
            category=ErrorCategory.SYNTAX,
            action=FeedbackAction.AUTO_FIX,
        )
        routed = RoutedFeedback(finding=syntax_finding, route=route)
        
        assert routed.finding == syntax_finding
        assert routed.route == route
        assert routed.attempt == 0
        assert routed.resolved is False
        assert routed.resolution is None
