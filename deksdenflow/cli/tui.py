from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Grid, Vertical, VerticalScroll
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
)

from deksdenflow.cli.client import APIClient, APIClientError
from deksdenflow.config import load_config
from deksdenflow.logging import get_logger, init_cli_logging, json_logging_from_env

log = get_logger("deksdenflow.cli.tui")


def env_default(key: str, fallback: Optional[str] = None) -> Optional[str]:
    return os.environ.get(key, fallback)


class DataListItem(ListItem):
    """List item that carries an integer ID."""

    def __init__(self, label: str, item_id: int, subtitle: str = "") -> None:
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


class TuiDashboard(App):
    CSS = """
    Screen {
        layout: grid;
        grid-size: 3 5;
        grid-rows: auto 1fr 1fr auto auto;
        grid-columns: 1fr 1fr 1fr;
    }

    Header {
        dock: top;
        background: $surface;
    }
    Footer {
        dock: bottom;
        background: $surface-darken-1;
    }

    #projects-panel, #protocols-panel, #steps-panel, #events-panel, #step-details {
        border: solid $surface-darken-2;
        padding: 1;
    }
    #projects-panel { grid-column: 1; grid-row: 2 / 4; }
    #protocols-panel { grid-column: 2; grid-row: 2; }
    #steps-panel { grid-column: 2; grid-row: 3; }
    #events-panel { grid-column: 3; grid-row: 2 / 4; }
    #step-details { grid-column: 1 / 4; grid-row: 4; }
    #status_bar {
        grid-column: 1 / span 3;
        grid-row: 5;
        height: 3;
        padding: 0 1;
    }
    .title { color: $primary; }
    .pill { border: tall $primary; padding: 0 1; }
    #step_meta, #step_policy, #step_runtime { padding: 0 1; }
    """

    BINDINGS = [
        Binding("r", "refresh", "Refresh", priority=True),
        Binding("?", "help", "Help", priority=True),
        Binding("q", "quit", "Quit", priority=True),
        Binding("tab", "focus_next", "Next pane", priority=True),
        Binding("shift+tab", "focus_previous", "Prev pane", priority=True),
        Binding("enter", "step_menu", "Step actions", show=True),
        Binding("c", "configure_tokens", "Config API/token", show=True),
        Binding("n", "run_next", "Run next step", show=True),
        Binding("t", "retry_latest", "Retry latest", show=True),
        Binding("y", "run_qa", "Run QA latest", show=True),
        Binding("a", "approve", "Approve latest", show=True),
        Binding("o", "open_pr", "Open PR", show=True),
        Binding("i", "import_codemachine", "Import CodeMachine", show=True),
    ]
    HELP_TEXT = "r refresh • tab/shift+tab focus panes • n run next • t retry • y run QA • a approve • o open PR • i import CodeMachine • q quit"

    status_message = reactive("Ready")
    refreshing = reactive(False)

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
        self.step_filter: Optional[str] = None
        self.modal_open = False

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        with Grid(id="layout"):
            with Vertical(id="projects-panel"):
                yield Static("Projects", classes="title")
                yield ListView(id="projects")
            with Vertical(id="protocols-panel"):
                yield Static("Protocols", classes="title")
                yield ListView(id="protocols")
            with Vertical(id="steps-panel"):
                yield Static("Steps", classes="title")
                yield ListView(id="steps")
            with VerticalScroll(id="events-panel"):
                yield Static("Events", classes="title")
                yield ListView(id="events")
                yield LoadingIndicator(id="loader", classes="hidden")
            with Vertical(id="step-details"):
                yield Static("Step details", classes="title")
                yield Static("", id="step_meta")
                yield Static("Policy (loop/trigger)", classes="title")
                yield Static("", id="step_policy")
                yield Static("Runtime state", classes="title")
                yield Static("", id="step_runtime")
            yield Static("", id="status_bar")
        yield Footer()

    async def on_mount(self) -> None:
        self.query_one("#loader", LoadingIndicator).display = False
        await self.refresh_all()
        self.set_interval(self.refresh_interval, self.refresh_all, pause=False)

    async def action_help(self) -> None:
        self.status_message = self.HELP_TEXT

    async def on_list_view_selected(self, event: ListView.Selected) -> None:
        if event.list_view.id == "projects":
            self.project_id = event.item.item_id if isinstance(event.item, DataListItem) else None
            await self._load_protocols()
        elif event.list_view.id == "protocols":
            self.protocol_id = event.item.item_id if isinstance(event.item, DataListItem) else None
            await self._load_steps()
            await self._load_events()
        elif event.list_view.id == "steps":
            self.step_id = event.item.item_id if isinstance(event.item, DataListItem) else None
            self._render_step_details()

    async def refresh_all(self) -> None:
        if self.refreshing or self.modal_open:
            return
        self.refreshing = True
        try:
            await self._load_projects()
            await self._load_protocols()
            await self._load_steps()
            await self._load_events()
        finally:
            self.refreshing = False

    def _get_list(self, list_id: str) -> ListView:
        return self.query_one(f"#{list_id}", ListView)

    async def _load_projects(self) -> None:
        try:
            projects = await asyncio.to_thread(self.client.get, "/projects")
        except Exception as exc:
            self.status_message = f"Error loading projects: {exc}"
            log.error("load_projects_failed", extra={"error": str(exc)})
            return
        self.projects = projects or []
        log.info("projects_loaded", extra={"count": len(self.projects)})
        list_view = self._get_list("projects")
        list_view.clear()
        for proj in self.projects:
            list_view.append(DataListItem(f"{proj['id']} {proj['name']}", proj["id"], subtitle=proj["base_branch"]))
        if self.projects:
            target = self.project_id or self.projects[0]["id"]
            self.project_id = target
            self._highlight(list_view, target)

    async def _load_protocols(self) -> None:
        list_view = self._get_list("protocols")
        list_view.clear()
        self.protocols = []
        if not self.project_id:
            return
        try:
            runs = await asyncio.to_thread(self.client.get, f"/projects/{self.project_id}/protocols")
        except Exception as exc:
            self.status_message = f"Error loading protocols: {exc}"
            log.error("load_protocols_failed", extra={"error": str(exc), "project_id": self.project_id})
            return
        self.protocols = runs or []
        log.info("protocols_loaded", extra={"count": len(self.protocols), "project_id": self.project_id})
        for run in self.protocols:
            list_view.append(
                DataListItem(
                    f"{run['id']} {run['protocol_name']}",
                    run["id"],
                    subtitle=f"{run['status']} · {run['base_branch']}",
                )
            )
        if self.protocols:
            target = self.protocol_id or self.protocols[0]["id"]
            self.protocol_id = target
            self._highlight(list_view, target)

    async def _load_steps(self) -> None:
        list_view = self._get_list("steps")
        list_view.clear()
        self.steps = []
        if not self.protocol_id:
            return
        try:
            steps = await asyncio.to_thread(self.client.get, f"/protocols/{self.protocol_id}/steps")
        except Exception as exc:
            self.status_message = f"Error loading steps: {exc}"
            log.error("load_steps_failed", extra={"error": str(exc), "protocol_id": self.protocol_id})
            return
        self.steps = steps or []
        log.info("steps_loaded", extra={"count": len(self.steps), "protocol_id": self.protocol_id})
        filtered = [s for s in self.steps if not self.step_filter or s["status"] == self.step_filter]
        for step in filtered:
            label = f"{step['step_index']}: {step['step_name']} [{step['status']}]"
            list_view.append(DataListItem(label, step["id"], subtitle=f"retries={step['retries']}"))
        if self.steps:
            target = self.step_id or self.steps[-1]["id"]
            self.step_id = target
            self._highlight(list_view, target)
        else:
            self.step_id = None
        self._render_step_details()

    async def _load_events(self) -> None:
        list_view = self._get_list("events")
        list_view.clear()
        self.events = []
        if not self.protocol_id:
            return
        try:
            events = await asyncio.to_thread(self.client.get, f"/protocols/{self.protocol_id}/events")
        except Exception as exc:
            self.status_message = f"Error loading events: {exc}"
            log.error("load_events_failed", extra={"error": str(exc), "protocol_id": self.protocol_id})
            return
        self.events = events or []
        log.info("events_loaded", extra={"count": len(self.events), "protocol_id": self.protocol_id})
        for ev in reversed(self.events[-50:]):
            text = f"{ev['event_type']}: {ev['message']}"
            if ev.get("metadata"):
                text += f" • {json.dumps(ev['metadata'])}"
            list_view.append(DataListItem(text, ev["id"]))

    def _highlight(self, list_view: ListView, target_id: int) -> None:
        for idx, item in enumerate(list_view.children):
            if isinstance(item, DataListItem) and item.item_id == target_id:
                list_view.index = idx
                break

    def _render_step_details(self) -> None:
        meta_widget = self.query_one("#step_meta", Static)
        policy_widget = self.query_one("#step_policy", Static)
        runtime_widget = self.query_one("#step_runtime", Static)
        if not self.steps:
            meta_widget.update("Select a step to see engine and policy details.")
            policy_widget.update("No policy attached.")
            runtime_widget.update("No runtime state yet.")
            return
        step = next((s for s in self.steps if s["id"] == self.step_id), None)
        if not step:
            step = self.steps[-1]
            self.step_id = step["id"]
            self._highlight(self._get_list("steps"), self.step_id)
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
        meta_widget.update("\n".join(meta_lines))
        policy_widget.update(self._format_json_block(step.get("policy"), empty="No policy attached."))
        runtime_widget.update(self._format_json_block(step.get("runtime_state"), empty="No runtime state yet."))

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

    async def action_refresh(self) -> None:
        await self.refresh_all()
        self.status_message = "Refreshed."

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
        latest = self.steps[-1] if self.steps else None
        if not latest:
            self.status_message = "No steps to QA."
            return
        await self._post_action(f"/steps/{latest['id']}/actions/run_qa", f"QA enqueued for {latest['step_name']}.")

    async def action_approve(self) -> None:
        latest = self.steps[-1] if self.steps else None
        if not latest:
            self.status_message = "No steps to approve."
            return
        await self._post_action(f"/steps/{latest['id']}/actions/approve", f"Approved {latest['step_name']}.")
        await self._load_steps()

    async def action_open_pr(self) -> None:
        if not self.protocol_id:
            self.status_message = "Select a protocol."
            return
        await self._post_action(f"/protocols/{self.protocol_id}/actions/open_pr", "Open PR job enqueued.")

    async def action_import_codemachine(self) -> None:
        if not self.project_id:
            self.status_message = "Select a project."
            return
        defaults = {}
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

    def watch_status_message(self, value: str) -> None:
        status_bar = self.query_one("#status_bar", Static)
        status_bar.update(value)

    def watch_refreshing(self, value: bool) -> None:
        loader = self.query_one("#loader", LoadingIndicator)
        loader.display = value

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

    async def _show_modal(self, screen: ModalScreen[Any]) -> Any:
        self.modal_open = True
        try:
            return await self.push_screen_wait(screen)
        finally:
            self.modal_open = False


def run_tui() -> None:
    import sys

    if not sys.stdin.isatty() or not sys.stdout.isatty():  # pragma: no cover - runtime guard
        print("Textual TUI requires a TTY. Run from an interactive terminal or use deksdenflow_cli.", file=sys.stderr)
        raise SystemExit(1)
    config = load_config()
    init_cli_logging(config.log_level, json_output=json_logging_from_env())
    base_url = env_default("DEKSDENFLOW_API_BASE", "http://localhost:8010")
    client = APIClient(
        base_url=base_url,
        token=env_default("DEKSDENFLOW_API_TOKEN"),
        project_token=env_default("DEKSDENFLOW_PROJECT_TOKEN"),
    )
    log.info("tui_start", extra={"base_url": base_url})
    app = TuiDashboard(client)
    app.run()


if __name__ == "__main__":
    run_tui()
