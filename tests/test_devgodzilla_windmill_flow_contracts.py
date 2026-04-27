from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "windmill" / "scripts" / "devgodzilla"
FLOWS_DIR = REPO_ROOT / "windmill" / "flows" / "devgodzilla"


def _script_signatures() -> dict[str, tuple[set[str], bool]]:
    signatures: dict[str, tuple[set[str], bool]] = {}
    for path in sorted(SCRIPTS_DIR.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in tree.body:
            if isinstance(node, ast.FunctionDef) and node.name == "main":
                accepted = {arg.arg for arg in node.args.args}
                accepted.update(arg.arg for arg in node.args.kwonlyargs)
                signatures[path.stem] = (accepted, node.args.kwarg is not None)
                break
    return signatures


def _iter_flow_script_calls(payload: Any) -> list[tuple[str, str, set[str]]]:
    calls: list[tuple[str, str, set[str]]] = []
    stack = [payload]
    while stack:
        current = stack.pop()
        if isinstance(current, dict):
            value = current.get("value")
            if isinstance(value, dict) and value.get("type") == "script":
                script_path = value.get("path")
                if isinstance(script_path, str) and script_path.startswith("u/devgodzilla/"):
                    script_name = script_path.split("/")[-1]
                    transforms = current.get("input_transforms") or value.get("input_transforms") or {}
                    calls.append((script_path, script_name, set(transforms.keys())))
            stack.extend(current.values())
        elif isinstance(current, list):
            stack.extend(current)
    return calls


def test_exported_windmill_flow_inputs_match_wrapper_signatures() -> None:
    signatures = _script_signatures()
    mismatches: list[str] = []

    for flow_path in sorted(FLOWS_DIR.glob("*.flow.json")):
        data = json.loads(flow_path.read_text(encoding="utf-8"))
        for script_path, script_name, passed_args in _iter_flow_script_calls(data):
            accepted_args, accepts_kwargs = signatures[script_name]
            if accepts_kwargs:
                continue
            extras = sorted(passed_args - accepted_args)
            if extras:
                mismatches.append(
                    f"{flow_path.name}: {script_path} passes unsupported args {extras}; "
                    f"wrapper accepts {sorted(accepted_args)}"
                )

    assert not mismatches, "Windmill flow/wrapper input mismatches:\n" + "\n".join(mismatches)


def test_spec_to_protocol_flow_reuses_implement_bootstrap_protocol() -> None:
    flow_path = FLOWS_DIR / "spec_to_protocol.flow.json"
    data = json.loads(flow_path.read_text(encoding="utf-8"))
    modules = data["value"]["modules"]
    module_by_id = {module["id"]: module for module in modules}

    assert "speckit_implement" in module_by_id
    assert "create_protocol" not in module_by_id

    protocol_start = module_by_id["protocol_start"]
    protocol_expr = (
        protocol_start["value"]["branches"][1]["modules"][0]["input_transforms"]["protocol_run_id"]["expr"]
    )
    assert protocol_expr == "results.speckit_implement.protocol_id"


def test_brownfield_feature_tasks_to_sprint_uses_generated_tasks_artifact() -> None:
    flow_path = FLOWS_DIR / "brownfield_feature.flow.json"
    data = json.loads(flow_path.read_text(encoding="utf-8"))
    module_by_id = {module["id"]: module for module in data["value"]["modules"]}
    sync_tasks = module_by_id["sync_tasks"]

    assert sync_tasks["skip_if"]["expr"] == "flow_input.output_mode !== 'tasks_to_sprint'"
    assert sync_tasks["value"]["input_transforms"]["spec_path"]["expr"] == "results.speckit_tasks.tasks_path"
    assert (
        sync_tasks["value"]["input_transforms"]["overwrite_existing"]["expr"]
        == "flow_input.overwrite_existing_tasks || false"
    )


def test_brownfield_feature_protocol_to_sprint_uses_created_protocol() -> None:
    flow_path = FLOWS_DIR / "brownfield_feature.flow.json"
    data = json.loads(flow_path.read_text(encoding="utf-8"))
    module_by_id = {module["id"]: module for module in data["value"]["modules"]}

    assert module_by_id["create_protocol"]["skip_if"]["expr"] == "!['task_cycle', 'protocol', 'protocol_to_sprint'].includes(flow_input.output_mode)"
    assert module_by_id["protocol_start"]["skip_if"]["expr"] == "!['task_cycle', 'protocol', 'protocol_to_sprint'].includes(flow_input.output_mode)"
    assert module_by_id["create_sprint"]["skip_if"]["expr"] == "flow_input.output_mode !== 'protocol_to_sprint'"
    assert module_by_id["protocol_start"]["value"]["input_transforms"]["protocol_run_id"]["expr"] == "results.create_protocol.protocol.id"
    assert module_by_id["create_sprint"]["value"]["input_transforms"]["protocol_id"]["expr"] == "results.create_protocol.protocol.id"


def test_brownfield_feature_task_cycle_uses_created_protocol_for_work_items() -> None:
    flow_path = FLOWS_DIR / "brownfield_feature.flow.json"
    data = json.loads(flow_path.read_text(encoding="utf-8"))
    module_by_id = {module["id"]: module for module in data["value"]["modules"]}

    assert module_by_id["get_task_cycle"]["skip_if"]["expr"] == "flow_input.output_mode !== 'task_cycle'"
    assert module_by_id["get_task_cycle"]["value"]["input_transforms"]["project_id"]["expr"] == "results.onboard_project.project_id"
    assert (
        module_by_id["get_task_cycle"]["value"]["input_transforms"]["protocol_run_id"]["expr"]
        == "results.create_protocol.protocol.id"
    )


def test_brownfield_feature_task_cycle_passes_helper_sidecar_inputs() -> None:
    flow_path = FLOWS_DIR / "brownfield_feature.flow.json"
    data = json.loads(flow_path.read_text(encoding="utf-8"))
    module_by_id = {module["id"]: module for module in data["value"]["modules"]}

    create_protocol = module_by_id["create_protocol"]["value"]["input_transforms"]
    assert create_protocol["task_cycle"]["expr"] == "flow_input.output_mode === 'task_cycle'"
    assert create_protocol["owner_agent"]["expr"] == "flow_input.owner_agent || null"
    assert create_protocol["helper_agents"]["expr"] == "flow_input.helper_agents || []"
    assert create_protocol["allow_helper_agents"]["expr"] == "flow_input.allow_helper_agents || false"
