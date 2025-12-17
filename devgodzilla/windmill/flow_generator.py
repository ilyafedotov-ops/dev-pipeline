"""
DevGodzilla Flow Generator

Converts task DAGs to Windmill flow definitions.
Handles parallel branches, dependencies, and step execution.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from devgodzilla.logging import get_logger

logger = get_logger(__name__)


@dataclass
class DAGNode:
    """A node in the execution DAG."""
    id: str
    description: str
    step_run_id: Optional[int] = None
    agent_id: Optional[str] = None
    parallel: bool = True
    depends_on: List[str] = field(default_factory=list)


@dataclass
class DAG:
    """Directed acyclic graph of execution tasks."""
    nodes: Dict[str, DAGNode]
    edges: List[Tuple[str, str]]  # (from_id, to_id)
    
    def get_dependencies(self, node_id: str) -> List[str]:
        """Get IDs of nodes this node depends on."""
        return [edge[0] for edge in self.edges if edge[1] == node_id]
    
    def get_dependents(self, node_id: str) -> List[str]:
        """Get IDs of nodes that depend on this node."""
        return [edge[1] for edge in self.edges if edge[0] == node_id]
    
    def get_roots(self) -> List[str]:
        """Get nodes with no dependencies."""
        all_nodes = set(self.nodes.keys())
        nodes_with_deps = {edge[1] for edge in self.edges}
        return sorted(all_nodes - nodes_with_deps)


class DAGBuilder:
    """
    Builds execution DAG from step data.
    
    Example:
        builder = DAGBuilder()
        dag = builder.build_from_steps(steps)
        cycles = builder.detect_cycles(dag)
        groups = builder.compute_parallel_groups(dag)
    """

    def build_from_steps(self, steps: List[Dict[str, Any]]) -> DAG:
        """
        Build DAG from step run data.
        
        Args:
            steps: List of step dicts with id, description, depends_on, agent
            
        Returns:
            DAG object
        """
        nodes = {}
        edges = []
        
        for step in steps:
            step_id = str(step.get("id") or step.get("step_name", f"step-{len(nodes)}"))
            nodes[step_id] = DAGNode(
                id=step_id,
                description=step.get("description", step.get("step_name", "")),
                step_run_id=step.get("id"),
                agent_id=step.get("assigned_agent") or step.get("agent"),
                parallel=step.get("parallel", True),
                depends_on=step.get("depends_on", []),
            )
            
            # Add edges for dependencies
            for dep in step.get("depends_on", []):
                dep_id = str(dep)
                edges.append((dep_id, step_id))
        
        return DAG(nodes=nodes, edges=edges)

    def detect_cycles(self, dag: DAG) -> List[List[str]]:
        """
        Detect cycles in the DAG using DFS.
        
        Returns list of cycles found (empty if no cycles).
        """
        visited = set()
        rec_stack = set()
        cycles = []
        
        def dfs(node_id: str, path: List[str]) -> bool:
            visited.add(node_id)
            rec_stack.add(node_id)
            path.append(node_id)
            
            for dep_id in dag.get_dependents(node_id):
                if dep_id not in visited:
                    if dfs(dep_id, path):
                        return True
                elif dep_id in rec_stack:
                    # Found cycle
                    cycle_start = path.index(dep_id)
                    cycles.append(path[cycle_start:] + [dep_id])
                    return True
            
            path.pop()
            rec_stack.remove(node_id)
            return False
        
        for node_id in dag.nodes:
            if node_id not in visited:
                dfs(node_id, [])
        
        return cycles

    def compute_parallel_groups(self, dag: DAG) -> Dict[str, List[str]]:
        """
        Compute which tasks can run in parallel.
        
        Groups tasks by topological level - tasks at the same level
        have no dependencies on each other and can run concurrently.
        
        Returns dict mapping group_id to list of node IDs.
        """
        levels = self._topological_levels(dag)
        return {f"group_{i}": list(level) for i, level in enumerate(levels)}

    def _topological_levels(self, dag: DAG) -> List[Set[str]]:
        """Compute topological levels (Kahn's algorithm)."""
        # Calculate in-degrees
        in_degree = {node_id: 0 for node_id in dag.nodes}
        for from_id, to_id in dag.edges:
            if to_id in in_degree:
                in_degree[to_id] += 1
        
        levels = []
        remaining = set(dag.nodes.keys())
        
        while remaining:
            # Find nodes with no remaining dependencies
            level = {
                node_id for node_id in remaining
                if in_degree.get(node_id, 0) == 0
            }
            
            if not level:
                # Cycle detected - break to avoid infinite loop
                logger.warning("cycle_detected_in_topological_sort", extra={"remaining": list(remaining)})
                break
            
            levels.append(level)
            remaining -= level
            
            # Decrease in-degrees
            for node_id in level:
                for dep_id in dag.get_dependents(node_id):
                    if dep_id in in_degree:
                        in_degree[dep_id] -= 1
        
        return levels


class FlowGenerator:
    """
    Generates Windmill flow definitions from DAGs.
    
    Example:
        generator = FlowGenerator(script_path="u/devgodzilla/execute_step")
        flow_def = generator.generate(dag, protocol_run_id=123)
    """

    def __init__(
        self,
        script_path: str = "u/devgodzilla/step_execute_api",
        qa_script_path: str = "u/devgodzilla/step_run_qa_api",
    ) -> None:
        self.script_path = script_path
        self.qa_script_path = qa_script_path

    def generate(
        self,
        dag: DAG,
        protocol_run_id: int,
        *,
        include_qa: bool = True,
        default_agent: str = "opencode",
    ) -> Dict[str, Any]:
        """
        Generate Windmill flow definition from DAG.
        
        Args:
            dag: Execution DAG
            protocol_run_id: Protocol run ID for context
            include_qa: Whether to add QA step after each execution
            default_agent: Default agent for steps without assignment
            
        Returns:
            Windmill flow definition dict
        """
        builder = DAGBuilder()
        parallel_groups = builder.compute_parallel_groups(dag)
        
        modules = []
        
        for group_id in sorted(parallel_groups.keys()):
            task_ids = parallel_groups[group_id]
            
            if len(task_ids) == 1:
                # Single task - simple module
                node = dag.nodes.get(task_ids[0])
                if node:
                    modules.append(self._make_step_module(
                        node,
                        protocol_run_id,
                        default_agent,
                        include_qa,
                    ))
            else:
                # Multiple tasks - parallel branch
                branches = []
                for task_id in task_ids:
                    node = dag.nodes.get(task_id)
                    if node:
                        branch_modules = [self._make_step_module(
                            node,
                            protocol_run_id,
                            default_agent,
                            include_qa,
                        )]
                        branches.append({"modules": branch_modules})
                
                if branches:
                    modules.append({
                        "id": group_id,
                        "value": {
                            "type": "branchall",
                            "branches": branches,
                        },
                    })
        
        return {
            "modules": modules,
            "schema": {
                "properties": {
                    "protocol_run_id": {
                        "type": "integer",
                        "default": protocol_run_id,
                    },
                },
            },
        }

    def _make_step_module(
        self,
        node: DAGNode,
        protocol_run_id: int,
        default_agent: str,
        include_qa: bool,
    ) -> Dict[str, Any]:
        """Create a module for executing a step."""
        step_module = {
            "id": node.id,
            "value": {
                "type": "script",
                "path": self.script_path,
                "input_transforms": {
                    "step_run_id": {"type": "static", "value": node.step_run_id},
                },
            },
        }
        
        if include_qa:
            # Wrap in a branch with QA
            return {
                "id": f"{node.id}_with_qa",
                "value": {
                    "type": "branchone",
                    "branches": [{
                        "modules": [
                            step_module,
                            {
                                "id": f"{node.id}_qa",
                                "value": {
                                    "type": "script",
                                    "path": self.qa_script_path,
                                    "input_transforms": {
                                        "step_run_id": {"type": "static", "value": node.step_run_id},
                                    },
                                },
                            },
                        ],
                    }],
                    "default": [],
                },
            }
        
        return step_module

    def generate_simple_flow(
        self,
        steps: List[Dict[str, Any]],
        protocol_run_id: int,
    ) -> Dict[str, Any]:
        """
        Generate a simple sequential flow from steps.
        
        For cases where full DAG is not needed.
        """
        modules = []
        
        for step in steps:
            step_id = step.get("step_name", f"step-{len(modules)}")
            step_run_id = step.get("id")
            
            modules.append({
                "id": step_id,
                "value": {
                    "type": "script",
                    "path": self.script_path,
                    "input_transforms": {
                        "step_run_id": {"type": "static", "value": step_run_id},
                    },
                },
            })
        
        return {
            "modules": modules,
            "schema": {
                "properties": {
                    "protocol_run_id": {
                        "type": "integer",
                        "default": protocol_run_id,
                    },
                },
            },
        }
