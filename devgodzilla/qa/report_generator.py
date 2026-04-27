"""QA report generation in multiple formats."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from devgodzilla.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ReportSection:
    """A section of a QA report."""
    title: str
    content: str
    level: int = 2  # Markdown heading level


@dataclass
class QAReport:
    """A complete QA report."""
    step_name: str
    step_id: str
    status: str
    score: float
    timestamp: datetime = field(default_factory=lambda: datetime.utcnow())
    sections: List[ReportSection] = field(default_factory=list)
    gates_summary: Dict[str, Any] = field(default_factory=dict)
    findings_count: int = 0


@dataclass
class ReportGenerator:
    """
    Generates QA reports in multiple formats.
    
    Supports markdown, JSON, and HTML output formats.
    
    Example:
        generator = ReportGenerator(format="markdown")
        report = generator.generate(step_run, gate_results, checklist_result, verdict)
        markdown_text = generator.render(report)
    """
    
    format: str = "markdown"  # "markdown", "json", "html"
    
    def generate(
        self,
        step_run: Any,
        gate_results: List[Any],
        checklist_result: Optional[Any],
        verdict: Any,
    ) -> QAReport:
        """
        Generate a QA report from results.
        
        Args:
            step_run: Step run object with step_name and step_id attributes
            gate_results: List of GateResult objects
            checklist_result: Optional checklist result
            verdict: Verdict object with passed and score attributes
            
        Returns:
            QAReport object ready for rendering
        """
        # Extract step info
        step_name = getattr(step_run, "step_name", "unknown")
        step_id = str(getattr(step_run, "step_id", getattr(step_run, "id", "unknown")))
        
        # Determine status and score
        passed = getattr(verdict, "passed", True)
        score = getattr(verdict, "score", 1.0 if passed else 0.0)
        
        report = QAReport(
            step_name=step_name,
            step_id=step_id,
            status="PASSED" if passed else "FAILED",
            score=score,
        )
        
        # Add gates section
        gates_section = self._format_gates_section(gate_results)
        report.sections.append(gates_section)
        
        # Build gates summary
        report.gates_summary = self._build_gates_summary(gate_results)
        
        # Add checklist section
        if checklist_result:
            checklist_section = self._format_checklist_section(checklist_result)
            report.sections.append(checklist_section)
        
        # Add findings section
        findings_section = self._format_findings_section(gate_results)
        report.sections.append(findings_section)
        
        # Count findings
        report.findings_count = sum(
            len(getattr(gr, "findings", [])) for gr in gate_results
        )
        
        # Add recommendation
        recommendation_section = self._format_recommendation(verdict)
        report.sections.append(recommendation_section)
        
        return report
    
    def render(self, report: QAReport, format: Optional[str] = None) -> str:
        """
        Render report to specified format.
        
        Args:
            report: QAReport to render
            format: Override format (defaults to self.format)
            
        Returns:
            String representation of the report
        """
        fmt = format or self.format
        
        if fmt == "markdown":
            return self._render_markdown(report)
        elif fmt == "json":
            return self._render_json(report)
        elif fmt == "html":
            return self._render_html(report)
        else:
            raise ValueError(f"Unknown format: {fmt}")
    
    def _format_gates_section(self, gate_results: List[Any]) -> ReportSection:
        """Format the gates section."""
        lines = []
        
        for gate_result in gate_results:
            gate_id = getattr(gate_result, "gate_id", "unknown")
            gate_name = getattr(gate_result, "gate_name", gate_id)
            verdict = getattr(gate_result, "verdict", None)
            verdict_str = verdict.value if hasattr(verdict, "value") else str(verdict)
            findings_count = len(getattr(gate_result, "findings", []))
            
            # Icon based on verdict
            icon = "✅"
            if verdict_str in ("fail", "error"):
                icon = "❌"
            elif verdict_str == "warn":
                icon = "⚠️"
            elif verdict_str == "skip":
                icon = "⏭️"
            
            lines.append(f"- {icon} **{gate_name}** ({gate_id}): {verdict_str.upper()}")
            if findings_count > 0:
                lines.append(f"  - {findings_count} finding(s)")
        
        content = "\n".join(lines) if lines else "No gates executed."
        return ReportSection(title="Gate Results", content=content, level=2)
    
    def _build_gates_summary(self, gate_results: List[Any]) -> Dict[str, Any]:
        """Build summary dict of gate results."""
        summary = {
            "total": len(gate_results),
            "passed": 0,
            "failed": 0,
            "warned": 0,
            "skipped": 0,
            "errored": 0,
        }
        
        for gate_result in gate_results:
            verdict = getattr(gate_result, "verdict", None)
            verdict_str = verdict.value if hasattr(verdict, "value") else str(verdict)
            
            if verdict_str == "pass":
                summary["passed"] += 1
            elif verdict_str == "fail":
                summary["failed"] += 1
            elif verdict_str == "warn":
                summary["warned"] += 1
            elif verdict_str == "skip":
                summary["skipped"] += 1
            elif verdict_str == "error":
                summary["errored"] += 1
        
        return summary
    
    def _format_checklist_section(self, checklist_result: Any) -> ReportSection:
        """Format the checklist section."""
        lines = []
        
        # Handle checklist with items
        items = getattr(checklist_result, "items", [])
        if not items and isinstance(checklist_result, dict):
            items = checklist_result.get("items", [])
        
        if items:
            for item in items:
                text = getattr(item, "text", str(item))
                checked = getattr(item, "checked", False)
                icon = "✅" if checked else "⬜"
                lines.append(f"- {icon} {text}")
        else:
            lines.append("No checklist items found.")
        
        content = "\n".join(lines)
        return ReportSection(title="Checklist", content=content, level=2)
    
    def _format_findings_section(self, gate_results: List[Any]) -> ReportSection:
        """Format the findings section."""
        all_findings = []
        
        for gate_result in gate_results:
            findings = getattr(gate_result, "findings", [])
            gate_id = getattr(gate_result, "gate_id", "unknown")
            for finding in findings:
                all_findings.append((gate_id, finding))
        
        if not all_findings:
            return ReportSection(
                title="Findings",
                content="No findings to report.",
                level=2
            )
        
        lines = ["| Gate | Severity | Message | File |", "|------|----------|---------|------|"]
        
        for gate_id, finding in all_findings[:50]:  # Limit to 50 findings
            severity = getattr(finding, "severity", "info")
            message = getattr(finding, "message", str(finding))[:50]
            file_path = getattr(finding, "file_path", "-") or "-"
            
            lines.append(f"| {gate_id} | {severity} | {message}... | {file_path} |")
        
        if len(all_findings) > 50:
            lines.append(f"\n*...and {len(all_findings) - 50} more findings*")
        
        content = "\n".join(lines)
        return ReportSection(title="Findings", content=content, level=2)
    
    def _format_recommendation(self, verdict: Any) -> ReportSection:
        """Format the recommendation section."""
        passed = getattr(verdict, "passed", True)
        score = getattr(verdict, "score", 1.0 if passed else 0.0)
        has_skipped_gates = getattr(verdict, "has_skipped_gates", False)
        
        if passed:
            if has_skipped_gates:
                recommendation = "⚠️ QA passed without blocking failures, but some gates were skipped. Treat this as partial validation, not high confidence."
            elif score >= 0.9:
                recommendation = "✅ Excellent! The code passes all quality checks with high confidence."
            elif score >= 0.7:
                recommendation = "✅ Good. The code passes quality checks. Consider addressing any warnings."
            else:
                recommendation = "✅ Acceptable. The code passes but review warnings for improvements."
        else:
            if score < 0.3:
                recommendation = "❌ Critical issues found. Immediate attention required before proceeding."
            elif score < 0.6:
                recommendation = "❌ Multiple issues found. Please address the failures before continuing."
            else:
                recommendation = "⚠️ Some issues found. Review and fix the reported problems."
        
        return ReportSection(
            title="Recommendation",
            content=recommendation,
            level=2
        )
    
    def _render_markdown(self, report: QAReport) -> str:
        """Render report as markdown."""
        lines = [
            f"# QA Report: {report.step_name}",
            "",
            f"**Step ID**: {report.step_id}",
            f"**Status**: {'✅ PASSED' if report.status == 'PASSED' else '❌ FAILED'}",
            f"**Quality Score**: {report.score:.0%}",
            f"**Timestamp**: {report.timestamp.isoformat()}",
            "",
            "---",
            "",
        ]
        
        for section in report.sections:
            heading = "#" * section.level
            lines.append(f"{heading} {section.title}")
            lines.append("")
            lines.append(section.content)
            lines.append("")
        
        lines.extend([
            "---",
            "",
            "*Generated by DevGodzilla QualityService*",
        ])
        
        return "\n".join(lines)
    
    def _render_json(self, report: QAReport) -> str:
        """Render report as JSON."""
        import json
        
        data = {
            "step_name": report.step_name,
            "step_id": report.step_id,
            "status": report.status,
            "score": report.score,
            "timestamp": report.timestamp.isoformat(),
            "gates_summary": report.gates_summary,
            "findings_count": report.findings_count,
            "sections": [
                {
                    "title": s.title,
                    "content": s.content,
                    "level": s.level,
                }
                for s in report.sections
            ],
        }
        
        return json.dumps(data, indent=2)
    
    def _render_html(self, report: QAReport) -> str:
        """Render report as HTML."""
        status_class = "passed" if report.status == "PASSED" else "failed"
        status_icon = "✅" if report.status == "PASSED" else "❌"
        
        sections_html = []
        for section in report.sections:
            sections_html.append(f"""
        <div class="section">
            <h{section.level}>{section.title}</h{section.level}>
            <div class="content">
                <pre>{section.content}</pre>
            </div>
        </div>
""")
        
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>QA Report: {report.step_name}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            background: #f5f5f5;
        }}
        .header {{
            background: white;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .status-passed {{ color: #28a745; }}
        .status-failed {{ color: #dc3545; }}
        .section {{
            background: white;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .content pre {{
            white-space: pre-wrap;
            font-family: 'Fira Code', monospace;
            font-size: 14px;
        }}
        .score {{
            font-size: 2em;
            font-weight: bold;
        }}
        .footer {{
            text-align: center;
            color: #666;
            margin-top: 40px;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>QA Report: {report.step_name}</h1>
        <p><strong>Step ID:</strong> {report.step_id}</p>
        <p><strong>Status:</strong> <span class="status-{status_class}">{status_icon} {report.status}</span></p>
        <p class="score">Quality Score: {report.score:.0%}</p>
        <p><strong>Timestamp:</strong> {report.timestamp.isoformat()}</p>
    </div>
    
    {''.join(sections_html)}
    
    <div class="footer">
        <p>Generated by DevGodzilla QualityService</p>
    </div>
</body>
</html>"""
        
        return html
