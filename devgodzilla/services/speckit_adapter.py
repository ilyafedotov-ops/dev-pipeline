"""
SpecKit execution adapter.

Runs SpecKit-provided scripts (bash/powershell) and returns structured outputs.
"""

from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import subprocess
from typing import Dict, List, Optional


@dataclass
class SpecKitScriptResult:
    success: bool
    data: Dict[str, str] = field(default_factory=dict)
    error: Optional[str] = None
    stdout: Optional[str] = None
    stderr: Optional[str] = None


class SpecKitAdapter:
    """Adapter for SpecKit CLI scripts."""

    def __init__(
        self,
        project_root: Path,
        *,
        script_type: str = "sh",
        env: Optional[Dict[str, str]] = None,
    ) -> None:
        self.project_root = project_root
        self.script_type = script_type
        self.env = env or os.environ.copy()

    def has_scripts(self) -> bool:
        return self._scripts_root().exists()

    def supports(self, command: str) -> bool:
        return self._script_path(command).exists()

    def create_feature(
        self,
        description: str,
        *,
        short_name: Optional[str] = None,
        number: Optional[int] = None,
    ) -> SpecKitScriptResult:
        args = ["--json"]
        if short_name:
            args.extend(["--short-name", short_name])
        if number is not None:
            args.extend(["--number", str(number)])
        args.append(description)
        return self._run_script("specify", args=args)

    def setup_plan(self, *, feature_name: Optional[str] = None) -> SpecKitScriptResult:
        env = self.env.copy()
        if feature_name:
            env["SPECIFY_FEATURE"] = feature_name
        return self._run_script("plan", args=["--json"], env=env)

    def check_prerequisites(self, *, include_tasks: bool = False) -> SpecKitScriptResult:
        args: List[str] = ["--json", "--paths-only"]
        if include_tasks:
            args.append("--include-tasks")
        return self._run_script("check", args=args)

    def _scripts_root(self) -> Path:
        folder = "bash" if self.script_type == "sh" else "powershell"
        return self.project_root / ".specify" / "scripts" / folder

    def _script_path(self, command: str) -> Path:
        mapping = {
            "specify": "create-new-feature.sh",
            "plan": "setup-plan.sh",
            "check": "check-prerequisites.sh",
        }
        filename = mapping.get(command)
        if not filename:
            return Path("/dev/null")
        return self._scripts_root() / filename

    def _run_script(
        self,
        command: str,
        *,
        args: List[str],
        env: Optional[Dict[str, str]] = None,
    ) -> SpecKitScriptResult:
        script_path = self._script_path(command)
        if not script_path.exists():
            return SpecKitScriptResult(
                success=False,
                error=f"SpecKit script not found: {script_path}",
            )

        if self.script_type == "sh":
            cmd = ["bash", str(script_path), *args]
        else:
            cmd = ["pwsh", "-File", str(script_path), *args]

        proc = subprocess.run(
            cmd,
            cwd=str(self.project_root),
            env=env or self.env,
            capture_output=True,
            text=True,
        )

        stdout = proc.stdout.strip()
        stderr = proc.stderr.strip()

        if proc.returncode != 0:
            return SpecKitScriptResult(
                success=False,
                error=stderr or stdout or f"SpecKit script failed: {command}",
                stdout=stdout or None,
                stderr=stderr or None,
            )

        payload = self._parse_json(stdout)
        if payload is None:
            return SpecKitScriptResult(
                success=False,
                error="SpecKit script did not return JSON output",
                stdout=stdout or None,
                stderr=stderr or None,
            )

        return SpecKitScriptResult(
            success=True,
            data=payload,
            stdout=stdout or None,
            stderr=stderr or None,
        )

    @staticmethod
    def _parse_json(output: str) -> Optional[Dict[str, str]]:
        if not output:
            return None
        for line in reversed(output.splitlines()):
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(data, dict):
                return {str(k): str(v) for k, v in data.items()}
        return None
