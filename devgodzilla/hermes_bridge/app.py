from __future__ import annotations

from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException

from devgodzilla.hermes_bridge.client import DevGodzillaBridgeError, DevGodzillaClient
from devgodzilla.hermes_bridge.config import BridgeConfig, load_bridge_config
from devgodzilla.hermes_bridge.models import SubmitFeedbackRequest, ToolErrorBody, ToolErrorEnvelope, ToolPayload, ToolResult
from devgodzilla.hermes_bridge.service import HermesBridgeService

app = FastAPI(
    title="Hermes DevGodzilla Bridge",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)


def get_config() -> BridgeConfig:
    return load_bridge_config()


def require_bridge_token(
    config: Annotated[BridgeConfig, Depends(get_config)],
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
    x_bridge_token: Annotated[str | None, Header(alias="X-Hermes-Bridge-Token")] = None,
) -> None:
    expected = config.hermes_bridge_token
    if not expected:
        return
    if x_bridge_token == expected:
        return
    if authorization:
        parts = authorization.strip().split(None, 1)
        if len(parts) == 2 and parts[0].lower() == "bearer" and parts[1] == expected:
            return
    raise HTTPException(status_code=401, detail="Unauthorized")


def get_service(config: Annotated[BridgeConfig, Depends(get_config)]) -> HermesBridgeService:
    return HermesBridgeService(DevGodzillaClient(config))


def _run_tool(tool: str, action):
    try:
        return ToolResult(tool=tool, data=action())
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=ToolErrorEnvelope(tool=tool, error=ToolErrorBody(code="VALIDATION_ERROR", message=str(exc))).model_dump(),
        ) from exc
    except DevGodzillaBridgeError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail=ToolErrorEnvelope(
                tool=tool,
                error=ToolErrorBody(code="UPSTREAM_ERROR", message=str(exc), details=exc.details, retryable=exc.status_code >= 500),
            ).model_dump(),
        ) from exc


@app.get("/health", dependencies=[Depends(require_bridge_token)], response_model=ToolResult)
def health(service: Annotated[HermesBridgeService, Depends(get_service)]):
    return _run_tool("health", service.health)


@app.get("/tools/projects", dependencies=[Depends(require_bridge_token)], response_model=ToolResult)
def list_projects(service: Annotated[HermesBridgeService, Depends(get_service)]):
    return _run_tool("list_projects", service.list_projects)


@app.post("/tools/projects", dependencies=[Depends(require_bridge_token)], response_model=ToolResult)
def create_project(payload: ToolPayload, service: Annotated[HermesBridgeService, Depends(get_service)]):
    return _run_tool("create_project", lambda: service.create_project(payload.data))


@app.post("/tools/projects/{project_id}/onboard", dependencies=[Depends(require_bridge_token)], response_model=ToolResult)
def onboard_project(project_id: int, payload: ToolPayload, service: Annotated[HermesBridgeService, Depends(get_service)]):
    return _run_tool("onboard_project", lambda: service.onboard_project(project_id, payload.data))


@app.post("/tools/specs/create", dependencies=[Depends(require_bridge_token)], response_model=ToolResult)
def create_spec(payload: ToolPayload, service: Annotated[HermesBridgeService, Depends(get_service)]):
    return _run_tool("create_spec", lambda: service.create_spec(payload.data))


@app.post("/tools/specs/plan", dependencies=[Depends(require_bridge_token)], response_model=ToolResult)
def plan_spec(payload: ToolPayload, service: Annotated[HermesBridgeService, Depends(get_service)]):
    return _run_tool("plan_spec", lambda: service.plan_spec(payload.data))


@app.post("/tools/specs/tasks", dependencies=[Depends(require_bridge_token)], response_model=ToolResult)
def generate_tasks(payload: ToolPayload, service: Annotated[HermesBridgeService, Depends(get_service)]):
    return _run_tool("generate_tasks", lambda: service.generate_tasks(payload.data))


@app.get("/tools/specs/{spec_run_id}", dependencies=[Depends(require_bridge_token)], response_model=ToolResult)
def get_spec(spec_run_id: int, service: Annotated[HermesBridgeService, Depends(get_service)]):
    return _run_tool("get_spec", lambda: service.get_spec(spec_run_id))


@app.get("/tools/specs/{spec_run_id}/content", dependencies=[Depends(require_bridge_token)], response_model=ToolResult)
def get_spec_content(spec_run_id: int, service: Annotated[HermesBridgeService, Depends(get_service)]):
    return _run_tool("get_spec_content", lambda: service.get_spec_content(spec_run_id))


@app.post("/tools/protocols", dependencies=[Depends(require_bridge_token)], response_model=ToolResult)
def create_protocol(payload: ToolPayload, service: Annotated[HermesBridgeService, Depends(get_service)]):
    return _run_tool("create_protocol", lambda: service.create_protocol(payload.data))


@app.post("/tools/protocols/{protocol_id}/plan", dependencies=[Depends(require_bridge_token)], response_model=ToolResult)
def plan_protocol(protocol_id: int, service: Annotated[HermesBridgeService, Depends(get_service)]):
    return _run_tool("plan_protocol", lambda: service.plan_protocol(protocol_id))


@app.get("/tools/protocols/{protocol_id}", dependencies=[Depends(require_bridge_token)], response_model=ToolResult)
def get_protocol_status(protocol_id: int, service: Annotated[HermesBridgeService, Depends(get_service)]):
    return _run_tool("get_protocol_status", lambda: service.get_protocol_status(protocol_id))


@app.get("/tools/protocols/{protocol_id}/steps", dependencies=[Depends(require_bridge_token)], response_model=ToolResult)
def list_steps(protocol_id: int, service: Annotated[HermesBridgeService, Depends(get_service)]):
    return _run_tool("list_steps", lambda: service.list_steps(protocol_id))


@app.get("/tools/protocols/{protocol_id}/artifacts", dependencies=[Depends(require_bridge_token)], response_model=ToolResult)
def get_protocol_artifacts(protocol_id: int, service: Annotated[HermesBridgeService, Depends(get_service)]):
    return _run_tool("get_protocol_artifacts", lambda: service.get_protocol_artifacts(protocol_id))


@app.get("/tools/protocols/{protocol_id}/policy", dependencies=[Depends(require_bridge_token)], response_model=ToolResult)
def get_protocol_policy(protocol_id: int, service: Annotated[HermesBridgeService, Depends(get_service)]):
    return _run_tool("get_protocol_policy", lambda: service.get_protocol_policy_findings(protocol_id))


@app.post("/tools/protocols/{protocol_id}/run-next-step", dependencies=[Depends(require_bridge_token)], response_model=ToolResult)
def run_next_step(protocol_id: int, service: Annotated[HermesBridgeService, Depends(get_service)]):
    return _run_tool("run_next_step", lambda: service.run_next_step(protocol_id))


@app.post("/tools/steps/{step_id}/execute-with-qa", dependencies=[Depends(require_bridge_token)], response_model=ToolResult)
def execute_step_with_qa(step_id: int, service: Annotated[HermesBridgeService, Depends(get_service)]):
    return _run_tool("execute_step_with_qa", lambda: service.execute_step_with_qa(step_id))


@app.get("/tools/steps/{step_id}/quality", dependencies=[Depends(require_bridge_token)], response_model=ToolResult)
def get_step_quality(step_id: int, service: Annotated[HermesBridgeService, Depends(get_service)]):
    return _run_tool("get_step_quality", lambda: service.get_step_quality(step_id))


@app.get("/tools/steps/{step_id}/artifacts", dependencies=[Depends(require_bridge_token)], response_model=ToolResult)
def get_step_artifacts(step_id: int, service: Annotated[HermesBridgeService, Depends(get_service)]):
    return _run_tool("get_step_artifacts", lambda: service.get_step_artifacts(step_id))


@app.post("/tools/projects/{project_id}/brownfield-run", dependencies=[Depends(require_bridge_token)], response_model=ToolResult)
def start_brownfield_run(project_id: int, payload: ToolPayload, service: Annotated[HermesBridgeService, Depends(get_service)]):
    return _run_tool("start_brownfield_run", lambda: service.start_brownfield_run(project_id, payload.data))


@app.get("/tools/projects/{project_id}/task-cycle", dependencies=[Depends(require_bridge_token)], response_model=ToolResult)
def list_task_cycle_work_items(project_id: int, service: Annotated[HermesBridgeService, Depends(get_service)]):
    return _run_tool("list_task_cycle_work_items", lambda: service.list_task_cycle_work_items(project_id))


@app.get("/tools/work-items/{work_item_id}", dependencies=[Depends(require_bridge_token)], response_model=ToolResult)
def get_work_item(work_item_id: int, service: Annotated[HermesBridgeService, Depends(get_service)]):
    return _run_tool("get_work_item", lambda: service.get_work_item(work_item_id))


@app.post("/tools/work-items/{work_item_id}/build-context", dependencies=[Depends(require_bridge_token)], response_model=ToolResult)
def build_work_item_context(work_item_id: int, payload: ToolPayload, service: Annotated[HermesBridgeService, Depends(get_service)]):
    return _run_tool("build_work_item_context", lambda: service.build_work_item_context(work_item_id, payload.data))


@app.post("/tools/work-items/{work_item_id}/implement", dependencies=[Depends(require_bridge_token)], response_model=ToolResult)
def implement_work_item(work_item_id: int, payload: ToolPayload, service: Annotated[HermesBridgeService, Depends(get_service)]):
    return _run_tool("implement_work_item", lambda: service.implement_work_item(work_item_id, payload.data))


@app.post("/tools/work-items/{work_item_id}/review", dependencies=[Depends(require_bridge_token)], response_model=ToolResult)
def review_work_item(work_item_id: int, service: Annotated[HermesBridgeService, Depends(get_service)]):
    return _run_tool("review_work_item", lambda: service.review_work_item(work_item_id))


@app.post("/tools/work-items/{work_item_id}/qa", dependencies=[Depends(require_bridge_token)], response_model=ToolResult)
def qa_work_item(work_item_id: int, payload: ToolPayload, service: Annotated[HermesBridgeService, Depends(get_service)]):
    return _run_tool("qa_work_item", lambda: service.qa_work_item(work_item_id, payload.data))


@app.post("/tools/protocols/{protocol_id}/feedback", dependencies=[Depends(require_bridge_token)], response_model=ToolResult)
def submit_feedback(
    protocol_id: int,
    request: SubmitFeedbackRequest,
    service: Annotated[HermesBridgeService, Depends(get_service)],
):
    return _run_tool("submit_feedback", lambda: service.submit_feedback(protocol_id, request))


@app.post("/tools/protocols/{protocol_id}/open-pr", dependencies=[Depends(require_bridge_token)], response_model=ToolResult)
def open_pull_request(protocol_id: int, payload: ToolPayload, service: Annotated[HermesBridgeService, Depends(get_service)]):
    return _run_tool("open_pull_request", lambda: service.open_pull_request(protocol_id, payload.data))
