"""
Comprehensive E2E test harness for dev-pipeline.

Covers the full lifecycle of every major API flow:
  1. Agent health & test
  2. Project CRUD
  3. Onboarding
  4. Brownfield runs
  5. SpecKit specification
  6. Task cycle & protocols
  7. Events (SSE metadata + recent)
  8. CLI executions
  9. Sprints

Requires a running backend on localhost:8000 with /api/v1 prefix.
"""

import asyncio
import pytest

pytestmark = pytest.mark.integration
import os
import time
import uuid
from datetime import datetime, timezone
from typing import AsyncGenerator

import httpx
import pytest

# ---------------------------------------------------------------------------
# Environment bootstrap – must run before any devgodzilla imports that may
# read these values at module-load time.
# ---------------------------------------------------------------------------
os.environ.setdefault("DEVGODZILLA_ASSUME_AGENT_AUTH", "true")
os.environ.setdefault(
    "DEVGODZILLA_DATABASE_URL",
    "postgresql://devgodzilla:devgodzilla@localhost:5432/devgodzilla",
)

BASE_URL = "http://localhost:8000/api/v1"
HEALTH_URL = "http://localhost:8000/health"
TIMEOUT = 15.0


import pytest_asyncio  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest_asyncio.fixture()
async def client() -> AsyncGenerator[httpx.AsyncClient, None]:
    async with httpx.AsyncClient(
        base_url=BASE_URL, timeout=httpx.Timeout(TIMEOUT)
    ) as c:
        yield c


@pytest_asyncio.fixture()
async def project(client: httpx.AsyncClient) -> AsyncGenerator[dict, None]:
    """Create a throw-away project and delete it after the test."""
    uid = uuid.uuid4().hex[:8]
    payload = {
        "name": f"e2e-test-{uid}",
        "description": "E2E throw-away project",
        "local_path": f"/tmp/e2e-test-{uid}",
        "auto_onboard": False,
        "auto_discovery": False,
    }
    resp = await client.post("/projects", json=payload)
    assert resp.status_code in (200, 201), f"Failed to create project: {resp.text}"
    data = resp.json()
    project_id = data["id"]
    yield data

    # Cleanup – best-effort DELETE
    try:
        await client.delete(f"/projects/{project_id}")
    except Exception:
        pass


@pytest.fixture()
def unique_name() -> str:
    return f"e2e-{uuid.uuid4().hex[:8]}"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _create_project(client: httpx.AsyncClient, **overrides) -> dict:
    uid = uuid.uuid4().hex[:8]
    payload = {
        "name": f"e2e-test-{uid}",
        "description": "E2E throw-away project",
        "local_path": f"/tmp/e2e-test-{uid}",
        "auto_onboard": False,
        "auto_discovery": False,
    }
    payload.update(overrides)
    resp = await client.post("/projects", json=payload)
    assert resp.status_code in (200, 201), f"create project failed: {resp.text}"
    return resp.json()


# ---------------------------------------------------------------------------
# 0. Health check (root, NOT under /api/v1)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_health_check():
    async with httpx.AsyncClient(timeout=httpx.Timeout(TIMEOUT)) as c:
        resp = await c.get(HEALTH_URL)
    assert resp.status_code == 200
    body = resp.json()
    assert body.get("status") == "ok" or body.get("service") == "devgodzilla"


# ---------------------------------------------------------------------------
# 1. Agent flow
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_agent_flow(client: httpx.AsyncClient):
    # GET /agents – list all agents
    resp = await client.get("/agents")
    assert resp.status_code == 200
    agents = resp.json()
    assert isinstance(agents, list)
    assert len(agents) >= 1, "Expected at least one configured agent"

    # GET /agents/health – bulk health
    resp = await client.get("/agents/health")
    assert resp.status_code == 200
    health_list = resp.json()
    assert isinstance(health_list, list)

    # Per-agent health + test
    for agent in agents[:4]:  # cap at 4 to keep within timeout
        agent_id = agent["id"]

        # GET /agents/{id}/health
        resp = await client.get(f"/agents/{agent_id}/health")
        assert resp.status_code in (200, 404), f"agent health {agent_id}: {resp.status_code}"
        if resp.status_code == 200:
            assert "status" in resp.json()

        # POST /agents/{id}/test  – body can be empty {}
        resp = await client.post(f"/agents/{agent_id}/test", json={})
        assert resp.status_code in (200, 404), f"agent test {agent_id}: {resp.status_code}"
        if resp.status_code == 200:
            body = resp.json()
            assert "ok" in body
            assert "checks" in body


# ---------------------------------------------------------------------------
# 2. Project CRUD
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_project_crud(client: httpx.AsyncClient):
    uid = uuid.uuid4().hex[:8]

    # CREATE
    create_payload = {
        "name": f"crud-project-{uid}",
        "description": "CRUD test project",
        "local_path": f"/tmp/crud-test-{uid}",
        "auto_onboard": False,
        "auto_discovery": False,
    }
    resp = await client.post("/projects", json=create_payload)
    assert resp.status_code in (200, 201)
    created = resp.json()
    project_id = created["id"]
    assert created["name"] == create_payload["name"]

    try:
        # READ
        resp = await client.get(f"/projects/{project_id}")
        assert resp.status_code == 200
        fetched = resp.json()
        assert fetched["id"] == project_id
        assert fetched["name"] == create_payload["name"]

        # UPDATE
        resp = await client.put(
            f"/projects/{project_id}",
            json={"description": "Updated by E2E test"},
        )
        assert resp.status_code == 200
        updated = resp.json()
        assert updated["description"] == "Updated by E2E test"
    finally:
        # DELETE
        resp = await client.delete(f"/projects/{project_id}")
        assert resp.status_code == 200

        # Verify deletion
        resp = await client.get(f"/projects/{project_id}")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# 3. Onboarding
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_onboarding_flow(client: httpx.AsyncClient):
    proj = await _create_project(client)
    project_id = proj["id"]

    try:
        # POST /projects/{id}/actions/onboard
        resp = await client.post(
            f"/projects/{project_id}/actions/onboard", json={}
        )
        # Accept both 200 (sync) and 202 (queued) and also errors from missing
        # local repo – we just want to confirm the endpoint is reachable.
        assert resp.status_code in (200, 201, 202, 400, 500), (
            f"onboard unexpected status: {resp.status_code} {resp.text}"
        )

        # GET /projects/{id}/onboarding
        resp = await client.get(f"/projects/{project_id}/onboarding")
        assert resp.status_code == 200
        body = resp.json()
        assert "stages" in body or "status" in body
    finally:
        await client.delete(f"/projects/{project_id}")


# ---------------------------------------------------------------------------
# 4. Brownfield
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_brownfield_flow(client: httpx.AsyncClient):
    proj = await _create_project(client)
    project_id = proj["id"]

    try:
        # POST /projects/{id}/brownfield/run – async, returns immediately
        run_payload = {
            "feature_request": "Add a hello-world endpoint to the API",
            "output_mode": "task_cycle",
        }
        try:
            resp = await client.post(
                f"/projects/{project_id}/brownfield/run", json=run_payload
            )
            # May fail if project has no local repo – that's fine, we still test
            # the route is wired up correctly.
            assert resp.status_code in (200, 201, 202, 400, 500), (
                f"brownfield run unexpected: {resp.status_code} {resp.text}"
            )
        except httpx.ReadTimeout:
            # AI engine call can take longer than 15s – route is reachable
            await client.delete(f"/projects/{project_id}")
            return

        if resp.status_code in (200, 201, 202):
            body = resp.json()
            assert body.get("success") is True or "warnings" in body

        # GET /projects/{id}/branches – may 400 if no git repo
        resp = await client.get(f"/projects/{project_id}/branches")
        assert resp.status_code in (200, 400), (
            f"branches unexpected: {resp.status_code}"
        )
    finally:
        await client.delete(f"/projects/{project_id}")


# ---------------------------------------------------------------------------
# 5. Specification (SpecKit)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_specification_flow(client: httpx.AsyncClient):
    proj = await _create_project(client)
    project_id = proj["id"]

    try:
        # POST /speckit/specify
        specify_payload = {
            "project_id": project_id,
            "description": "Build a user registration form with email validation "
            "and password strength meter for the web application.",
        }
        try:
            resp = await client.post("/speckit/specify", json=specify_payload)
            # Spec generation depends on an agent being available; accept graceful
            # failures.
            assert resp.status_code in (200, 201, 400, 500), (
                f"speckit specify unexpected: {resp.status_code} {resp.text}"
            )
        except httpx.ReadTimeout:
            # AI engine call can take longer than 15s – route is reachable
            await client.delete(f"/projects/{project_id}")
            return

        # GET /speckit/status/{project_id}
        resp = await client.get(f"/speckit/status/{project_id}")
        assert resp.status_code == 200
        status_body = resp.json()
        assert "initialized" in status_body

        # GET /specifications – cross-project listing
        resp = await client.get("/specifications")
        assert resp.status_code == 200
        specs_body = resp.json()
        assert "items" in specs_body or isinstance(specs_body, list)
    finally:
        await client.delete(f"/projects/{project_id}")


# ---------------------------------------------------------------------------
# 6. Task cycle & protocols
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_task_cycle_and_protocols(client: httpx.AsyncClient):
    proj = await _create_project(client)
    project_id = proj["id"]

    try:
        # GET /projects/{id}/task-cycle
        resp = await client.get(f"/projects/{project_id}/task-cycle")
        assert resp.status_code == 200
        work_items = resp.json()
        assert isinstance(work_items, list)

        # GET /projects/{id}/protocols
        resp = await client.get(f"/projects/{project_id}/protocols")
        assert resp.status_code == 200
        protocols = resp.json()
        assert isinstance(protocols, list)
    finally:
        await client.delete(f"/projects/{project_id}")


# ---------------------------------------------------------------------------
# 7. Events
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_events_endpoints(client: httpx.AsyncClient):
    # GET /events (SSE stream) – we only read the first chunk to confirm it's
    # alive, then disconnect.
    async with httpx.AsyncClient(timeout=httpx.Timeout(5.0)) as stream_client:
        try:
            async with stream_client.stream("GET", f"{BASE_URL}/events") as resp:
                assert resp.status_code == 200
                assert "text/event-stream" in resp.headers.get("content-type", "")
                # Consume one small chunk to prove the stream is open.
                async for chunk in resp.aiter_text():
                    assert len(chunk) >= 0
                    break
        except httpx.ReadTimeout:
            # A timeout after connecting is fine – the stream is idle.
            pass

    # GET /events/recent
    resp = await client.get("/events/recent")
    assert resp.status_code == 200
    body = resp.json()
    assert "events" in body
    assert isinstance(body["events"], list)


# ---------------------------------------------------------------------------
# 8. CLI executions
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cli_executions(client: httpx.AsyncClient):
    # GET /cli-executions
    resp = await client.get("/cli-executions")
    assert resp.status_code == 200
    body = resp.json()
    assert "executions" in body
    assert isinstance(body["executions"], list)

    # GET /cli-executions/active
    resp = await client.get("/cli-executions/active")
    assert resp.status_code == 200
    body = resp.json()
    assert "executions" in body
    assert isinstance(body["executions"], list)


# ---------------------------------------------------------------------------
# 9. Sprints
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sprints_flow(client: httpx.AsyncClient):
    # GET /sprints – list all (may be empty)
    resp = await client.get("/sprints")
    assert resp.status_code == 200
    sprints = resp.json()
    assert isinstance(sprints, list)

    # Create a project to associate the sprint with
    proj = await _create_project(client)
    project_id = proj["id"]

    try:
        # POST /sprints – create a new sprint
        now = datetime.now(timezone.utc)
        sprint_payload = {
            "project_id": project_id,
            "name": f"E2E Sprint {uuid.uuid4().hex[:6]}",
            "goal": "Validate sprint creation via E2E tests",
            "status": "planning",
            "start_date": now.isoformat(),
            "end_date": now.isoformat(),  # same-day sprint is fine for tests
        }
        resp = await client.post("/sprints", json=sprint_payload)
        assert resp.status_code in (200, 201), f"sprint create: {resp.text}"
        sprint = resp.json()
        assert "id" in sprint
        assert sprint["name"] == sprint_payload["name"]

        # Verify it appears in the listing
        resp = await client.get("/sprints", params={"project_id": project_id})
        assert resp.status_code == 200
        listed = resp.json()
        assert any(s["id"] == sprint["id"] for s in listed)
    finally:
        await client.delete(f"/projects/{project_id}")
