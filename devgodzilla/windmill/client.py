"""
DevGodzilla Windmill Client

HTTP client wrapper for Windmill API.
Handles job submission, flow management, and status queries.
"""

import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from devgodzilla.logging import get_logger

logger = get_logger(__name__)

# Try to import httpx for async HTTP support
try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    httpx = None  # type: ignore
    HTTPX_AVAILABLE = False


class JobStatus(str, Enum):
    """Windmill job status values."""
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"


@dataclass
class JobInfo:
    """Information about a Windmill job."""
    id: str
    status: JobStatus
    created_at: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    result: Optional[Any] = None
    error: Optional[str] = None
    logs: Optional[str] = None


@dataclass
class FlowInfo:
    """Information about a Windmill flow."""
    path: str
    name: str
    summary: Optional[str] = None
    schema: Optional[Dict[str, Any]] = None


@dataclass
class WindmillConfig:
    """Windmill connection configuration."""
    base_url: str
    token: str
    workspace: str = "starter"
    timeout: float = 30.0


def get_windmill_config() -> WindmillConfig:
    """Load Windmill configuration from environment."""
    return WindmillConfig(
        base_url=os.environ.get("DEVGODZILLA_WINDMILL_URL", "http://localhost:8000"),
        token=os.environ.get("DEVGODZILLA_WINDMILL_TOKEN", ""),
        workspace=os.environ.get("DEVGODZILLA_WINDMILL_WORKSPACE", "starter"),
        timeout=float(os.environ.get("DEVGODZILLA_WINDMILL_TIMEOUT", "30")),
    )


class WindmillClient:
    """
    HTTP client for Windmill API.
    
    Provides methods for:
    - Flow management (create, update, delete, list)
    - Job management (run, get status, cancel)
    - Script management (run scripts)
    
    Example:
        config = get_windmill_config()
        client = WindmillClient(config)
        
        # Create a flow
        client.create_flow("f/devgodzilla/my-flow", flow_definition)
        
        # Run a job
        job_id = client.run_flow("f/devgodzilla/my-flow", {"step_id": "T001"})
        
        # Check status
        job = client.get_job(job_id)
        print(job.status)
    """

    def __init__(self, config: Optional[WindmillConfig] = None) -> None:
        self.config = config or get_windmill_config()
        if not HTTPX_AVAILABLE:
            raise ImportError("httpx is required for WindmillClient. Install: pip install httpx")
        self._client: Optional[httpx.Client] = None

    def _get_client(self) -> "httpx.Client":
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.Client(
                base_url=self.config.base_url,
                timeout=self.config.timeout,
                headers={
                    "Authorization": f"Bearer {self.config.token}",
                    "Content-Type": "application/json",
                },
            )
        return self._client

    def _url(self, path: str) -> str:
        """Build API URL."""
        return f"/api/w/{self.config.workspace}{path}"

    def close(self) -> None:
        """Close HTTP client."""
        if self._client:
            self._client.close()
            self._client = None

    # Flow Management
    def create_flow(
        self,
        path: str,
        definition: Dict[str, Any],
        *,
        summary: Optional[str] = None,
        description: Optional[str] = None,
    ) -> FlowInfo:
        """
        Create a new flow in Windmill.
        
        Args:
            path: Flow path (e.g., "f/devgodzilla/protocol-123")
            definition: Flow definition dict with modules
            summary: Optional flow summary
            description: Optional flow description
            
        Returns:
            FlowInfo object
        """
        payload = {
            "path": path,
            "value": definition,
            "summary": summary or path.split("/")[-1],
            "description": description or "",
        }
        
        resp = self._get_client().post(self._url("/flows/create"), json=payload)
        resp.raise_for_status()
        
        logger.info("flow_created", extra={"path": path})
        return FlowInfo(path=path, name=summary or path.split("/")[-1])

    def update_flow(
        self,
        path: str,
        definition: Dict[str, Any],
        *,
        summary: Optional[str] = None,
    ) -> FlowInfo:
        """Update an existing flow."""
        payload = {
            "value": definition,
            "summary": summary,
        }
        
        resp = self._get_client().post(self._url(f"/flows/update/{path}"), json=payload)
        resp.raise_for_status()
        
        logger.info("flow_updated", extra={"path": path})
        return FlowInfo(path=path, name=summary or path.split("/")[-1])

    def delete_flow(self, path: str) -> None:
        """Delete a flow."""
        resp = self._get_client().delete(self._url(f"/flows/delete/{path}"))
        resp.raise_for_status()
        logger.info("flow_deleted", extra={"path": path})

    def get_flow(self, path: str) -> FlowInfo:
        """Get flow details."""
        resp = self._get_client().get(self._url(f"/flows/get/{path}"))
        resp.raise_for_status()
        data = resp.json()
        return FlowInfo(
            path=path,
            name=data.get("summary", path.split("/")[-1]),
            summary=data.get("summary"),
            schema=data.get("schema"),
        )

    def list_flows(self, prefix: Optional[str] = None) -> List[FlowInfo]:
        """List flows, optionally filtered by path prefix."""
        params = {}
        if prefix:
            params["path_prefix"] = prefix
        
        resp = self._get_client().get(self._url("/flows/list"), params=params)
        resp.raise_for_status()
        
        flows = []
        for item in resp.json():
            flows.append(FlowInfo(
                path=item.get("path", ""),
                name=item.get("summary", ""),
            ))
        return flows

    # Job Management
    def run_flow(
        self,
        path: str,
        args: Optional[Dict[str, Any]] = None,
        *,
        scheduled_for: Optional[str] = None,
        invisible_to_owner: bool = False,
    ) -> str:
        """
        Run a flow and return the job ID.
        
        Args:
            path: Flow path
            args: Input arguments
            scheduled_for: Optional ISO timestamp to schedule for
            invisible_to_owner: If True, job not visible in owner's dashboard
            
        Returns:
            Job ID (UUID string)
        """
        payload = args or {}
        params = {"invisible_to_owner": str(invisible_to_owner).lower()}
        if scheduled_for:
            params["scheduled_for"] = scheduled_for
        
        resp = self._get_client().post(
            self._url(f"/jobs/run/f/{path}"),
            json=payload,
            params=params,
        )
        resp.raise_for_status()
        
        job_id = resp.text.strip('"')
        logger.info("flow_job_started", extra={"path": path, "job_id": job_id})
        return job_id

    def run_script(
        self,
        path: str,
        args: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Run a script and return the job ID.
        
        Args:
            path: Script path
            args: Input arguments
            
        Returns:
            Job ID (UUID string)
        """
        payload = args or {}
        
        resp = self._get_client().post(
            self._url(f"/jobs/run/p/{path}"),
            json=payload,
        )
        resp.raise_for_status()
        
        job_id = resp.text.strip('"')
        logger.info("script_job_started", extra={"path": path, "job_id": job_id})
        return job_id

    def get_job(self, job_id: str) -> JobInfo:
        """Get job status and details."""
        resp = self._get_client().get(self._url(f"/jobs/get/{job_id}"))
        resp.raise_for_status()
        data = resp.json()
        
        # Map Windmill status to our enum
        raw_status = data.get("status", "").lower()
        status = JobStatus.QUEUED
        if raw_status == "running":
            status = JobStatus.RUNNING
        elif raw_status in ("success", "completed"):
            status = JobStatus.COMPLETED
        elif raw_status == "failure":
            status = JobStatus.FAILED
        elif raw_status == "canceled":
            status = JobStatus.CANCELED
        
        return JobInfo(
            id=job_id,
            status=status,
            created_at=data.get("created_at"),
            started_at=data.get("started_at"),
            completed_at=data.get("completed_at"),
            result=data.get("result"),
            error=data.get("error"),
        )

    def get_job_logs(self, job_id: str) -> str:
        """Get job logs."""
        resp = self._get_client().get(self._url(f"/jobs/get/{job_id}/logs"))
        resp.raise_for_status()
        return resp.text

    def cancel_job(self, job_id: str) -> None:
        """Cancel a running job."""
        resp = self._get_client().post(self._url(f"/jobs/cancel/{job_id}"))
        resp.raise_for_status()
        logger.info("job_canceled", extra={"job_id": job_id})

    def wait_for_job(
        self,
        job_id: str,
        *,
        timeout: float = 300,
        poll_interval: float = 1.0,
    ) -> JobInfo:
        """
        Wait for a job to complete.
        
        Args:
            job_id: Job ID to wait for
            timeout: Maximum time to wait in seconds
            poll_interval: Time between status checks
            
        Returns:
            Final JobInfo
            
        Raises:
            TimeoutError: If job doesn't complete within timeout
        """
        import time
        
        start = time.time()
        while True:
            job = self.get_job(job_id)
            if job.status in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELED):
                return job
            
            if time.time() - start > timeout:
                raise TimeoutError(f"Job {job_id} did not complete within {timeout}s")
            
            time.sleep(poll_interval)

    # Health Check
    def health_check(self) -> bool:
        """Check if Windmill is reachable."""
        try:
            resp = self._get_client().get("/api/version")
            return resp.status_code == 200
        except Exception:
            return False

    def get_version(self) -> Optional[str]:
        """Get Windmill version."""
        try:
            resp = self._get_client().get("/api/version")
            resp.raise_for_status()
            return resp.text.strip()
        except Exception:
            return None
