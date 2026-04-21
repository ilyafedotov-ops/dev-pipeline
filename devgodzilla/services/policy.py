"""
DevGodzilla Policy Service

Manages policy packs, policy resolution, and policy evaluation.
Policies define governance rules for projects, protocols, and steps.
"""

import hashlib
import json
import re
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
    Looks for: .devgodzilla/policy.(json|yaml|yml)
    """
    policy_dirs = [repo_root / ".devgodzilla"]
    json_names = ["policy.json"]
    yaml_names = ["policy.yaml", "policy.yml"]

    for policy_dir in policy_dirs:
        # Try JSON first
        for name in json_names:
            json_path = policy_dir / name
            if json_path.exists():
                try:
                    return json.loads(json_path.read_text())
                except Exception:
                    pass

        # Try YAML if available
        for name in yaml_names:
            yaml_path = policy_dir / name
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
        pack_version = project.policy_pack_version
        
        try:
            pack = self.db.get_policy_pack(key=pack_key, version=pack_version)
            base_policy = pack.pack
            resolved_version = pack.version
        except KeyError:
            # Fallback to empty policy
            base_policy = {}
            resolved_version = pack_version or "1.0"
        
        sources = {"pack": {"key": pack_key, "version": resolved_version}}
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
            pack_version=resolved_version,
            sources=sources,
        )

    def evaluate_project(self, project_id: int) -> List[Finding]:
        """
        Evaluate project-level policy compliance.
        
        Checks:
        - Required configuration is present
        - Policy pack is valid
        - Enforcement mode is valid
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
        
        # Check policy pack exists
        if project.policy_pack_key:
            pack_key = project.policy_pack_key
            pack_version = project.policy_pack_version
            try:
                self.db.get_policy_pack(key=pack_key, version=pack_version)
            except KeyError:
                findings.append(Finding(
                    code="policy.project.pack_not_found",
                    severity="warning",
                    message=f"Policy pack not found: {pack_key}@{pack_version or 'latest'}",
                    scope="project",
                    suggested_fix="Update the project's policy_pack_key or policy_pack_version to reference an existing pack",
                    metadata={"pack_key": pack_key, "pack_version": pack_version},
                ))
        
        # Check enforcement mode is valid
        valid_modes = {"warn", "block", None}
        if project.policy_enforcement_mode not in valid_modes:
            findings.append(Finding(
                code="policy.project.invalid_enforcement_mode",
                severity="warning",
                message=f"Invalid policy enforcement mode: {project.policy_enforcement_mode!r}. Must be 'warn', 'block', or None.",
                scope="project",
                suggested_fix="Set policy_enforcement_mode to 'warn', 'block', or remove it",
                metadata={"policy_enforcement_mode": project.policy_enforcement_mode},
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
        - Step naming conventions
        - Minimum step coverage
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
        
        # Check step structure
        if run.protocol_root:
            protocol_path = Path(run.protocol_root)
            if protocol_path.exists():
                step_files = sorted(protocol_path.glob("step-*.md"))
                
                # No step files at all
                if not step_files:
                    findings.append(Finding(
                        code="policy.protocol.no_steps",
                        severity="warning",
                        message="No step files found in protocol directory",
                        scope="protocol",
                        suggested_fix="Add step files matching step-*.md pattern",
                    ))
                else:
                    # Check naming convention
                    naming_pattern = re.compile(r"^step-\d{2}-.+\.md$")
                    for sf in step_files:
                        if not naming_pattern.match(sf.name):
                            findings.append(Finding(
                                code="policy.protocol.step_naming",
                                severity="info",
                                message=f"Step file does not follow naming convention: {sf.name}",
                                scope="protocol",
                                suggested_fix=f"Rename to match pattern step-NN-description.md (e.g. step-01-setup.md)",
                                metadata={"file": sf.name},
                            ))
                    
                    # Check minimum step coverage
                    min_steps = requirements.get("min_steps")
                    if min_steps is not None and len(step_files) < min_steps:
                        findings.append(Finding(
                            code="policy.protocol.insufficient_steps",
                            severity="warning",
                            message=f"Protocol has {len(step_files)} steps but policy requires at least {min_steps}",
                            scope="protocol",
                            suggested_fix=f"Add at least {min_steps - len(step_files)} more step file(s)",
                            metadata={"current_steps": len(step_files), "min_steps": min_steps},
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
        - Step markdown file exists
        - Required step sections are present
        - CI checks are referenced in the protocol
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
        
        requirements = policy.get("requirements", {})
        required_sections = requirements.get("step_sections", [])
        
        # Determine step file path
        step_file: Optional[Path] = None
        if run.protocol_root:
            step_file = Path(run.protocol_root) / f"{step.step_name}.md"
        
        # a) Check step markdown file exists
        if step_file is None or not step_file.exists():
            findings.append(Finding(
                code="policy.step.file_missing",
                severity="warning",
                message=f"Step markdown file missing: {step.step_name}.md",
                scope="step",
                suggested_fix=f"Create {step.step_name}.md in the protocol directory",
                metadata={"step_name": step.step_name},
            ))
        else:
            # b) Check required sections
            if required_sections:
                try:
                    content = step_file.read_text(encoding="utf-8")
                    headings = re.findall(r"^##\s+(.+)$", content, re.MULTILINE)
                    heading_set = {h.strip() for h in headings}
                    for section in required_sections:
                        if section not in heading_set:
                            findings.append(Finding(
                                code="policy.step.missing_section",
                                severity="warning",
                                message=f"Required section missing in {step.step_name}.md: {section}",
                                scope="step",
                                suggested_fix=f"Add a '## {section}' heading to {step.step_name}.md",
                                metadata={"step_name": step.step_name, "missing_section": section},
                            ))
                except Exception as exc:
                    logger.warning("Failed to read step file %s: %s", step_file, exc)
        
        # c) CI checks validation
        required_checks = _policy_required_checks(policy)
        if required_checks and run.protocol_root:
            protocol_path = Path(run.protocol_root)
            if protocol_path.exists():
                # Gather all step names and file contents for reference checks
                all_step_names: List[str] = []
                all_step_content = ""
                try:
                    all_steps = self.db.list_step_runs(step.protocol_run_id)
                    all_step_names = [s.step_name for s in all_steps]
                except Exception:
                    pass
                
                # Also scan step files for content references
                for sf in protocol_path.glob("step-*.md"):
                    try:
                        all_step_content += sf.read_text(encoding="utf-8").lower() + "\n"
                    except Exception:
                        pass
                
                for check_name in required_checks:
                    check_lower = check_name.lower()
                    # Check if referenced in step names or file content
                    found = any(
                        check_lower in name.lower()
                        for name in all_step_names
                    ) or check_lower in all_step_content
                    
                    if not found:
                        findings.append(Finding(
                            code="policy.ci.required_check_missing",
                            severity="warning",
                            message=f"Required CI check not referenced in protocol: {check_name}",
                            scope="step",
                            suggested_fix=f"Add a step or content referencing the '{check_name}' CI check",
                            metadata={"check": check_name},
                        ))
                
                # Check if project has ci_provider configured (one finding, not per-check)
                try:
                    project = self.db.get_project(run.project_id)
                    if not project.ci_provider:
                        findings.append(Finding(
                            code="policy.ci.required_check_not_executable",
                            severity="warning",
                            message="CI checks are required by policy but project has no ci_provider configured",
                            scope="step",
                            suggested_fix="Configure a ci_provider for the project (e.g. 'github-actions')",
                            metadata={"required_checks": required_checks},
                        ))
                except Exception:
                    pass
        
        # Persist effective policy snapshot
        try:
            self.persist_step_policy(step_run_id, effective, findings)
        except Exception as exc:
            logger.warning("Failed to persist step policy for step_run_id=%s: %s", step_run_id, exc)
        
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
        lines.append("### QA Policy: prompt-driven (auto-run after execution)")
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

    def persist_step_policy(
        self,
        step_run_id: int,
        effective: EffectivePolicy,
        findings: List[Finding],
    ) -> None:
        """Record the effective policy and findings for a step run."""
        self.db.update_step_run(
            step_run_id,
            policy={
                "effective_hash": effective.effective_hash,
                "pack_key": effective.pack_key,
                "pack_version": effective.pack_version,
                "findings": [f.asdict() for f in findings],
            },
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

    def render_constitution(self, effective: EffectivePolicy) -> str:
        """Render a SpecKit constitution document from an effective policy."""
        policy = dict(effective.policy)
        meta = policy.get("meta")
        if not isinstance(meta, dict):
            meta = {}
        meta.setdefault("key", effective.pack_key)
        meta.setdefault("version", effective.pack_version)
        policy["meta"] = meta

        policy_json = json.dumps(policy, indent=2, sort_keys=True)

        lines = [
            "# Project Constitution",
            "",
            "## Policy Pack",
            f"- key: {meta.get('key', effective.pack_key)}",
            f"- version: {meta.get('version', effective.pack_version)}",
            "",
            "## Policy JSON",
            "```json",
            policy_json,
            "```",
            "",
        ]
        return "\n".join(lines)

    def parse_constitution_policy(self, content: str) -> Optional[Dict[str, Any]]:
        """Extract policy JSON from a constitution document."""
        match = re.search(r"```json\\s*(\\{.*?\\})\\s*```", content, re.DOTALL)
        if not match:
            return None
        try:
            payload = json.loads(match.group(1))
        except Exception:
            return None
        return payload if isinstance(payload, dict) else None

    def policy_override_from_constitution(
        self,
        content: str,
    ) -> tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
        """
        Extract a policy override payload + meta from constitution content.
        
        Returns (override, meta).
        """
        payload = self.parse_constitution_policy(content)
        if not payload:
            return None, {}
        meta = payload.get("meta") if isinstance(payload.get("meta"), dict) else {}
        override = _sanitize_policy_override(payload)
        return override or None, meta
