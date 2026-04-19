"""
DevGodzilla Clarifier Service

Manages clarification requests for ambiguous requirements.
Clarifications can block workflow execution until answered.
"""

import json
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from devgodzilla.engines.interface import EngineRequest, EngineResult, SandboxMode
from devgodzilla.engines.registry import get_registry
from devgodzilla.logging import get_logger
from devgodzilla.models.domain import Clarification
from devgodzilla.services.base import Service, ServiceContext
from devgodzilla.services.events import (
    ClarificationAnswered,
    ClarificationCreated,
    EventBus,
    get_event_bus,
)

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

    def __init__(
        self,
        context: ServiceContext,
        db,
        event_bus: Optional[EventBus] = None,
    ) -> None:
        super().__init__(context)
        self.db = db
        self._event_bus = event_bus

    @property
    def event_bus(self) -> EventBus:
        """Get the event bus (global if not provided)."""
        if self._event_bus is None:
            self._event_bus = get_event_bus()
        return self._event_bus

    def _emit_created_event(self, clarification: Clarification) -> None:
        """Emit a ClarificationCreated event."""
        try:
            event = ClarificationCreated(
                clarification_id=str(clarification.id),
                scope=clarification.scope,
                key=clarification.key,
                question=clarification.question,
                options=clarification.options,
                blocking=clarification.blocking,
                project_id=clarification.project_id,
                protocol_run_id=clarification.protocol_run_id,
                step_run_id=clarification.step_run_id,
            )
            self.event_bus.publish(event)
        except Exception as exc:
            self.logger.warning(
                "clarification_event_emit_failed",
                extra=self.log_extra(
                    clarification_id=str(clarification.id),
                    event_type="created",
                    error=str(exc),
                ),
            )

    def _emit_answered_event(
        self,
        clarification: Clarification,
        answer: Any,
        answered_by: Optional[str],
    ) -> None:
        """Emit a ClarificationAnswered event."""
        try:
            event = ClarificationAnswered(
                clarification_id=str(clarification.id),
                answer=answer,
                answered_by=answered_by,
                project_id=clarification.project_id,
                protocol_run_id=clarification.protocol_run_id,
                step_run_id=clarification.step_run_id,
            )
            self.event_bus.publish(event)
        except Exception as exc:
            self.logger.warning(
                "clarification_event_emit_failed",
                extra=self.log_extra(
                    clarification_id=str(clarification.id),
                    event_type="answered",
                    error=str(exc),
                ),
            )

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
        if isinstance(clarifications, dict):
            items = clarifications.get("items")
            questions = clarifications.get("questions")
            if isinstance(items, list):
                clarifications = items
            elif isinstance(questions, list):
                clarifications = questions
            else:
                values = list(clarifications.values())
                if values and all(isinstance(v, dict) for v in values):
                    clarifications = values
                else:
                    clarifications = None

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
                # Emit clarification.created event
                self._emit_created_event(row)
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
        clarification = self.db.answer_clarification(
            scope=scope,
            key=key,
            answer=answer,
            answered_by=answered_by,
            status="answered",
        )
        # Emit clarification.answered event
        self._emit_answered_event(clarification, answer, answered_by)
        return clarification

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

    # -----------------------------------------------------------------
    # SPEX-002: LLM-based ambiguity detection
    # -----------------------------------------------------------------

    #: Prompt template for the ambiguity detection LLM call.
    AMBIGUITY_PROMPT_TEMPLATE = """\
You are an expert software requirements analyst. Your task is to review the
following content and identify any ambiguities, vague requirements, missing
details, contradictions, or unclear specifications.

For each issue you find, produce a single JSON object with exactly these fields:
- "key": a short snake_case identifier for the issue (e.g. "missing_error_handling")
- "question": a clear question that would resolve the ambiguity
- "blocking": true if this issue could cause incorrect implementation, false otherwise

Return a JSON array of these objects. If the content is clear and has no
ambiguities, return an empty array [].

{context_section}
Content to review:
---
{content}
---

Respond ONLY with the JSON array, no other text.
"""

    def detect_ambiguities(
        self,
        content: str,
        context: str = "",
        *,
        project_id: Optional[int] = None,
        engine_id: Optional[str] = None,
        model: Optional[str] = None,
        persist: bool = True,
    ) -> List[Clarification]:
        """
        Use an LLM to detect ambiguities in the given content.

        Takes spec/plan/tasks text content, sends it to an LLM for analysis,
        and returns a list of Clarification objects representing detected
        ambiguities.

        Args:
            content: The text content to analyse for ambiguities.
            context: Optional additional context (e.g., related spec/plan).
            project_id: Optional project ID for engine resolution & persistence.
            engine_id: Optional engine ID to use (falls back to default).
            model: Optional model override.
            persist: If True, persist detected clarifications to DB.

        Returns:
            List of Clarification objects (one per detected ambiguity).
        """
        if not content or not content.strip():
            return []

        # Build the prompt
        context_section = ""
        if context and context.strip():
            context_section = f"Additional context:\n---\n{context.strip()}\n---\n"
        prompt_text = self.AMBIGUITY_PROMPT_TEMPLATE.format(
            context_section=context_section,
            content=content.strip(),
        )

        # Resolve engine
        try:
            engine, resolved_engine_id, resolved_model = self._resolve_engine(
                engine_id, model, project_id=project_id,
            )
        except Exception as exc:
            self.logger.warning(
                "ambiguity_engine_resolve_failed",
                extra=self.log_extra(
                    project_id=project_id, error=str(exc),
                ),
            )
            return []

        # Build request
        request = EngineRequest(
            project_id=project_id or 0,
            protocol_run_id=0,
            step_run_id=0,
            model=resolved_model,
            prompt_text=prompt_text,
            prompt_files=[],
            working_dir=".",
            sandbox=SandboxMode.READ_ONLY,
            extra={"job_id": "ambiguity_detection", "engine_id": resolved_engine_id},
        )

        # Call the LLM
        try:
            result: EngineResult = engine.qa(request)
        except Exception as exc:
            self.logger.warning(
                "ambiguity_llm_call_failed",
                extra=self.log_extra(
                    project_id=project_id, error=str(exc),
                ),
            )
            return []

        if not result.success:
            self.logger.warning(
                "ambiguity_llm_unsuccessful",
                extra=self.log_extra(
                    project_id=project_id,
                    error=result.error or "unknown",
                ),
            )
            return []

        # Parse the response
        items = self._parse_ambiguity_response(result.stdout)
        if not items:
            return []

        # Optionally persist
        clarifications: List[Clarification] = []
        if persist and self.db and project_id:
            clarifications = self._persist_ambiguity_items(
                items, project_id=project_id, applies_to="tasks",
            )
        else:
            # Return transient Clarification-like objects (no DB id)
            clarifications = self._make_transient_clarifications(
                items, project_id=project_id,
            )

        self.logger.info(
            "ambiguity_detection_complete",
            extra=self.log_extra(
                project_id=project_id,
                detected_count=len(items),
                persisted_count=len(clarifications),
            ),
        )
        return clarifications

    # -- Private helpers for detect_ambiguities --

    def _resolve_engine(
        self,
        engine_id: Optional[str],
        model: Optional[str],
        *,
        project_id: Optional[int] = None,
    ):
        """Resolve an engine and model from the registry."""
        registry = get_registry()
        if not registry.list_ids():
            try:
                from devgodzilla.engines.bootstrap import bootstrap_default_engines
                bootstrap_default_engines(replace=False)
            except Exception:
                pass

        resolved_engine_id = engine_id.strip() if engine_id and engine_id.strip() else None
        if not resolved_engine_id:
            # Try default
            try:
                resolved_engine_id = registry.default_id
            except Exception:
                ids = registry.list_ids()
                resolved_engine_id = ids[0] if ids else None
        if not resolved_engine_id:
            raise RuntimeError("No engine available for ambiguity detection")

        from devgodzilla.engines import EngineNotFoundError
        try:
            engine = registry.get(resolved_engine_id)
        except EngineNotFoundError as exc:
            raise RuntimeError(
                f"Engine not registered: {resolved_engine_id}"
            ) from exc

        resolved_model = model.strip() if isinstance(model, str) and model.strip() else None
        if not resolved_model:
            resolved_model = engine.metadata.default_model
        return engine, resolved_engine_id, resolved_model

    def _parse_ambiguity_response(self, raw: str) -> List[Dict[str, Any]]:
        """Parse the LLM response into a list of ambiguity dicts."""
        if not raw or not raw.strip():
            return []

        # Try to extract JSON from the response (handle markdown fences)
        text = raw.strip()
        # Remove markdown code fences if present
        fence_match = re.search(r"```(?:json)?\s*\n?(.*?)```", text, re.DOTALL)
        if fence_match:
            text = fence_match.group(1).strip()

        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            # Try to find a JSON array in the text
            bracket_match = re.search(r"\[.*\]", text, re.DOTALL)
            if bracket_match:
                try:
                    parsed = json.loads(bracket_match.group(0))
                except json.JSONDecodeError:
                    return []
            else:
                return []

        if not isinstance(parsed, list):
            return []

        items: List[Dict[str, Any]] = []
        for entry in parsed:
            if not isinstance(entry, dict):
                continue
            key = entry.get("key", "")
            question = entry.get("question", "")
            if not isinstance(key, str) or not key.strip():
                continue
            if not isinstance(question, str) or not question.strip():
                continue
            items.append({
                "key": key.strip(),
                "question": question.strip(),
                "blocking": bool(entry.get("blocking", False)),
            })
        return items

    def _persist_ambiguity_items(
        self,
        items: List[Dict[str, Any]],
        *,
        project_id: int,
        applies_to: str = "tasks",
    ) -> List[Clarification]:
        """Persist detected ambiguity items as Clarification rows."""
        scope = _scope_key(project_id=project_id)
        out: List[Clarification] = []
        for item in items:
            try:
                row = self.db.upsert_clarification(
                    scope=scope,
                    project_id=project_id,
                    key=f"ambiguity_{item['key']}",
                    question=item["question"],
                    blocking=item.get("blocking", False),
                    applies_to=applies_to,
                )
                out.append(row)
                self._emit_created_event(row)
            except Exception as exc:
                self.logger.warning(
                    "ambiguity_clarification_persist_failed",
                    extra=self.log_extra(
                        project_id=project_id,
                        key=item.get("key"),
                        error=str(exc),
                    ),
                )
        return out

    @staticmethod
    def _make_transient_clarifications(
        items: List[Dict[str, Any]],
        *,
        project_id: Optional[int] = None,
    ) -> List[Clarification]:
        """Create transient Clarification objects without DB persistence."""
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()
        return [
            Clarification(
                id=0,
                scope="transient",
                project_id=project_id or 0,
                key=f"ambiguity_{item['key']}",
                question=item["question"],
                status="open",
                created_at=now,
                updated_at=now,
                blocking=item.get("blocking", False),
                applies_to="tasks",
            )
            for item in items
        ]

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
