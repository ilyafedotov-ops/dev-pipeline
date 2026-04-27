from __future__ import annotations

from typing import Any

from devgodzilla.hermes_bridge.client import DevGodzillaClient
from devgodzilla.hermes_bridge.models import SubmitFeedbackRequest


class HermesBridgeService:
    def __init__(self, client: DevGodzillaClient) -> None:
        self.client = client

    def _resolve_specification_id(self, spec_run_id: int) -> int:
        try:
            spec = self.client.request("GET", f"/specifications/{spec_run_id}")
        except Exception:
            spec = None
        if isinstance(spec, dict) and (spec.get("spec_run_id") == spec_run_id or spec.get("id") == spec_run_id):
            resolved_id = spec.get("id")
            if isinstance(resolved_id, int):
                return resolved_id

        specs = self.client.request("GET", "/specifications?limit=1000")
        items = specs.get("items", []) if isinstance(specs, dict) else specs
        for item in items:
            if not isinstance(item, dict):
                continue
            if item.get("spec_run_id") == spec_run_id or item.get("id") == spec_run_id:
                resolved_id = item.get("id")
                if isinstance(resolved_id, int):
                    return resolved_id
        raise ValueError(f"Specification for spec_run_id {spec_run_id} not found")

    def health(self) -> dict[str, Any]:
        health = self.client.request("GET", "/health")
        ready = self.client.request("GET", "/health/ready")
        return {"bridge": "ok", "devgodzilla": health, "ready": ready}

    def list_projects(self) -> Any:
        return self.client.request("GET", "/projects")

    def create_project(self, payload: dict[str, Any]) -> Any:
        return self.client.request("POST", "/projects", json=payload)

    def onboard_project(self, project_id: int, payload: dict[str, Any]) -> Any:
        return self.client.request("POST", f"/projects/{project_id}/actions/onboard", json=payload)

    def create_spec(self, payload: dict[str, Any]) -> Any:
        return self.client.request("POST", "/speckit/specify", json=payload)

    def plan_spec(self, payload: dict[str, Any]) -> Any:
        return self.client.request("POST", "/speckit/plan", json=payload)

    def generate_tasks(self, payload: dict[str, Any]) -> Any:
        return self.client.request("POST", "/speckit/tasks", json=payload)

    def get_spec(self, spec_run_id: int) -> Any:
        specification_id = self._resolve_specification_id(spec_run_id)
        return self.client.request("GET", f"/specifications/{specification_id}")

    def get_spec_content(self, spec_run_id: int) -> Any:
        specification_id = self._resolve_specification_id(spec_run_id)
        return self.client.request("GET", f"/specifications/{specification_id}/content")

    def create_protocol(self, payload: dict[str, Any]) -> Any:
        spec_run_id = payload.get("spec_run_id")
        if isinstance(spec_run_id, int) and (not payload.get("spec_path") or not payload.get("tasks_path")):
            specification = self.get_spec(spec_run_id)
            if isinstance(specification, dict):
                if not payload.get("spec_path") and specification.get("spec_path"):
                    payload = {**payload, "spec_path": specification["spec_path"]}
                if not payload.get("tasks_path") and specification.get("tasks_path"):
                    payload = {**payload, "tasks_path": specification["tasks_path"]}
        return self.client.request("POST", "/protocols/from-spec", json=payload)

    def plan_protocol(self, protocol_id: int) -> Any:
        return self.client.request("POST", f"/protocols/{protocol_id}/actions/start", json={})

    def get_protocol_status(self, protocol_id: int) -> Any:
        return self.client.request("GET", f"/protocols/{protocol_id}")

    def list_steps(self, protocol_id: int) -> Any:
        return self.client.request("GET", f"/protocols/{protocol_id}/steps")

    def get_protocol_artifacts(self, protocol_id: int) -> Any:
        return self.client.request("GET", f"/protocols/{protocol_id}/artifacts")

    def get_protocol_policy_findings(self, protocol_id: int) -> Any:
        return self.client.request("GET", f"/protocols/{protocol_id}/policy/findings")

    def run_next_step(self, protocol_id: int) -> Any:
        return self.client.request("POST", f"/protocols/{protocol_id}/actions/run_next_step", json={})

    def execute_step_with_qa(self, step_id: int) -> Any:
        return self.client.request("POST", f"/steps/{step_id}/actions/execute", json={})

    def get_step_quality(self, step_id: int) -> Any:
        return self.client.request("GET", f"/steps/{step_id}/quality")

    def get_step_artifacts(self, step_id: int) -> Any:
        return self.client.request("GET", f"/steps/{step_id}/artifacts")

    def start_brownfield_run(self, project_id: int, payload: dict[str, Any]) -> Any:
        return self.client.request("POST", f"/projects/{project_id}/brownfield/run", json=payload)

    def list_task_cycle_work_items(self, project_id: int) -> Any:
        return self.client.request("GET", f"/projects/{project_id}/task-cycle")

    def get_work_item(self, work_item_id: int) -> Any:
        return self.client.request("GET", f"/work-items/{work_item_id}")

    def build_work_item_context(self, work_item_id: int, payload: dict[str, Any]) -> Any:
        return self.client.request("POST", f"/work-items/{work_item_id}/build-context", json=payload)

    def implement_work_item(self, work_item_id: int, payload: dict[str, Any]) -> Any:
        return self.client.request("POST", f"/work-items/{work_item_id}/actions/implement", json=payload)

    def review_work_item(self, work_item_id: int) -> Any:
        return self.client.request("POST", f"/work-items/{work_item_id}/actions/review", json={})

    def qa_work_item(self, work_item_id: int, payload: dict[str, Any]) -> Any:
        return self.client.request("POST", f"/work-items/{work_item_id}/actions/qa", json=payload)

    def open_pull_request(self, protocol_id: int, payload: dict[str, Any]) -> Any:
        return self.client.request("POST", f"/protocols/{protocol_id}/actions/open_pr", json=payload)

    def submit_feedback(self, protocol_id: int, request: SubmitFeedbackRequest) -> Any:
        if request.action in {"retry", "approve", "reject"}:
            body = {
                "action": request.action,
                "message": request.message,
                "metadata": request.metadata,
            }
            return self.client.request("POST", f"/protocols/{protocol_id}/feedback", json=body)

        if request.action == "clarify_create":
            body = {
                "action": "clarify",
                "message": request.message,
                "metadata": request.metadata,
            }
            return self.client.request("POST", f"/protocols/{protocol_id}/feedback", json=body)

        body = {
            "answer": request.answer or request.message or "",
            "answered_by": request.answered_by or "hermes",
        }
        key = request.key or request.metadata.get("key")
        if not key:
            raise ValueError("clarify_answer requires key")
        return self.client.request("POST", f"/protocols/{protocol_id}/clarifications/{key}", json=body)
