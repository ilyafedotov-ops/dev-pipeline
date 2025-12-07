from pathlib import Path
from typing import Any

from tasksgodzilla.codex import run_process
from tasksgodzilla.engines import Engine, EngineMetadata, EngineRequest, EngineResult, registry


class CodexEngine:
    """
    Thin Engine wrapper around the Codex CLI.

    For now this uses a simple contract:
    - plan/execute/qa all shell out to `codex exec` with the provided model.
    - prompt_files are concatenated in caller-specific order before being passed.
    """

    metadata = EngineMetadata(
        id="codex",
        display_name="Codex CLI",
        kind="cli",
        default_model=None,
    )

    def _run(
        self,
        req: EngineRequest,
        sandbox: str,
    ) -> EngineResult:
        # The higher-level workers are responsible for assembling the actual prompt text.
        # Here we only ensure the CLI invocation contract.
        # We still allow prompt_files to be passed for future use (e.g., tracing),
        # but Codex CLI itself currently receives the assembled prompt via stdin.
        extra: dict[str, Any] = dict(req.extra or {})

        # Allow callers to override sandbox via extra to keep the EngineRequest
        # contract generic.
        effective_sandbox = str(extra.get("sandbox", sandbox))

        model = req.model or self.metadata.default_model or ""
        if not model:
            raise ValueError("CodexEngine requires a model")

        cwd = Path(req.working_dir)
        cmd = [
            "codex",
            "exec",
            "-m",
            model,
            "--cd",
            str(cwd),
            "--sandbox",
            effective_sandbox,
            "--skip-git-repo-check",
        ]

        output_schema = extra.get("output_schema")
        if output_schema:
            cmd.extend(["--output-schema", str(output_schema)])
        output_last_message = extra.get("output_last_message")
        if output_last_message:
            cmd.extend(["--output-last-message", str(output_last_message)])

        cmd.append("-")

        prompt_text = ""
        prompt_from_extra = extra.get("prompt_text")
        if isinstance(prompt_from_extra, str) and prompt_from_extra:
            prompt_text = prompt_from_extra
        else:
            for path in req.prompt_files:
                try:
                    prompt_text += Path(path).read_text(encoding="utf-8") + "\n"
                except FileNotFoundError:
                    continue

        proc = run_process(cmd, cwd=cwd, capture_output=True, text=True, input_text=prompt_text, check=True)
        return EngineResult(
            success=True,
            stdout=proc.stdout or "",
            stderr=proc.stderr or "",
            tokens_used=None,
            cost=None,
            metadata={"returncode": proc.returncode, "sandbox": effective_sandbox},
        )

    def plan(self, req: EngineRequest) -> EngineResult:
        return self._run(req, sandbox="read-only")

    def execute(self, req: EngineRequest) -> EngineResult:
        return self._run(req, sandbox="workspace-write")

    def qa(self, req: EngineRequest) -> EngineResult:
        return self._run(req, sandbox="read-only")

    def sync_config(self, additional_agents=None) -> None:  # pragma: no cover - optional hook
        return None


def register_default_codex_engine() -> None:
    """
    Register CodexEngine in the global registry.

    This function is intentionally separate so that callers can control import timing.
    """
    registry.register(CodexEngine(), default=True)


# Register on import for now so that existing workers can rely on a default engine.
register_default_codex_engine()
