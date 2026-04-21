"""
Built-in policy-pack catalog and project-classification mapping.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class BuiltinPolicyPackDefinition:
    key: str
    version: str
    name: str
    description: str
    project_classification: str
    status: str
    pack: Dict[str, Any]


_BUILTIN_POLICY_PACKS: tuple[BuiltinPolicyPackDefinition, ...] = (
    BuiltinPolicyPackDefinition(
        key="default",
        version="1.0",
        name="General Purpose",
        description="Balanced defaults for most projects with warnings-first policy guidance.",
        project_classification="default",
        status="active",
        pack={
            "meta": {
                "key": "default",
                "version": "1.0",
                "classification": "default",
                "label": "General Purpose",
            },
            "defaults": {
                "ci": {"required_checks": ["lint", "test"]},
                "qa": {"policy": "prompt-driven"},
            },
            "requirements": {
                "protocol_files": ["README.md"],
                "step_sections": ["Context", "Task", "Output Specification"],
                "min_steps": 2,
            },
            "clarifications": [],
            "enforcement": {"mode": "warn"},
        },
    ),
    BuiltinPolicyPackDefinition(
        key="beginner-guided",
        version="1.0",
        name="Beginner Guided",
        description="More scaffolding, stronger structure requirements, and early clarification prompts.",
        project_classification="beginner-guided",
        status="active",
        pack={
            "meta": {
                "key": "beginner-guided",
                "version": "1.0",
                "classification": "beginner-guided",
                "label": "Beginner Guided",
            },
            "defaults": {
                "ci": {"required_checks": ["lint", "test"]},
                "qa": {"policy": "prompt-driven"},
            },
            "requirements": {
                "protocol_files": ["README.md", "PLAN.md"],
                "step_sections": ["Context", "Task", "Constraints", "Output Specification"],
                "min_steps": 3,
            },
            "clarifications": [
                {
                    "key": "success_criteria",
                    "question": "What does a successful first milestone look like for this project?",
                    "blocking": True,
                }
            ],
            "enforcement": {"mode": "warn"},
        },
    ),
    BuiltinPolicyPackDefinition(
        key="startup-fast",
        version="1.0",
        name="Startup Fast",
        description="Minimal overhead for rapid iteration with lightweight governance.",
        project_classification="startup-fast",
        status="active",
        pack={
            "meta": {
                "key": "startup-fast",
                "version": "1.0",
                "classification": "startup-fast",
                "label": "Startup Fast",
            },
            "defaults": {
                "ci": {"required_checks": ["test"]},
                "qa": {"policy": "prompt-driven"},
            },
            "requirements": {
                "protocol_files": ["README.md"],
                "step_sections": ["Task", "Output Specification"],
                "min_steps": 1,
            },
            "clarifications": [],
            "enforcement": {"mode": "warn"},
        },
    ),
    BuiltinPolicyPackDefinition(
        key="team-standard",
        version="1.0",
        name="Team Standard",
        description="Shared team workflow defaults with standard CI and review expectations.",
        project_classification="team-standard",
        status="active",
        pack={
            "meta": {
                "key": "team-standard",
                "version": "1.0",
                "classification": "team-standard",
                "label": "Team Standard",
            },
            "defaults": {
                "ci": {"required_checks": ["lint", "typecheck", "test"]},
                "qa": {"policy": "prompt-driven"},
            },
            "requirements": {
                "protocol_files": ["README.md", "DESIGN.md"],
                "step_sections": ["Context", "Task", "Output Specification", "Validation"],
                "min_steps": 2,
            },
            "clarifications": [
                {
                    "key": "release_process",
                    "question": "Does this team require any release or rollout approval gates?",
                    "blocking": False,
                }
            ],
            "enforcement": {"mode": "warn"},
        },
    ),
    BuiltinPolicyPackDefinition(
        key="enterprise-compliance",
        version="1.0",
        name="Enterprise Compliance",
        description="Tighter governance for regulated or higher-assurance delivery workflows.",
        project_classification="enterprise-compliance",
        status="active",
        pack={
            "meta": {
                "key": "enterprise-compliance",
                "version": "1.0",
                "classification": "enterprise-compliance",
                "label": "Enterprise Compliance",
            },
            "defaults": {
                "ci": {"required_checks": ["lint", "typecheck", "test", "security"]},
                "qa": {"policy": "prompt-driven"},
            },
            "requirements": {
                "protocol_files": ["README.md", "DESIGN.md", "RISKS.md"],
                "step_sections": ["Context", "Task", "Constraints", "Output Specification", "Validation"],
                "min_steps": 3,
            },
            "clarifications": [
                {
                    "key": "data_classification",
                    "question": "What data classification applies to this project?",
                    "blocking": True,
                },
                {
                    "key": "approval_owner",
                    "question": "Who owns compliance sign-off for delivery approvals?",
                    "blocking": True,
                },
            ],
            "enforcement": {
                "mode": "warn",
                "block_codes": [
                    "policy.ci.required_check_missing",
                    "policy.ci.required_check_not_executable",
                    "policy.protocol.missing_file",
                    "policy.step.missing_section",
                    "policy.step.file_missing",
                ],
            },
        },
    ),
)

CLASSIFICATION_TO_PACK_KEY: dict[str, str] = {
    item.project_classification: item.key for item in _BUILTIN_POLICY_PACKS
}
PACK_KEY_TO_CLASSIFICATION: dict[str, str] = {
    item.key: item.project_classification for item in _BUILTIN_POLICY_PACKS
}
RESERVED_BUILTIN_KEYS: frozenset[str] = frozenset(PACK_KEY_TO_CLASSIFICATION)


def list_builtin_policy_packs() -> list[BuiltinPolicyPackDefinition]:
    return list(_BUILTIN_POLICY_PACKS)


def get_builtin_policy_pack(
    key: str,
    version: Optional[str] = None,
) -> Optional[BuiltinPolicyPackDefinition]:
    candidates = [item for item in _BUILTIN_POLICY_PACKS if item.key == key]
    if not candidates:
        return None
    if version is None:
        return max(candidates, key=lambda item: item.version)
    for item in candidates:
        if item.version == version:
            return item
    return None


def is_builtin_policy_pack_key(key: Optional[str]) -> bool:
    return bool(key) and key in RESERVED_BUILTIN_KEYS


def builtin_latest_version(key: str) -> Optional[str]:
    builtin = get_builtin_policy_pack(key)
    return builtin.version if builtin else None


def classification_for_pack_key(key: Optional[str]) -> Optional[str]:
    if not key:
        return None
    return PACK_KEY_TO_CLASSIFICATION.get(key)


def cloned_builtin_policy_pack_payloads() -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    for item in _BUILTIN_POLICY_PACKS:
        payloads.append(
            {
                "key": item.key,
                "version": item.version,
                "name": item.name,
                "description": item.description,
                "project_classification": item.project_classification,
                "status": item.status,
                "is_builtin": True,
                "pack": deepcopy(item.pack),
            }
        )
    return payloads


def resolve_project_policy_selection(
    *,
    project_classification: Optional[str],
    policy_pack_key: Optional[str],
    policy_pack_version: Optional[str],
) -> tuple[Optional[str], str, str]:
    normalized_classification = (project_classification or "").strip() or None
    normalized_key = (policy_pack_key or "").strip() or None
    normalized_version = (policy_pack_version or "").strip() or None

    if normalized_key:
        latest_builtin = builtin_latest_version(normalized_key)
        if latest_builtin and not normalized_version:
            normalized_version = latest_builtin
        if normalized_classification is None:
            normalized_classification = classification_for_pack_key(normalized_key)
        return normalized_classification, normalized_key, normalized_version or "1.0"

    if normalized_classification not in CLASSIFICATION_TO_PACK_KEY:
        normalized_classification = "default"

    normalized_key = CLASSIFICATION_TO_PACK_KEY[normalized_classification]
    normalized_version = normalized_version or builtin_latest_version(normalized_key) or "1.0"
    return normalized_classification, normalized_key, normalized_version
