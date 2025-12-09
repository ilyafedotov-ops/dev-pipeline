from dataclasses import dataclass, field
from typing import Dict, Optional

from tasksgodzilla.codex import enforce_token_budget, estimate_tokens
from tasksgodzilla.errors import BudgetExceededError
from tasksgodzilla.logging import get_logger
from tasksgodzilla.metrics import metrics

log = get_logger(__name__)


@dataclass
class BudgetService:
    """Service for managing token budgets and tracking usage.
    
    This service provides centralized token budget management for protocol and step
    execution. It tracks cumulative token usage, enforces budget limits, and records
    usage for observability.
    
    Responsibilities:
    - Estimate and enforce token budgets for prompts
    - Track cumulative token usage per protocol and per step
    - Support multiple budget enforcement modes (strict, warn, off)
    - Record actual token usage for metrics and observability
    
    Budget Enforcement Modes:
    - strict: Raise BudgetExceededError when budget is exceeded
    - warn: Log a warning but allow execution to continue
    - off: No budget enforcement
    
    Usage:
        budget_service = BudgetService()
        
        # Check and track estimated tokens
        estimated = budget_service.check_and_track(
            prompt_text="...",
            model="gpt-5.1-high",
            phase="exec",
            budget_mode="strict",
            max_tokens=10000
        )
        
        # Check protocol-level budget
        budget_service.check_protocol_budget(
            protocol_run_id=123,
            estimated_tokens=5000,
            max_protocol_tokens=50000,
            budget_mode="strict"
        )
        
        # Record actual usage after execution
        budget_service.record_usage(
            protocol_run_id=123,
            step_run_id=456,
            phase="exec",
            model="gpt-5.1-high",
            prompt_tokens=1000,
            completion_tokens=500
        )
    """
    
    # In-memory tracking of cumulative token usage per protocol
    _protocol_token_usage: Dict[int, int] = field(default_factory=dict)
    # In-memory tracking of cumulative token usage per step
    _step_token_usage: Dict[int, int] = field(default_factory=dict)

    def check_and_track(
        self,
        prompt_text: str,
        model: str,
        phase: str,
        budget_mode: str,
        max_tokens: Optional[int],
    ) -> int:
        """
        Enforce configured token budgets and record estimated usage for observability.
        Returns the estimated token count for the prompt.
        
        Raises:
            BudgetExceededError: If the estimated tokens exceed the max_tokens limit
                               and budget_mode is 'strict'.
        """
        enforce_token_budget(prompt_text, max_tokens, phase, mode=budget_mode)
        estimated = estimate_tokens(prompt_text)
        metrics.observe_tokens(phase, model, estimated)
        return estimated

    def check_protocol_budget(
        self,
        protocol_run_id: int,
        estimated_tokens: int,
        max_protocol_tokens: Optional[int],
        budget_mode: str = "strict",
    ) -> None:
        """
        Check if protocol has budget remaining for the estimated tokens.
        Tracks cumulative token usage per protocol and enforces budget limits.
        
        Args:
            protocol_run_id: The protocol run ID to track budget for
            estimated_tokens: Number of tokens to be consumed
            max_protocol_tokens: Maximum tokens allowed for the entire protocol (None = unlimited)
            budget_mode: Budget enforcement mode ('strict', 'warn', or 'off')
        
        Raises:
            BudgetExceededError: If cumulative tokens would exceed max_protocol_tokens
                               and budget_mode is 'strict'.
        """
        if not max_protocol_tokens or budget_mode == "off":
            # No budget limit or enforcement disabled
            return
        
        # Get current cumulative usage for this protocol
        current_usage = self._protocol_token_usage.get(protocol_run_id, 0)
        projected_usage = current_usage + estimated_tokens
        
        if projected_usage > max_protocol_tokens:
            message = (
                f"Protocol {protocol_run_id} cumulative token usage ({projected_usage}) "
                f"would exceed configured limit ({max_protocol_tokens}). "
                f"Current usage: {current_usage}, estimated additional: {estimated_tokens}. "
                "Reduce context or raise the protocol budget."
            )
            
            if budget_mode == "warn":
                log.warning(
                    "Protocol budget exceeded",
                    extra={
                        "protocol_run_id": protocol_run_id,
                        "current_usage": current_usage,
                        "estimated_tokens": estimated_tokens,
                        "projected_usage": projected_usage,
                        "max_protocol_tokens": max_protocol_tokens,
                    },
                )
                return
            
            # strict mode: raise error
            raise BudgetExceededError(
                message,
                metadata={
                    "protocol_run_id": protocol_run_id,
                    "current_usage": current_usage,
                    "estimated_tokens": estimated_tokens,
                    "projected_usage": projected_usage,
                    "max_protocol_tokens": max_protocol_tokens,
                },
            )
        
        log.debug(
            "Protocol budget ok",
            extra={
                "protocol_run_id": protocol_run_id,
                "current_usage": current_usage,
                "estimated_tokens": estimated_tokens,
                "projected_usage": projected_usage,
                "max_protocol_tokens": max_protocol_tokens,
            },
        )
        
        # Update cumulative usage
        self._protocol_token_usage[protocol_run_id] = projected_usage

    def check_step_budget(
        self,
        step_run_id: int,
        estimated_tokens: int,
        max_step_tokens: Optional[int],
        budget_mode: str = "strict",
    ) -> None:
        """
        Check if step has budget remaining for the estimated tokens.
        Tracks cumulative token usage per step and enforces budget limits.
        
        Args:
            step_run_id: The step run ID to track budget for
            estimated_tokens: Number of tokens to be consumed
            max_step_tokens: Maximum tokens allowed for the step (None = unlimited)
            budget_mode: Budget enforcement mode ('strict', 'warn', or 'off')
        
        Raises:
            BudgetExceededError: If cumulative tokens would exceed max_step_tokens
                               and budget_mode is 'strict'.
        """
        if not max_step_tokens or budget_mode == "off":
            # No budget limit or enforcement disabled
            return
        
        # Get current cumulative usage for this step
        current_usage = self._step_token_usage.get(step_run_id, 0)
        projected_usage = current_usage + estimated_tokens
        
        if projected_usage > max_step_tokens:
            message = (
                f"Step {step_run_id} cumulative token usage ({projected_usage}) "
                f"would exceed configured limit ({max_step_tokens}). "
                f"Current usage: {current_usage}, estimated additional: {estimated_tokens}. "
                "Reduce context or raise the step budget."
            )
            
            if budget_mode == "warn":
                log.warning(
                    "Step budget exceeded",
                    extra={
                        "step_run_id": step_run_id,
                        "current_usage": current_usage,
                        "estimated_tokens": estimated_tokens,
                        "projected_usage": projected_usage,
                        "max_step_tokens": max_step_tokens,
                    },
                )
                return
            
            # strict mode: raise error
            raise BudgetExceededError(
                message,
                metadata={
                    "step_run_id": step_run_id,
                    "current_usage": current_usage,
                    "estimated_tokens": estimated_tokens,
                    "projected_usage": projected_usage,
                    "max_step_tokens": max_step_tokens,
                },
            )
        
        log.debug(
            "Step budget ok",
            extra={
                "step_run_id": step_run_id,
                "current_usage": current_usage,
                "estimated_tokens": estimated_tokens,
                "projected_usage": projected_usage,
                "max_step_tokens": max_step_tokens,
            },
        )
        
        # Update cumulative usage
        self._step_token_usage[step_run_id] = projected_usage

    def record_usage(
        self,
        protocol_run_id: int,
        step_run_id: Optional[int],
        phase: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
    ) -> None:
        """
        Record actual token usage for observability and tracking.
        Updates cumulative totals and records metrics.
        
        Args:
            protocol_run_id: The protocol run ID
            step_run_id: The step run ID (None for protocol-level operations like planning)
            phase: The phase of execution (e.g., 'planning', 'exec', 'qa', 'decompose')
            model: The model used
            prompt_tokens: Number of prompt tokens consumed
            completion_tokens: Number of completion tokens generated
        """
        total_tokens = prompt_tokens + completion_tokens
        
        # Update cumulative protocol usage
        current_protocol_usage = self._protocol_token_usage.get(protocol_run_id, 0)
        self._protocol_token_usage[protocol_run_id] = current_protocol_usage + total_tokens
        
        # Update cumulative step usage if step_run_id provided
        if step_run_id is not None:
            current_step_usage = self._step_token_usage.get(step_run_id, 0)
            self._step_token_usage[step_run_id] = current_step_usage + total_tokens
        
        # Record metrics for observability
        metrics.observe_tokens(phase, model, total_tokens)
        
        log.debug(
            "Token usage recorded",
            extra={
                "protocol_run_id": protocol_run_id,
                "step_run_id": step_run_id,
                "phase": phase,
                "model": model,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
                "protocol_cumulative": self._protocol_token_usage[protocol_run_id],
                "step_cumulative": self._step_token_usage.get(step_run_id) if step_run_id else None,
            },
        )
