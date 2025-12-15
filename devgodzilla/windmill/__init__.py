"""
DevGodzilla Windmill Integration

Industrial-grade workflow orchestration via Windmill.
"""

from devgodzilla.windmill.client import (
    WindmillClient,
    WindmillConfig,
    get_windmill_config,
    JobStatus,
    JobInfo,
    FlowInfo,
)
from devgodzilla.windmill.flow_generator import (
    DAGBuilder,
    DAGNode,
    DAG,
    FlowGenerator,
)

__all__ = [
    # Client
    "WindmillClient",
    "WindmillConfig",
    "get_windmill_config",
    "JobStatus",
    "JobInfo",
    "FlowInfo",
    # Flow Generator
    "DAGBuilder",
    "DAGNode",
    "DAG",
    "FlowGenerator",
]
