"""
Specifications API Routes

Endpoints for listing and managing feature specifications across projects.
Enhanced with comprehensive filtering support.
"""
from typing import List, Optional, Any, Dict
from datetime import datetime, timedelta
from pathlib import Path
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException, Query

from devgodzilla.api.dependencies import get_db, get_service_context, Database
from devgodzilla.logging import get_logger, log_extra
from devgodzilla.services.base import ServiceContext
from devgodzilla.services.specification import SpecificationService

router = APIRouter(tags=["specifications"])
logger = get_logger(__name__)


def _spec_value(item: Any, key: str, default: Any = None) -> Any:
    if isinstance(item, dict):
        return item.get(key, default)
    return getattr(item, key, default)


def _spec_key(item: Any, resolved_spec_id: int) -> str:
    spec_run_id = _spec_value(item, "spec_run_id", None) or _spec_value(item, "id", None)
    if spec_run_id is not None:
        return f"run:{spec_run_id}"
    spec_path_value = str(_spec_value(item, "path", "") or "")
    spec_slug = Path(spec_path_value).name if spec_path_value else str(resolved_spec_id)
    return f"slug:{spec_slug}"


class SpecificationOut(BaseModel):
    id: int
    spec_run_id: Optional[int] = None
    path: str
    spec_path: Optional[str] = None
    plan_path: Optional[str] = None
    tasks_path: Optional[str] = None
    checklist_path: Optional[str] = None
    analysis_path: Optional[str] = None
    implement_path: Optional[str] = None
    title: str
    project_id: int
    project_name: str
    status: str
    error_message: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    worktree_path: Optional[str] = None
    branch_name: Optional[str] = None
    base_branch: Optional[str] = None
    feature_name: Optional[str] = None
    spec_number: Optional[int] = None
    tasks_generated: bool = False
    protocol_id: Optional[int] = None
    sprint_id: Optional[int] = None
    sprint_name: Optional[str] = None
    linked_tasks: int = 0
    completed_tasks: int = 0
    story_points: int = 0
    has_plan: bool = False
    has_tasks: bool = False


class SpecificationFilterParams(BaseModel):
    """Filter parameters for specifications listing."""
    project_id: Optional[int] = None
    sprint_id: Optional[int] = None
    status: Optional[str] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    has_plan: Optional[bool] = None
    has_tasks: Optional[bool] = None
    search: Optional[str] = None


class SpecificationLinkSprintRequest(BaseModel):
    sprint_id: Optional[int] = Field(None, description="Sprint ID to link, or None to unlink")


class SpecificationContentOut(BaseModel):
    id: int
    path: str
    title: str
    spec_content: Optional[str] = None
    plan_content: Optional[str] = None
    tasks_content: Optional[str] = None
    checklist_content: Optional[str] = None
    analysis_content: Optional[str] = None


class SpecificationsListOut(BaseModel):
    """Paginated list of specifications with filter metadata."""
    items: List[SpecificationOut]
    total: int
    filters_applied: Dict[str, Any]


def get_specification_service(
    ctx: ServiceContext = Depends(get_service_context),
    db: Database = Depends(get_db),
) -> SpecificationService:
    return SpecificationService(ctx, db)


@router.get("/specifications", response_model=SpecificationsListOut)
def list_specifications(
    project_id: Optional[int] = Query(None, description="Filter by project ID"),
    sprint_id: Optional[int] = Query(None, description="Filter by sprint ID"),
    status: Optional[str] = Query(None, description="Filter by status: draft, in-progress, completed"),
    date_from: Optional[str] = Query(None, description="Filter by created date from (ISO format)"),
    date_to: Optional[str] = Query(None, description="Filter by created date to (ISO format)"),
    has_plan: Optional[bool] = Query(None, description="Filter by has implementation plan"),
    has_tasks: Optional[bool] = Query(None, description="Filter by has tasks generated"),
    search: Optional[str] = Query(None, description="Search in title and path"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Database = Depends(get_db),
    service: SpecificationService = Depends(get_specification_service),
):
    """
    List all feature specifications across projects with comprehensive filtering.
    
    Filters:
    - project_id: Filter to a specific project
    - sprint_id: Filter specs linked to a specific sprint
    - status: draft | in-progress | completed
    - date_from/date_to: Date range filter (ISO format: YYYY-MM-DD)
    - has_plan: Filter by whether spec has implementation plan
    - has_tasks: Filter by whether spec has tasks generated
    - search: Full-text search in title and path
    """
    # Build applied filters dict for response
    filters_applied = {}
    if project_id is not None:
        filters_applied["project_id"] = project_id
    if sprint_id is not None:
        filters_applied["sprint_id"] = sprint_id
    if status:
        filters_applied["status"] = status
    if date_from:
        filters_applied["date_from"] = date_from
    if date_to:
        filters_applied["date_to"] = date_to
    if has_plan is not None:
        filters_applied["has_plan"] = has_plan
    if has_tasks is not None:
        filters_applied["has_tasks"] = has_tasks
    if search:
        filters_applied["search"] = search
    
    # Get projects to iterate
    if project_id:
        try:
            project = db.get_project(project_id)
            projects = [project] if project else []
        except (KeyError, Exception):
            raise HTTPException(status_code=404, detail=f"Project {project_id} not found")
    else:
        projects = db.list_projects()[:100]
    
    # If filtering by sprint, get sprint details
    sprint_project_filter = None
    if sprint_id:
        try:
            sprint = db.get_sprint(sprint_id)
            sprint_project_filter = sprint.project_id
        except (KeyError, Exception):
            raise HTTPException(status_code=404, detail=f"Sprint {sprint_id} not found")
    
    all_specifications = []
    spec_id = 0
    
    for project in projects:
        if not project or not project.local_path:
            continue
        
        # Skip if sprint filter and project doesn't match
        if sprint_project_filter is not None and project.id != sprint_project_filter:
            continue
            
        try:
            specs = service.list_specs(project.local_path, project_id=project.id)
            project_tasks = db.list_tasks(project_id=project.id, limit=500)
            project_sprints = {sprint.id: sprint for sprint in db.list_sprints(project_id=project.id)}
            try:
                project_spec_links = db.list_spec_sprint_links(project.id)
            except Exception:
                project_spec_links = {}
            spec_task_map: Dict[str, List[Any]] = {}
            for task in project_tasks:
                spec_label = next((label for label in task.labels if label.startswith("spec:")), None)
                if not spec_label:
                    continue
                spec_slug = spec_label.split(":", 1)[1]
                spec_task_map.setdefault(spec_slug, []).append(task)
            for spec in specs:
                spec_id += 1
                resolved_spec_id = _spec_value(spec, "spec_run_id", None) or _spec_value(spec, "id", None) or spec_id
                spec_ref_key = _spec_key(spec, resolved_spec_id)
                
                # Determine status based on what exists
                has_tasks_value = bool(_spec_value(spec, "has_tasks", False))
                has_plan_value = bool(_spec_value(spec, "has_plan", False))
                has_spec_value = bool(_spec_value(spec, "has_spec", False))

                status_override = _spec_value(spec, "status", None)
                if status_override in ("cleaned", "failed"):
                    spec_status = status_override
                else:
                    if has_tasks_value:
                        spec_status = "completed"
                    elif has_plan_value:
                        spec_status = "in-progress"
                    elif has_spec_value:
                        spec_status = "draft"
                    else:
                        continue  # Skip if no spec file
                
                # Apply status filter
                if status and spec_status != status:
                    continue
                
                # Apply has_plan filter
                if has_plan is not None and has_plan_value != has_plan:
                    continue
                
                # Apply has_tasks filter
                if has_tasks is not None and has_tasks_value != has_tasks:
                    continue
                
                # Try to extract title from spec name
                spec_name = _spec_value(spec, "name", "spec")
                title = spec_name.replace("-", " ").replace("_", " ").title()
                if title.startswith("Feature "):
                    title = title[8:]
                
                # Apply search filter
                if search:
                    search_lower = search.lower()
                    spec_path_value = str(_spec_value(spec, "path", ""))
                    if search_lower not in title.lower() and search_lower not in spec_path_value.lower():
                        continue
                
                # Get spec file modification time for date filtering
                spec_created_at = None
                try:
                    spec_dir = Path(_spec_value(spec, "path", ""))
                    if not spec_dir.is_absolute():
                        spec_dir = Path(project.local_path) / spec_dir
                    spec_file = spec_dir / "spec.md"
                    if spec_file.exists():
                        stat = spec_file.stat()
                        spec_created_at = datetime.fromtimestamp(stat.st_mtime).isoformat()
                except Exception:
                    pass
                
                # Apply date filters
                if date_from and spec_created_at:
                    try:
                        from_date = datetime.fromisoformat(date_from.replace('Z', '+00:00'))
                        spec_date = datetime.fromisoformat(spec_created_at.replace('Z', '+00:00'))
                        if spec_date < from_date:
                            continue
                    except ValueError:
                        pass
                
                if date_to and spec_created_at:
                    try:
                        to_date = datetime.fromisoformat(date_to.replace('Z', '+00:00'))
                        spec_date = datetime.fromisoformat(spec_created_at.replace('Z', '+00:00'))
                        if spec_date > to_date:
                            continue
                    except ValueError:
                        pass
                
                spec_slug = Path(_spec_value(spec, "path", "")).name
                spec_tasks = spec_task_map.get(spec_slug, [])
                linked_tasks = len(spec_tasks)
                completed_tasks = sum(1 for t in spec_tasks if t.board_status == "done")
                story_points = sum(t.story_points or 0 for t in spec_tasks)
                spec_sprint_ids = {t.sprint_id for t in spec_tasks if t.sprint_id}
                linked_sprint_id = project_spec_links.get(spec_ref_key)
                if linked_sprint_id is not None:
                    spec_sprint_ids.add(linked_sprint_id)
                spec_sprint_id = None
                spec_sprint_name = None

                if linked_sprint_id is not None:
                    spec_sprint_id = linked_sprint_id
                    sprint = project_sprints.get(spec_sprint_id)
                    spec_sprint_name = sprint.name if sprint else None
                elif len(spec_sprint_ids) == 1:
                    spec_sprint_id = next(iter(spec_sprint_ids))
                    sprint = project_sprints.get(spec_sprint_id)
                    spec_sprint_name = sprint.name if sprint else None
                elif len(spec_sprint_ids) > 1:
                    spec_sprint_name = "Multiple"

                if sprint_id is not None:
                    if sprint_id not in spec_sprint_ids:
                        continue
                    spec_sprint_id = sprint_id
                    sprint = project_sprints.get(spec_sprint_id)
                    spec_sprint_name = sprint.name if sprint else spec_sprint_name
                
                all_specifications.append(SpecificationOut(
                    id=resolved_spec_id,
                    spec_run_id=_spec_value(spec, "spec_run_id", None) or _spec_value(spec, "id", None),
                    path=_spec_value(spec, "path", ""),
                    spec_path=_spec_value(spec, "spec_path"),
                    plan_path=_spec_value(spec, "plan_path"),
                    tasks_path=_spec_value(spec, "tasks_path"),
                    checklist_path=_spec_value(spec, "checklist_path"),
                    analysis_path=_spec_value(spec, "analysis_path"),
                    implement_path=_spec_value(spec, "implement_path"),
                    title=title,
                    project_id=project.id,
                    project_name=project.name,
                    status=spec_status,
                    created_at=spec_created_at,
                    worktree_path=_spec_value(spec, "worktree_path"),
                    branch_name=_spec_value(spec, "branch_name"),
                    base_branch=_spec_value(spec, "base_branch"),
                    feature_name=_spec_value(spec, "feature_name"),
                    spec_number=_spec_value(spec, "spec_number"),
                    tasks_generated=has_tasks_value,
                    linked_tasks=linked_tasks,
                    completed_tasks=completed_tasks,
                    story_points=story_points,
                    has_plan=has_plan_value,
                    has_tasks=has_tasks_value,
                    sprint_id=spec_sprint_id,
                    sprint_name=spec_sprint_name,
                ))
        except Exception as exc:
            logger.warning(
                "specifications_project_scan_failed",
                extra=log_extra(project_id=project.id, error=str(exc)),
            )
            continue
    
    # Apply pagination
    total = len(all_specifications)
    paginated = all_specifications[offset:offset + limit]
    
    logger.info(
        "specifications_listed",
        extra=log_extra(
            project_id=project_id,
            sprint_id=sprint_id,
            status=status,
            has_plan=has_plan,
            has_tasks=has_tasks,
            search=search,
            limit=limit,
            offset=offset,
            total=total,
            result_count=len(paginated),
        ),
    )
    return SpecificationsListOut(
        items=paginated,
        total=total,
        filters_applied=filters_applied,
    )


def _get_specification_by_id(
    spec_id: int,
    db: Database,
    service: SpecificationService,
) -> SpecificationOut:
    result = list_specifications(
        project_id=None,
        sprint_id=None,
        status=None,
        date_from=None,
        date_to=None,
        has_plan=None,
        has_tasks=None,
        search=None,
        limit=500,
        offset=0,
        db=db,
        service=service,
    )
    for spec in result.items:
        if spec.id == spec_id:
            return spec
    raise HTTPException(status_code=404, detail=f"Specification {spec_id} not found")


@router.get("/specifications/{spec_id}", response_model=SpecificationOut)
def get_specification(
    spec_id: int,
    db: Database = Depends(get_db),
    service: SpecificationService = Depends(get_specification_service),
):
    """Get a single specification by ID."""
    spec = _get_specification_by_id(spec_id=spec_id, db=db, service=service)
    logger.info(
        "specification_loaded",
        extra=log_extra(
            project_id=spec.project_id,
            spec_id=spec.id,
            spec_run_id=spec.spec_run_id,
            sprint_id=spec.sprint_id,
            status=spec.status,
        ),
    )
    return spec


@router.get("/specifications/{spec_id}/content", response_model=SpecificationContentOut)
def get_specification_content(
    spec_id: int,
    db: Database = Depends(get_db),
    service: SpecificationService = Depends(get_specification_service),
):
    """Get specification content including spec, plan, and tasks markdown."""
    spec = _get_specification_by_id(spec_id=spec_id, db=db, service=service)
    
    # Get project to find local path
    try:
        project = db.get_project(spec.project_id)
    except (KeyError, Exception):
        logger.warning(
            "specification_content_project_not_found",
            extra=log_extra(project_id=spec.project_id, spec_id=spec_id),
        )
        raise HTTPException(status_code=404, detail=f"Project {spec.project_id} not found")
    
    if not project.local_path:
        logger.warning(
            "specification_content_missing_local_path",
            extra=log_extra(project_id=spec.project_id, spec_id=spec_id),
        )
        raise HTTPException(status_code=400, detail="Project has no local path")
    
    spec_dir = Path(spec.path)
    if not spec_dir.is_absolute():
        spec_dir = Path(project.local_path) / spec.path
    
    spec_content = None
    plan_content = None
    tasks_content = None
    checklist_content = None
    analysis_content = None
    
    # Read spec.md
    spec_file = spec_dir / "spec.md"
    if spec_file.exists():
        try:
            spec_content = spec_file.read_text()
        except Exception:
            pass
    
    # Read plan.md
    plan_file = spec_dir / "plan.md"
    if plan_file.exists():
        try:
            plan_content = plan_file.read_text()
        except Exception:
            pass
    
    # Read tasks.md
    tasks_file = spec_dir / "tasks.md"
    if tasks_file.exists():
        try:
            tasks_content = tasks_file.read_text()
        except Exception:
            pass

    # Read checklist.md
    checklist_file = spec_dir / "checklist.md"
    if checklist_file.exists():
        try:
            checklist_content = checklist_file.read_text()
        except Exception:
            pass

    # Read analysis.md
    analysis_file = spec_dir / "analysis.md"
    if analysis_file.exists():
        try:
            analysis_content = analysis_file.read_text()
        except Exception:
            pass
    
    logger.info(
        "specification_content_loaded",
        extra=log_extra(
            project_id=spec.project_id,
            spec_id=spec.id,
            spec_run_id=spec.spec_run_id,
            has_spec_content=spec_content is not None,
            has_plan_content=plan_content is not None,
            has_tasks_content=tasks_content is not None,
            has_checklist_content=checklist_content is not None,
            has_analysis_content=analysis_content is not None,
        ),
    )
    return SpecificationContentOut(
        id=spec_id,
        path=spec.path,
        title=spec.title,
        spec_content=spec_content,
        plan_content=plan_content,
        tasks_content=tasks_content,
        checklist_content=checklist_content,
        analysis_content=analysis_content,
    )


@router.post("/specifications/{spec_id}/link-sprint")
def link_specification_to_sprint(
    spec_id: int,
    request: SpecificationLinkSprintRequest,
    db: Database = Depends(get_db),
    service: SpecificationService = Depends(get_specification_service),
):
    """Link or unlink a specification to/from a sprint."""
    spec = _get_specification_by_id(spec_id=spec_id, db=db, service=service)
    
    # Verify sprint exists if linking
    if request.sprint_id is not None:
        try:
            sprint = db.get_sprint(request.sprint_id)
            # Verify sprint belongs to same project
            if sprint.project_id != spec.project_id:
                logger.warning(
                    "specification_link_sprint_project_mismatch",
                    extra=log_extra(
                        project_id=spec.project_id,
                        spec_id=spec.id,
                        sprint_id=request.sprint_id,
                        sprint_project_id=sprint.project_id,
                    ),
                )
                raise HTTPException(
                    status_code=400,
                    detail="Sprint must belong to the same project as the specification"
                )
        except KeyError:
            logger.warning(
                "specification_link_sprint_not_found",
                extra=log_extra(project_id=spec.project_id, spec_id=spec.id, sprint_id=request.sprint_id),
            )
            raise HTTPException(status_code=404, detail=f"Sprint {request.sprint_id} not found")
        except HTTPException:
            raise
        except Exception as exc:
            logger.error(
                "specification_link_sprint_load_failed",
                extra=log_extra(
                    project_id=spec.project_id,
                    spec_id=spec.id,
                    sprint_id=request.sprint_id,
                    error=str(exc),
                ),
            )
            raise HTTPException(status_code=500, detail=f"Failed to load sprint {request.sprint_id}: {exc}")
    
    spec_ref_key = _spec_key(spec, spec.id)
    try:
        db.set_spec_sprint_link(spec.project_id, spec_ref_key, request.sprint_id)
    except ValueError as exc:
        logger.warning(
            "specification_link_sprint_invalid",
            extra=log_extra(
                project_id=spec.project_id,
                spec_id=spec.id,
                sprint_id=request.sprint_id,
                error=str(exc),
            ),
        )
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.error(
            "specification_link_sprint_persist_failed",
            extra=log_extra(
                project_id=spec.project_id,
                spec_id=spec.id,
                sprint_id=request.sprint_id,
                error=str(exc),
            ),
        )
        raise HTTPException(status_code=500, detail=f"Failed to persist spec-sprint link: {exc}")
    logger.info(
        "specification_sprint_link_updated",
        extra=log_extra(
            project_id=spec.project_id,
            spec_id=spec.id,
            spec_run_id=spec.spec_run_id,
            sprint_id=request.sprint_id,
            action="link" if request.sprint_id is not None else "unlink",
        ),
    )

    return {
        "success": True,
        "persisted": True,
        "spec_id": spec_id,
        "sprint_id": request.sprint_id,
        "message": f"Specification {'linked to' if request.sprint_id else 'unlinked from'} sprint"
    }
