from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Protocol


@dataclass
class EngineMetadata:
    id: str
    display_name: str
    kind: str  # e.g. "cli", "api"
    default_model: Optional[str] = None


@dataclass
class EngineRequest:
    project_id: int
    protocol_run_id: int
    step_run_id: int
    model: Optional[str]
    prompt_files: Iterable[str]
    working_dir: str
    extra: Optional[Dict[str, Any]] = None


@dataclass
class EngineResult:
    success: bool
    stdout: str
    stderr: str
    tokens_used: Optional[int] = None
    cost: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None


class Engine(Protocol):
    metadata: EngineMetadata

    def plan(self, req: EngineRequest) -> EngineResult: ...

    def execute(self, req: EngineRequest) -> EngineResult: ...

    def qa(self, req: EngineRequest) -> EngineResult: ...

    def sync_config(self, additional_agents: Optional[List[Dict[str, Any]]] = None) -> None: ...  # pragma: no cover - optional


class EngineRegistry:
    def __init__(self) -> None:
        self._engines: Dict[str, Engine] = {}
        self._default_id: Optional[str] = None

    def register(self, engine: Engine, default: bool = False) -> None:
        eid = engine.metadata.id
        if eid in self._engines:
            raise ValueError(f"Engine {eid} already registered")
        self._engines[eid] = engine
        if default or self._default_id is None:
            self._default_id = eid

    def get(self, engine_id: str) -> Engine:
        try:
            return self._engines[engine_id]
        except KeyError as exc:  # pragma: no cover - defensive
            raise KeyError(f"Engine {engine_id} not registered") from exc

    def get_default(self) -> Engine:
        if not self._default_id:
            raise RuntimeError("No default engine configured")
        return self._engines[self._default_id]

    def list_all(self) -> List[Engine]:
        return list(self._engines.values())


registry = EngineRegistry()


# Ensure built-in engines are registered when the registry is imported.
# This keeps service layer code simple (it can assume "codex"/"opencode" exist).
try:  # pragma: no cover - import side effects only
    import tasksgodzilla.engines_codex  # noqa: F401
    import tasksgodzilla.engines_opencode  # noqa: F401
except Exception:
    # Best effort: unit tests may register their own engines and not require these.
    pass

