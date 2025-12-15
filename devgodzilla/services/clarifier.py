"""
DevGodzilla Clarifier Service

Manages clarification requests for ambiguous requirements.
Clarifications can block workflow execution until answered.
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from devgodzilla.logging import get_logger
from devgodzilla.models.domain import Clarification
from devgodzilla.services.base import Service, ServiceContext

logger = get_logger(__name__)


def _scope_key(
    *,
    project_id: int,
    protocol_run_id: Optional[int] = None,
    step_run_id: Optional[int] = None,
) -> str:
    """Build a scope key for clarification uniqueness."""
    if step_run_id is not None:
        return f"step:{step_run_id}"
    if protocol_run_id is not None:
        return f"protocol:{protocol_run_id}"
    return f"project:{project_id}"


class ClarifierService(Service):
    """
    Service for managing clarification requests.
    
    Clarifications are questions that must be answered before workflow
    can proceed. They can be marked as blocking (must be answered) or
    non-blocking (informational).
    
    Common use cases:
    - Policy-defined questions (e.g., "What data classification applies?")
    - Ambiguous specification resolution
    - User preference collection during onboarding
    
    Example:
        clarifier = ClarifierService(context, db)
        
        # Create clarifications from policy
        clarifier.ensure_from_policy(
            project_id=1,
            policy=policy_pack,
            applies_to="onboarding"
        )
        
        # Check for blocking clarifications
        if clarifier.has_blocking_open(project_id=1):
            return "Blocked on clarifications"
    """

    def __init__(self, context: ServiceContext, db) -> None:
        super().__init__(context)
        self.db = db

    def ensure_from_policy(
        self,
        *,
        project_id: int,
        policy: Dict[str, Any],
        applies_to: str,
        protocol_run_id: Optional[int] = None,
        step_run_id: Optional[int] = None,
        answered_by: Optional[str] = None,
    ) -> List[Clarification]:
        """
        Materialize clarification questions from a policy into the DB.
        
        Filters by applies_to and de-dupes by (scope, key).
        
        Args:
            project_id: Project ID
            policy: Policy dict containing 'clarifications' list
            applies_to: Filter clarifications by this phase (e.g., 'onboarding', 'execution')
            protocol_run_id: Optional protocol run ID for scoping
            step_run_id: Optional step run ID for scoping
            answered_by: Optional user/system that answered
            
        Returns:
            List of created/updated Clarification objects
        """
        clarifications = policy.get("clarifications") if isinstance(policy, dict) else None
        if not isinstance(clarifications, list) or not clarifications:
            return []

        scope = _scope_key(
            project_id=project_id,
            protocol_run_id=protocol_run_id,
            step_run_id=step_run_id,
        )
        out: List[Clarification] = []
        
        for item in clarifications:
            if not isinstance(item, dict):
                continue
                
            key = item.get("key")
            question = item.get("question")
            item_applies = item.get("applies_to") or item.get("appliesTo")
            
            if not isinstance(key, str) or not key.strip():
                continue
            if not isinstance(question, str) or not question.strip():
                continue
            if item_applies and str(item_applies) != applies_to:
                continue
                
            blocking = bool(item.get("blocking")) if "blocking" in item else False
            recommended = item.get("recommended")
            if recommended is not None and not isinstance(recommended, dict):
                recommended = {"value": recommended}
            options = item.get("options")
            if options is not None and not isinstance(options, list):
                options = None
                
            try:
                row = self.db.upsert_clarification(
                    scope=scope,
                    project_id=project_id,
                    protocol_run_id=protocol_run_id,
                    step_run_id=step_run_id,
                    key=key.strip(),
                    question=question.strip(),
                    recommended=recommended,
                    options=options,
                    applies_to=applies_to,
                    blocking=blocking,
                )
                out.append(row)
            except Exception as exc:
                self.logger.warning(
                    "clarification_upsert_failed",
                    extra=self.log_extra(
                        project_id=project_id,
                        scope=scope,
                        key=key,
                        error=str(exc),
                    ),
                )
        return out

    def list_open(
        self,
        *,
        project_id: Optional[int] = None,
        protocol_run_id: Optional[int] = None,
        step_run_id: Optional[int] = None,
        applies_to: Optional[str] = None,
        limit: int = 200,
    ) -> List[Clarification]:
        """
        List open (unanswered) clarifications.
        
        Args:
            project_id: Filter by project ID
            protocol_run_id: Filter by protocol run ID
            step_run_id: Filter by step run ID
            applies_to: Filter by applies_to phase
            limit: Maximum number of results
            
        Returns:
            List of open Clarification objects
        """
        return self.db.list_clarifications(
            project_id=project_id,
            protocol_run_id=protocol_run_id,
            step_run_id=step_run_id,
            status="open",
            applies_to=applies_to,
            limit=limit,
        )

    def answer(
        self,
        *,
        project_id: int,
        key: str,
        answer: Optional[Dict[str, Any]],
        protocol_run_id: Optional[int] = None,
        step_run_id: Optional[int] = None,
        answered_by: Optional[str] = None,
    ) -> Clarification:
        """
        Set the answer for a clarification.
        
        Args:
            project_id: Project ID
            key: Clarification key
            answer: Answer dict (or None to dismiss)
            protocol_run_id: Optional protocol run ID for scoping
            step_run_id: Optional step run ID for scoping
            answered_by: Optional user/system that answered
            
        Returns:
            Updated Clarification object
        """
        scope = _scope_key(
            project_id=project_id,
            protocol_run_id=protocol_run_id,
            step_run_id=step_run_id,
        )
        return self.db.answer_clarification(
            scope=scope,
            key=key,
            answer=answer,
            answered_by=answered_by,
            status="answered",
        )

    def has_blocking_open(
        self,
        *,
        project_id: Optional[int] = None,
        protocol_run_id: Optional[int] = None,
        step_run_id: Optional[int] = None,
        applies_to: Optional[str] = None,
    ) -> bool:
        """Check if there are any blocking open clarifications."""
        open_items = self.list_open(
            project_id=project_id,
            protocol_run_id=protocol_run_id,
            step_run_id=step_run_id,
            applies_to=applies_to,
        )
        return any(c.blocking for c in open_items)

    def list_blocking_open(
        self,
        *,
        project_id: Optional[int] = None,
        protocol_run_id: Optional[int] = None,
        step_run_id: Optional[int] = None,
        applies_to: Optional[str] = None,
        limit: int = 200,
    ) -> List[Clarification]:
        """List only blocking open clarifications."""
        items = self.list_open(
            project_id=project_id,
            protocol_run_id=protocol_run_id,
            step_run_id=step_run_id,
            applies_to=applies_to,
            limit=limit,
        )
        return [c for c in items if c.blocking]

    def get_answer(
        self,
        *,
        project_id: int,
        key: str,
        protocol_run_id: Optional[int] = None,
        step_run_id: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Get the answer for a clarification by key.
        
        Returns None if clarification doesn't exist or is unanswered.
        """
        # List all clarifications and find the matching one
        clarifications = self.db.list_clarifications(
            project_id=project_id,
            protocol_run_id=protocol_run_id,
            step_run_id=step_run_id,
            limit=500,
        )
        scope = _scope_key(
            project_id=project_id,
            protocol_run_id=protocol_run_id,
            step_run_id=step_run_id,
        )
        for c in clarifications:
            if c.scope == scope and c.key == key and c.status == "answered":
                return c.answer
        return None
