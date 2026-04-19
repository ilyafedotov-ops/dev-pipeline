"""
Quality Dashboard API Routes

Aggregate quality metrics across projects and protocols.
"""
from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends

from devgodzilla.api.dependencies import get_db, get_service_context, Database
from devgodzilla.logging import get_logger, log_extra
from devgodzilla.speckit_metadata import extract_spec_run_id
from devgodzilla.services.base import ServiceContext

router = APIRouter(tags=["quality"])
logger = get_logger(__name__)


class QAOverview(BaseModel):
    total_protocols: int = 0
    passed: int = 0
    warnings: int = 0
    failed: int = 0
    average_score: int = 100


class QAFinding(BaseModel):
    id: int
    protocol_id: int
    spec_run_id: Optional[int] = None
    project_name: str
    article: str
    article_name: str
    severity: str
    message: str
    timestamp: str


class ConstitutionalGate(BaseModel):
    article: str
    name: str
    status: str
    checks: int


class QualityDashboard(BaseModel):
    overview: QAOverview
    recent_findings: List[QAFinding]
    constitutional_gates: List[ConstitutionalGate]


@router.get("/quality/dashboard", response_model=QualityDashboard)
def get_quality_dashboard(
    db: Database = Depends(get_db),
    ctx: ServiceContext = Depends(get_service_context),
):
    """
    Get aggregate quality dashboard data across all projects.
    """
    protocols = db.list_all_protocol_runs(limit=200)
    qa_results = db.list_qa_results(limit=500)

    results_by_protocol: Dict[int, List[Any]] = {}
    for result in qa_results:
        results_by_protocol.setdefault(result.protocol_run_id, []).append(result)

    passed = 0
    warnings = 0
    failed = 0

    for protocol in protocols:
        items = results_by_protocol.get(protocol.id, [])
        if not items:
            continue
        if any(r.verdict in ("fail", "error") for r in items):
            failed += 1
        elif any(r.verdict == "warn" for r in items):
            warnings += 1
        else:
            passed += 1

    total = len(protocols)
    average_score = 100 if total == 0 else int(((passed + warnings * 0.5) / total) * 100)

    overview = QAOverview(
        total_protocols=total,
        passed=passed,
        warnings=warnings,
        failed=failed,
        average_score=average_score,
    )

    recent_findings: List[QAFinding] = []
    projects_cache: Dict[int, str] = {}
    protocol_review_cache: Dict[int, Optional[int]] = {}
    finding_id = 0

    def _spec_run_id_for_protocol(protocol_id: int) -> Optional[int]:
        if protocol_id <= 0:
            return None
        if protocol_id not in protocol_review_cache:
            try:
                protocol_review_cache[protocol_id] = extract_spec_run_id(
                    db.get_protocol_run(protocol_id).speckit_metadata
                )
            except Exception:
                protocol_review_cache[protocol_id] = None
        return protocol_review_cache[protocol_id]

    for result in qa_results:
        for finding in result.findings or []:
            severity = finding.get("severity", "warning")
            if severity not in ("warning", "error", "critical"):
                continue
            project_id = result.project_id
            if project_id not in projects_cache:
                try:
                    projects_cache[project_id] = db.get_project(project_id).name
                except Exception:
                    projects_cache[project_id] = "Unknown"
            finding_id += 1
            recent_findings.append(
                QAFinding(
                    id=finding_id,
                    protocol_id=result.protocol_run_id,
                    spec_run_id=_spec_run_id_for_protocol(result.protocol_run_id),
                    project_name=projects_cache[project_id],
                    article=str(finding.get("metadata", {}).get("article") or finding.get("gate_id") or "QA"),
                    article_name=str(finding.get("metadata", {}).get("article_title") or finding.get("gate_id") or "QA"),
                    severity="error" if severity in ("error", "critical") else "warning",
                    message=str(finding.get("message", ""))[:160],
                    timestamp=str(result.created_at or ""),
                )
            )
            if len(recent_findings) >= 5:
                break
        if len(recent_findings) >= 5:
            break

    gate_stats: Dict[str, Dict[str, Any]] = {}
    for result in qa_results:
        for gate in result.gate_results or []:
            if gate.get("gate_id") != "constitutional":
                continue
            meta = gate.get("metadata") or {}
            for article in meta.get("article_statuses", []) or []:
                article_id = str(article.get("article") or "Unknown")
                status = str(article.get("status") or "unknown")
                gate_stats.setdefault(
                    article_id,
                    {"passed": 0, "failed": 0, "warning": 0, "name": article.get("name", article_id)},
                )
                if status in ("passed", "failed", "warning"):
                    gate_stats[article_id][status] += 1

    gates = []
    for article, stats in sorted(gate_stats.items()):
        total_checks = stats["passed"] + stats["failed"] + stats["warning"]
        if stats["failed"] > 0:
            status = "failed"
        elif stats["warning"] > 0:
            status = "warning"
        else:
            status = "passed"
        gates.append(
            ConstitutionalGate(
                article=article,
                name=str(stats.get("name", article)),
                status=status,
                checks=total_checks,
            )
        )

    logger.info(
        "quality_dashboard_loaded",
        extra=log_extra(
            request_id=ctx.request_id,
            total_protocols=overview.total_protocols,
            passed=overview.passed,
            warnings=overview.warnings,
            failed=overview.failed,
            average_score=overview.average_score,
            recent_findings_count=len(recent_findings),
            constitutional_gate_count=len(gates),
        ),
    )
    return QualityDashboard(
        overview=overview,
        recent_findings=recent_findings,
        constitutional_gates=gates,
    )
