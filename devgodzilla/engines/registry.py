"""
DevGodzilla Engine Registry

Central registry for AI coding engines.
Manages engine registration, lookup, and health checks.
"""

from typing import Dict, List, Optional

from devgodzilla.engines.interface import Engine, EngineMetadata, EngineKind, EngineRequest, EngineResult
from devgodzilla.logging import get_logger

logger = get_logger(__name__)


class EngineNotFoundError(Exception):
    """Raised when an engine is not found in the registry."""
    pass


class EngineRegistry:
    """
    Central registry for AI coding engines.
    
    Manages:
    - Engine registration
    - Default engine selection
    - Engine lookup by ID
    - Health checks
    
    Example:
        registry = EngineRegistry()
        registry.register(CodexEngine(), default=True)
        registry.register(ClaudeCodeEngine())
        
        engine = registry.get("codex")
        result = engine.execute(request)
    """

    def __init__(self) -> None:
        self._engines: Dict[str, Engine] = {}
        self._default_id: Optional[str] = None

    def register(
        self,
        engine: Engine,
        *,
        default: bool = False,
        replace: bool = False,
    ) -> None:
        """
        Register an engine.
        
        Args:
            engine: Engine instance to register
            default: If True, set as default engine
            replace: If True, replace existing engine with same ID
        """
        engine_id = engine.metadata.id
        
        if engine_id in self._engines and not replace:
            raise ValueError(f"Engine '{engine_id}' already registered")
        
        self._engines[engine_id] = engine
        
        if default or self._default_id is None:
            self._default_id = engine_id
        
        logger.info(
            "engine_registered",
            extra={
                "engine_id": engine_id,
                "display_name": engine.metadata.display_name,
                "kind": engine.metadata.kind,
                "is_default": default,
            },
        )

    def unregister(self, engine_id: str) -> None:
        """Remove an engine from the registry."""
        if engine_id in self._engines:
            del self._engines[engine_id]
            if self._default_id == engine_id:
                self._default_id = next(iter(self._engines), None)

    def get(self, engine_id: str) -> Engine:
        """
        Get an engine by ID.
        
        Raises EngineNotFoundError if not found.
        """
        if engine_id not in self._engines:
            raise EngineNotFoundError(f"Engine '{engine_id}' not registered")
        return self._engines[engine_id]

    def get_or_default(self, engine_id: Optional[str] = None) -> Engine:
        """Get an engine by ID, or return the default engine."""
        if engine_id:
            return self.get(engine_id)
        return self.get_default()

    def get_default(self) -> Engine:
        """
        Get the default engine.
        
        Raises RuntimeError if no engine is registered.
        """
        if not self._default_id:
            raise RuntimeError("No default engine configured")
        return self._engines[self._default_id]

    def set_default(self, engine_id: str) -> None:
        """Set the default engine by ID."""
        if engine_id not in self._engines:
            raise EngineNotFoundError(f"Engine '{engine_id}' not registered")
        self._default_id = engine_id

    def list_all(self) -> List[Engine]:
        """List all registered engines."""
        return list(self._engines.values())

    def list_ids(self) -> List[str]:
        """List all registered engine IDs."""
        return list(self._engines.keys())

    def list_by_kind(self, kind: EngineKind) -> List[Engine]:
        """List engines of a specific kind."""
        return [e for e in self._engines.values() if e.metadata.kind == kind]

    def has(self, engine_id: str) -> bool:
        """Check if an engine is registered."""
        return engine_id in self._engines

    def check_all_available(self) -> Dict[str, bool]:
        """Check availability of all engines."""
        return {
            engine_id: engine.check_availability()
            for engine_id, engine in self._engines.items()
        }

    def get_metadata(self, engine_id: str) -> EngineMetadata:
        """Get engine metadata by ID."""
        return self.get(engine_id).metadata

    def list_metadata(self) -> List[EngineMetadata]:
        """List metadata for all engines."""
        return [e.metadata for e in self._engines.values()]

class PlaceholderEngine(Engine):
    """Placeholder engine for agents loaded from config."""
    
    def __init__(self, metadata: EngineMetadata):
        self._metadata = metadata
        
    @property
    def metadata(self) -> EngineMetadata:
        return self._metadata
        
    def plan(self, req: EngineRequest) -> EngineResult:
        return EngineResult(success=False, error="Not implemented")
        
    def execute(self, req: EngineRequest) -> EngineResult:
        return EngineResult(success=False, error="Not implemented")
        
    def qa(self, req: EngineRequest) -> EngineResult:
        return EngineResult(success=False, error="Not implemented")

    def load_from_yaml(self, path: str) -> None:
        """
        Load engine configurations from a YAML file.
        
        Args:
            path: Path to the YAML configuration file.
        """
        import yaml
        from pathlib import Path
        
        config_path = Path(path)
        if not config_path.exists():
            logger.warning("agent_config_not_found", path=path)
            return

        try:
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
            
            if not config or 'agents' not in config:
                return
                
            for agent_conf in config['agents']:
                meta = EngineMetadata(
                    id=agent_conf.get('id'),
                    display_name=agent_conf.get('name'),
                    kind=EngineKind(agent_conf.get('kind', 'cli')),
                    description=agent_conf.get('description')
                )
                self.register(PlaceholderEngine(meta))
                logger.info("loaded_agent_config", agent_id=agent_conf.get('id'))
                
        except Exception as e:
            logger.error("failed_loading_agent_config", error=str(e))


# Global registry instance
_registry: Optional[EngineRegistry] = None


def get_registry() -> EngineRegistry:
    """Get the global engine registry."""
    global _registry
    if _registry is None:
        _registry = EngineRegistry()
    return _registry


def register_engine(engine: Engine, *, default: bool = False) -> None:
    """Register an engine in the global registry."""
    get_registry().register(engine, default=default)


def get_engine(engine_id: str) -> Engine:
    """Get an engine from the global registry."""
    return get_registry().get(engine_id)


def get_default_engine() -> Engine:
    """Get the default engine from the global registry."""
    return get_registry().get_default()
