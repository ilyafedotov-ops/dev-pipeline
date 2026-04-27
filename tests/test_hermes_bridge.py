from __future__ import annotations

from fastapi.testclient import TestClient

from devgodzilla.hermes_bridge.app import app, get_config, get_service
from devgodzilla.hermes_bridge.config import BridgeConfig
from devgodzilla.hermes_bridge.models import SubmitFeedbackRequest
from devgodzilla.hermes_bridge.service import HermesBridgeService


class StubBridgeService:
    def health(self):
        return {"bridge": "ok"}

    def list_projects(self):
        return [{"id": 1, "name": "demo"}]

    def create_project(self, payload):
        return payload

    def onboard_project(self, project_id, payload):
        return {"project_id": project_id, **payload}

    def create_spec(self, payload):
        return payload

    def plan_spec(self, payload):
        return payload

    def generate_tasks(self, payload):
        return payload

    def get_spec(self, spec_run_id):
        return {"id": spec_run_id, "spec_run_id": spec_run_id, "title": "demo spec"}

    def get_spec_content(self, spec_run_id):
        return {"id": spec_run_id, "spec_content": "# Spec", "plan_content": "# Plan", "tasks_content": "# Tasks"}

    def create_protocol(self, payload):
        return payload

    def plan_protocol(self, protocol_id):
        return {"protocol_id": protocol_id, "status": "planning"}

    def get_protocol_status(self, protocol_id):
        return {"id": protocol_id, "status": "planned"}

    def list_steps(self, protocol_id):
        return [{"id": 11, "protocol_id": protocol_id}]

    def get_protocol_artifacts(self, protocol_id):
        return [{"id": "72:quality-report.md", "protocol_id": protocol_id}]

    def get_protocol_policy_findings(self, protocol_id):
        return [{"code": "policy.protocol.missing_file", "protocol_id": protocol_id}]

    def run_next_step(self, protocol_id):
        return {"protocol_id": protocol_id, "step_run_id": 11}

    def execute_step_with_qa(self, step_id):
        return {"step_id": step_id, "status": "completed"}

    def get_step_quality(self, step_id):
        return {"step_id": step_id, "overall_status": "passed"}

    def get_step_artifacts(self, step_id):
        return [{"id": "qa_report.md", "step_id": step_id}]

    def start_brownfield_run(self, project_id, payload):
        return {"project_id": project_id, **payload}

    def list_task_cycle_work_items(self, project_id):
        return [{"id": 101, "project_id": project_id}]

    def get_work_item(self, work_item_id):
        return {"id": work_item_id, "status": "todo"}

    def build_work_item_context(self, work_item_id, payload):
        return {"id": work_item_id, "context_built": True, **payload}

    def implement_work_item(self, work_item_id, payload):
        return {"id": work_item_id, "implemented": True, **payload}

    def review_work_item(self, work_item_id):
        return {"verdict": "pass", "work_item_id": work_item_id}

    def qa_work_item(self, work_item_id, payload):
        return {"work_item": {"id": work_item_id}, "qa": {"requested_gates": payload.get("gates", [])}}

    def submit_feedback(self, protocol_id, request: SubmitFeedbackRequest):
        return {"protocol_id": protocol_id, "action": request.action}

    def open_pull_request(self, protocol_id, payload):
        return {"protocol_id": protocol_id, **payload}


def _client() -> TestClient:
    app.dependency_overrides[get_config] = lambda: BridgeConfig(
        devgodzilla_base_url="http://example.test/api/v1",
        devgodzilla_api_token=None,
        hermes_bridge_token="bridge-secret",
        timeout_seconds=10,
    )
    app.dependency_overrides[get_service] = lambda: StubBridgeService()
    return TestClient(app)


def teardown_function() -> None:
    app.dependency_overrides.clear()


def test_bridge_requires_token() -> None:
    client = _client()
    response = client.get("/health")
    assert response.status_code == 401


def test_health_succeeds_with_token() -> None:
    client = _client()
    response = client.get("/health", headers={"X-Hermes-Bridge-Token": "bridge-secret"})
    assert response.status_code == 200
    assert response.json()["tool"] == "health"
    assert response.json()["data"] == {"bridge": "ok"}


def test_submit_feedback_routes_through_bridge() -> None:
    client = _client()
    response = client.post(
        "/tools/protocols/42/feedback",
        headers={"X-Hermes-Bridge-Token": "bridge-secret"},
        json={"action": "clarify_answer", "key": "compatibility", "answer": "Keep backward compatibility"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["tool"] == "submit_feedback"
    assert body["data"] == {"protocol_id": 42, "action": "clarify_answer"}


def test_brownfield_run_routes_through_bridge() -> None:
    client = _client()
    response = client.post(
        "/tools/projects/7/brownfield-run",
        headers={"X-Hermes-Bridge-Token": "bridge-secret"},
        json={"data": {"feature_request": "Add export button", "output_mode": "task_cycle"}},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["tool"] == "start_brownfield_run"
    assert body["data"]["project_id"] == 7
    assert body["data"]["output_mode"] == "task_cycle"


def test_spec_content_routes_through_bridge() -> None:
    client = _client()
    response = client.get(
        "/tools/specs/34/content",
        headers={"X-Hermes-Bridge-Token": "bridge-secret"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["tool"] == "get_spec_content"
    assert body["data"]["id"] == 34
    assert body["data"]["spec_content"] == "# Spec"


def test_protocol_policy_routes_through_bridge() -> None:
    client = _client()
    response = client.get(
        "/tools/protocols/30/policy",
        headers={"X-Hermes-Bridge-Token": "bridge-secret"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["tool"] == "get_protocol_policy"
    assert body["data"][0]["code"] == "policy.protocol.missing_file"


def test_create_protocol_backfills_spec_and_tasks_paths_from_spec_run_id() -> None:
    class RecordingClient:
        def __init__(self) -> None:
            self.calls = []

        def request(self, method, path, json=None):
            self.calls.append((method, path, json))
            if method == "GET" and path == "/specifications/34":
                return {
                    "id": 34,
                    "spec_run_id": 34,
                    "spec_path": "/tmp/spec.md",
                    "tasks_path": "/tmp/tasks.md",
                }
            if method == "POST" and path == "/protocols/from-spec":
                return json
            raise AssertionError((method, path, json))

    service = HermesBridgeService(RecordingClient())  # type: ignore[arg-type]
    result = service.create_protocol({"project_id": 4, "spec_run_id": 34})

    assert result["spec_path"] == "/tmp/spec.md"
    assert result["tasks_path"] == "/tmp/tasks.md"
