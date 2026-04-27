from __future__ import annotations

import json
from pathlib import Path


PROJECT_DETAIL_APP = Path("windmill/apps/devgodzilla/devgodzilla_project_detail.app.json")


def _load_project_detail_app() -> dict:
    return json.loads(PROJECT_DETAIL_APP.read_text(encoding="utf-8"))


def _component_by_id(app: dict, component_id: str) -> dict:
    for component in app["value"]["components"]:
        if component.get("id") == component_id:
            return component
    raise AssertionError(f"component {component_id!r} not found")


def test_project_detail_app_has_first_class_task_cycle_tab() -> None:
    app = _load_project_detail_app()

    tabs = _component_by_id(app, "tabs")
    assert "Task Cycle" in tabs["tabs"]

    task_cycle_tab = _component_by_id(app, "task_cycle_tab")
    assert task_cycle_tab["hidden"] == "{tabs.selected !== 'Task Cycle'}"


def test_project_detail_app_wires_task_cycle_data_and_next_work_item() -> None:
    app = _load_project_detail_app()
    scripts = {entry["name"]: entry for entry in app["value"]["hiddenInlineScripts"]}

    assert scripts["task_cycle_data"]["script"] == "u/devgodzilla/get_task_cycle_api"
    assert scripts["task_cycle_data"]["args"]["project_id"] == "{$state.project_id}"

    assert scripts["next_work_item_data"]["script"] == "u/devgodzilla/get_work_item_api"
    assert scripts["next_work_item_data"]["args"]["work_item_id"] == "{task_cycle_data.next_work_item_id}"


def test_project_detail_app_task_cycle_actions_use_thin_adapters() -> None:
    app = _load_project_detail_app()
    tab = _component_by_id(app, "task_cycle_tab")

    next_card = next(child for child in tab["children"] if child.get("id") == "task_cycle_next_card")
    next_details = next(child for child in next_card["children"] if child.get("id") == "task_cycle_next_details")
    actions = next(child for child in next_details["children"] if child.get("id") == "task_cycle_next_actions")

    button_names = {
        child["id"]: child["onClick"]["name"]
        for child in actions["children"]
        if child.get("type") == "button" and child.get("onClick", {}).get("type") == "runnableByName"
    }

    assert button_names["task_cycle_btn_build_context"] == "u/devgodzilla/build_context_work_item_api"
    assert button_names["task_cycle_btn_implement"] == "u/devgodzilla/implement_work_item_api"
    assert button_names["task_cycle_btn_review"] == "u/devgodzilla/review_work_item_api"
    assert button_names["task_cycle_btn_qa"] == "u/devgodzilla/qa_work_item_api"
    assert button_names["task_cycle_btn_mark_pr_ready"] == "u/devgodzilla/mark_pr_ready_work_item_api"
