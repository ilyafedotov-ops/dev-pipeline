from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from devgodzilla.logging import get_logger
from devgodzilla.models.domain import Clarification
from devgodzilla.services.base import ServiceContext
from devgodzilla.services.clarifier import ClarifierService
from devgodzilla.services.policy import EffectivePolicy, PolicyService

logger = get_logger(__name__)


@dataclass
class WorkflowPromptContext:
    effective_policy: EffectivePolicy
    policy_context: str
    answered_clarifications: list[Clarification]
    open_clarifications: list[Clarification]
    blocking_open_clarifications: list[Clarification]
    rendered: str


def _clarification_value_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        for key in ("text", "value", "answer", "recommended", "default", "option"):
            candidate = value.get(key)
            if isinstance(candidate, str) and candidate.strip():
                return candidate.strip()
        try:
            return json.dumps(value, sort_keys=True)
        except Exception:
            return str(value)
    if isinstance(value, list):
        parts = [_clarification_value_text(item) for item in value]
        return ", ".join(part for part in parts if part)
    return str(value)


def _matches_stage(clarification: Clarification, stage: str) -> bool:
    applies_to = (clarification.applies_to or "").strip()
    return not applies_to or applies_to == stage


def _render_answered_clarifications(items: list[Clarification]) -> str:
    if not items:
        return ""
    lines = ["## Resolved Clarifications", ""]
    for item in items:
        answer_text = _clarification_value_text(item.answer)
        if not answer_text:
            continue
        applies_to = f" [{item.applies_to}]" if item.applies_to else ""
        lines.append(f"- `{item.key}`{applies_to}: {item.question}")
        lines.append(f"  Resolution: {answer_text}")
    return "\n".join(lines).strip()


def _render_open_clarifications(items: list[Clarification], *, blocking_only: bool) -> str:
    if not items:
        return ""
    title = "## Blocking Open Clarifications" if blocking_only else "## Open Clarifications"
    lines = [title, ""]
    for item in items:
        recommended = _clarification_value_text(item.recommended)
        lines.append(f"- `{item.key}`: {item.question}")
        if recommended:
            lines.append(f"  Recommended: {recommended}")
        if item.options:
            lines.append(f"  Options: {', '.join(option for option in item.options if option)}")
    return "\n".join(lines).strip()


def build_workflow_prompt_context(
    context: ServiceContext,
    db,
    *,
    project_id: int,
    repo_root: Path,
    stage: str,
) -> WorkflowPromptContext:
    policy_service = PolicyService(context, db)
    effective = policy_service.resolve_effective_policy(
        project_id,
        repo_root=repo_root,
        include_repo_local=True,
    )
    clarifier = ClarifierService(context, db)
    clarifier.ensure_from_policy(
        project_id=project_id,
        policy=effective.policy,
        applies_to=stage,
    )

    all_answered = db.list_clarifications(project_id=project_id, status="answered", limit=500)
    all_open = db.list_clarifications(project_id=project_id, status="open", limit=500)
    stage_open = [item for item in all_open if _matches_stage(item, stage)]
    blocking_open = [item for item in stage_open if bool(item.blocking)]

    sections = []
    policy_context = policy_service.build_policy_prompt_context(effective, stage=stage)
    if policy_context:
        sections.append(policy_context)
    answered_context = _render_answered_clarifications(all_answered)
    if answered_context:
        sections.append(answered_context)
    blocking_context = _render_open_clarifications(blocking_open, blocking_only=True)
    if blocking_context:
        sections.append(blocking_context)
    advisory_context = _render_open_clarifications(
        [item for item in stage_open if not bool(item.blocking)],
        blocking_only=False,
    )
    if advisory_context:
        sections.append(advisory_context)

    return WorkflowPromptContext(
        effective_policy=effective,
        policy_context=policy_context,
        answered_clarifications=all_answered,
        open_clarifications=stage_open,
        blocking_open_clarifications=blocking_open,
        rendered="\n\n".join(section for section in sections if section).strip(),
    )
