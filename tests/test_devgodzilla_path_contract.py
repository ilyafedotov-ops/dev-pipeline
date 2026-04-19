from __future__ import annotations

from pathlib import Path

from devgodzilla.config import Config, load_config
from devgodzilla.services.path_contract import validate_path_contract


def test_load_config_exposes_new_path_fields(monkeypatch) -> None:
    monkeypatch.setenv("DEVGODZILLA_WINDMILL_ONBOARD_SCRIPT_PATH", "u/custom/project_onboard")
    monkeypatch.setenv("DEVGODZILLA_WINDMILL_IMPORT_ROOT", "windmill")
    monkeypatch.setenv("DEVGODZILLA_PROJECTS_ROOT", "projects")
    cfg = load_config()

    assert cfg.windmill_onboard_script_path == "u/custom/project_onboard"
    assert cfg.windmill_import_root.is_absolute()
    assert cfg.projects_root.is_absolute()


def test_validate_path_contract_reports_missing_import_root(tmp_path: Path) -> None:
    missing_root = tmp_path / "missing-windmill-root"
    cfg = Config(
        db_path=tmp_path / "devgodzilla.sqlite",
        projects_root=tmp_path / "projects",
        windmill_import_root=missing_root,
        windmill_onboard_script_path="u/devgodzilla/project_onboard_api",
    )

    report = validate_path_contract(cfg)
    assert report.errors
    assert any("windmill_import_root" in error for error in report.errors)


def test_validate_path_contract_reports_invalid_onboard_script_path(tmp_path: Path) -> None:
    valid_root = tmp_path / "windmill"
    (valid_root / "scripts" / "devgodzilla").mkdir(parents=True)
    (valid_root / "flows" / "devgodzilla").mkdir(parents=True)
    (valid_root / "apps" / "devgodzilla").mkdir(parents=True)
    cfg = Config(
        db_path=tmp_path / "devgodzilla.sqlite",
        projects_root=tmp_path / "projects",
        windmill_import_root=valid_root,
        windmill_onboard_script_path="project_onboard_api",
    )

    report = validate_path_contract(cfg)
    assert report.errors
    assert any("windmill_onboard_script_path" in error for error in report.errors)
