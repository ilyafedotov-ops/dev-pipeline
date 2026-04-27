from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any

import httpx
import pytest

from devgodzilla.config import load_config
from devgodzilla.windmill.client import JobStatus, WindmillClient, WindmillConfig


pytestmark = pytest.mark.integration

REPO_ROOT = Path(__file__).resolve().parents[1]


def _flag(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _run_local_windmill_import() -> None:
    script = REPO_ROOT / "scripts" / "run-local-dev.sh"
    proc = subprocess.run(  # noqa: S603
        ["bash", str(script), "import"],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        timeout=900,
        check=False,
    )
    if proc.returncode != 0:
        raise AssertionError(
            "Windmill asset import failed before live flow execution:\n"
            f"stdout:\n{proc.stdout[-4000:]}\n\nstderr:\n{proc.stderr[-4000:]}"
        )


def _ensure_host_backend_ready() -> None:
    health_url = os.environ.get("DEVGODZILLA_LIVE_HOST_BACKEND_HEALTH_URL", "http://localhost:8000/health").rstrip("/")
    try:
        response = httpx.get(health_url, timeout=5)
        if response.status_code == 200:
            return
    except Exception:
        pass

    script = REPO_ROOT / "scripts" / "run-local-dev.sh"
    env = os.environ.copy()
    env.setdefault("DEVGODZILLA_OPENCODE_MODEL", "zai-coding-plan/glm-5")
    subprocess.run(  # noqa: S603
        [
            "bash",
            "-lc",
            f"nohup bash {script} backend start > /tmp/devgodzilla-live-windmill-backend.log 2>&1 &",
        ],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )

    deadline = time.monotonic() + 90
    last_error = ""
    while time.monotonic() < deadline:
        try:
            response = httpx.get(health_url, timeout=5)
            if response.status_code == 200:
                return
            last_error = response.text[:500]
        except Exception as exc:
            last_error = str(exc)
        time.sleep(1)

    raise AssertionError(f"Host DevGodzilla backend did not become ready at {health_url}: {last_error}")


def _host_path_from_runtime(raw_path: str) -> Path:
    path = Path(raw_path).expanduser()
    if path.exists():
        return path.resolve(strict=False)
    parts = path.parts
    if len(parts) >= 3 and parts[1] == "app":
        translated = REPO_ROOT.joinpath(*parts[2:])
        if translated.exists():
            return translated.resolve(strict=False)
    raise AssertionError(f"Runtime path is not visible from the host workspace: {raw_path}")


def _job_payload(client: WindmillClient, job_id: str) -> dict[str, Any]:
    payload = client._request("get", f"/jobs_u/get/{job_id}").json()
    assert isinstance(payload, dict)
    return payload


def _assert_no_template_markers(path: Path, *, markers: list[str]) -> None:
    content = path.read_text(encoding="utf-8")
    detected = [marker for marker in markers if marker in content]
    assert not detected, f"{path} still contains template markers: {detected}"


def _assert_module_job_succeeded(client: WindmillClient, module_job_id: str, *, module_id: str) -> dict[str, Any]:
    payload = _job_payload(client, module_job_id)
    result = payload.get("result")
    status_code = int(result.get("status_code") or 200) if isinstance(result, dict) else 200
    logical_success = not (isinstance(result, dict) and result.get("success") is False)
    if payload.get("success") is not True or status_code >= 400 or not logical_success:
        logs = client.get_job_logs(module_job_id)
        raise AssertionError(
            f"Windmill module {module_id} failed.\n"
            f"result={result}\n"
            f"logs:\n{logs[-6000:]}"
        )
    assert isinstance(result, dict), f"Expected dict result for module {module_id}, got {type(result).__name__}"
    return result


def _collect_module_jobs(client: WindmillClient, modules: list[dict[str, Any]]) -> dict[str, str]:
    jobs: dict[str, str] = {}
    stack: list[dict[str, Any]] = list(modules)
    while stack:
        module = stack.pop()
        module_id = module.get("id")
        job_id = module.get("job")
        if isinstance(module_id, str) and isinstance(job_id, str):
            jobs[module_id] = job_id
            if job_id != "00000000-0000-0000-0000-000000000000":
                try:
                    payload = _job_payload(client, job_id)
                except Exception:
                    payload = {}
                nested_status = payload.get("flow_status")
                if isinstance(nested_status, dict):
                    nested_modules = nested_status.get("modules")
                    if isinstance(nested_modules, list):
                        stack.extend(item for item in nested_modules if isinstance(item, dict))
        nested = module.get("modules")
        if isinstance(nested, list):
            stack.extend(item for item in nested if isinstance(item, dict))
    return jobs


def _create_live_project(
    api: httpx.Client,
    *,
    host_api_base_url: str,
    repo_url: str,
    base_branch: str,
    name_prefix: str,
) -> int:
    created = api.post(
        f"{host_api_base_url}/projects",
        json={
            "name": f"{name_prefix}-{int(time.time())}",
            "git_url": repo_url,
            "base_branch": base_branch,
            "auto_onboard": False,
            "auto_discovery": False,
        },
    )
    assert created.status_code == 200, f"project creation failed: {created.text}"
    project = created.json()
    return int(project["id"])


def _create_live_sprint(
    api: httpx.Client,
    *,
    host_api_base_url: str,
    project_id: int,
    name: str,
) -> int:
    created = api.post(
        f"{host_api_base_url}/sprints",
        json={
            "project_id": project_id,
            "name": name,
            "status": "active",
        },
    )
    assert created.status_code == 200, f"sprint creation failed: {created.text}"
    sprint = created.json()
    return int(sprint["id"])


def test_live_windmill_stack_end_to_end() -> None:
    """
    Opt-in integration test that hits a real running Windmill + DevGodzilla stack.

    Enable with:
      - DEVGODZILLA_RUN_LIVE_WINDMILL_TESTS=1

    This test refreshes imported Windmill assets, creates a real project against a
    small GitHub repo, onboards it, runs the exported SpecKit -> protocol flow,
    and validates the generated artifacts and linkage.
    """
    if not _flag("DEVGODZILLA_RUN_LIVE_WINDMILL_TESTS"):
        pytest.skip("set DEVGODZILLA_RUN_LIVE_WINDMILL_TESTS=1 to enable live integration test")

    public_base_url = os.environ.get("DEVGODZILLA_LIVE_BASE_URL", "http://localhost:8080").rstrip("/")
    host_api_base_url = os.environ.get("DEVGODZILLA_LIVE_HOST_API_URL", "http://localhost:8000").rstrip("/")
    repo_url = os.environ.get(
        "DEVGODZILLA_LIVE_WINDMILL_REPO_URL",
        "https://github.com/ilyafedotov-ops/test-glm5-demo.git",
    ).strip()
    base_branch = (os.environ.get("DEVGODZILLA_LIVE_WINDMILL_REPO_BRANCH") or "main").strip()
    config = load_config()

    assert config.windmill_url, "DEVGODZILLA_WINDMILL_URL must be set (or provided via DEVGODZILLA_WINDMILL_ENV_FILE)"
    assert config.windmill_token, "DEVGODZILLA_WINDMILL_TOKEN must be set (or provided via DEVGODZILLA_WINDMILL_ENV_FILE)"
    assert config.windmill_workspace, "DEVGODZILLA_WINDMILL_WORKSPACE must be set"

    _ensure_host_backend_ready()
    _run_local_windmill_import()

    ready = httpx.get(f"{public_base_url}/health/ready", timeout=10)
    assert ready.status_code == 200, f"stack not ready at {public_base_url}/health/ready: {ready.text}"

    flows = httpx.get(f"{public_base_url}/flows", timeout=20)
    assert flows.status_code == 200, f"/flows failed: {flows.text}"
    assert isinstance(flows.json(), list)

    jobs = httpx.get(f"{public_base_url}/jobs", timeout=20)
    assert jobs.status_code == 200, f"/jobs failed: {jobs.text}"
    assert isinstance(jobs.json(), list)

    windmill = WindmillClient(
        WindmillConfig(
            base_url=config.windmill_url,
            token=config.windmill_token,
            workspace=config.windmill_workspace,
            timeout=30,
        )
    )
    project_id: int | None = None
    try:
        live_flow = windmill._request("get", "/flows/get/f/devgodzilla/spec_to_protocol").json()
        modules = live_flow["value"]["modules"]
        module_ids = [module["id"] for module in modules]
        assert "create_protocol" not in module_ids, "Imported spec_to_protocol flow is stale; re-import assets"
        assert "protocol_start" in module_ids
        module_by_id = {module["id"]: module for module in modules}
        assert module_by_id["speckit_specify"]["value"]["input_transforms"]["project_id"]["expr"] == "flow_input.project_id"
        assert (
            module_by_id["protocol_start"]["value"]["input_transforms"]["protocol_run_id"]["expr"]
            == "results.speckit_implement.protocol_id"
        )

        with httpx.Client(timeout=180) as api:
            created = api.post(
                f"{host_api_base_url}/projects",
                json={
                    "name": f"windmill-flow-{int(time.time())}",
                    "git_url": repo_url,
                    "base_branch": base_branch,
                    "auto_onboard": False,
                    "auto_discovery": False,
                },
            )
            assert created.status_code == 200, f"project creation failed: {created.text}"
            project = created.json()
            project_id = int(project["id"])

            onboard = api.post(
                f"{host_api_base_url}/projects/{project_id}/actions/onboard",
                json={
                    "branch": base_branch,
                    "clone_if_missing": True,
                    "run_discovery_agent": False,
                    "discovery_pipeline": False,
                },
                timeout=2700,
            )
            assert onboard.status_code == 200, f"project onboarding failed: {onboard.text}"
            onboard_payload = onboard.json()
            assert onboard_payload["success"] is True

            feature_request = (
                "Add a small dashboard health card with explicit verification output and no broader UI redesign."
            )
            job_id = windmill.run_flow(
                "f/devgodzilla/spec_to_protocol",
                {
                    "project_id": project_id,
                    "feature_request": feature_request,
                    "feature_name": "dashboard-health-card",
                    "clarification_entries": [
                        {
                            "question": "Implementation constraint?",
                            "answer": "Keep the scope minimal and include automated verification.",
                        }
                    ],
                    "clarification_notes": "Prefer a tight slice that preserves the current workflows.",
                },
            )
            job = windmill.wait_for_job(job_id, timeout=900, poll_interval=2.0)
            parent = _job_payload(windmill, job_id)

            assert job.status == JobStatus.COMPLETED, f"flow job did not complete: {windmill.get_job_logs(job_id)}"
            assert parent.get("success") is True, f"flow job failed: {parent}"

            flow_modules = parent["flow_status"]["modules"]
            flow_module_ids = [module["id"] for module in flow_modules]
            assert flow_module_ids == [
                "speckit_specify",
                "speckit_clarify",
                "speckit_plan",
                "speckit_checklist",
                "speckit_tasks",
                "speckit_analyze",
                "speckit_implement",
                "protocol_start",
            ]
            assert all(module["type"] == "Success" for module in flow_modules)

            module_jobs = {module["id"]: module["job"] for module in flow_modules}
            specify = _assert_module_job_succeeded(windmill, module_jobs["speckit_specify"], module_id="speckit_specify")
            clarify = _assert_module_job_succeeded(windmill, module_jobs["speckit_clarify"], module_id="speckit_clarify")
            plan = _assert_module_job_succeeded(windmill, module_jobs["speckit_plan"], module_id="speckit_plan")
            checklist = _assert_module_job_succeeded(windmill, module_jobs["speckit_checklist"], module_id="speckit_checklist")
            tasks = _assert_module_job_succeeded(windmill, module_jobs["speckit_tasks"], module_id="speckit_tasks")
            analyze = _assert_module_job_succeeded(windmill, module_jobs["speckit_analyze"], module_id="speckit_analyze")
            implement = _assert_module_job_succeeded(windmill, module_jobs["speckit_implement"], module_id="speckit_implement")
            protocol_start = _assert_module_job_succeeded(windmill, module_jobs["protocol_start"], module_id="protocol_start")

            spec_run_id = int(specify["spec_run_id"])
            worktree_path = str(specify["worktree_path"])
            assert spec_run_id > 0
            assert worktree_path
            assert int(clarify["spec_run_id"]) == spec_run_id
            assert int(plan["spec_run_id"]) == spec_run_id
            assert int(tasks["spec_run_id"]) == spec_run_id
            assert int(checklist["spec_run_id"]) == spec_run_id
            assert int(analyze["spec_run_id"]) == spec_run_id
            assert int(implement["spec_run_id"]) == spec_run_id
            assert str(clarify["worktree_path"]) == worktree_path
            assert str(plan["worktree_path"]) == worktree_path
            assert str(tasks["worktree_path"]) == worktree_path
            assert str(checklist["worktree_path"]) == worktree_path
            assert str(analyze["worktree_path"]) == worktree_path
            assert str(implement["worktree_path"]) == worktree_path

            host_worktree = _host_path_from_runtime(worktree_path)
            host_spec = _host_path_from_runtime(str(specify["spec_path"]))
            host_plan = _host_path_from_runtime(str(plan["plan_path"]))
            host_tasks = _host_path_from_runtime(str(tasks["tasks_path"]))
            host_checklist = _host_path_from_runtime(str(checklist["checklist_path"]))
            host_report = _host_path_from_runtime(str(analyze["report_path"]))
            host_protocol_root = _host_path_from_runtime(str(implement["protocol_root"]))
            host_metadata = _host_path_from_runtime(str(implement["metadata_path"]))

            assert host_worktree.exists()
            assert host_spec.exists()
            assert host_plan.exists()
            assert host_tasks.exists()
            assert host_checklist.exists()
            assert host_report.exists()
            assert host_protocol_root.exists()
            assert host_metadata.exists()

            assert int(tasks["task_count"]) > 0
            assert int(checklist["item_count"]) > 0
            assert int(implement["protocol_id"]) > 0
            assert int(implement["step_count"]) >= 1
            _assert_no_template_markers(
                host_spec,
                markers=[
                    "[Brief Title]",
                    "[Describe this user journey in plain language]",
                    "System MUST [specific capability",
                ],
            )
            _assert_no_template_markers(
                host_plan,
                markers=[
                    "[Extract from feature spec:",
                    "[REMOVE IF UNUSED]",
                    "NEEDS CLARIFICATION",
                ],
            )
            _assert_no_template_markers(
                host_tasks,
                markers=[
                    "IMPORTANT: The tasks below are SAMPLE TASKS",
                    "Initialize [language] project with [framework] dependencies",
                    "Contract test for [endpoint]",
                ],
            )
            assert "(To be generated)" not in host_report.read_text(encoding="utf-8")
            assert "Implementation constraint?" in host_spec.read_text(encoding="utf-8")
            assert protocol_start.get("protocol", {}).get("id") == int(implement["protocol_id"])
    finally:
        try:
            if project_id is not None:
                httpx.delete(f"{host_api_base_url}/projects/{project_id}", timeout=60)
        finally:
            windmill.close()


def test_live_windmill_brownfield_tasks_to_sprint() -> None:
    if not _flag("DEVGODZILLA_RUN_LIVE_WINDMILL_TESTS"):
        pytest.skip("set DEVGODZILLA_RUN_LIVE_WINDMILL_TESTS=1 to enable live integration test")

    host_api_base_url = os.environ.get("DEVGODZILLA_LIVE_HOST_API_URL", "http://localhost:8000").rstrip("/")
    repo_url = os.environ.get(
        "DEVGODZILLA_LIVE_WINDMILL_REPO_URL",
        "https://github.com/ilyafedotov-ops/test-glm5-demo.git",
    ).strip()
    base_branch = (os.environ.get("DEVGODZILLA_LIVE_WINDMILL_REPO_BRANCH") or "main").strip()
    config = load_config()

    assert config.windmill_url
    assert config.windmill_token
    assert config.windmill_workspace

    _ensure_host_backend_ready()
    _run_local_windmill_import()

    windmill = WindmillClient(
        WindmillConfig(
            base_url=config.windmill_url,
            token=config.windmill_token,
            workspace=config.windmill_workspace,
            timeout=30,
        )
    )
    project_id: int | None = None
    try:
        with httpx.Client(timeout=180) as api:
            project_id = _create_live_project(
                api,
                host_api_base_url=host_api_base_url,
                repo_url=repo_url,
                base_branch=base_branch,
                name_prefix="windmill-brownfield-tasks",
            )
            sprint_id = _create_live_sprint(
                api,
                host_api_base_url=host_api_base_url,
                project_id=project_id,
                name="Brownfield Tasks Sprint",
            )

            job_id = windmill.run_flow(
                "f/devgodzilla/brownfield_feature",
                {
                    "project_id": project_id,
                    "branch": base_branch,
                    "feature_request": "Add a compact admin health card and capture the work as sprint tasks only.",
                    "feature_name": "admin-health-card",
                    "output_mode": "tasks_to_sprint",
                    "sprint_id": sprint_id,
                    "overwrite_existing_tasks": True,
                    "run_checklist": False,
                    "run_analysis": False,
                    "run_discovery_agent": False,
                    "discovery_pipeline": False,
                },
            )
            job = windmill.wait_for_job(job_id, timeout=1200, poll_interval=2.0)
            parent = _job_payload(windmill, job_id)

            assert job.status == JobStatus.COMPLETED, f"flow job did not complete: {windmill.get_job_logs(job_id)}"
            assert parent.get("success") is True, f"flow job failed: {parent}"

            module_jobs = _collect_module_jobs(windmill, parent["flow_status"]["modules"])
            for module_id in ["onboard_project", "speckit_specify", "speckit_plan", "speckit_tasks", "sync_tasks"]:
                assert module_id in module_jobs, f"missing executed module {module_id}: {sorted(module_jobs)}"

            specify = _assert_module_job_succeeded(windmill, module_jobs["speckit_specify"], module_id="speckit_specify")
            plan = _assert_module_job_succeeded(windmill, module_jobs["speckit_plan"], module_id="speckit_plan")
            tasks = _assert_module_job_succeeded(windmill, module_jobs["speckit_tasks"], module_id="speckit_tasks")
            sync_tasks = _assert_module_job_succeeded(windmill, module_jobs["sync_tasks"], module_id="sync_tasks")

            host_spec = _host_path_from_runtime(str(specify["spec_path"]))
            host_plan = _host_path_from_runtime(str(plan["plan_path"]))
            host_tasks = _host_path_from_runtime(str(tasks["tasks_path"]))

            assert host_spec.exists()
            assert host_plan.exists()
            assert host_tasks.exists()
            assert int(tasks["task_count"]) > 0
            assert int(sync_tasks["sprint_id"]) == sprint_id
            assert int(sync_tasks["tasks_synced"]) > 0

            sprint_tasks = api.get(f"{host_api_base_url}/sprints/{sprint_id}/tasks")
            assert sprint_tasks.status_code == 200, f"failed to fetch sprint tasks: {sprint_tasks.text}"
            payload = sprint_tasks.json()
            assert len(payload) == int(sync_tasks["tasks_synced"])
            assert all("speckit" in (task.get("labels") or []) for task in payload)
    finally:
        try:
            if project_id is not None:
                httpx.delete(f"{host_api_base_url}/projects/{project_id}", timeout=60)
        finally:
            windmill.close()


def test_live_windmill_brownfield_protocol_to_sprint() -> None:
    if not _flag("DEVGODZILLA_RUN_LIVE_WINDMILL_TESTS"):
        pytest.skip("set DEVGODZILLA_RUN_LIVE_WINDMILL_TESTS=1 to enable live integration test")

    host_api_base_url = os.environ.get("DEVGODZILLA_LIVE_HOST_API_URL", "http://localhost:8000").rstrip("/")
    repo_url = os.environ.get(
        "DEVGODZILLA_LIVE_WINDMILL_REPO_URL",
        "https://github.com/ilyafedotov-ops/test-glm5-demo.git",
    ).strip()
    base_branch = (os.environ.get("DEVGODZILLA_LIVE_WINDMILL_REPO_BRANCH") or "main").strip()
    config = load_config()

    assert config.windmill_url
    assert config.windmill_token
    assert config.windmill_workspace

    _ensure_host_backend_ready()
    _run_local_windmill_import()

    windmill = WindmillClient(
        WindmillConfig(
            base_url=config.windmill_url,
            token=config.windmill_token,
            workspace=config.windmill_workspace,
            timeout=30,
        )
    )
    project_id: int | None = None
    try:
        with httpx.Client(timeout=180) as api:
            project_id = _create_live_project(
                api,
                host_api_base_url=host_api_base_url,
                repo_url=repo_url,
                base_branch=base_branch,
                name_prefix="windmill-brownfield-protocol",
            )

            job_id = windmill.run_flow(
                "f/devgodzilla/brownfield_feature",
                {
                    "project_id": project_id,
                    "branch": base_branch,
                    "feature_request": "Add a compact dashboard health card and create a sprint from the resulting protocol.",
                    "feature_name": "dashboard-health-card-sprint",
                    "output_mode": "protocol_to_sprint",
                    "sprint_name": "Protocol Delivery Sprint",
                    "auto_sync_sprint": True,
                    "run_checklist": False,
                    "run_analysis": False,
                    "run_discovery_agent": False,
                    "discovery_pipeline": False,
                },
            )
            job = windmill.wait_for_job(job_id, timeout=1200, poll_interval=2.0)
            parent = _job_payload(windmill, job_id)

            assert job.status == JobStatus.COMPLETED, f"flow job did not complete: {windmill.get_job_logs(job_id)}"
            assert parent.get("success") is True, f"flow job failed: {parent}"

            module_jobs = _collect_module_jobs(windmill, parent["flow_status"]["modules"])
            for module_id in [
                "onboard_project",
                "speckit_specify",
                "speckit_plan",
                "speckit_tasks",
                "create_protocol",
                "protocol_start",
                "create_sprint",
            ]:
                assert module_id in module_jobs, f"missing executed module {module_id}: {sorted(module_jobs)}"

            create_protocol = _assert_module_job_succeeded(windmill, module_jobs["create_protocol"], module_id="create_protocol")
            protocol_start = _assert_module_job_succeeded(windmill, module_jobs["protocol_start"], module_id="protocol_start")
            create_sprint = _assert_module_job_succeeded(windmill, module_jobs["create_sprint"], module_id="create_sprint")

            protocol_id = int(create_protocol["protocol"]["id"])
            sprint_id = int(create_sprint["id"])
            assert protocol_start.get("protocol", {}).get("id") == protocol_id

            sprint_payload = api.get(f"{host_api_base_url}/sprints/{sprint_id}")
            assert sprint_payload.status_code == 200, f"failed to fetch created sprint: {sprint_payload.text}"
            sprint = sprint_payload.json()
            assert int(sprint["project_id"]) == project_id
            assert sprint["name"] == "Protocol Delivery Sprint"

            linked = api.get(f"{host_api_base_url}/protocols/{protocol_id}/sprint")
            assert linked.status_code == 200, f"failed to fetch linked sprint: {linked.text}"
            linked_payload = linked.json()
            assert linked_payload is not None
            assert int(linked_payload["id"]) == sprint_id

            sprint_tasks = api.get(f"{host_api_base_url}/sprints/{sprint_id}/tasks")
            assert sprint_tasks.status_code == 200, f"failed to fetch sprint tasks: {sprint_tasks.text}"
            tasks_payload = sprint_tasks.json()
            assert len(tasks_payload) >= 1
            assert all(int(task["protocol_run_id"]) == protocol_id for task in tasks_payload if task.get("protocol_run_id"))
    finally:
        try:
            if project_id is not None:
                httpx.delete(f"{host_api_base_url}/projects/{project_id}", timeout=60)
        finally:
            windmill.close()


def test_live_windmill_brownfield_task_cycle() -> None:
    if not _flag("DEVGODZILLA_RUN_LIVE_WINDMILL_TESTS"):
        pytest.skip("set DEVGODZILLA_RUN_LIVE_WINDMILL_TESTS=1 to enable live integration test")

    host_api_base_url = os.environ.get("DEVGODZILLA_LIVE_HOST_API_URL", "http://localhost:8000").rstrip("/")
    repo_url = os.environ.get(
        "DEVGODZILLA_LIVE_WINDMILL_REPO_URL",
        "https://github.com/ilyafedotov-ops/test-glm5-demo.git",
    ).strip()
    base_branch = (os.environ.get("DEVGODZILLA_LIVE_WINDMILL_REPO_BRANCH") or "main").strip()
    config = load_config()

    assert config.windmill_url
    assert config.windmill_token
    assert config.windmill_workspace

    _ensure_host_backend_ready()
    _run_local_windmill_import()

    windmill = WindmillClient(
        WindmillConfig(
            base_url=config.windmill_url,
            token=config.windmill_token,
            workspace=config.windmill_workspace,
            timeout=30,
        )
    )
    project_id: int | None = None
    try:
        with httpx.Client(timeout=180) as api:
            project_id = _create_live_project(
                api,
                host_api_base_url=host_api_base_url,
                repo_url=repo_url,
                base_branch=base_branch,
                name_prefix="windmill-brownfield-task-cycle",
            )

            job_id = windmill.run_flow(
                "f/devgodzilla/brownfield_feature",
                {
                    "project_id": project_id,
                    "branch": base_branch,
                    "feature_request": "Add a compact dashboard health card and expose the work as task-cycle items.",
                    "feature_name": "dashboard-health-card-cycle",
                    "output_mode": "task_cycle",
                    "protocol_name": "Dashboard Health Task Cycle",
                    "run_checklist": False,
                    "run_analysis": False,
                    "run_discovery_agent": False,
                    "discovery_pipeline": False,
                },
            )
            job = windmill.wait_for_job(job_id, timeout=1200, poll_interval=2.0)
            parent = _job_payload(windmill, job_id)

            assert job.status == JobStatus.COMPLETED, f"flow job did not complete: {windmill.get_job_logs(job_id)}"
            assert parent.get("success") is True, f"flow job failed: {parent}"

            module_jobs = _collect_module_jobs(windmill, parent["flow_status"]["modules"])
            for module_id in [
                "onboard_project",
                "speckit_specify",
                "speckit_plan",
                "speckit_tasks",
                "create_protocol",
                "protocol_start",
                "get_task_cycle",
            ]:
                assert module_id in module_jobs, f"missing executed module {module_id}: {sorted(module_jobs)}"

            create_protocol = _assert_module_job_succeeded(windmill, module_jobs["create_protocol"], module_id="create_protocol")
            protocol_start = _assert_module_job_succeeded(windmill, module_jobs["protocol_start"], module_id="protocol_start")
            get_task_cycle = _assert_module_job_succeeded(windmill, module_jobs["get_task_cycle"], module_id="get_task_cycle")

            protocol_id = int(create_protocol["protocol"]["id"])
            assert protocol_start.get("protocol", {}).get("id") == protocol_id
            assert int(get_task_cycle["count"]) >= 1
            assert int(get_task_cycle["next_work_item_id"]) >= 1

            work_items = get_task_cycle.get("work_items")
            assert isinstance(work_items, list)
            assert len(work_items) == int(get_task_cycle["count"])
            assert all(int(item["protocol_run_id"]) == protocol_id for item in work_items)
            assert all(int(item["project_id"]) == project_id for item in work_items)
            assert any(str(item["status"]) in {"queued", "context_ready", "in_progress", "awaiting_review", "needs_rework", "ready_for_pr", "pr_ready"} for item in work_items)

            api_items = api.get(f"{host_api_base_url}/projects/{project_id}/task-cycle", params={"protocol_run_id": protocol_id})
            assert api_items.status_code == 200, f"failed to fetch task-cycle items: {api_items.text}"
            api_payload = api_items.json()
            assert len(api_payload) == len(work_items)
            assert sorted(int(item["id"]) for item in api_payload) == sorted(int(item["id"]) for item in work_items)
    finally:
        try:
            if project_id is not None:
                httpx.delete(f"{host_api_base_url}/projects/{project_id}", timeout=60)
        finally:
            windmill.close()


def test_live_task_cycle_work_item_lifecycle() -> None:
    if not _flag("DEVGODZILLA_RUN_LIVE_WINDMILL_TESTS"):
        pytest.skip("set DEVGODZILLA_RUN_LIVE_WINDMILL_TESTS=1 to enable live integration test")

    host_api_base_url = os.environ.get("DEVGODZILLA_LIVE_HOST_API_URL", "http://localhost:8000").rstrip("/")
    repo_url = os.environ.get(
        "DEVGODZILLA_LIVE_WINDMILL_REPO_URL",
        "https://github.com/ilyafedotov-ops/test-glm5-demo.git",
    ).strip()
    base_branch = (os.environ.get("DEVGODZILLA_LIVE_WINDMILL_REPO_BRANCH") or "main").strip()
    config = load_config()

    assert config.windmill_url
    assert config.windmill_token
    assert config.windmill_workspace

    _ensure_host_backend_ready()
    _run_local_windmill_import()

    windmill = WindmillClient(
        WindmillConfig(
            base_url=config.windmill_url,
            token=config.windmill_token,
            workspace=config.windmill_workspace,
            timeout=30,
        )
    )
    project_id: int | None = None
    try:
        with httpx.Client(timeout=600) as api:
            project_id = _create_live_project(
                api,
                host_api_base_url=host_api_base_url,
                repo_url=repo_url,
                base_branch=base_branch,
                name_prefix="windmill-task-cycle-lifecycle",
            )

            job_id = windmill.run_flow(
                "f/devgodzilla/brownfield_feature",
                {
                    "project_id": project_id,
                    "branch": base_branch,
                    "feature_request": "Add a small dashboard health card with explicit verification output and no broader UI redesign.",
                    "feature_name": "dashboard-health-card-lifecycle",
                    "output_mode": "task_cycle",
                    "protocol_name": "Dashboard Health Lifecycle",
                    "run_checklist": False,
                    "run_analysis": False,
                    "run_discovery_agent": False,
                    "discovery_pipeline": False,
                },
            )
            job = windmill.wait_for_job(job_id, timeout=1200, poll_interval=2.0)
            parent = _job_payload(windmill, job_id)

            assert job.status == JobStatus.COMPLETED, f"flow job did not complete: {windmill.get_job_logs(job_id)}"
            assert parent.get("success") is True, f"flow job failed: {parent}"

            module_jobs = _collect_module_jobs(windmill, parent["flow_status"]["modules"])
            get_task_cycle = _assert_module_job_succeeded(windmill, module_jobs["get_task_cycle"], module_id="get_task_cycle")
            work_items = get_task_cycle.get("work_items")
            assert isinstance(work_items, list) and work_items, f"task_cycle did not produce work items: {get_task_cycle}"

            selected_item = next(
                (item for item in work_items if "implementation" in str(item.get("title", "")).lower()),
                None,
            ) or next(
                (item for item in work_items if "user-story" in str(item.get("title", "")).lower()),
                None,
            ) or work_items[0]

            work_item_id = int(selected_item["id"])
            protocol_id = int(selected_item["protocol_run_id"])

            context_resp = api.post(
                f"{host_api_base_url}/work-items/{work_item_id}/build-context",
                json={"refresh": False},
                timeout=300,
            )
            assert context_resp.status_code == 200, f"build-context failed: {context_resp.text}"
            context_item = context_resp.json()
            assert context_item["id"] == work_item_id
            context_path = Path(context_item["artifact_refs"]["context_pack_json"])
            assert context_path.exists()

            implement_resp = api.post(
                f"{host_api_base_url}/work-items/{work_item_id}/actions/implement",
                json={"owner_agent": "opencode"},
                timeout=2700,
            )
            assert implement_resp.status_code == 200, f"implement failed: {implement_resp.text}"
            implement_item = implement_resp.json()
            assert implement_item["id"] == work_item_id
            assert implement_item["iteration_count"] >= 1
            assert implement_item["status"] in {"awaiting_review", "ready_for_pr", "needs_rework"}

            review_resp = api.post(
                f"{host_api_base_url}/work-items/{work_item_id}/actions/review",
                timeout=300,
            )
            assert review_resp.status_code == 200, f"review failed: {review_resp.text}"
            review_payload = review_resp.json()
            assert review_payload["verdict"] == "passed", f"review did not pass: {review_payload}"

            qa_resp = api.post(
                f"{host_api_base_url}/work-items/{work_item_id}/actions/qa",
                json={"gates": ["test"]},
                timeout=1800,
            )
            assert qa_resp.status_code == 200, f"qa failed: {qa_resp.text}"
            qa_payload = qa_resp.json()
            assert qa_payload["qa"]["verdict"] in {"passed", "failed"}, f"unexpected qa verdict: {qa_payload}"

            artifact_checks = {
                "context_pack_json": '"work_item_id"',
                "review_report_json": '"verdict": "passed"',
            }
            for artifact_key, needle in artifact_checks.items():
                artifact_resp = api.get(
                    f"{host_api_base_url}/work-items/{work_item_id}/artifacts/{artifact_key}/content",
                    timeout=300,
                )
                assert artifact_resp.status_code == 200, f"artifact read failed for {artifact_key}: {artifact_resp.text}"
                assert needle in artifact_resp.json()["content"]

            test_report_resp = api.get(
                f"{host_api_base_url}/work-items/{work_item_id}/artifacts/test_report_json/content",
                timeout=300,
            )
            assert test_report_resp.status_code == 200, f"artifact read failed for test_report_json: {test_report_resp.text}"
            test_report_content = test_report_resp.json()["content"]
            assert '"verdict":' in test_report_content

            if qa_payload["qa"]["verdict"] == "passed":
                assert '"verdict": "passed"' in test_report_content
                pr_ready_resp = api.post(
                    f"{host_api_base_url}/work-items/{work_item_id}/actions/mark-pr-ready",
                    timeout=300,
                )
                assert pr_ready_resp.status_code == 200, f"mark-pr-ready failed: {pr_ready_resp.text}"
                pr_ready = pr_ready_resp.json()
                assert pr_ready["status"] == "pr_ready"
                assert pr_ready["pr_ready"] is True
                expected_status = "pr_ready"
                expected_pr_ready = True
            else:
                findings = qa_payload["qa"]["gates"][0]["findings"]
                assert findings, f"qa failed without findings: {qa_payload}"
                assert any("exit code" in str(item.get("message", "")) or "FAILED" in str(item.get("message", "")) for item in findings)
                expected_status = "needs_rework"
                expected_pr_ready = False

            list_resp = api.get(
                f"{host_api_base_url}/projects/{project_id}/task-cycle",
                params={"protocol_run_id": protocol_id},
                timeout=300,
            )
            assert list_resp.status_code == 200, f"task-cycle listing failed: {list_resp.text}"
            listed = list_resp.json()
            current = next(item for item in listed if int(item["id"]) == work_item_id)
            assert current["status"] == expected_status
            assert current["pr_ready"] is expected_pr_ready
    finally:
        try:
            if project_id is not None:
                httpx.delete(f"{host_api_base_url}/projects/{project_id}", timeout=60)
        finally:
            windmill.close()


def test_live_windmill_task_cycle_helper_sidecars() -> None:
    if not _flag("DEVGODZILLA_RUN_LIVE_WINDMILL_TESTS"):
        pytest.skip("set DEVGODZILLA_RUN_LIVE_WINDMILL_TESTS=1 to enable live integration test")

    public_base_url = os.environ.get("DEVGODZILLA_LIVE_BASE_URL", "http://localhost:8080").rstrip("/")
    host_api_base_url = os.environ.get("DEVGODZILLA_LIVE_HOST_API_URL", "http://localhost:8000").rstrip("/")
    repo_url = os.environ.get(
        "DEVGODZILLA_LIVE_WINDMILL_REPO_URL",
        "https://github.com/ilyafedotov-ops/test-glm5-demo.git",
    ).strip()
    base_branch = (os.environ.get("DEVGODZILLA_LIVE_WINDMILL_REPO_BRANCH") or "main").strip()
    owner_agent = (os.environ.get("DEVGODZILLA_LIVE_TASK_CYCLE_OWNER_AGENT") or "").strip() or None
    helper_agents = [
        item.strip()
        for item in (os.environ.get("DEVGODZILLA_LIVE_TASK_CYCLE_HELPER_AGENTS") or "trace,tests").split(",")
        if item.strip()
    ]
    config = load_config()

    assert config.windmill_url, "DEVGODZILLA_WINDMILL_URL must be set"
    assert config.windmill_token, "DEVGODZILLA_WINDMILL_TOKEN must be set"
    assert config.windmill_workspace, "DEVGODZILLA_WINDMILL_WORKSPACE must be set"

    _ensure_host_backend_ready()
    _run_local_windmill_import()

    ready = httpx.get(f"{public_base_url}/health/ready", timeout=10)
    assert ready.status_code == 200, f"stack not ready at {public_base_url}/health/ready: {ready.text}"

    windmill = WindmillClient(
        WindmillConfig(
            base_url=config.windmill_url,
            token=config.windmill_token,
            workspace=config.windmill_workspace,
            timeout=30,
        )
    )
    project_id: int | None = None
    try:
        with httpx.Client(timeout=180) as api:
            project_id = _create_live_project(
                api,
                host_api_base_url=host_api_base_url,
                repo_url=repo_url,
                base_branch=base_branch,
                name_prefix="windmill-task-cycle-helpers",
            )

            job_id = windmill.run_flow_by_path(
                "f/devgodzilla/brownfield_feature",
                {
                    "project_id": project_id,
                    "feature_name": "helper-sidecar-audit",
                    "feature_request": (
                        "Add a small brownfield task-cycle change and keep helper-sidecar execution enabled "
                        "so the owner can consume helper findings."
                    ),
                    "output_mode": "task_cycle",
                    "branch": base_branch,
                    "protocol_timeout_seconds": 300,
                    "owner_agent": owner_agent or "",
                    "helper_agents": helper_agents,
                    "allow_helper_agents": True,
                },
            )
            job = windmill.wait_for_job(job_id, timeout=1200, poll_interval=2.0)
            parent = _job_payload(windmill, job_id)

            assert job.status == JobStatus.COMPLETED, f"flow job did not complete: {windmill.get_job_logs(job_id)}"
            assert parent.get("success") is True, f"flow job failed: {parent}"

            module_jobs = _collect_module_jobs(windmill, parent["flow_status"]["modules"])
            get_task_cycle = _assert_module_job_succeeded(windmill, module_jobs["get_task_cycle"], module_id="get_task_cycle")
            work_items = get_task_cycle.get("work_items")
            assert isinstance(work_items, list) and work_items, f"task_cycle did not produce work items: {get_task_cycle}"

            selected_item = work_items[0]
            work_item_id = int(selected_item["id"])
            protocol_id = int(selected_item["protocol_run_id"])
            assert selected_item["helper_agents"] == helper_agents
            assert "helpers configured under the owner" in str(selected_item.get("helper_agent_summary") or "")

            steps_before = api.get(f"{host_api_base_url}/protocols/{protocol_id}/steps", timeout=300)
            assert steps_before.status_code == 200, f"protocol step listing failed: {steps_before.text}"
            before_payload = steps_before.json()
            before_count = len(before_payload)

            context_resp = api.post(
                f"{host_api_base_url}/work-items/{work_item_id}/build-context",
                json={"refresh": False},
                timeout=300,
            )
            assert context_resp.status_code == 200, f"build-context failed: {context_resp.text}"

            implement_body: dict[str, Any] = {}
            if owner_agent:
                implement_body["owner_agent"] = owner_agent
            implement_resp = api.post(
                f"{host_api_base_url}/work-items/{work_item_id}/actions/implement",
                json=implement_body,
                timeout=2700,
            )
            assert implement_resp.status_code == 200, f"implement failed: {implement_resp.text}"
            implement_item = implement_resp.json()
            assert implement_item["id"] == work_item_id
            assert implement_item["helper_agents"] == helper_agents
            assert "helpers under the owner" in str(implement_item.get("helper_agent_summary") or "")

            task_dir = Path(str(implement_item["task_dir"]))
            helper_summary = task_dir / "helpers" / "helper_summary.json"
            assert helper_summary.exists(), f"missing helper summary artifact: {helper_summary}"
            helper_payload = json.loads(helper_summary.read_text(encoding="utf-8"))
            helpers = helper_payload.get("helpers")
            assert isinstance(helpers, list) and len(helpers) == len(helper_agents)
            assert {item["helper_agent"] for item in helpers} == set(helper_agents)

            steps_after = api.get(f"{host_api_base_url}/protocols/{protocol_id}/steps", timeout=300)
            assert steps_after.status_code == 200, f"protocol step listing failed after implement: {steps_after.text}"
            after_payload = steps_after.json()
            assert len(after_payload) == before_count, "helper sidecars must not create first-class workflow lanes"

            list_resp = api.get(
                f"{host_api_base_url}/projects/{project_id}/task-cycle",
                params={"protocol_run_id": protocol_id},
                timeout=300,
            )
            assert list_resp.status_code == 200, f"task-cycle listing failed: {list_resp.text}"
            current = next(item for item in list_resp.json() if int(item["id"]) == work_item_id)
            assert current["helper_agents"] == helper_agents
            assert "helpers under the owner" in str(current.get("helper_agent_summary") or "")
    finally:
        try:
            if project_id is not None:
                httpx.delete(f"{host_api_base_url}/projects/{project_id}", timeout=60)
        finally:
            windmill.close()
