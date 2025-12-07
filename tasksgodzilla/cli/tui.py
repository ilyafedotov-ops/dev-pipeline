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
    ]
    HELP_TEXT = (
        "1-6 switch pages • r refresh • f filter steps • enter step actions • "
        "n run next • t retry • y run QA • a approve • o open PR • i import CodeMachine • c config • q quit"
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

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
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
                            yield Static("Spec", classes="title")
                            yield Static("", id="protocol_spec")
                        with Vertical(id="step-detail", classes="panel"):
                            yield Static("Step details", classes="title")
                            yield Static("", id="step_meta")
                            yield Static("Policy", classes="title")
                            yield Static("", id="step_policy")
                            yield Static("Runtime", classes="title")
                            yield Static("", id="step_runtime")
                        with Vertical(id="onboarding-detail", classes="panel"):
                            yield Static("Onboarding", classes="title")
                            yield Static("", id="onboarding_meta")
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
            await self.action_retry_latest()
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
            await self._protocol_action("cancel", "Protocol cancelled.")
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
        meta_lines = [
            f"{step['step_index']}: {step['step_name']} [{step['status']}]",
            f"Engine: {engine} | Model: {model} | Type: {step.get('step_type', '')}",
            f"Retries: {step.get('retries', 0)}",
        ]
        if summary:
            meta_lines.append(f"Summary: {summary}")
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
        last = summary.get("last_event")
        last_line = ""
        if last:
            last_line = f"Last: {last.get('event_type')} {format_ts(last.get('created_at'))} {last.get('message','')}"
        stage_bits = []
        for st in summary.get("stages", []):
            stage_bits.append(f"{st.get('name')}: {st.get('status')}")
        stages_line = "; ".join(stage_bits) if stage_bits else "stages: -"
        text = f"Onboarding [{status}] • {path}\n{stages_line}\n{last_line}"
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
        if not self.protocol_id:
            self.status_message = "Select a protocol."
            return
        await self._post_action(f"/protocols/{self.protocol_id}/actions/retry_latest", "Retry enqueued.")

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
            await self.action_retry_latest()
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
        try:
            await asyncio.to_thread(self.client.post, path)
            self.status_message = success_message
            log.info("action_success", extra={"path": path, "protocol_id": self.protocol_id})
            await self._load_steps()
            await self._load_events()
        except APIClientError as exc:
            self.status_message = str(exc)
            log.error("action_failed", extra={"path": path, "error": str(exc), "protocol_id": self.protocol_id})
        except Exception as exc:  # pragma: no cover - defensive
            self.status_message = f"Error: {exc}"
            log.error("action_failed", extra={"path": path, "error": str(exc), "protocol_id": self.protocol_id})

    async def _create_project(self) -> None:
        payload = await self._show_modal(ProjectCreateScreen())
        if not payload:
            return
        try:
            project = await asyncio.to_thread(self.client.post, "/projects", payload)
            self.status_message = f"Created project {project['id']}."
            self.project_id = project["id"]
            await self._load_projects()
            await self._load_onboarding()
        except Exception as exc:
            self.status_message = f"Create project failed: {exc}"

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
            self.status_message = f"Created protocol {run['id']}."
            self.protocol_id = run["id"]
            if payload.get("start_now"):
                await asyncio.to_thread(self.client.post, f"/protocols/{run['id']}/actions/start")
                self.status_message = f"Protocol {run['id']} queued for planning."
            await self._load_protocols()
            await self._load_steps()
        except Exception as exc:
            self.status_message = f"Create protocol failed: {exc}"

    async def _protocol_action(self, action: str, success: str) -> None:
        if not self.protocol_id:
            self.status_message = "Select a protocol."
            return
        path = f"/protocols/{self.protocol_id}/actions/{action}"
        await self._post_action(path, success)
        await self._load_protocols()

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
        except Exception as exc:
            self.status_message = f"Spec audit failed: {exc}"

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
            self.status_message = f"Deleted branch {self.selected_branch}."
            await self._load_branches(force=True)
        except Exception as exc:
            self.status_message = f"Delete failed: {exc}"

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
            return
        payload["workspace_path"] = str(workspace_path)
        payload["base_branch"] = payload.get("base_branch") or defaults.get("base_branch") or "main"
        try:
            resp = await asyncio.to_thread(
                self.client.post, f"/projects/{self.project_id}/codemachine/import", payload
            )
            message = resp.get("message", "Imported.")
            self.status_message = message
            protocol = resp.get("protocol_run", {})
            self.protocol_id = protocol.get("id", self.protocol_id)
            await self._load_protocols()
            await self._load_steps()
            await self._load_events()
        except Exception as exc:
            self.status_message = f"Import failed: {exc}"

    def watch_status_message(self, value: str) -> None:
        status_bar = self.query_one("#status_bar", Static)
        status_bar.update(value)

    def watch_refreshing(self, value: bool) -> None:
        loader = next(iter(self.query("#loader")), None)
        if loader:
            loader.display = value

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
