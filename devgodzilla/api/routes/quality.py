"""
Quality Dashboard API Routes

Aggregate quality metrics across projects and protocols.
"""
from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends

from devgodzilla.api.dependencies import get_db, get_service_context, Database
from devgodzilla.services.base import ServiceContext

router = APIRouter(tags=["quality"])


class QAOverview(BaseModel):
    total_protocols: int = 0
    passed: int = 0
    warnings: int = 0
    failed: int = 0
    average_score: int = 100


class QAFinding(BaseModel):
    id: int
    protocol_id: int
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
    # Get all protocols to calculate stats
    protocols = db.list_protocol_runs(limit=100)
    
    passed = 0
    warnings = 0
    failed = 0
    
    for protocol in protocols:
        if protocol.status == "completed":
            passed += 1
        elif protocol.status == "failed":
            failed += 1
        elif protocol.status in ("running", "blocked"):
            warnings += 1
    
    total = len(protocols)
    average_score = 100 if total == 0 else int(((passed + warnings * 0.5) / total) * 100) if total > 0 else 100
    
    overview = QAOverview(
        total_protocols=total,
        passed=passed,
        warnings=warnings,
        failed=failed,
        average_score=average_score,
    )
    
    # Get recent events that are QA-related for findings
    events = db.list_events(limit=20)
    recent_findings: List[QAFinding] = []
    
    finding_id = 0
    for event in events:
        if "fail" in event.event_type.lower() or "error" in event.message.lower():
            finding_id += 1
            recent_findings.append(QAFinding(
                id=finding_id,
                protocol_id=event.protocol_run_id or 0,
                project_name=event.project_name or "Unknown",
                article="III",
                article_name="Quality",
                severity="error" if "fail" in event.event_type.lower() else "warning",
                message=event.message[:100],
                timestamp=event.created_at.strftime("%Y-%m-%d %H:%M") if event.created_at else "",
            ))
            if len(recent_findings) >= 5:
                break
    
    # Build constitutional gates summary from real QA data
    step_runs = db.list_step_runs(limit=200)
    gate_stats: Dict[str, Dict[str, Any]] = {}

    for run in step_runs:
        if run.policy and isinstance(run.policy, dict) and 'gates' in run.policy:
            for gate in run.policy['gates']:
                article = gate.get('article', 'Unknown')
                status = gate.get('status', 'unknown')

                if article not in gate_stats:
                    gate_stats[article] = {
                        'passed': 0,
                        'failed': 0,
                        'warning': 0,
                        'name': gate.get('name', article)
                    }

                if status in ('passed', 'failed', 'warning'):
                    gate_stats[article][status] = gate_stats[article].get(status, 0) + 1

    # Build gates from stats, fallback to defaults if no QA data
    if gate_stats:
        gates = []
        for article, stats in sorted(gate_stats.items()):
            total_checks = stats['passed'] + stats['failed'] + stats['warning']
            if stats['failed'] > 0:
                status = 'failed'
            elif stats['warning'] > 0:
                status = 'warning'
            else:
                status = 'passed'

            gates.append(ConstitutionalGate(
                article=article,
                name=stats['name'],
                status=status,
                checks=total_checks
            ))
    else:
        gates = [
            ConstitutionalGate(article="I", name="No Breaking Changes", status="passed", checks=passed),
            ConstitutionalGate(article="II", name="Backward Compatibility", status="passed", checks=passed),
            ConstitutionalGate(article="III", name="Code Quality", status="failed" if failed > 0 else "passed", checks=total),
            ConstitutionalGate(article="IV", name="Security", status="warning" if warnings > 0 else "passed", checks=total),
            ConstitutionalGate(article="V", name="Scope Control", status="passed", checks=passed),
            ConstitutionalGate(article="IX", name="Documentation", status="passed", checks=passed),
        ]
    
    return QualityDashboard(
        overview=overview,
        recent_findings=recent_findings,
        constitutional_gates=gates,
    )
