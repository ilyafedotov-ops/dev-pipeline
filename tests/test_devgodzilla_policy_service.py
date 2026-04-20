"""
Unit tests for DevGodzilla Policy Service evaluation logic.

Tests evaluate_project(), evaluate_protocol(), evaluate_step(), and persist_step_policy().
"""

import json
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock

import pytest

from devgodzilla.config import Config
from devgodzilla.db.database import SQLiteDatabase
from devgodzilla.services.base import ServiceContext
from devgodzilla.services.policy import (
    EffectivePolicy,
    Finding,
    PolicyService,
    _DEFAULT_BLOCK_CODES,
    _deep_merge,
    _policy_block_codes,
    _policy_required_checks,
    _sanitize_policy_override,
    _stable_hash,
)


@pytest.fixture
def tmp_env():
    """Create a temporary directory with an SQLite database."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        db_path = tmp / "test.sqlite"
        db = SQLiteDatabase(db_path)
        db.init_schema()
        yield tmp, db


@pytest.fixture
def config():
    """Create a minimal Config for testing."""
    return Config(db_path=Path("/tmp/test.sqlite"))


@pytest.fixture
def ctx(config):
    """Create a ServiceContext for testing."""
    return ServiceContext(config=config)


@pytest.fixture
def svc(ctx, tmp_env):
    """Create a PolicyService with a real SQLite database."""
    _, db = tmp_env
    return PolicyService(ctx, db)


# ─────────────────────────────────────────────────
# Helper: create project + protocol run + step run
# ─────────────────────────────────────────────────

def _seed_project(
    db: SQLiteDatabase,
    tmp: Path,
    *,
    git_url: Optional[str] = None,
    base_branch: str = "main",
    policy_pack_key: Optional[str] = None,
    policy_pack_version: Optional[str] = None,
    policy_overrides: Optional[Dict[str, Any]] = None,
    policy_enforcement_mode: Optional[str] = None,
    ci_provider: Optional[str] = None,
    skip_repo: bool = False,
):
    repo = tmp / "repo"
    repo.mkdir(parents=True, exist_ok=True)
    effective_git_url = git_url if git_url is not None else str(repo)
    project = db.create_project(
        name="test-project",
        git_url=effective_git_url,
        base_branch=base_branch,
        local_path="" if skip_repo else str(repo),
        policy_pack_key=policy_pack_key,
        policy_pack_version=policy_pack_version,
    )
    if policy_overrides or policy_enforcement_mode:
        db.update_project_policy(
            project.id,
            policy_overrides=policy_overrides,
            policy_enforcement_mode=policy_enforcement_mode,
        )
    if ci_provider:
        # ci_provider is set through update_project if available
        pass
    return project


def _seed_protocol(
    db: SQLiteDatabase,
    project_id: int,
    tmp: Path,
    *,
    protocol_name: str = "test-protocol",
    protocol_root: Optional[str] = None,
    step_name: str = "step-01-setup",
):
    """Create a protocol run and a step run."""
    root = protocol_root or str(tmp / "protocol")
    Path(root).mkdir(parents=True, exist_ok=True)

    run = db.create_protocol_run(
        project_id=project_id,
        protocol_name=protocol_name,
        status="planned",
        base_branch="main",
    )
    # Set protocol_root manually via direct SQL
    with db._transaction() as conn:
        conn.execute(
            "UPDATE protocol_runs SET protocol_root = ? WHERE id = ?",
            (root, run.id),
        )

    step = db.create_step_run(
        protocol_run_id=run.id,
        step_index=0,
        step_name=step_name,
        step_type="plan",
        status="pending",
    )
    return run, step, Path(root)


# ─────────────────────────────────────────────────
# Tests: evaluate_project()
# ─────────────────────────────────────────────────

class TestEvaluateProject:
    def test_missing_git_url(self, svc, tmp_env):
        tmp, db = tmp_env
        project = _seed_project(db, tmp, git_url="")
        findings = svc.evaluate_project(project.id)
        codes = [f.code for f in findings]
        assert "policy.project.missing_git_url" in codes

    def test_missing_base_branch(self, svc, tmp_env):
        tmp, db = tmp_env
        project = _seed_project(db, tmp, base_branch="")
        findings = svc.evaluate_project(project.id)
        codes = [f.code for f in findings]
        assert "policy.project.missing_base_branch" in codes

    def test_valid_project_no_findings(self, svc, tmp_env):
        tmp, db = tmp_env
        project = _seed_project(db, tmp)
        findings = svc.evaluate_project(project.id)
        # Should not have errors — only git_url and base_branch are set
        assert all(f.code != "policy.project.missing_git_url" for f in findings)
        assert all(f.code != "policy.project.missing_base_branch" for f in findings)

    def test_pack_not_found(self, svc, tmp_env):
        tmp, db = tmp_env
        project = _seed_project(
            db, tmp,
            policy_pack_key="nonexistent",
            policy_pack_version="99.0",
        )
        findings = svc.evaluate_project(project.id)
        codes = [f.code for f in findings]
        assert "policy.project.pack_not_found" in codes

    def test_pack_found_no_finding(self, svc, tmp_env):
        tmp, db = tmp_env
        db.upsert_policy_pack(
            key="my-pack",
            version="1.0",
            name="My Pack",
            status="active",
            pack={"meta": {"key": "my-pack"}},
        )
        project = _seed_project(
            db, tmp,
            policy_pack_key="my-pack",
            policy_pack_version="1.0",
        )
        findings = svc.evaluate_project(project.id)
        codes = [f.code for f in findings]
        assert "policy.project.pack_not_found" not in codes

    def test_invalid_enforcement_mode(self, svc, tmp_env):
        tmp, db = tmp_env
        project = _seed_project(db, tmp)
        db.update_project_policy(project.id, policy_enforcement_mode="strict")
        findings = svc.evaluate_project(project.id)
        codes = [f.code for f in findings]
        assert "policy.project.invalid_enforcement_mode" in codes

    def test_valid_enforcement_modes(self, svc, tmp_env):
        tmp, db = tmp_env
        for mode in ("warn", "block"):
            project = _seed_project(db, tmp, base_branch=f"main-{mode}")
            db.update_project_policy(project.id, policy_enforcement_mode=mode)
            findings = svc.evaluate_project(project.id)
            codes = [f.code for f in findings]
            assert "policy.project.invalid_enforcement_mode" not in codes

    def test_project_not_found(self, svc, tmp_env):
        findings = svc.evaluate_project(99999)
        codes = [f.code for f in findings]
        assert "policy.project.not_found" in codes


# ─────────────────────────────────────────────────
# Tests: evaluate_protocol()
# ─────────────────────────────────────────────────

class TestEvaluateProtocol:
    def test_no_step_files(self, svc, tmp_env):
        tmp, db = tmp_env
        project = _seed_project(db, tmp)
        run, step, root = _seed_protocol(db, project.id, tmp)
        # root dir is empty — no step files
        findings = svc.evaluate_protocol(run.id)
        codes = [f.code for f in findings]
        assert "policy.protocol.no_steps" in codes

    def test_step_naming_violation(self, svc, tmp_env):
        tmp, db = tmp_env
        project = _seed_project(db, tmp)
        run, step, root = _seed_protocol(db, project.id, tmp)
        # Create a badly-named step file (starts with step- but doesn't match step-NN-name.md)
        (root / "step-bad.md").write_text("# Bad step\n## Goal\nDo stuff\n")
        findings = svc.evaluate_protocol(run.id)
        codes = [f.code for f in findings]
        assert "policy.protocol.step_naming" in codes

    def test_good_naming_no_finding(self, svc, tmp_env):
        tmp, db = tmp_env
        project = _seed_project(db, tmp)
        run, step, root = _seed_protocol(db, project.id, tmp)
        (root / "step-01-setup.md").write_text("# Setup\n## Goal\nSetup\n")
        findings = svc.evaluate_protocol(run.id)
        codes = [f.code for f in findings]
        assert "policy.protocol.step_naming" not in codes
        assert "policy.protocol.no_steps" not in codes

    def test_insufficient_steps(self, svc, tmp_env):
        tmp, db = tmp_env
        db.upsert_policy_pack(
            key="default", version="1.0",
            name="Default", status="active",
            pack={"requirements": {"min_steps": 5}},
        )
        project = _seed_project(
            db, tmp,
            policy_pack_key="default",
            policy_pack_version="1.0",
        )
        run, step, root = _seed_protocol(db, project.id, tmp)
        (root / "step-01-setup.md").write_text("# Setup\n## Goal\nSetup\n")
        findings = svc.evaluate_protocol(run.id)
        codes = [f.code for f in findings]
        assert "policy.protocol.insufficient_steps" in codes

    def test_sufficient_steps_no_finding(self, svc, tmp_env):
        tmp, db = tmp_env
        db.upsert_policy_pack(
            key="default", version="1.0",
            name="Default", status="active",
            pack={"requirements": {"min_steps": 1}},
        )
        project = _seed_project(
            db, tmp,
            policy_pack_key="default",
            policy_pack_version="1.0",
        )
        run, step, root = _seed_protocol(db, project.id, tmp)
        (root / "step-01-setup.md").write_text("# Setup\n## Goal\nSetup\n")
        findings = svc.evaluate_protocol(run.id)
        codes = [f.code for f in findings]
        assert "policy.protocol.insufficient_steps" not in codes

    def test_missing_protocol_file(self, svc, tmp_env):
        tmp, db = tmp_env
        db.upsert_policy_pack(
            key="default", version="1.0",
            name="Default", status="active",
            pack={"requirements": {"protocol_files": ["README.md"]}},
        )
        project = _seed_project(
            db, tmp,
            policy_pack_key="default",
            policy_pack_version="1.0",
        )
        run, step, root = _seed_protocol(db, project.id, tmp)
        findings = svc.evaluate_protocol(run.id)
        codes = [f.code for f in findings]
        assert "policy.protocol.missing_file" in codes

    def test_protocol_not_found(self, svc, tmp_env):
        findings = svc.evaluate_protocol(99999)
        codes = [f.code for f in findings]
        assert "policy.protocol.not_found" in codes


# ─────────────────────────────────────────────────
# Tests: evaluate_step()
# ─────────────────────────────────────────────────

class TestEvaluateStep:
    def test_step_file_missing(self, svc, tmp_env):
        tmp, db = tmp_env
        project = _seed_project(db, tmp)
        run, step, root = _seed_protocol(db, project.id, tmp)
        # No step markdown file created
        findings = svc.evaluate_step(step.id)
        codes = [f.code for f in findings]
        assert "policy.step.file_missing" in codes

    def test_step_file_exists_no_finding(self, svc, tmp_env):
        tmp, db = tmp_env
        project = _seed_project(db, tmp)
        run, step, root = _seed_protocol(db, project.id, tmp)
        (root / "step-01-setup.md").write_text(
            "# Setup\n## Goal\nSetup things\n## Tasks\n- [ ] Do it\n"
        )
        findings = svc.evaluate_step(step.id)
        codes = [f.code for f in findings]
        assert "policy.step.file_missing" not in codes

    def test_missing_required_sections(self, svc, tmp_env):
        tmp, db = tmp_env
        db.upsert_policy_pack(
            key="default", version="1.0",
            name="Default", status="active",
            pack={"requirements": {"step_sections": ["Goal", "Tasks", "Notes"]}},
        )
        project = _seed_project(
            db, tmp,
            policy_pack_key="default",
            policy_pack_version="1.0",
        )
        run, step, root = _seed_protocol(db, project.id, tmp)
        # Only "Goal" section present, "Tasks" and "Notes" missing
        (root / "step-01-setup.md").write_text("# Setup\n## Goal\nSetup\n")
        findings = svc.evaluate_step(step.id)
        codes = [f.code for f in findings]
        assert "policy.step.missing_section" in codes
        missing_sections = [
            f.metadata["missing_section"]
            for f in findings
            if f.code == "policy.step.missing_section"
        ]
        assert "Tasks" in missing_sections
        assert "Notes" in missing_sections
        assert "Goal" not in missing_sections

    def test_all_sections_present_no_finding(self, svc, tmp_env):
        tmp, db = tmp_env
        db.upsert_policy_pack(
            key="default", version="1.0",
            name="Default", status="active",
            pack={"requirements": {"step_sections": ["Goal", "Tasks"]}},
        )
        project = _seed_project(
            db, tmp,
            policy_pack_key="default",
            policy_pack_version="1.0",
        )
        run, step, root = _seed_protocol(db, project.id, tmp)
        (root / "step-01-setup.md").write_text(
            "# Setup\n## Goal\nSetup\n## Tasks\n- [ ] Do it\n"
        )
        findings = svc.evaluate_step(step.id)
        codes = [f.code for f in findings]
        assert "policy.step.missing_section" not in codes

    def test_ci_check_missing(self, svc, tmp_env):
        tmp, db = tmp_env
        db.upsert_policy_pack(
            key="default", version="1.0",
            name="Default", status="active",
            pack={
                "defaults": {
                    "ci": {"required_checks": ["lint", "test", "build"]}
                }
            },
        )
        project = _seed_project(
            db, tmp,
            policy_pack_key="default",
            policy_pack_version="1.0",
        )
        run, step, root = _seed_protocol(db, project.id, tmp)
        (root / "step-01-setup.md").write_text("# Setup\n## Goal\nSetup\n")
        findings = svc.evaluate_step(step.id)
        codes = [f.code for f in findings]
        assert "policy.ci.required_check_missing" in codes

    def test_ci_check_referenced_in_content(self, svc, tmp_env):
        tmp, db = tmp_env
        db.upsert_policy_pack(
            key="default", version="1.0",
            name="Default", status="active",
            pack={
                "defaults": {
                    "ci": {"required_checks": ["lint", "test"]}
                }
            },
        )
        project = _seed_project(
            db, tmp,
            policy_pack_key="default",
            policy_pack_version="1.0",
        )
        run, step, root = _seed_protocol(db, project.id, tmp)
        # Step file references both lint and test
        (root / "step-01-setup.md").write_text(
            "# Setup\n## Goal\nRun lint and test checks\n"
        )
        findings = svc.evaluate_step(step.id)
        codes = [f.code for f in findings]
        assert "policy.ci.required_check_missing" not in codes

    def test_ci_provider_not_configured(self, svc, tmp_env):
        tmp, db = tmp_env
        db.upsert_policy_pack(
            key="default", version="1.0",
            name="Default", status="active",
            pack={
                "defaults": {
                    "ci": {"required_checks": ["test"]}
                }
            },
        )
        project = _seed_project(
            db, tmp,
            policy_pack_key="default",
            policy_pack_version="1.0",
        )
        run, step, root = _seed_protocol(db, project.id, tmp)
        (root / "step-01-setup.md").write_text(
            "# Setup\n## Goal\nRun test check\n"
        )
        findings = svc.evaluate_step(step.id)
        codes = [f.code for f in findings]
        assert "policy.ci.required_check_not_executable" in codes

    def test_step_not_found(self, svc, tmp_env):
        findings = svc.evaluate_step(99999)
        codes = [f.code for f in findings]
        assert "policy.step.not_found" in codes


# ─────────────────────────────────────────────────
# Tests: persist_step_policy()
# ─────────────────────────────────────────────────

class TestPersistStepPolicy:
    def test_persist_writes_to_db(self, svc, tmp_env):
        tmp, db = tmp_env
        project = _seed_project(db, tmp)
        run, step, root = _seed_protocol(db, project.id, tmp)
        (root / "step-01-setup.md").write_text("# Setup\n## Goal\nSetup\n")

        effective = EffectivePolicy(
            policy={"test": True},
            effective_hash="abc123",
            pack_key="default",
            pack_version="1.0",
        )
        findings = [
            Finding(
                code="policy.step.missing_section",
                severity="warning",
                message="Missing section",
                scope="step",
            )
        ]

        svc.persist_step_policy(step.id, effective, findings)

        # Verify it was written
        updated = db.get_step_run(step.id)
        assert updated.policy is not None
        assert updated.policy["effective_hash"] == "abc123"
        assert updated.policy["pack_key"] == "default"
        assert len(updated.policy["findings"]) == 1
        assert updated.policy["findings"][0]["code"] == "policy.step.missing_section"

    def test_evaluate_step_auto_persists(self, svc, tmp_env):
        tmp, db = tmp_env
        project = _seed_project(db, tmp)
        run, step, root = _seed_protocol(db, project.id, tmp)
        (root / "step-01-setup.md").write_text("# Setup\n## Goal\nSetup\n")

        svc.evaluate_step(step.id)

        updated = db.get_step_run(step.id)
        assert updated.policy is not None
        assert "effective_hash" in updated.policy


# ─────────────────────────────────────────────────
# Tests: enforcement mode
# ─────────────────────────────────────────────────

class TestEnforcementMode:
    def test_block_mode_escelates_warnings(self):
        findings = [
            Finding(
                code="policy.step.missing_section",
                severity="warning",
                message="Missing",
                scope="step",
            )
        ]
        result = PolicyService.apply_enforcement_mode(
            findings, "block",
        )
        assert result[0].severity == "error"

    def test_warn_mode_keeps_warnings(self):
        findings = [
            Finding(
                code="policy.step.missing_section",
                severity="warning",
                message="Missing",
                scope="step",
            )
        ]
        result = PolicyService.apply_enforcement_mode(
            findings, "warn",
        )
        assert result[0].severity == "warning"

    def test_has_blocking_findings(self):
        assert not PolicyService.has_blocking_findings([
            Finding(code="x", severity="warning", message="m", scope="step")
        ])
        assert PolicyService.has_blocking_findings([
            Finding(code="x", severity="error", message="m", scope="step")
        ])


# ─────────────────────────────────────────────────
# Tests: utility functions
# ─────────────────────────────────────────────────

class TestUtilities:
    def test_stable_hash_deterministic(self):
        h1 = _stable_hash({"a": 1, "b": 2})
        h2 = _stable_hash({"b": 2, "a": 1})
        assert h1 == h2

    def test_deep_merge(self):
        result = _deep_merge(
            {"a": {"x": 1}, "b": 2},
            {"a": {"y": 3}, "c": 4},
        )
        assert result == {"a": {"x": 1, "y": 3}, "b": 2, "c": 4}

    def test_sanitize_policy_override(self):
        result = _sanitize_policy_override({
            "defaults": {"ci": True},
            "dangerous_key": "should be removed",
        })
        assert "defaults" in result
        assert "dangerous_key" not in result

    def test_policy_required_checks_from_defaults(self):
        result = _policy_required_checks({
            "defaults": {"ci": {"required_checks": ["lint", "test"]}}
        })
        assert result == ["lint", "test"]

    def test_policy_required_checks_from_requirements(self):
        result = _policy_required_checks({
            "requirements": {"required_checks": ["build"]}
        })
        assert result == ["build"]

    def test_policy_required_checks_empty(self):
        assert _policy_required_checks({}) == []

    def test_policy_block_codes_default(self):
        result = _policy_block_codes({})
        assert result == _DEFAULT_BLOCK_CODES

    def test_policy_block_codes_custom(self):
        result = _policy_block_codes({
            "enforcement": {"block_codes": ["custom.code"]}
        })
        assert result == {"custom.code"}
