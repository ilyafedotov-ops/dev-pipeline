"""
DevGodzilla Agent Configuration Service

Loads and manages agent configurations from YAML files.
Provides runtime health checks and agent capability discovery.
"""

import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from devgodzilla.services.base import Service, ServiceContext


@dataclass
class AgentConfig:
    """Configuration for a single AI agent."""
    id: str
    name: str
    kind: str  # cli, ide, api
    command: Optional[str] = None
    command_dir: Optional[str] = None
    endpoint: Optional[str] = None
    default_model: Optional[str] = None
    sandbox: str = "none"  # none, workspace-write, cloud
    capabilities: List[str] = field(default_factory=list)
    enabled: bool = True
    format: str = "default"
    
    @property
    def is_cli(self) -> bool:
        return self.kind == "cli"
    
    @property
    def is_ide(self) -> bool:
        return self.kind == "ide"
    
    @property
    def is_api(self) -> bool:
        return self.kind == "api"


@dataclass
class HealthCheckResult:
    """Result of an agent health check."""
    agent_id: str
    available: bool
    version: Optional[str] = None
    error: Optional[str] = None
    response_time_ms: Optional[float] = None


class AgentConfigService(Service):
    """
    Manages agent configurations and health checks.
    
    Loads configuration from YAML and provides:
    - Agent discovery
    - Health checks
    - Capability matching
    - Default agent selection
    """
    
    DEFAULT_CONFIG_PATH = "config/agents.yaml"
    
    def __init__(
        self,
        context: ServiceContext,
        config_path: Optional[str] = None,
    ) -> None:
        super().__init__(context)
        self._config_path = config_path
        self._agents: Dict[str, AgentConfig] = {}
        self._defaults: Dict[str, str] = {}
        self._health_config: Dict[str, Any] = {}
        self._loaded = False
    
    def load_config(self, force: bool = False) -> None:
        """Load agent configuration from YAML file."""
        if self._loaded and not force:
            return
            
        config_path = self._resolve_config_path()
        if not config_path.exists():
            self.logger.warning("agent_config_not_found", extra={"path": str(config_path)})
            self._create_default_config(config_path)
        
        try:
            with open(config_path, "r") as f:
                data = yaml.safe_load(f)
            
            # Parse agents
            for agent_id, agent_data in data.get("agents", {}).items():
                self._agents[agent_id] = AgentConfig(
                    id=agent_id,
                    name=agent_data.get("name", agent_id),
                    kind=agent_data.get("kind", "cli"),
                    command=agent_data.get("command"),
                    command_dir=agent_data.get("command_dir"),
                    endpoint=agent_data.get("endpoint"),
                    default_model=agent_data.get("default_model"),
                    sandbox=agent_data.get("sandbox", "none"),
                    capabilities=agent_data.get("capabilities", []),
                    enabled=agent_data.get("enabled", True),
                    format=agent_data.get("format", "default"),
                )
            
            self._defaults = data.get("defaults", {})
            self._health_config = data.get("health_check", {})
            self._loaded = True
            
            self.logger.info("agent_config_loaded", extra={
                "agent_count": len(self._agents),
                "path": str(config_path),
            })
            
        except Exception as e:
            self.logger.error("agent_config_load_failed", extra={"error": str(e)})
            raise
    
    def _resolve_config_path(self) -> Path:
        """Resolve the configuration file path."""
        if self._config_path:
            return Path(self._config_path)
        
        # Look in devgodzilla package directory
        package_dir = Path(__file__).parent.parent
        return package_dir / self.DEFAULT_CONFIG_PATH
    
    def _create_default_config(self, path: Path) -> None:
        """Create a default configuration file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        # Minimal default config
        default_config = {
            "agents": {
                "codex": {
                    "name": "OpenAI Codex",
                    "kind": "cli",
                    "command": "codex",
                    "enabled": True,
                },
                "opencode": {
                    "name": "OpenCode",
                    "kind": "cli",
                    "command": "opencode",
                    "enabled": True,
                },
            },
            "defaults": {
                "code_gen": "opencode",
            },
        }
        with open(path, "w") as f:
            yaml.dump(default_config, f, default_flow_style=False)
    
    def get_agent(self, agent_id: str) -> Optional[AgentConfig]:
        """Get agent configuration by ID."""
        self.load_config()
        return self._agents.get(agent_id)
    
    def list_agents(self, enabled_only: bool = True) -> List[AgentConfig]:
        """List all agents."""
        self.load_config()
        agents = list(self._agents.values())
        if enabled_only:
            agents = [a for a in agents if a.enabled]
        return agents
    
    def get_agents_by_capability(self, capability: str) -> List[AgentConfig]:
        """Get agents with a specific capability."""
        self.load_config()
        return [a for a in self._agents.values() if capability in a.capabilities and a.enabled]
    
    def get_default_agent(self, task_type: str) -> Optional[AgentConfig]:
        """Get the default agent for a task type."""
        self.load_config()
        agent_id = self._defaults.get(task_type)
        if agent_id:
            return self._agents.get(agent_id)
        return None
    
    def check_health(self, agent_id: str) -> HealthCheckResult:
        """Check if an agent is available."""
        agent = self.get_agent(agent_id)
        if not agent:
            return HealthCheckResult(
                agent_id=agent_id,
                available=False,
                error="Agent not found",
            )
        
        if not agent.enabled:
            return HealthCheckResult(
                agent_id=agent_id,
                available=False,
                error="Agent is disabled",
            )
        
        if agent.is_cli:
            return self._check_cli_health(agent)
        elif agent.is_api:
            return self._check_api_health(agent)
        else:
            return HealthCheckResult(
                agent_id=agent_id,
                available=False,
                error=f"Health check not supported for kind: {agent.kind}",
            )
    
    def _check_cli_health(self, agent: AgentConfig) -> HealthCheckResult:
        """Check health of a CLI-based agent."""
        import time
        
        if not agent.command:
            return HealthCheckResult(
                agent_id=agent.id,
                available=False,
                error="No command configured",
            )
        
        try:
            start = time.time()
            # Try to get version
            result = subprocess.run(
                [agent.command, "--version"],
                capture_output=True,
                text=True,
                timeout=self._health_config.get("timeout_seconds", 30),
            )
            response_time = (time.time() - start) * 1000
            
            if result.returncode == 0:
                version = result.stdout.strip().split("\n")[0] if result.stdout else None
                return HealthCheckResult(
                    agent_id=agent.id,
                    available=True,
                    version=version,
                    response_time_ms=response_time,
                )
            else:
                return HealthCheckResult(
                    agent_id=agent.id,
                    available=False,
                    error=result.stderr.strip() or "Command failed",
                    response_time_ms=response_time,
                )
                
        except FileNotFoundError:
            return HealthCheckResult(
                agent_id=agent.id,
                available=False,
                error=f"Command not found: {agent.command}",
            )
        except subprocess.TimeoutExpired:
            return HealthCheckResult(
                agent_id=agent.id,
                available=False,
                error="Health check timed out",
            )
        except Exception as e:
            return HealthCheckResult(
                agent_id=agent.id,
                available=False,
                error=str(e),
            )
    
    def _check_api_health(self, agent: AgentConfig) -> HealthCheckResult:
        """Check health of an API-based agent."""
        # Placeholder for API health checks
        return HealthCheckResult(
            agent_id=agent.id,
            available=False,
            error="API health checks not yet implemented",
        )
    
    def check_all_health(self) -> List[HealthCheckResult]:
        """Check health of all enabled agents."""
        self.load_config()
        results = []
        for agent in self.list_agents(enabled_only=True):
            results.append(self.check_health(agent.id))
        return results
