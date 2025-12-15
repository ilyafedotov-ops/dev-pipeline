"""
DevGodzilla Policy Service

Manages policy packs, policy resolution, and policy evaluation.
Policies define governance rules for projects, protocols, and steps.
"""

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from devgodzilla.logging import get_logger
from devgodzilla.services.base import Service, ServiceContext

logger = get_logger(__name__)

# Default policy codes that can block execution
_DEFAULT_BLOCK_CODES = {
    "policy.ci.required_check_missing",
    "policy.ci.required_check_not_executable",
    "policy.protocol.missing_file",
    "policy.step.missing_section",
    "policy.step.file_missing",
}


@dataclass
class EffectivePolicy:
    """Result of policy resolution with merged sources."""
    policy: Dict[str, Any]
    effective_hash: str
    pack_key: str
    pack_version: str
    sources: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Finding:
    """A policy evaluation finding (violation or warning)."""
    code: str
    severity: str  # 'error', 'warning', 'info'
    message: str
    scope: str  # 'project', 'protocol', 'step'
    suggested_fix: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    def asdict(self) -> Dict[str, Any]:
        """Convert to dict for serialization."""
        return {
            "code": self.code,
            "severity": self.severity,
            "message": self.message,
            "scope": self.scope,
            "suggested_fix": self.suggested_fix,
            "metadata": self.metadata,
        }


def _sanitize_policy_override(override: Dict[str, Any]) -> Dict[str, Any]:
    """
    Allow only a conservative subset of keys from overrides.
    
    Prevents unexpected keys from influencing execution behavior.
    """
    allowed_keys = {"defaults", "requirements", "clarifications", "enforcement"}
    return {k: v for k, v in override.items() if k in allowed_keys}


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """
    Deep-merge override into base (dicts merge recursively, other values replace).
    
    Returns a new dict.
    """
    result = dict(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _stable_hash(payload: Dict[str, Any]) -> str:
    """Generate a stable hash for a policy payload."""
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:16]


def _load_repo_local_policy(repo_root: Path) -> Optional[Dict[str, Any]]:
    """
    Best-effort loader for repo-local override policy.
    
    Supports JSON always; YAML only if PyYAML is available.
    Looks for: .devgodzilla/policy.json, .devgodzilla/policy.yaml
    """
    policy_dir = repo_root / ".devgodzilla"
    
    # Try JSON first
    json_path = policy_dir / "policy.json"
    if json_path.exists():
        try:
            return json.loads(json_path.read_text())
        except Exception:
            pass
    
    # Try YAML if available
    yaml_path = policy_dir / "policy.yaml"
    if yaml_path.exists():
        try:
            import yaml
            return yaml.safe_load(yaml_path.read_text())
        except ImportError:
            pass
        except Exception:
            pass
    
    return None


def _policy_required_checks(policy: Dict[str, Any]) -> List[str]:
    """Extract required CI checks from policy."""
    # Check defaults.ci.required_checks
    defaults = policy.get("defaults", {})
    ci_config = defaults.get("ci", {})
    if isinstance(ci_config.get("required_checks"), list):
        return ci_config["required_checks"]
    
    # Check requirements.required_checks (forward compat)
    requirements = policy.get("requirements", {})
    if isinstance(requirements.get("required_checks"), list):
        return requirements["required_checks"]
    
    return []


def _policy_block_codes(policy: Dict[str, Any]) -> set:
    """Determine which finding codes become blocking when enforcement_mode=block."""
    enforcement = policy.get("enforcement", {})
    block_codes = enforcement.get("block_codes")
    if isinstance(block_codes, list):
        return set(block_codes)
    return _DEFAULT_BLOCK_CODES


class PolicyService(Service):
    """
    Service for policy management and evaluation.
    
    Handles:
    - Policy pack resolution (base + project overrides + repo-local)
    - Policy evaluation (project, protocol, step level)
    - Enforcement mode application (warn vs block)
    - Finding generation and blocking check
    
    Example:
        policy_service = PolicyService(context, db)
        
        # Resolve effective policy for a project
        effective = policy_service.resolve_effective_policy(
            project_id=1,
            repo_root=Path("/path/to/repo")
        )
        
        # Evaluate protocol compliance
        findings = policy_service.evaluate_protocol(protocol_run_id=1)
        
        # Check for blocking findings
        if PolicyService.has_blocking_findings(findings):
            return "Blocked by policy"
    """

    def __init__(self, context: ServiceContext, db) -> None:
        super().__init__(context)
        self.db = db

    def resolve_effective_policy(
        self,
        project_id: int,
        *,
        repo_root: Optional[Path] = None,
        include_repo_local: bool = True,
    ) -> EffectivePolicy:
        """
        Resolve the effective policy for a project.
        
        Merges:
        1. Base policy pack (from project.policy_pack_key)
        2. Project-level overrides (from project.policy_overrides)
        3. Repo-local overrides (from .devgodzilla/policy.json) if enabled
        
        Args:
            project_id: Project ID
            repo_root: Optional repo root for loading repo-local policy
            include_repo_local: Whether to include repo-local overrides
            
        Returns:
            EffectivePolicy with merged policy and sources
        """
        project = self.db.get_project(project_id)
        
        # Load base policy pack
        pack_key = project.policy_pack_key or "default"
        pack_version = project.policy_pack_version or "1.0"
        
        try:
            pack = self.db.get_policy_pack(key=pack_key, version=pack_version)
            base_policy = pack.pack
        except KeyError:
            # Fallback to empty policy
            base_policy = {}
        
        sources = {"pack": {"key": pack_key, "version": pack_version}}
        merged = dict(base_policy)
        
        # Apply project overrides
        if project.policy_overrides:
            sanitized = _sanitize_policy_override(project.policy_overrides)
            merged = _deep_merge(merged, sanitized)
            sources["project_overrides"] = True
        
        # Apply repo-local overrides
        if include_repo_local and project.policy_repo_local_enabled and repo_root:
            repo_local = _load_repo_local_policy(repo_root)
            if repo_local:
                sanitized = _sanitize_policy_override(repo_local)
                merged = _deep_merge(merged, sanitized)
                sources["repo_local"] = True
        
        effective_hash = _stable_hash(merged)
        
        return EffectivePolicy(
            policy=merged,
            effective_hash=effective_hash,
            pack_key=pack_key,
            pack_version=pack_version,
            sources=sources,
        )

    def evaluate_project(self, project_id: int) -> List[Finding]:
        """
        Evaluate project-level policy compliance.
        
        Checks:
        - Required configuration is present
        - Policy pack is valid
        """
        findings: List[Finding] = []
        
        try:
            project = self.db.get_project(project_id)
        except KeyError:
            findings.append(Finding(
                code="policy.project.not_found",
                severity="error",
                message=f"Project {project_id} not found",
                scope="project",
            ))
            return findings
        
        # Check required fields
        if not project.git_url:
            findings.append(Finding(
                code="policy.project.missing_git_url",
                severity="error",
                message="Project is missing git_url",
                scope="project",
            ))
        
        if not project.base_branch:
            findings.append(Finding(
                code="policy.project.missing_base_branch",
                severity="error",
                message="Project is missing base_branch",
                scope="project",
            ))
        
        return findings

    def evaluate_protocol(
        self,
        protocol_run_id: int,
        *,
        repo_root: Optional[Path] = None,
    ) -> List[Finding]:
        """
        Evaluate protocol-level policy compliance.
        
        Checks:
        - Required protocol files exist
        - Protocol structure matches policy
        """
        findings: List[Finding] = []
        
        try:
            run = self.db.get_protocol_run(protocol_run_id)
        except KeyError:
            findings.append(Finding(
                code="policy.protocol.not_found",
                severity="error",
                message=f"ProtocolRun {protocol_run_id} not found",
                scope="protocol",
            ))
            return findings
        
        # Resolve effective policy
        effective = self.resolve_effective_policy(
            run.project_id,
            repo_root=repo_root,
        )
        policy = effective.policy
        
        # Check required protocol files
        requirements = policy.get("requirements", {})
        required_files = requirements.get("protocol_files", [])
        
        if run.protocol_root and required_files:
            protocol_path = Path(run.protocol_root)
            for file_name in required_files:
                if not (protocol_path / file_name).exists():
                    findings.append(Finding(
                        code="policy.protocol.missing_file",
                        severity="warning",
                        message=f"Required protocol file missing: {file_name}",
                        scope="protocol",
                        suggested_fix=f"Create {file_name} in protocol directory",
                        metadata={"file": file_name},
                    ))
        
        return findings

    def evaluate_step(
        self,
        step_run_id: int,
        *,
        repo_root: Optional[Path] = None,
    ) -> List[Finding]:
        """
        Evaluate step-level policy compliance.
        
        Checks:
        - Required step sections are present
        - CI checks are executable
        """
        findings: List[Finding] = []
        
        try:
            step = self.db.get_step_run(step_run_id)
            run = self.db.get_protocol_run(step.protocol_run_id)
        except KeyError:
            findings.append(Finding(
                code="policy.step.not_found",
                severity="error",
                message=f"StepRun {step_run_id} not found",
                scope="step",
            ))
            return findings
        
        # Resolve effective policy
        effective = self.resolve_effective_policy(
            run.project_id,
            repo_root=repo_root,
        )
        policy = effective.policy
        
        # Check required step sections
        requirements = policy.get("requirements", {})
        required_sections = requirements.get("step_sections", [])
        
        # Would check step markdown for required sections here
        # For now, return empty (implementation depends on step file format)
        
        return findings

    def build_policy_guidelines(self, effective: EffectivePolicy) -> str:
        """
        Build a policy guidelines string for inclusion in prompts.
        
        Summarizes key policy requirements for the AI agent.
        """
        policy = effective.policy
        lines = ["## Policy Guidelines", ""]
        
        # Extract requirements
        requirements = policy.get("requirements", {})
        
        # Required step sections
        step_sections = requirements.get("step_sections", [])
        if step_sections:
            lines.append("### Required Step Sections")
            for section in step_sections:
                lines.append(f"- {section}")
            lines.append("")
        
        # Required protocol files
        protocol_files = requirements.get("protocol_files", [])
        if protocol_files:
            lines.append("### Required Protocol Files")
            for file in protocol_files:
                lines.append(f"- {file}")
            lines.append("")
        
        # CI configuration
        defaults = policy.get("defaults", {})
        ci_config = defaults.get("ci", {})
        required_checks = ci_config.get("required_checks", [])
        if required_checks:
            lines.append("### Required CI Checks")
            for check in required_checks:
                lines.append(f"- {check}")
            lines.append("")
        
        # QA policy
        qa_config = defaults.get("qa", {})
        qa_policy = qa_config.get("policy", "full")
        lines.append(f"### QA Policy: {qa_policy}")
        lines.append("")
        
        return "\n".join(lines)

    @staticmethod
    def apply_enforcement_mode(
        findings: List[Finding],
        enforcement_mode: str,
        *,
        policy: Optional[Dict[str, Any]] = None,
    ) -> List[Finding]:
        """
        Translate finding severities based on project enforcement mode.
        
        In 'block' mode, certain warnings become errors.
        In 'warn' mode, errors may be downgraded to warnings.
        """
        if enforcement_mode == "warn":
            return findings
        
        if enforcement_mode != "block":
            return findings
        
        block_codes = _policy_block_codes(policy or {})
        updated = []
        
        for finding in findings:
            if finding.code in block_codes and finding.severity == "warning":
                updated.append(Finding(
                    code=finding.code,
                    severity="error",
                    message=finding.message,
                    scope=finding.scope,
                    suggested_fix=finding.suggested_fix,
                    metadata=finding.metadata,
                ))
            else:
                updated.append(finding)
        
        return updated

    @staticmethod
    def has_blocking_findings(findings: List[Finding]) -> bool:
        """Check if any findings are blocking (error severity)."""
        return any(f.severity == "error" for f in findings)

    def persist_project_policy_hash(
        self,
        project_id: int,
        effective_hash: str,
    ) -> None:
        """Update project with the effective policy hash."""
        self.db.update_project_policy(
            project_id,
            policy_effective_hash=effective_hash,
        )

    def audit_protocol_policy(
        self,
        protocol_run_id: int,
        *,
        pack_key: str,
        pack_version: str,
        effective_hash: str,
        policy: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Record the effective policy used for a protocol run (audit trail)."""
        self.db.update_protocol_policy_audit(
            protocol_run_id,
            policy_pack_key=pack_key,
            policy_pack_version=pack_version,
            policy_effective_hash=effective_hash,
            policy_effective_json=policy,
        )
