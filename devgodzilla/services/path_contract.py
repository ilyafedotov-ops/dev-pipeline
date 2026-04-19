from __future__ import annotations

from dataclasses import dataclass, field

from devgodzilla.config import Config
from devgodzilla.logging import get_logger

logger = get_logger(__name__)


@dataclass
class PathContractReport:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return not self.errors


def _is_valid_windmill_script_path(path: str) -> bool:
    if not path or not isinstance(path, str):
        return False
    if not path.startswith("u/"):
        return False
    parts = [part for part in path.split("/") if part]
    return len(parts) >= 3


def validate_path_contract(config: Config) -> PathContractReport:
    report = PathContractReport()

    if not config.projects_root.is_absolute():
        report.errors.append(
            f"projects_root must be absolute; got {config.projects_root!s}"
        )

    if not _is_valid_windmill_script_path(config.windmill_onboard_script_path):
        report.errors.append(
            "windmill_onboard_script_path must look like 'u/<folder>/<script_name>'"
        )

    if not config.windmill_import_root.exists():
        report.errors.append(
            f"windmill_import_root does not exist: {config.windmill_import_root!s}"
        )
        return report

    required_dirs = (
        config.windmill_import_root / "scripts" / "devgodzilla",
        config.windmill_import_root / "flows" / "devgodzilla",
        config.windmill_import_root / "apps" / "devgodzilla",
    )
    for required in required_dirs:
        if not required.exists():
            report.errors.append(f"missing required directory under windmill_import_root: {required!s}")

    if _is_valid_windmill_script_path(config.windmill_onboard_script_path):
        script_name = config.windmill_onboard_script_path.split("/")[-1]
        script_file = config.windmill_import_root / "scripts" / "devgodzilla" / f"{script_name}.py"
        if not script_file.exists():
            report.errors.append(
                f"onboarding script file not found for windmill_onboard_script_path: {script_file!s}"
            )

    if config.windmill_env_file and not config.windmill_env_file.exists():
        report.warnings.append(
            f"windmill_env_file does not exist: {config.windmill_env_file!s}"
        )

    return report
