from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import quote

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.message import Message
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    Footer,
    Header,
    Input,
    Label,
    ListItem,
    ListView,
    LoadingIndicator,
    Static,
    TabPane,
    TabbedContent,
)

from tasksgodzilla.cli.client import APIClient, APIClientError
from tasksgodzilla.config import load_config
from tasksgodzilla.logging import get_logger, init_cli_logging, json_logging_from_env

log = get_logger("tasksgodzilla.cli.tui")


def env_default(key: str, fallback: Optional[str] = None) -> Optional[str]:
    return os.environ.get(key, fallback)


def format_ts(ts: Optional[str]) -> str:
    if not ts:
        return "-"
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return ts


class DataListItem(ListItem):
    """List item that carries a payload identifier."""

    def __init__(self, label: str, item_id: Any, subtitle: str = "") -> None:
        content = Label(f"{label}{(' • ' + subtitle) if subtitle else ''}")
        super().__init__(content)
        self.item_id = item_id


class ImportScreen(ModalScreen[Optional[Dict[str, Any]]]):
    """Modal form to import a CodeMachine workspace."""

    def __init__(self, defaults: Optional[Dict[str, str]] = None) -> None:
        super().__init__()
        self.defaults = defaults or {}

    def compose(self) -> ComposeResult:
        yield Static("Import CodeMachine workspace", classes="title")
        yield Input(placeholder="Protocol name (e.g., 0002-cm)", id="protocol_name", value=self.defaults.get("protocol_name", ""))
        yield Input(placeholder="Workspace path", id="workspace_path", value=self.defaults.get("workspace_path", ""))
        yield Input(placeholder="Base branch (default: main)", id="base_branch", value=self.defaults.get("base_branch", ""))
        yield Input(placeholder="Description (optional)", id="description", value=self.defaults.get("description", ""))
        enqueue_default = self.defaults.get("enqueue", "")
        yield Input(placeholder="Enqueue job? (y/N)", id="enqueue", value=str(enqueue_default))
        yield Button("Submit", id="submit", variant="primary")
        yield Button("Cancel", id="cancel", variant="default")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel":
            self.dismiss(None)
            return
        if event.button.id == "submit":
            protocol_name = self.query_one("#protocol_name", Input).value.strip()
            workspace_path = self.query_one("#workspace_path", Input).value.strip()
            base_branch = self.query_one("#base_branch", Input).value.strip() or "main"
            description = self.query_one("#description", Input).value.strip() or None
            enqueue_raw = self.query_one("#enqueue", Input).value.strip().lower()
            enqueue = enqueue_raw.startswith("y")
            if not protocol_name or not workspace_path:
                self.app.bell()
                return
            self.dismiss(
                {
                    "protocol_name": protocol_name,
                    "workspace_path": workspace_path,
                    "base_branch": base_branch,
                    "description": description,
                    "enqueue": enqueue,
                }
            )


class StepActionScreen(ModalScreen[Optional[str]]):
    """Modal menu for step actions."""

    def compose(self) -> ComposeResult:
        yield Static("Step actions", classes="title")
        yield Button("Run next", id="run_next", variant="primary")
        yield Button("Retry latest", id="retry_latest")
        yield Button("Run QA", id="run_qa")
        yield Button("Approve", id="approve")
        yield Button("Open PR", id="open_pr")
        yield Button("Cancel", id="cancel", variant="default")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel":
            self.dismiss(None)
        else:
            self.dismiss(event.button.id)


class TokenConfigScreen(ModalScreen[Optional[Dict[str, str]]]):
    """Modal to update API base and tokens without env edits."""

    def compose(self) -> ComposeResult:
        yield Static("Configure API base/token", classes="title")
        yield Input(placeholder="API base (e.g., http://localhost:8000)", id="api_base")
        yield Input(placeholder="API token (optional)", id="api_token", password=True)
        yield Input(placeholder="Project token (optional)", id="project_token", password=True)
        yield Button("Save", id="save", variant="primary")
        yield Button("Cancel", id="cancel", variant="default")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel":
            self.dismiss(None)
            return
        api_base = self.query_one("#api_base", Input).value.strip()
        api_token = self.query_one("#api_token", Input).value.strip()
        project_token = self.query_one("#project_token", Input).value.strip()
        if not api_base:
            self.app.bell()
            return
        self.dismiss(
            {
                "api_base": api_base,
                "api_token": api_token or None,
                "project_token": project_token or None,
            }
        )


class ProjectCreateScreen(ModalScreen[Optional[Dict[str, Any]]]):
    """Modal to create a project."""

    def compose(self) -> ComposeResult:
        yield Static("Create project", classes="title")
        yield Input(placeholder="Name", id="name")
        yield Input(placeholder="Git URL or path", id="git_url")
        yield Input(placeholder="Base branch (default: main)", id="base_branch", value="main")
        yield Input(placeholder="Local path (optional)", id="local_path")
        yield Input(placeholder="CI provider (optional)", id="ci_provider")
        yield Button("Create", id="create", variant="primary")
        yield Button("Cancel", id="cancel", variant="default")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel":
            self.dismiss(None)
            return
        name = self.query_one("#name", Input).value.strip()
        git_url = self.query_one("#git_url", Input).value.strip()
        base_branch = self.query_one("#base_branch", Input).value.strip() or "main"
        local_path = self.query_one("#local_path", Input).value.strip() or None
        ci_provider = self.query_one("#ci_provider", Input).value.strip() or None
        if not name or not git_url:
            self.app.bell()
            return
        self.dismiss(
            {
                "name": name,
                "git_url": git_url,
                "base_branch": base_branch,
                "local_path": local_path,
                "ci_provider": ci_provider,
            }
        )


class ProtocolCreateScreen(ModalScreen[Optional[Dict[str, Any]]]):
    """Modal to create a protocol run."""

    def compose(self) -> ComposeResult:
        yield Static("Create protocol run", classes="title")
        yield Input(placeholder="Protocol name (e.g., 0001-demo)", id="protocol_name")
        yield Input(placeholder="Base branch (default: main)", id="base_branch", value="main")
        yield Input(placeholder="Description (optional)", id="description")
        yield Input(placeholder="Start planning now? (y/N)", id="start_now", value="y")
        yield Button("Create", id="create", variant="primary")
        yield Button("Cancel", id="cancel", variant="default")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel":
            self.dismiss(None)
            return
        name = self.query_one("#protocol_name", Input).value.strip()
        base_branch = self.query_one("#base_branch", Input).value.strip() or "main"
        description = self.query_one("#description", Input).value.strip() or None
        start_now_raw = self.query_one("#start_now", Input).value.strip().lower()
        start_now = start_now_raw.startswith("y")
        if not name:
            self.app.bell()
            return
        self.dismiss(
            {
                "protocol_name": name,
                "base_branch": base_branch,
                "description": description,
                "start_now": start_now,
            }
        )


class SpecAuditScreen(ModalScreen[Optional[Dict[str, Any]]]):
    """Modal to enqueue spec audit/backfill."""

    def __init__(self, project_id: Optional[int], protocol_id: Optional[int]) -> None:
        super().__init__()
        self.project_id = project_id
        self.protocol_id = protocol_id

    def compose(self) -> ComposeResult:
        yield Static("Spec audit", classes="title")
        yield Input(placeholder="Project ID (optional)", id="project_id", value=str(self.project_id or ""))
        yield Input(placeholder="Protocol ID (optional)", id="protocol_id", value=str(self.protocol_id or ""))
        yield Input(placeholder="Backfill missing? (y/N)", id="backfill", value="y")
        yield Input(placeholder="Interval seconds override (optional)", id="interval_seconds")
        yield Button("Enqueue audit", id="enqueue", variant="primary")
        yield Button("Cancel", id="cancel", variant="default")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel":
            self.dismiss(None)
            return
        project_raw = self.query_one("#project_id", Input).value.strip()
        protocol_raw = self.query_one("#protocol_id", Input).value.strip()
        backfill_raw = self.query_one("#backfill", Input).value.strip().lower()
        interval_raw = self.query_one("#interval_seconds", Input).value.strip()
        payload: Dict[str, Any] = {}
        if project_raw:
            try:
                payload["project_id"] = int(project_raw)
            except ValueError:
                self.app.bell()
                return
        if protocol_raw:
            try:
                payload["protocol_id"] = int(protocol_raw)
            except ValueError:
                self.app.bell()
                return
        payload["backfill"] = backfill_raw.startswith("y")
        if interval_raw:
            try:
                payload["interval_seconds"] = int(interval_raw)
            except ValueError:
                self.app.bell()
                return
        self.dismiss(payload)


class BranchDeleteScreen(ModalScreen[bool]):
    """Confirm branch deletion."""

    def __init__(self, branch: str) -> None:
        super().__init__()
        self.branch = branch

    def compose(self) -> ComposeResult:
        yield Static(f"Delete remote branch '{self.branch}'?", classes="title")
        yield Static("This will run POST /branches/{branch}/delete with confirm=true.")
        yield Button("Delete", id="confirm", variant="error")
        yield Button("Cancel", id="cancel", variant="default")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "confirm")


class ConfirmActionScreen(ModalScreen[bool]):
    """Generic confirmation dialog for destructive actions."""

    def __init__(self, title: str, message: str, confirm_label: str = "Confirm", danger: bool = True) -> None:
        super().__init__()
        self.title_text = title
        self.message_text = message
        self.confirm_label = confirm_label
        self.danger = danger

    def compose(self) -> ComposeResult:
        yield Static(self.title_text, classes="title")
        yield Static(self.message_text)
        yield Button(self.confirm_label, id="confirm", variant="error" if self.danger else "primary")
        yield Button("Cancel", id="cancel", variant="default")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "confirm")


class ClarificationsScreen(ModalScreen[Optional[Dict[str, Any]]]):
    """Modal to view and answer clarifications."""

    def __init__(self, clarifications: List[Dict[str, Any]], scope: str = "project") -> None:
        super().__init__()
        self.clarifications = clarifications
        self.scope = scope
        self.selected_idx = 0

    def compose(self) -> ComposeResult:
        yield Static(f"Clarifications ({self.scope})", classes="title")
        if not self.clarifications:
            yield Static("No open clarifications.")
            yield Button("Close", id="close", variant="default")
            return
        with VerticalScroll(id="clarifications_list"):
            for idx, clar in enumerate(self.clarifications):
                blocking = "BLOCKING" if clar.get("blocking") else "optional"
                status = clar.get("status", "open")
                yield Static(
                    f"[{idx + 1}] {clar['key']} ({blocking}, {status})\n"
                    f"   Q: {clar['question']}\n"
                    f"   Options: {', '.join(str(o) for o in (clar.get('options') or ['free text']))}\n"
                    f"   Current: {clar.get('answer') or '-'}",
                    id=f"clar_{idx}",
                )
        yield Static("Select clarification to answer:", classes="title")
        yield Input(placeholder="Clarification number (1, 2, ...)", id="clar_num")
        yield Input(placeholder="Your answer", id="answer_input")
        yield Button("Submit Answer", id="submit", variant="primary")
        yield Button("Close", id="close", variant="default")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "close":
            self.dismiss(None)
            return
        if event.button.id == "submit":
            try:
                num = int(self.query_one("#clar_num", Input).value.strip()) - 1
                if num < 0 or num >= len(self.clarifications):
                    self.app.bell()
                    return
                answer = self.query_one("#answer_input", Input).value.strip()
                if not answer:
                    self.app.bell()
                    return
                clar = self.clarifications[num]
                self.dismiss({"key": clar["key"], "answer": answer, "scope": self.scope})
            except ValueError:
                self.app.bell()


class LogViewerScreen(ModalScreen[None]):
    """Modal to view execution logs."""

    def __init__(self, title: str, content: str) -> None:
        super().__init__()
        self.title_text = title
        self.content = content

    def compose(self) -> ComposeResult:
        yield Static(self.title_text, classes="title")
        with VerticalScroll(id="log_content"):
            yield Static(self.content or "No logs available.")
        yield Button("Close", id="close", variant="default")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(None)


class ErrorDetailScreen(ModalScreen[None]):
    """Modal to view full error details."""

    def __init__(self, error_type: str, error_message: str, context: Optional[Dict[str, Any]] = None) -> None:
        super().__init__()
        self.error_type = error_type
        self.error_message = error_message
        self.context = context or {}

    def compose(self) -> ComposeResult:
        yield Static(f"Error: {self.error_type}", classes="title")
        with VerticalScroll(id="error_content"):
            yield Static(f"Message:\n{self.error_message}\n")
            if self.context:
                ctx_text = "\n".join(f"  {k}: {v}" for k, v in self.context.items())
                yield Static(f"Context:\n{ctx_text}")
        yield Button("Close", id="close", variant="default")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(None)


class PolicyFindingsScreen(ModalScreen[None]):
    """Modal to view policy findings."""

    def __init__(self, findings: List[Dict[str, Any]]) -> None:
        super().__init__()
        self.findings = findings

    def compose(self) -> ComposeResult:
        yield Static("Policy Findings", classes="title")
        if not self.findings:
            yield Static("No policy issues found.")
        else:
            with VerticalScroll(id="findings_list"):
                for f in self.findings:
                    severity = f.get("severity", "info")
                    code = f.get("code", "unknown")
                    message = f.get("message", "")
                    fix = f.get("suggested_fix", "")
                    icon = "🚫" if severity == "error" else "⚠️" if severity == "warning" else "ℹ️"
                    text = f"{icon} [{code}] {message}"
                    if fix:
                        text += f"\n   Fix: {fix}"
                    yield Static(text)
        yield Button("Close", id="close", variant="default")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(None)


class JobInspectorScreen(ModalScreen[Optional[str]]):
    """Modal to inspect Codex runs for a step."""

    def __init__(self, runs: List[Dict[str, Any]], step_name: str = "") -> None:
        super().__init__()
        self.runs = runs
        self.step_name = step_name
        self.selected_idx = 0

    def compose(self) -> ComposeResult:
        title = f"Job Inspector: {self.step_name}" if self.step_name else "Job Inspector"
        yield Static(title, classes="title")
        if not self.runs:
            yield Static("No Codex runs found for this step.")
        else:
            yield Static(f"{len(self.runs)} run(s) found. Select one to view details.", id="runs_count")
            with Horizontal(id="inspector_layout"):
                with Vertical(id="runs_list_panel"):
                    yield Static("Runs", classes="title")
                    yield ListView(id="runs_list")
                with VerticalScroll(id="run_detail_panel"):
                    yield Static("Details", classes="title")
                    yield Static("Select a run from the list.", id="run_detail")
        with Horizontal(classes="row"):
            yield Button("View Logs", id="view_logs", variant="primary")
            yield Button("Artifacts", id="view_artifacts", variant="default")
            yield Button("Close", id="close", variant="default")

    def on_mount(self) -> None:
        if not self.runs:
            return
        runs_view = self.query_one("#runs_list", ListView)
        for run in self.runs:
            run_id = run.get("run_id", "?")
            status = run.get("status", "?")
            job_type = run.get("job_type", "?")
            created = run.get("created_at", "")[:19] if run.get("created_at") else "-"
            label = f"{run_id[:8]} [{status}] {job_type} {created}"
            runs_view.append(DataListItem(label, run_id))
        if self.runs:
            runs_view.index = 0
            self._render_run_detail(self.runs[0])

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        if not event.item or not isinstance(event.item, DataListItem):
            return
        run_id = event.item.item_id
        run = next((r for r in self.runs if r.get("run_id") == run_id), None)
        if run:
            self._render_run_detail(run)
            self.selected_idx = next((i for i, r in enumerate(self.runs) if r.get("run_id") == run_id), 0)

    def _render_run_detail(self, run: Dict[str, Any]) -> None:
        lines = [
            f"Run ID: {run.get('run_id', '-')}",
            f"Status: {run.get('status', '-')}",
            f"Job Type: {run.get('job_type', '-')}",
            f"Run Kind: {run.get('run_kind', '-')}",
            f"Model: {run.get('params', {}).get('model', '-') if run.get('params') else '-'}",
            "",
            f"Created: {run.get('created_at', '-')}",
            f"Started: {run.get('started_at', '-')}",
            f"Finished: {run.get('finished_at', '-')}",
            "",
            f"Tokens: {run.get('cost_tokens', 0):,}",
            f"Cost: {run.get('cost_cents', 0)} cents",
            "",
            f"Worker: {run.get('worker_id', '-')}",
            f"Queue: {run.get('queue', '-')}",
            f"Attempt: {run.get('attempt', '-')}",
        ]
        if run.get("error"):
            lines.extend(["", f"Error: {run.get('error')}"])
        detail_widget = self.query_one("#run_detail", Static)
        detail_widget.update("\n".join(lines))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "close":
            self.dismiss(None)
        elif event.button.id == "view_logs":
            if self.runs and 0 <= self.selected_idx < len(self.runs):
                run_id = self.runs[self.selected_idx].get("run_id")
                self.dismiss({"action": "logs", "run_id": run_id})
            else:
                self.dismiss(None)
        elif event.button.id == "view_artifacts":
            if self.runs and 0 <= self.selected_idx < len(self.runs):
                run_id = self.runs[self.selected_idx].get("run_id")
                self.dismiss({"action": "artifacts", "run_id": run_id})
            else:
                self.dismiss(None)


class ArtifactViewerScreen(ModalScreen[Optional[Dict[str, Any]]]):
    """Modal to browse artifacts for a Codex run."""

    def __init__(self, artifacts: List[Dict[str, Any]], run_id: str = "") -> None:
        super().__init__()
        self.artifacts = artifacts
        self.run_id = run_id
        self.selected_idx = 0

    def compose(self) -> ComposeResult:
        title = f"Artifacts: {self.run_id[:12]}" if self.run_id else "Artifacts"
        yield Static(title, classes="title")
        if not self.artifacts:
            yield Static("No artifacts found for this run.")
        else:
            yield Static(f"{len(self.artifacts)} artifact(s) found.", id="artifacts_count")
            with Horizontal(id="artifacts_layout"):
                with Vertical(id="artifacts_list_panel"):
                    yield Static("Files", classes="title")
                    yield ListView(id="artifacts_list")
                with VerticalScroll(id="artifact_detail_panel"):
                    yield Static("Details", classes="title")
                    yield Static("Select an artifact.", id="artifact_detail")
        with Horizontal(classes="row"):
            yield Button("View Content", id="view_content", variant="primary")
            yield Button("Close", id="close", variant="default")

    def on_mount(self) -> None:
        if not self.artifacts:
            return
        artifacts_view = self.query_one("#artifacts_list", ListView)
        for art in self.artifacts:
            name = art.get("name", "?")
            kind = art.get("kind", "?")
            size = art.get("bytes", 0)
            size_str = self._format_size(size) if size else "-"
            label = f"{name} [{kind}] {size_str}"
            artifacts_view.append(DataListItem(label, art.get("id")))
        if self.artifacts:
            artifacts_view.index = 0
            self._render_artifact_detail(self.artifacts[0])

    def _format_size(self, size: int) -> str:
        if size < 1024:
            return f"{size}B"
        elif size < 1024 * 1024:
            return f"{size // 1024}KB"
        else:
            return f"{size // (1024 * 1024)}MB"

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        if not event.item or not isinstance(event.item, DataListItem):
            return
        artifact_id = event.item.item_id
        artifact = next((a for a in self.artifacts if a.get("id") == artifact_id), None)
        if artifact:
            self._render_artifact_detail(artifact)
            self.selected_idx = next((i for i, a in enumerate(self.artifacts) if a.get("id") == artifact_id), 0)

    def _render_artifact_detail(self, art: Dict[str, Any]) -> None:
        size = art.get("bytes", 0)
        lines = [
            f"ID: {art.get('id', '-')}",
            f"Name: {art.get('name', '-')}",
            f"Kind: {art.get('kind', '-')}",
            f"Size: {self._format_size(size) if size else '-'}",
            f"Path: {art.get('path', '-')}",
            f"SHA256: {art.get('sha256', '-')[:16]}..." if art.get("sha256") else "SHA256: -",
            f"Created: {art.get('created_at', '-')}",
        ]
        detail_widget = self.query_one("#artifact_detail", Static)
        detail_widget.update("\n".join(lines))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "close":
            self.dismiss(None)
        elif event.button.id == "view_content":
            if self.artifacts and 0 <= self.selected_idx < len(self.artifacts):
                self.dismiss(self.artifacts[self.selected_idx])
            else:
                self.dismiss(None)


class TuiDashboard(App):
    CSS = """
    Screen { layout: vertical; }

    Header { dock: top; background: $surface; }
    Footer { dock: bottom; background: $surface-darken-1; }

    .banner {
        text-align: center;
        padding: 1 2;
        color: $primary;
        background: $surface-darken-1;
        border: tall $primary 30%;
    }

    #layout { layout: vertical; height: 1fr; }
    TabbedContent { height: 1fr; }
    #context_bar, #status_bar { padding: 0 1; height: 3; }
    #context_bar { background: $surface-darken-1; }
    #status_bar { background: $surface-darken-2; }

    .panel { border: solid $surface-darken-2; padding: 1; }
    .title { color: $primary; }
    .row { padding: 0 1; }
    #dash-main { height: 1fr; }
    #dash-left, #dash-middle, #dash-right { padding: 1; }
    #dash-right Vertical { margin-bottom: 1; }

    #global_loader {
        dock: top;
        height: 1;
        background: $primary;
        color: $text;
        text-align: center;
    }

    #global_loader.hidden { display: none; }

    .success { color: $success; }
    .error { color: $error; }
    .warning { color: $warning; }
    """

    BINDINGS = [
        Binding("r", "refresh", "Refresh", priority=True),
        Binding("?", "help", "Help", priority=True),
        Binding("q", "quit", "Quit", priority=True),
        Binding("tab", "focus_next", "Next", priority=True),
        Binding("shift+tab", "focus_previous", "Prev", priority=True),
        Binding("1", "switch_page('dashboard')", "Dashboard", show=True),
        Binding("2", "switch_page('projects-page')", "Projects", show=True),
        Binding("3", "switch_page('protocols-page')", "Protocols", show=True),
        Binding("4", "switch_page('steps-page')", "Steps", show=True),
        Binding("5", "switch_page('events-page')", "Events", show=True),
        Binding("6", "switch_page('queues-page')", "Queues", show=True),
        Binding("enter", "step_menu", "Step actions", show=True),
        Binding("n", "run_next", "Run next step", show=True),
        Binding("t", "retry_latest", "Retry latest", show=True),
        Binding("y", "run_qa", "Run QA", show=True),
        Binding("a", "approve", "Approve", show=True),
        Binding("o", "open_pr", "Open PR", show=True),
        Binding("c", "configure_tokens", "Config API/token", show=True),
        Binding("f", "cycle_filter", "Step filter", show=True),
        Binding("i", "import_codemachine", "Import CodeMachine", show=True),
        Binding("k", "view_clarifications", "Clarifications", show=True),
        Binding("l", "view_logs", "View logs", show=True),
        Binding("e", "view_error", "View error", show=True),
        Binding("j", "view_jobs", "Job inspector", show=True),
    ]
    HELP_TEXT = (
        "1-6 switch pages • r refresh • f filter steps • enter step actions • "
        "n run next • t retry • y run QA • a approve • o open PR • i import CodeMachine • "
        "k clarifications • l logs • e error • j jobs • c config • q quit"
    )

    status_message = reactive("Ready")
    refreshing = reactive(False)
    auto_refresh = reactive(True)
    TITLE = "TasksGodzilla TUI"
    SUB_TITLE = "Orchestrator console"

    def __init__(self, client: APIClient, refresh_interval: float = 4.0) -> None:
        super().__init__()
        self.client = client
        self.refresh_interval = refresh_interval
        self.project_id: Optional[int] = None
        self.protocol_id: Optional[int] = None
        self.step_id: Optional[int] = None
        self.projects: List[Dict[str, Any]] = []
        self.protocols: List[Dict[str, Any]] = []
        self.steps: List[Dict[str, Any]] = []
        self.events: List[Dict[str, Any]] = []
        self.global_events: List[Dict[str, Any]] = []
        self.branches: List[str] = []
        self.queue_stats: Dict[str, Any] = {}
        self.queue_jobs: List[Dict[str, Any]] = []
        self.protocol_spec: Optional[Dict[str, Any]] = None
        self.onboarding: Optional[Dict[str, Any]] = None
        self.step_filter: Optional[str] = None
        self.job_status_filter: Optional[str] = None
        self.selected_branch: Optional[str] = None
        self.modal_open = False
        self.project_clarifications: List[Dict[str, Any]] = []
        self.protocol_clarifications: List[Dict[str, Any]] = []
        self.ci_summary: Optional[Dict[str, Any]] = None
        self.step_runs: List[Dict[str, Any]] = []
        self.last_error: Optional[Dict[str, Any]] = None
        self.policy_findings: List[Dict[str, Any]] = []

    def _record_error(self, error_type: str, message: str, context: Optional[Dict[str, Any]] = None) -> None:
        self.last_error = {
            "type": error_type,
            "message": str(message),
            "context": context or {},
            "timestamp": datetime.now().isoformat(),
        }
        short_msg = str(message)[:80] + "..." if len(str(message)) > 80 else str(message)
        self.status_message = f"Error: {short_msg} (press 'e' for details)"
        self.notify(f"{error_type}: {short_msg}", severity="error", timeout=5)

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        yield Static("Loading...", id="global_loader", classes="hidden")
        yield Static("TASKSGODZILLA • ORCHESTRATOR TUI", classes="banner")
        with Vertical(id="layout"):
            yield Static("", id="context_bar")
            with TabbedContent(id="pages", initial="dashboard"):
                with TabPane("Dashboard", id="dashboard"):
                    with Horizontal(id="dash-main"):
                        with Vertical(id="dash-left"):
                            with Vertical(id="projects-panel", classes="panel"):
                                yield Static("Projects", classes="title")
                                yield ListView(id="projects")
                            with Vertical(id="protocols-panel", classes="panel"):
                                yield Static("Protocols", classes="title")
                                yield ListView(id="protocols")
                        with Vertical(id="dash-middle"):
                            with Horizontal(id="step-actions", classes="row"):
                                yield Button("Run next", id="run_next", variant="primary")
                                yield Button("Retry", id="retry_latest")
                                yield Button("QA latest", id="run_qa")
                                yield Button("Approve", id="approve")
                                yield Button("Open PR", id="open_pr")
                                yield Button("Filter", id="filter_steps")
                            with Horizontal(id="bulk-actions", classes="row"):
                                yield Button("Retry All Failed", id="retry_all_failed", variant="warning")
                                yield Button("Approve All Pending", id="approve_all_pending", variant="success")
                            with Vertical(id="steps-panel", classes="panel"):
                                yield Static("Steps", classes="title")
                                yield Static("Filter: all", id="step_filter_label")
                                yield ListView(id="steps")
                        with VerticalScroll(id="dash-right"):
                            with Vertical(id="events-panel", classes="panel"):
                                yield Static("Protocol events", classes="title")
                                yield ListView(id="events")
                                yield LoadingIndicator(id="loader", classes="hidden")
                            with Vertical(id="recent-panel", classes="panel"):
                                yield Static("Recent events", classes="title")
                                yield ListView(id="recent_events")
                    with Horizontal(id="detail-row"):
                        with Vertical(id="protocol-detail", classes="panel"):
                            yield Static("Protocol", classes="title")
                            yield Static("", id="protocol_meta")
                            yield Static("CI/CD", classes="title")
                            yield Static("CI: n/a", id="ci_summary_text")
                            yield Static("Spec", classes="title")
                            yield Static("", id="protocol_spec")
                        with Vertical(id="step-detail", classes="panel"):
                            yield Static("Step details", classes="title")
                            yield Static("", id="step_meta")
                            with Horizontal(classes="row"):
                                yield Button("View Logs", id="view_step_logs", variant="default")
                                yield Button("Jobs", id="view_jobs", variant="default")
                            yield Static("Policy", classes="title")
                            yield Static("", id="step_policy")
                            yield Static("Runtime", classes="title")
                            yield Static("", id="step_runtime")
                        with Vertical(id="onboarding-detail", classes="panel"):
                            yield Static("Onboarding", classes="title")
                            yield Static("", id="onboarding_meta")
                            yield Static("Policy: no issues", id="policy_findings_summary")
                            yield Static("Clarifications: none pending", id="clarifications_summary")
                            with Horizontal(classes="row"):
                                yield Button("Answer", id="answer_clarifications", variant="primary")
                                yield Button("Policy", id="view_policy", variant="default")
                with TabPane("Projects", id="projects-page"):
                    with Horizontal(id="projects-layout"):
                        with Vertical(classes="panel", id="projects-full-panel"):
                            with Horizontal(classes="row"):
                                yield Button("Refresh", id="refresh_projects")
                                yield Button("New project", id="new_project", variant="primary")
                                yield Button("Branches", id="refresh_branches")
                            yield ListView(id="projects_full")
                        with Vertical(classes="panel", id="project-detail-panel"):
                            yield Static("Project detail", classes="title")
                            yield Static("", id="project_detail")
                            yield Static("Onboarding", classes="title")
                            yield Static("", id="project_onboarding")
                            yield Static("Branches", classes="title")
                            with Horizontal(classes="row"):
                                yield Button("Delete branch", id="delete_branch")
                            yield ListView(id="branches")
                with TabPane("Protocols", id="protocols-page"):
                    with Vertical(id="protocols-layout"):
                        with Horizontal(classes="row"):
                            yield Button("Refresh", id="refresh_protocols")
                            yield Button("New protocol", id="new_protocol", variant="primary")
                            yield Button("Start", id="start_protocol")
                            yield Button("Pause", id="pause_protocol")
                            yield Button("Resume", id="resume_protocol")
                            yield Button("Cancel", id="cancel_protocol")
                            yield Button("Spec audit", id="audit_spec")
                            yield Button("Import CM", id="import_codemachine")
                        with Horizontal():
                            with Vertical(classes="panel", id="protocols-full-panel"):
                                yield Static("Protocols", classes="title")
                                yield ListView(id="protocols_full")
                            with Vertical(classes="panel", id="protocol-detail-full"):
                                yield Static("Protocol detail", classes="title")
                                yield Static("", id="protocol_detail_long")
                                yield Static("Spec & validation", classes="title")
                                yield Static("", id="protocol_spec_full")
                                yield Static("Protocol events", classes="title")
                                yield ListView(id="protocol_events")
                with TabPane("Steps", id="steps-page"):
                    with Vertical():
                        with Horizontal(classes="row"):
                            yield Button("Run step", id="run_step")
                            yield Button("Run QA", id="run_qa_step")
                            yield Button("Approve", id="approve_step")
                            yield Button("Filter", id="filter_steps_steps_page")
                        with Horizontal():
                            with Vertical(classes="panel"):
                                yield Static("Steps", classes="title")
                                yield ListView(id="steps_full")
                            with Vertical(classes="panel"):
                                yield Static("Step meta", classes="title")
                                yield Static("", id="step_meta_full")
                                yield Static("Policy", classes="title")
                                yield Static("", id="step_policy_full")
                                yield Static("Runtime", classes="title")
                                yield Static("", id="step_runtime_full")
                                yield Static("Events", classes="title")
                                yield ListView(id="step_events")
                with TabPane("Events", id="events-page"):
                    with Horizontal():
                        with Vertical(classes="panel"):
                            yield Static("Protocol events", classes="title")
                            yield ListView(id="events_full")
                        with Vertical(classes="panel"):
                            yield Static("Recent events", classes="title")
                            yield ListView(id="recent_events_full")
                            yield Static("Selected event", classes="title")
                            yield Static("", id="event_detail")
                with TabPane("Queues", id="queues-page"):
                    with Vertical():
                        with Horizontal(classes="row"):
                            yield Button("Refresh queues", id="refresh_queues")
                            yield Button("Cycle job filter", id="filter_jobs")
                        yield Static("", id="queue_stats", classes="panel")
                        with Horizontal():
                            with Vertical(classes="panel"):
                                yield Static("Queue jobs", classes="title")
                                yield ListView(id="queue_jobs")
                            with Vertical(classes="panel"):
                                yield Static("Job detail", classes="title")
                                yield Static("", id="queue_job_detail")
                with TabPane("Settings", id="settings-page"):
                    with Vertical(classes="panel"):
                        yield Static("Settings", classes="title")
                        with Horizontal(classes="row"):
                            yield Button("Configure API/token", id="configure_tokens_btn", variant="primary")
                            yield Button("Toggle auto-refresh", id="toggle_refresh")
                        yield Static("", id="settings_info")
            yield Static("", id="status_bar")
        yield Footer()

    async def on_mount(self) -> None:
        loader = self.query_one("#loader", LoadingIndicator)
        loader.display = False
        await self.refresh_all()
        self.set_interval(self.refresh_interval, self._interval_refresh, pause=False)

    async def _interval_refresh(self) -> None:
        if self.auto_refresh and not self.modal_open:
            await self.refresh_all()

    async def action_help(self) -> None:
        self.status_message = self.HELP_TEXT

    async def action_switch_page(self, page: str) -> None:
        try:
            tabs = self.query_one("#pages", TabbedContent)
            tabs.active = page
            self._update_context_bar()
        except Exception:
            pass

    async def on_list_view_selected(self, event: ListView.Selected) -> None:
        lid = event.list_view.id
        if lid in ("projects", "projects_full"):
            self.project_id = event.item.item_id if isinstance(event.item, DataListItem) else None
            await self._load_onboarding()
            await self._load_protocols()
            await self._load_branches()
            await self._load_global_events()
        elif lid in ("protocols", "protocols_full"):
            self.protocol_id = event.item.item_id if isinstance(event.item, DataListItem) else None
            await self._load_steps()
            await self._load_events()
            await self._load_protocol_spec()
        elif lid in ("steps", "steps_full"):
            self.step_id = event.item.item_id if isinstance(event.item, DataListItem) else None
            self._render_step_details()
        elif lid in ("events", "protocol_events", "events_full"):
            self._render_event_detail(event.item, protocol_scope=True)
        elif lid in ("recent_events", "recent_events_full"):
            self._render_event_detail(event.item, protocol_scope=False)
        elif lid == "branches":
            self.selected_branch = event.item.item_id if isinstance(event.item, DataListItem) else None
            if self.selected_branch:
                self.status_message = f"Selected branch {self.selected_branch}"
        elif lid == "queue_jobs":
            self._render_queue_job_detail(event.item)
        self._update_context_bar()

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid == "run_next":
            await self.action_run_next()
        elif bid == "retry_latest":
            await self._retry_with_confirm()
        elif bid in ("run_qa", "run_qa_step"):
            await self.action_run_qa()
        elif bid in ("approve", "approve_step"):
            await self.action_approve()
        elif bid == "open_pr":
            await self.action_open_pr()
        elif bid in ("filter_steps", "filter_steps_steps_page"):
            await self.action_cycle_filter()
        elif bid == "new_project":
            await self._create_project()
        elif bid == "refresh_projects":
            await self._load_projects()
        elif bid == "refresh_branches":
            await self._load_branches(force=True)
        elif bid == "delete_branch":
            await self._delete_branch()
        elif bid == "new_protocol":
            await self._create_protocol()
        elif bid == "refresh_protocols":
            await self._load_protocols()
        elif bid == "start_protocol":
            await self._protocol_action("start", "Planning enqueued.")
        elif bid == "pause_protocol":
            await self._protocol_action("pause", "Protocol paused.")
        elif bid == "resume_protocol":
            await self._protocol_action("resume", "Protocol resumed.")
        elif bid == "cancel_protocol":
            await self._cancel_protocol_with_confirm()
        elif bid == "audit_spec":
            await self._run_spec_audit()
        elif bid == "run_step":
            await self._run_selected_step()
        elif bid == "import_codemachine":
            await self.action_import_codemachine()
        elif bid == "refresh_queues":
            await self._load_queue()
        elif bid == "filter_jobs":
            await self._cycle_job_filter()
        elif bid == "configure_tokens_btn":
            await self.action_configure_tokens()
        elif bid == "toggle_refresh":
            self.auto_refresh = not self.auto_refresh
            self.status_message = f"Auto-refresh {'on' if self.auto_refresh else 'off'}."
            self._render_settings()
        elif bid == "answer_clarifications":
            await self._open_clarifications_modal()
        elif bid == "view_step_logs":
            await self._view_step_logs()
        elif bid == "view_policy":
            await self._view_policy_findings()
        elif bid == "view_jobs":
            await self._open_job_inspector()
        elif bid == "retry_all_failed":
            await self._retry_all_failed()
        elif bid == "approve_all_pending":
            await self._approve_all_pending()

    async def refresh_all(self) -> None:
        if self.refreshing or self.modal_open:
            return
        self.refreshing = True
        try:
            await self._load_projects()
            await self._load_onboarding()
            await self._load_protocols()
            await self._load_steps()
            await self._load_events()
            await self._load_protocol_spec()
            await self._load_branches()
            await self._load_global_events()
            await self._load_queue()
            await self._load_clarifications()
            await self._load_ci_summary()
            await self._load_step_runs()
            await self._load_policy_findings()
            self._render_settings()
        finally:
            self.refreshing = False
        self.status_message = "Refreshed."
        self._update_context_bar()

    def _get_list(self, list_id: str) -> ListView:
        try:
            return self.query_one(f"#{list_id}", ListView)
        except Exception as exc:  # pragma: no cover - defensive
            log.error("list_lookup_failed", extra={"list_id": list_id, "error": str(exc)})
            return ListView()

    def _update_text(self, text: str, *ids: str) -> None:
        for wid in ids:
            widget = next(iter(self.query(f"#{wid}")), None)
            if isinstance(widget, Static):
                widget.update(text)

    def _update_context_bar(self) -> None:
        proj_name = next((p["name"] for p in self.projects if p["id"] == self.project_id), "-")
        proto_name = next((r["protocol_name"] for r in self.protocols if r["id"] == self.protocol_id), "-")
        step = next((s for s in self.steps if s["id"] == self.step_id), None)
        step_label = f"{step['step_index']} {step['step_name']}" if step else "-"
        page = "-"
        try:
            page = self.query_one("#pages", TabbedContent).active or "-"
        except Exception:
            pass
        self._update_text(
            f"Page: {page} • Project: {proj_name} ({self.project_id or '-'}) • "
            f"Protocol: {proto_name} ({self.protocol_id or '-'}) • Step: {step_label}",
            "context_bar",
        )

    async def _load_projects(self) -> None:
        try:
            projects = await asyncio.to_thread(self.client.get, "/projects")
        except Exception as exc:
            self.status_message = f"Error loading projects: {exc}"
            log.error("load_projects_failed", extra={"error": str(exc)})
            return
        self.projects = projects or []
        ids = {p["id"] for p in self.projects}
        if self.project_id not in ids:
            self.project_id = next(iter(ids), None)
        for list_id in ("projects", "projects_full"):
            view = self._get_list(list_id)
            view.clear()
            for proj in self.projects:
                view.append(DataListItem(f"{proj['id']} {proj['name']}", proj["id"], subtitle=proj.get("base_branch", "")))
            if self.project_id:
                self._highlight(view, self.project_id)
        self._render_project_detail()

    async def _load_protocols(self) -> None:
        self.protocols = []
        if not self.project_id:
            for list_id in ("protocols", "protocols_full"):
                self._get_list(list_id).clear()
            self._render_protocol_details()
            return
        try:
            runs = await asyncio.to_thread(self.client.get, f"/projects/{self.project_id}/protocols")
        except Exception as exc:
            self.status_message = f"Error loading protocols: {exc}"
            log.error("load_protocols_failed", extra={"error": str(exc), "project_id": self.project_id})
            return
        self.protocols = runs or []
        ids = {r["id"] for r in self.protocols}
        if self.protocol_id not in ids:
            self.protocol_id = next(iter(ids), None)
        for list_id in ("protocols", "protocols_full"):
            list_view = self._get_list(list_id)
            list_view.clear()
            for run in self.protocols:
                subtitle = f"{run['status']} · {run.get('base_branch','')}"
                list_view.append(DataListItem(f"{run['id']} {run['protocol_name']}", run["id"], subtitle=subtitle))
            if self.protocol_id:
                self._highlight(list_view, self.protocol_id)
        self._render_protocol_details()
        await self._load_steps()
        await self._load_events()
        await self._load_protocol_spec()

    async def _load_steps(self) -> None:
        self.steps = []
        for list_id in ("steps", "steps_full"):
            self._get_list(list_id).clear()
        if not self.protocol_id:
            self._render_step_details()
            return
        try:
            steps = await asyncio.to_thread(self.client.get, f"/protocols/{self.protocol_id}/steps")
        except Exception as exc:
            self.status_message = f"Error loading steps: {exc}"
            log.error("load_steps_failed", extra={"error": str(exc), "protocol_id": self.protocol_id})
            return
        self.steps = steps or []
        filtered = [s for s in self.steps if not self.step_filter or s["status"] == self.step_filter]
        if filtered:
            valid_ids = {s["id"] for s in filtered}
            if self.step_id not in valid_ids:
                self.step_id = filtered[-1]["id"]
        else:
            self.step_id = None
        for list_id in ("steps", "steps_full"):
            view = self._get_list(list_id)
            view.clear()
            for step in filtered:
                label = f"{step['step_index']}: {step['step_name']} [{step['status']}]"
                view.append(DataListItem(label, step["id"], subtitle=f"retries={step.get('retries', 0)}"))
            if self.step_id:
                self._highlight(view, self.step_id)
        filter_label = self.step_filter or "all"
        self._update_text(f"Filter: {filter_label}", "step_filter_label")
        self._render_step_details()

    async def _load_events(self) -> None:
        self.events = []
        for list_id in ("events", "protocol_events", "events_full"):
            self._get_list(list_id).clear()
        if not self.protocol_id:
            return
        try:
            events = await asyncio.to_thread(self.client.get, f"/protocols/{self.protocol_id}/events")
        except Exception as exc:
            self.status_message = f"Error loading events: {exc}"
            log.error("load_events_failed", extra={"error": str(exc), "protocol_id": self.protocol_id})
            return
        self.events = events or []
        for list_id in ("events", "protocol_events", "events_full"):
            view = self._get_list(list_id)
            for ev in reversed(self.events[-100:]):
                text = f"{ev['event_type']}: {ev['message']}"
                view.append(DataListItem(text, ev["id"]))
            if view.children:
                view.index = 0

    async def _load_global_events(self) -> None:
        params: Dict[str, Any] = {"limit": 50}
        if self.project_id:
            params["project_id"] = self.project_id
        try:
            events = await asyncio.to_thread(self.client.get, "/events", params=params)
        except Exception as exc:
            self.status_message = f"Error loading recent events: {exc}"
            log.error("load_global_events_failed", extra={"error": str(exc)})
            return
        self.global_events = events or []
        for list_id in ("recent_events", "recent_events_full"):
            view = self._get_list(list_id)
            view.clear()
            for ev in self.global_events:
                text = f"{ev['event_type']}: {ev['message']}"
                view.append(DataListItem(text, ev["id"]))
            if view.children:
                view.index = 0

    async def _load_protocol_spec(self) -> None:
        if not self.protocol_id:
            self.protocol_spec = None
            self._render_protocol_spec()
            return
        try:
            spec = await asyncio.to_thread(self.client.get, f"/protocols/{self.protocol_id}/spec")
        except Exception as exc:
            self.status_message = f"Error loading spec: {exc}"
            log.error("load_spec_failed", extra={"error": str(exc), "protocol_id": self.protocol_id})
            return
        self.protocol_spec = spec or None
        self._render_protocol_spec()

    async def _load_onboarding(self) -> None:
        if not self.project_id:
            self.onboarding = None
            self._render_onboarding()
            return
        try:
            summary = await asyncio.to_thread(self.client.get, f"/projects/{self.project_id}/onboarding")
        except Exception as exc:
            self.status_message = f"Error loading onboarding: {exc}"
            log.error("load_onboarding_failed", extra={"error": str(exc), "project_id": self.project_id})
            return
        self.onboarding = summary or None
        self._render_onboarding()

    async def _load_branches(self, force: bool = False) -> None:
        if not self.project_id:
            self.branches = []
            self._get_list("branches").clear()
            return
        if self.branches and not force:
            return
        try:
            resp = await asyncio.to_thread(self.client.get, f"/projects/{self.project_id}/branches")
            branches = resp.get("branches", []) if isinstance(resp, dict) else []
        except Exception as exc:
            self.status_message = f"Error loading branches: {exc}"
            log.error("load_branches_failed", extra={"error": str(exc), "project_id": self.project_id})
            return
        self.branches = branches
        view = self._get_list("branches")
        view.clear()
        for br in self.branches:
            view.append(DataListItem(br, br))
        if self.selected_branch:
            self._highlight(view, self.selected_branch)

    async def _load_queue(self) -> None:
        try:
            stats = await asyncio.to_thread(self.client.get, "/queues")
            params = {"status": self.job_status_filter} if self.job_status_filter else None
            jobs = await asyncio.to_thread(self.client.get, "/queues/jobs", params=params)
        except Exception as exc:
            self.status_message = f"Error loading queue: {exc}"
            log.error("load_queue_failed", extra={"error": str(exc)})
            return
        self.queue_stats = stats or {}
        self.queue_jobs = jobs or []
        self._render_queue()

    async def _load_clarifications(self) -> None:
        self.project_clarifications = []
        self.protocol_clarifications = []
        if self.project_id:
            try:
                items = await asyncio.to_thread(
                    self.client.get, f"/projects/{self.project_id}/clarifications", params={"status": "open"}
                )
                self.project_clarifications = items or []
            except Exception as exc:
                log.error("load_project_clarifications_failed", extra={"error": str(exc)})
        if self.protocol_id:
            try:
                items = await asyncio.to_thread(
                    self.client.get, f"/protocols/{self.protocol_id}/clarifications", params={"status": "open"}
                )
                self.protocol_clarifications = items or []
            except Exception as exc:
                log.error("load_protocol_clarifications_failed", extra={"error": str(exc)})
        self._render_clarifications_summary()

    async def _load_ci_summary(self) -> None:
        self.ci_summary = None
        if not self.protocol_id:
            return
        try:
            summary = await asyncio.to_thread(self.client.get, f"/protocols/{self.protocol_id}/ci/summary")
            self.ci_summary = summary
        except Exception as exc:
            log.error("load_ci_summary_failed", extra={"error": str(exc), "protocol_id": self.protocol_id})
        self._render_ci_summary()

    async def _load_step_runs(self) -> None:
        self.step_runs = []
        if not self.step_id:
            return
        try:
            runs = await asyncio.to_thread(self.client.get, f"/steps/{self.step_id}/runs")
            self.step_runs = runs or []
        except Exception as exc:
            log.error("load_step_runs_failed", extra={"error": str(exc), "step_id": self.step_id})

    async def _load_policy_findings(self) -> None:
        self.policy_findings = []
        if not self.project_id:
            self._render_policy_findings()
            return
        try:
            findings = await asyncio.to_thread(self.client.get, f"/projects/{self.project_id}/policy/findings")
            self.policy_findings = findings or []
        except Exception as exc:
            log.error("load_policy_findings_failed", extra={"error": str(exc), "project_id": self.project_id})
        self._render_policy_findings()

    def _render_policy_findings(self) -> None:
        if not self.policy_findings:
            self._update_text("Policy: no issues", "policy_findings_summary")
            return
        blocking = [f for f in self.policy_findings if f.get("severity") == "error"]
        warnings = [f for f in self.policy_findings if f.get("severity") == "warning"]
        text = f"Policy: {len(blocking)} blocking, {len(warnings)} warnings"
        if blocking:
            codes = ", ".join(f["code"] for f in blocking[:3])
            text += f" [{codes}{'...' if len(blocking) > 3 else ''}]"
        self._update_text(text, "policy_findings_summary")

    def _render_clarifications_summary(self) -> None:
        total_project = len(self.project_clarifications)
        total_protocol = len(self.protocol_clarifications)
        blocking_project = sum(1 for c in self.project_clarifications if c.get("blocking"))
        blocking_protocol = sum(1 for c in self.protocol_clarifications if c.get("blocking"))
        if total_project or total_protocol:
            text = f"Clarifications: {total_project} project ({blocking_project} blocking), {total_protocol} protocol ({blocking_protocol} blocking)"
        else:
            text = "Clarifications: none pending"
        self._update_text(text, "clarifications_summary")

    def _render_ci_summary(self) -> None:
        if not self.ci_summary:
            self._update_text("CI: n/a", "ci_summary_text")
            return
        pr_num = self.ci_summary.get("pr_number")
        pr_url = self.ci_summary.get("pr_url")
        status = self.ci_summary.get("status") or "-"
        conclusion = self.ci_summary.get("conclusion") or "-"
        check_name = self.ci_summary.get("check_name") or "-"
        pr_text = f"PR #{pr_num}" if pr_num else "no PR"
        if pr_url:
            pr_text = f"{pr_text} ({pr_url})"
        text = f"CI: {pr_text} | status={status} conclusion={conclusion} check={check_name}"
        self._update_text(text, "ci_summary_text")

    def _render_project_detail(self) -> None:
        proj = next((p for p in self.projects if p["id"] == self.project_id), None)
        if not proj:
            self._update_text("No project selected.", "project_detail")
            return
        text = (
            f"{proj['name']} [{proj.get('base_branch','-')}] • git={proj.get('git_url') or '-'}\n"
            f"Updated: {format_ts(proj.get('updated_at'))}"
        )
        self._update_text(text, "project_detail")

    def _render_protocol_details(self) -> None:
        run = next((r for r in self.protocols if r["id"] == self.protocol_id), None)
        if not run:
            self._update_text("No protocol selected.", "protocol_meta", "protocol_detail_long")
            return
        counts: Dict[str, int] = {}
        for s in self.steps:
            counts[s["status"]] = counts.get(s["status"], 0) + 1
        counts_text = ", ".join(f"{k}:{v}" for k, v in counts.items()) if counts else "no steps"
        meta = (
            f"{run['protocol_name']} [{run.get('status','-')}] • base={run.get('base_branch','-')} "
            f"• steps={counts_text}\n{run.get('description') or ''}\nupdated={run.get('updated_at','-')}"
        )
        self._update_text(meta, "protocol_meta", "protocol_detail_long")
        self._render_onboarding()

    def _render_protocol_spec(self) -> None:
        if not self.protocol_spec:
            self._update_text("Spec: n/a", "protocol_spec", "protocol_spec_full")
            return
        status = self.protocol_spec.get("validation_status") or "-"
        spec_hash = self.protocol_spec.get("spec_hash") or "-"
        validated = format_ts(self.protocol_spec.get("validated_at"))
        errors = self.protocol_spec.get("validation_errors")
        summary = f"Spec hash={spec_hash} • status={status} • validated={validated}"
        if errors:
            summary += f"\nErrors: {errors}"
        spec_body = self._format_json_block(self.protocol_spec.get("spec"), empty="No spec attached.")
        self._update_text(f"{summary}\n{spec_body}", "protocol_spec", "protocol_spec_full")

    def _render_step_details(self) -> None:
        step = next((s for s in self.steps if s["id"] == self.step_id), None)
        if not step:
            text = "Select a step to see engine, policy, and runtime details."
            self._update_text(text, "step_meta", "step_meta_full")
            self._update_text("No policy attached.", "step_policy", "step_policy_full")
            self._update_text("No runtime state yet.", "step_runtime", "step_runtime_full")
            return
        engine = step.get("engine_id") or "default"
        model = step.get("model") or "n/a"
        summary = step.get("summary") or ""
        runtime = step.get("runtime_state") or {}
        tokens_used = runtime.get("tokens_used") or step.get("tokens_used") or 0
        token_limit = runtime.get("token_limit") or step.get("token_limit") or 0
        qa_verdict = runtime.get("qa_verdict") or step.get("qa_verdict") or "-"
        qa_summary = runtime.get("qa_summary") or step.get("qa_summary") or ""
        meta_lines = [
            f"{step['step_index']}: {step['step_name']} [{step['status']}]",
            f"Engine: {engine} | Model: {model} | Type: {step.get('step_type', '')}",
            f"Retries: {step.get('retries', 0)}",
        ]
        if tokens_used or token_limit:
            budget_pct = f" ({100 * tokens_used // token_limit}%)" if token_limit else ""
            meta_lines.append(f"Tokens: {tokens_used:,} / {token_limit:,}{budget_pct}")
        if qa_verdict != "-":
            meta_lines.append(f"QA Verdict: {qa_verdict}")
        if qa_summary:
            meta_lines.append(f"QA: {qa_summary[:100]}{'...' if len(qa_summary) > 100 else ''}")
        if summary:
            meta_lines.append(f"Summary: {summary}")
        runs_info = f"Runs: {len(self.step_runs)}" if self.step_runs else "Runs: 0 (press 'l' to load)"
        meta_lines.append(runs_info)
        meta_text = "\n".join(meta_lines)
        self._update_text(meta_text, "step_meta", "step_meta_full")
        self._update_text(self._format_json_block(step.get("policy"), empty="No policy attached."), "step_policy", "step_policy_full")
        self._update_text(
            self._format_json_block(step.get("runtime_state"), empty="No runtime state yet."),
            "step_runtime",
            "step_runtime_full",
        )

    def _render_onboarding(self) -> None:
        target_ids = ["onboarding_meta", "project_onboarding"]
        if not self.onboarding:
            self._update_text("Onboarding: n/a", *target_ids)
            return
        summary = self.onboarding
        status = summary.get("status", "-")
        path = summary.get("workspace_path") or "-"
        hint = summary.get("hint")
        last = summary.get("last_event")
        last_line = ""
        if last:
            last_line = f"Last: {last.get('event_type')} {format_ts(last.get('created_at'))} {last.get('message','')}"
        stage_bits = []
        for st in summary.get("stages", []):
            stage_bits.append(f"{st.get('name')}: {st.get('status')}")
        stages_line = "; ".join(stage_bits) if stage_bits else "stages: -"
        hint_line = f"Hint: {hint}" if hint else ""
        lines = [f"Onboarding [{status}] • {path}", stages_line, last_line, hint_line]
        text = "\n".join([l for l in lines if l])
        self._update_text(text, *target_ids)

    def _render_event_detail(self, item: ListItem, protocol_scope: bool) -> None:
        if not isinstance(item, DataListItem):
            return
        event_id = item.item_id
        source = self.events if protocol_scope else self.global_events
        ev = next((e for e in source if e["id"] == event_id), None)
        if not ev:
            return
        meta = ev.get("metadata") or {}
        detail = f"{ev['event_type']} • {format_ts(ev.get('created_at'))}\n{ev['message']}"
        if meta:
            detail += "\n" + self._format_json_block(meta, empty="")
        self._update_text(detail, "event_detail")

    def _render_queue(self) -> None:
        stats_lines = [f"{k}: {v}" for k, v in sorted(self.queue_stats.items())]
        stats_text = "Queue stats\n" + "\n".join(stats_lines) if stats_lines else "Queue stats unavailable."
        self._update_text(stats_text, "queue_stats")
        jobs_view = self._get_list("queue_jobs")
        jobs_view.clear()
        for job in self.queue_jobs:
            label = f"{job.get('job_id','?')} [{job.get('status','?')}]"
            jobs_view.append(DataListItem(label, job.get("job_id")))

    def _render_queue_job_detail(self, item: ListItem) -> None:
        if not isinstance(item, DataListItem):
            return
        job_id = item.item_id
        job = next((j for j in self.queue_jobs if j.get("job_id") == job_id), None)
        if not job:
            return
        self._update_text(self._format_json_block(job, empty=""), "queue_job_detail")

    def _format_json_block(self, data: Any, empty: str) -> str:
        if data in (None, {}, []):
            return empty
        try:
            text = json.dumps(data, indent=2)
        except TypeError:
            text = str(data)
        return self._truncate_text(text)

    def _truncate_text(self, text: str, limit: int = 1600) -> str:
        if len(text) > limit:
            return f"{text[:limit]}... (truncated)"
        return text

    def _highlight(self, list_view: ListView, target_id: Any) -> None:
        for idx, item in enumerate(list_view.children):
            if isinstance(item, DataListItem) and item.item_id == target_id:
                list_view.index = idx
                break

    async def action_refresh(self) -> None:
        await self.refresh_all()

    async def action_run_next(self) -> None:
        if not self.protocol_id:
            self.status_message = "Select a protocol."
            return
        await self._post_action(f"/protocols/{self.protocol_id}/actions/run_next_step", "Next step enqueued.")

    async def action_retry_latest(self) -> None:
        await self._retry_with_confirm()

    async def action_run_qa(self) -> None:
        step = next((s for s in self.steps if s["id"] == self.step_id), None) or (self.steps[-1] if self.steps else None)
        if not step:
            self.status_message = "No steps to QA."
            return
        await self._post_action(f"/steps/{step['id']}/actions/run_qa", f"QA enqueued for {step['step_name']}.")

    async def action_approve(self) -> None:
        step = next((s for s in self.steps if s["id"] == self.step_id), None) or (self.steps[-1] if self.steps else None)
        if not step:
            self.status_message = "No steps to approve."
            return
        await self._post_action(f"/steps/{step['id']}/actions/approve", f"Approved {step['step_name']}.")
        await self._load_steps()

    async def action_open_pr(self) -> None:
        if not self.protocol_id:
            self.status_message = "Select a protocol."
            return
        await self._post_action(f"/protocols/{self.protocol_id}/actions/open_pr", "Open PR job enqueued.")
        await self._load_protocols()

    async def action_view_clarifications(self) -> None:
        await self._open_clarifications_modal()

    async def action_view_logs(self) -> None:
        await self._view_step_logs()

    async def action_view_error(self) -> None:
        if not self.last_error:
            self.status_message = "No recent errors."
            self.notify("No recent errors to display.", severity="information", timeout=2)
            return
        await self._show_modal(
            ErrorDetailScreen(
                error_type=self.last_error["type"],
                error_message=self.last_error["message"],
                context=self.last_error.get("context"),
            )
        )

    async def action_view_jobs(self) -> None:
        await self._open_job_inspector()

    async def _open_job_inspector(self) -> None:
        if not self.step_id:
            self.status_message = "Select a step to view its execution history."
            self.notify("Select a step first.", severity="warning", timeout=3)
            return
        if not self.step_runs:
            await self._load_step_runs()
        step = next((s for s in self.steps if s["id"] == self.step_id), None)
        step_name = step["step_name"] if step else ""
        result = await self._show_modal(JobInspectorScreen(self.step_runs, step_name))
        if result and isinstance(result, dict):
            action = result.get("action")
            run_id = result.get("run_id")
            if action == "logs" and run_id:
                await self._fetch_and_show_logs(run_id)
            elif action == "artifacts" and run_id:
                await self._fetch_and_show_artifacts(run_id)

    async def _fetch_and_show_logs(self, run_id: str) -> None:
        global_loader = next(iter(self.query("#global_loader")), None)
        if global_loader:
            global_loader.remove_class("hidden")
            global_loader.update("Loading logs...")
        try:
            logs = await asyncio.to_thread(self.client.get, f"/codex/runs/{run_id}/logs")
            if global_loader:
                global_loader.add_class("hidden")
            if logs:
                await self._show_modal(LogViewerScreen(f"Logs: {run_id[:12]}", logs))
            else:
                self.status_message = "No logs available."
                self.notify("No logs available for this run.", severity="warning", timeout=3)
        except Exception as exc:
            if global_loader:
                global_loader.add_class("hidden")
            self._record_error("Load Logs Failed", str(exc), {"run_id": run_id})

    async def _fetch_and_show_artifacts(self, run_id: str) -> None:
        global_loader = next(iter(self.query("#global_loader")), None)
        if global_loader:
            global_loader.remove_class("hidden")
            global_loader.update("Loading artifacts...")
        try:
            artifacts = await asyncio.to_thread(self.client.get, f"/codex/runs/{run_id}/artifacts")
            if global_loader:
                global_loader.add_class("hidden")
            if not artifacts:
                self.status_message = "No artifacts available."
                self.notify("No artifacts for this run.", severity="warning", timeout=3)
                return
            selected = await self._show_modal(ArtifactViewerScreen(artifacts, run_id))
            if selected and isinstance(selected, dict):
                await self._view_artifact_content(run_id, selected)
        except Exception as exc:
            if global_loader:
                global_loader.add_class("hidden")
            self._record_error("Load Artifacts Failed", str(exc), {"run_id": run_id})

    async def _view_artifact_content(self, run_id: str, artifact: Dict[str, Any]) -> None:
        artifact_id = artifact.get("id")
        if not artifact_id:
            return
        global_loader = next(iter(self.query("#global_loader")), None)
        if global_loader:
            global_loader.remove_class("hidden")
            global_loader.update("Loading artifact content...")
        try:
            content = await asyncio.to_thread(
                self.client.get, f"/codex/runs/{run_id}/artifacts/{artifact_id}/content"
            )
            if global_loader:
                global_loader.add_class("hidden")
            if content:
                name = artifact.get("name", "artifact")
                await self._show_modal(LogViewerScreen(f"Artifact: {name}", content))
            else:
                self.status_message = "No content available."
                self.notify("Artifact content is empty.", severity="warning", timeout=3)
        except Exception as exc:
            if global_loader:
                global_loader.add_class("hidden")
            self._record_error("Load Artifact Content Failed", str(exc), {"run_id": run_id, "artifact_id": artifact_id})

    async def _view_policy_findings(self) -> None:
        if not self.project_id:
            self.status_message = "Select a project."
            return
        if not self.policy_findings:
            await self._load_policy_findings()
        await self._show_modal(PolicyFindingsScreen(self.policy_findings))

    async def action_step_menu(self) -> None:
        if not self.protocol_id:
            self.status_message = "Select a protocol."
            return
        choice = await self._show_modal(StepActionScreen())
        if not choice:
            return
        if choice == "run_next":
            await self.action_run_next()
        elif choice == "retry_latest":
            await self._retry_with_confirm()
        elif choice == "run_qa":
            await self.action_run_qa()
        elif choice == "approve":
            await self.action_approve()
        elif choice == "open_pr":
            await self.action_open_pr()

    async def action_configure_tokens(self) -> None:
        result = await self._show_modal(TokenConfigScreen())
        if not result:
            return
        self.client.base_url = result["api_base"]
        self.client.token = result.get("api_token")
        self.client.project_token = result.get("project_token")
        self.status_message = f"Updated API base to {self.client.base_url}"
        log.info("api_config_updated", extra={"base_url": self.client.base_url})
        self._render_settings()

    async def _show_modal(self, screen: ModalScreen[Any]) -> Any:
        self.modal_open = True
        loop = asyncio.get_running_loop()
        result_future: asyncio.Future[Any] = loop.create_future()

        def _on_dismiss(result: Any) -> None:
            if not result_future.done():
                result_future.set_result(result)

        try:
            await self.push_screen(screen, callback=_on_dismiss)
            return await result_future
        finally:
            self.modal_open = False

    async def _post_action(self, path: str, success_message: str) -> None:
        global_loader = next(iter(self.query("#global_loader")), None)
        if global_loader:
            global_loader.remove_class("hidden")
            global_loader.update("Processing...")
        try:
            await asyncio.to_thread(self.client.post, path)
            self.status_message = success_message
            self.notify(success_message, severity="information", timeout=3)
            log.info("action_success", extra={"path": path, "protocol_id": self.protocol_id})
            await self._load_steps()
            await self._load_events()
        except APIClientError as exc:
            self._record_error("API Error", str(exc), {"path": path, "protocol_id": self.protocol_id})
            log.error("action_failed", extra={"path": path, "error": str(exc), "protocol_id": self.protocol_id})
        except Exception as exc:  # pragma: no cover - defensive
            self._record_error("Action Failed", str(exc), {"path": path, "protocol_id": self.protocol_id})
            log.error("action_failed", extra={"path": path, "error": str(exc), "protocol_id": self.protocol_id})
        finally:
            if global_loader:
                global_loader.add_class("hidden")

    async def _create_project(self) -> None:
        payload = await self._show_modal(ProjectCreateScreen())
        if not payload:
            return
        try:
            project = await asyncio.to_thread(self.client.post, "/projects", payload)
            msg = f"Created project {project['id']}."
            self.status_message = msg
            self.notify(msg, severity="information", timeout=3)
            self.project_id = project["id"]
            await self._load_projects()
            await self._load_onboarding()
        except Exception as exc:
            self._record_error("Create Project Failed", str(exc), {"payload": payload})

    async def _create_protocol(self) -> None:
        if not self.project_id:
            self.status_message = "Select a project."
            return
        payload = await self._show_modal(ProtocolCreateScreen())
        if not payload:
            return
        create_payload = {
            "protocol_name": payload["protocol_name"],
            "base_branch": payload["base_branch"],
            "description": payload.get("description"),
            "status": "pending",
        }
        try:
            run = await asyncio.to_thread(self.client.post, f"/projects/{self.project_id}/protocols", create_payload)
            msg = f"Created protocol {run['id']}."
            self.status_message = msg
            self.notify(msg, severity="information", timeout=3)
            self.protocol_id = run["id"]
            if payload.get("start_now"):
                await asyncio.to_thread(self.client.post, f"/protocols/{run['id']}/actions/start")
                msg = f"Protocol {run['id']} queued for planning."
                self.status_message = msg
                self.notify(msg, severity="information", timeout=3)
            await self._load_protocols()
            await self._load_steps()
        except Exception as exc:
            self._record_error("Create Protocol Failed", str(exc), {"project_id": self.project_id, "payload": create_payload})

    async def _protocol_action(self, action: str, success: str) -> None:
        if not self.protocol_id:
            self.status_message = "Select a protocol."
            return
        path = f"/protocols/{self.protocol_id}/actions/{action}"
        await self._post_action(path, success)
        await self._load_protocols()

    async def _cancel_protocol_with_confirm(self) -> None:
        if not self.protocol_id:
            self.status_message = "Select a protocol."
            return
        run = next((r for r in self.protocols if r["id"] == self.protocol_id), None)
        name = run["protocol_name"] if run else f"#{self.protocol_id}"
        confirm = await self._show_modal(
            ConfirmActionScreen(
                title="Cancel Protocol?",
                message=f"This will cancel protocol '{name}' and stop all pending steps.\nThis action cannot be undone.",
                confirm_label="Cancel Protocol",
                danger=True,
            )
        )
        if confirm:
            await self._protocol_action("cancel", "Protocol cancelled.")

    async def _retry_with_confirm(self) -> None:
        if not self.protocol_id:
            self.status_message = "Select a protocol."
            return
        latest_step = self.steps[-1] if self.steps else None
        step_name = latest_step["step_name"] if latest_step else "latest step"
        confirm = await self._show_modal(
            ConfirmActionScreen(
                title="Retry Latest Step?",
                message=f"This will retry '{step_name}'.\nAny existing work for this step may be overwritten.",
                confirm_label="Retry",
                danger=False,
            )
        )
        if confirm:
            await self._post_action(f"/protocols/{self.protocol_id}/actions/retry_latest", "Retry enqueued.")

    async def _retry_all_failed(self) -> None:
        if not self.protocol_id:
            self.status_message = "Select a protocol."
            return
        failed_steps = [s for s in self.steps if s.get("status") == "failed"]
        if not failed_steps:
            self.status_message = "No failed steps to retry."
            self.notify("No failed steps to retry.", severity="warning", timeout=3)
            return
        step_names = ", ".join(s["step_name"] for s in failed_steps[:3])
        if len(failed_steps) > 3:
            step_names += f" (+{len(failed_steps) - 3} more)"
        confirm = await self._show_modal(
            ConfirmActionScreen(
                title="Retry All Failed Steps?",
                message=f"This will retry {len(failed_steps)} failed step(s):\n{step_names}\n\nExisting work may be overwritten.",
                confirm_label="Retry All",
                danger=False,
            )
        )
        if not confirm:
            return
        global_loader = next(iter(self.query("#global_loader")), None)
        if global_loader:
            global_loader.remove_class("hidden")
            global_loader.update(f"Retrying {len(failed_steps)} steps...")
        success_count = 0
        error_count = 0
        for step in failed_steps:
            try:
                await asyncio.to_thread(self.client.post, f"/steps/{step['id']}/actions/run")
                success_count += 1
            except Exception as exc:
                error_count += 1
                log.error("bulk_retry_step_failed", extra={"step_id": step["id"], "error": str(exc)})
        if global_loader:
            global_loader.add_class("hidden")
        msg = f"Retry: {success_count} enqueued, {error_count} failed"
        self.status_message = msg
        self.notify(msg, severity="information" if error_count == 0 else "warning", timeout=4)
        await self._load_steps()
        await self._load_events()

    async def _approve_all_pending(self) -> None:
        if not self.protocol_id:
            self.status_message = "Select a protocol."
            return
        pending_steps = [s for s in self.steps if s.get("status") == "needs_qa"]
        if not pending_steps:
            self.status_message = "No steps pending approval."
            self.notify("No steps pending approval.", severity="warning", timeout=3)
            return
        step_names = ", ".join(s["step_name"] for s in pending_steps[:3])
        if len(pending_steps) > 3:
            step_names += f" (+{len(pending_steps) - 3} more)"
        confirm = await self._show_modal(
            ConfirmActionScreen(
                title="Approve All Pending Steps?",
                message=f"This will approve {len(pending_steps)} step(s) pending QA:\n{step_names}",
                confirm_label="Approve All",
                danger=False,
            )
        )
        if not confirm:
            return
        global_loader = next(iter(self.query("#global_loader")), None)
        if global_loader:
            global_loader.remove_class("hidden")
            global_loader.update(f"Approving {len(pending_steps)} steps...")
        success_count = 0
        error_count = 0
        for step in pending_steps:
            try:
                await asyncio.to_thread(self.client.post, f"/steps/{step['id']}/actions/approve")
                success_count += 1
            except Exception as exc:
                error_count += 1
                log.error("bulk_approve_step_failed", extra={"step_id": step["id"], "error": str(exc)})
        if global_loader:
            global_loader.add_class("hidden")
        msg = f"Approve: {success_count} approved, {error_count} failed"
        self.status_message = msg
        self.notify(msg, severity="information" if error_count == 0 else "warning", timeout=4)
        await self._load_steps()
        await self._load_events()

    async def _run_selected_step(self) -> None:
        if not self.step_id:
            self.status_message = "Select a step."
            return
        await self._post_action(f"/steps/{self.step_id}/actions/run", "Step enqueued.")

    async def _run_spec_audit(self) -> None:
        payload = await self._show_modal(SpecAuditScreen(self.project_id, self.protocol_id))
        if not payload:
            return
        try:
            await asyncio.to_thread(self.client.post, "/specs/audit", payload)
            self.status_message = "Spec audit enqueued."
            self.notify("Spec audit enqueued.", severity="information", timeout=3)
        except Exception as exc:
            self._record_error("Spec Audit Failed", str(exc), {"payload": payload})

    async def _delete_branch(self) -> None:
        if not self.selected_branch:
            self.status_message = "Select a branch."
            return
        confirm = await self._show_modal(BranchDeleteScreen(self.selected_branch))
        if not confirm:
            return
        branch_path = quote(self.selected_branch, safe="")
        try:
            await asyncio.to_thread(
                self.client.post,
                f"/projects/{self.project_id}/branches/{branch_path}/delete",
                {"confirm": True},
            )
            msg = f"Deleted branch {self.selected_branch}."
            self.status_message = msg
            self.notify(msg, severity="information", timeout=3)
            self.selected_branch = None
            await self._load_branches(force=True)
        except Exception as exc:
            self._record_error("Delete Branch Failed", str(exc), {"branch": self.selected_branch, "project_id": self.project_id})

    async def _cycle_job_filter(self) -> None:
        order = [None, "queued", "started", "failed", "finished"]
        idx = order.index(self.job_status_filter) if self.job_status_filter in order else 0
        self.job_status_filter = order[(idx + 1) % len(order)]
        await self._load_queue()
        label = self.job_status_filter or "all"
        self.status_message = f"Job filter: {label}"

    async def action_import_codemachine(self) -> None:
        if not self.project_id:
            self.status_message = "Select a project."
            return
        defaults: Dict[str, str] = {}
        if self.protocol_id:
            run = next((r for r in self.protocols if r["id"] == self.protocol_id), None)
            if run:
                defaults["protocol_name"] = f"{run['protocol_name']}-cm"
                defaults["base_branch"] = run.get("base_branch", "main")
        payload = await self._show_modal(ImportScreen(defaults))
        if not payload:
            return
        workspace_path = Path(payload["workspace_path"]).expanduser()
        if not workspace_path.exists():
            self.status_message = f"Workspace not found: {workspace_path}"
            self.notify(f"Workspace not found: {workspace_path}", severity="error", timeout=5)
            return
        payload["workspace_path"] = str(workspace_path)
        payload["base_branch"] = payload.get("base_branch") or defaults.get("base_branch") or "main"
        global_loader = next(iter(self.query("#global_loader")), None)
        if global_loader:
            global_loader.remove_class("hidden")
            global_loader.update("Importing workspace...")
        try:
            resp = await asyncio.to_thread(
                self.client.post, f"/projects/{self.project_id}/codemachine/import", payload
            )
            message = resp.get("message", "Imported.")
            self.status_message = message
            self.notify(message, severity="information", timeout=3)
            protocol = resp.get("protocol_run", {})
            self.protocol_id = protocol.get("id", self.protocol_id)
            await self._load_protocols()
            await self._load_steps()
            await self._load_events()
        except Exception as exc:
            self._record_error("Import Failed", str(exc), {"project_id": self.project_id, "workspace_path": str(workspace_path)})
        finally:
            if global_loader:
                global_loader.add_class("hidden")

    async def _open_clarifications_modal(self) -> None:
        all_clarifications = self.project_clarifications + self.protocol_clarifications
        if not all_clarifications:
            self.status_message = "No open clarifications."
            self.notify("No open clarifications.", severity="information", timeout=2)
            return
        result = await self._show_modal(ClarificationsScreen(all_clarifications, scope="combined"))
        if not result:
            return
        key = result["key"]
        answer = result["answer"]
        clar = next((c for c in all_clarifications if c["key"] == key), None)
        if not clar:
            return
        endpoint = ""
        if clar.get("protocol_run_id"):
            endpoint = f"/protocols/{clar['protocol_run_id']}/clarifications/{key}"
        elif clar.get("project_id"):
            endpoint = f"/projects/{clar['project_id']}/clarifications/{key}"
        if not endpoint:
            self.status_message = "Cannot determine clarification endpoint."
            return
        try:
            await asyncio.to_thread(self.client.post, endpoint, {"answer": answer})
            self.status_message = f"Answered clarification '{key}'."
            self.notify(f"Answered clarification '{key}'.", severity="information", timeout=3)
            await self._load_clarifications()
            await self._load_onboarding()
        except Exception as exc:
            self._record_error("Answer Clarification Failed", str(exc), {"key": key, "endpoint": endpoint})

    async def _view_step_logs(self) -> None:
        if not self.step_runs:
            if self.step_id:
                await self._load_step_runs()
        if not self.step_runs:
            self.status_message = "No execution runs for this step."
            self.notify("No execution runs for this step.", severity="warning", timeout=3)
            return
        latest_run = self.step_runs[0] if self.step_runs else None
        if not latest_run:
            return
        run_id = latest_run.get("run_id")
        if not run_id:
            self.status_message = "No run ID available."
            return
        global_loader = next(iter(self.query("#global_loader")), None)
        if global_loader:
            global_loader.remove_class("hidden")
            global_loader.update("Loading logs...")
        try:
            logs = await asyncio.to_thread(self.client.get, f"/codex/runs/{run_id}/logs")
            log_content = logs if isinstance(logs, str) else str(logs)
            step = next((s for s in self.steps if s["id"] == self.step_id), None)
            step_name = step["step_name"] if step else f"Step #{self.step_id}"
            await self._show_modal(LogViewerScreen(f"Logs: {step_name} (run {run_id})", log_content))
        except Exception as exc:
            self._record_error("Load Logs Failed", str(exc), {"run_id": run_id, "step_id": self.step_id})
        finally:
            if global_loader:
                global_loader.add_class("hidden")

    def watch_status_message(self, value: str) -> None:
        status_bar = self.query_one("#status_bar", Static)
        status_bar.update(value)

    def watch_refreshing(self, value: bool) -> None:
        loader = next(iter(self.query("#loader")), None)
        if loader:
            loader.display = value
        global_loader = next(iter(self.query("#global_loader")), None)
        if global_loader:
            if value:
                global_loader.remove_class("hidden")
                global_loader.update("Refreshing...")
            else:
                global_loader.add_class("hidden")

    def _render_settings(self) -> None:
        text = (
            f"API: {self.client.base_url}\n"
            f"Token: {'set' if self.client.token else '-'} • Project token: {'set' if self.client.project_token else '-'}\n"
            f"Auto-refresh: {'on' if self.auto_refresh else 'off'} • Step filter: {self.step_filter or 'all'}\n"
            f"Job filter: {self.job_status_filter or 'all'}"
        )
        self._update_text(text, "settings_info")

    async def action_cycle_filter(self) -> None:
        order = [None, "pending", "running", "needs_qa", "failed"]
        idx = order.index(self.step_filter) if self.step_filter in order else 0
        self.step_filter = order[(idx + 1) % len(order)]
        await self._load_steps()
        label = self.step_filter or "all"
        self.status_message = f"Step filter: {label}"
        self._update_text(f"Filter: {label}", "step_filter_label")


def run_tui() -> None:
    import sys

    if not sys.stdin.isatty() or not sys.stdout.isatty():  # pragma: no cover - runtime guard
        print("Textual TUI requires a TTY. Run from an interactive terminal or use tasksgodzilla_cli.", file=sys.stderr)
        raise SystemExit(1)
    config = load_config()
    init_cli_logging(config.log_level, json_output=json_logging_from_env())
    base_url = env_default("TASKSGODZILLA_API_BASE", "http://localhost:8011")
    client = APIClient(
        base_url=base_url,
        token=env_default("TASKSGODZILLA_API_TOKEN"),
        project_token=env_default("TASKSGODZILLA_PROJECT_TOKEN"),
    )
    log.info("tui_start", extra={"base_url": base_url})
    app = TuiDashboard(client)
    app.run()


if __name__ == "__main__":
    run_tui()
