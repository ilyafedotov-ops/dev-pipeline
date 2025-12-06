#!/usr/bin/env python3
import argparse
import json
import os
import sys
import time
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional

from deksdenflow.cli.client import APIClient, APIClientError
from deksdenflow.config import load_config
from deksdenflow.logging import EXIT_RUNTIME_ERROR, EXIT_OK, init_cli_logging, json_logging_from_env
from deksdenflow.spec_tools import audit_specs
from deksdenflow.storage import create_database

DEFAULT_API_BASE = os.environ.get("DEKSDENFLOW_API_BASE", "http://localhost:8010")
DEFAULT_TOKEN = os.environ.get("DEKSDENFLOW_API_TOKEN")
DEFAULT_PROJECT_TOKEN = os.environ.get("DEKSDENFLOW_PROJECT_TOKEN")


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Interactive CLI for the DeksdenFlow orchestrator. Run with no args for interactive mode.",
    )
    parser.add_argument("--api-base", default=None, help=f"API base URL (default: {DEFAULT_API_BASE})")
    parser.add_argument("--token", default=None, help="Bearer token (or DEKSDENFLOW_API_TOKEN)")
    parser.add_argument("--project-token", default=None, help="Project token (or DEKSDENFLOW_PROJECT_TOKEN)")
    parser.add_argument("--json", dest="as_json", action="store_true", help="Print raw JSON responses.")

    subparsers = parser.add_subparsers(dest="command")

    # Projects
    projects = subparsers.add_parser("projects", help="Project commands")
    proj_sub = projects.add_subparsers(dest="action")
    proj_sub.add_parser("list", help="List projects")

    proj_create = proj_sub.add_parser("create", help="Create a project")
    proj_create.add_argument("--name", required=True, help="Project name")
    proj_create.add_argument("--git-url", required=True, help="Git URL or local path")
    proj_create.add_argument("--base-branch", default="main")
    proj_create.add_argument("--ci-provider", default=None)
    proj_create.add_argument("--default-models", default=None, help='JSON string, e.g. {"planning":"gpt-5.1-high"}')

    proj_show = proj_sub.add_parser("show", help="Show a project")
    proj_show.add_argument("project_id", type=int)

    # Protocols
    protocols = subparsers.add_parser("protocols", help="Protocol run commands")
    proto_sub = protocols.add_subparsers(dest="action")
    proto_list = proto_sub.add_parser("list", help="List protocol runs for a project")
    proto_list.add_argument("--project", type=int, required=True)

    proto_show = proto_sub.add_parser("show", help="Show a protocol run")
    proto_show.add_argument("protocol_id", type=int)

    proto_create = proto_sub.add_parser("create-and-start", help="Create a protocol and enqueue planning")
    proto_create.add_argument("--project", type=int, required=True)
    proto_create.add_argument("--name", required=True, help="Protocol name (e.g. 0001-demo)")
    proto_create.add_argument("--base-branch", default="main")
    proto_create.add_argument("--description", default=None)

    for action in ("start", "pause", "resume", "cancel", "run-next", "retry-latest", "open-pr"):
        p = proto_sub.add_parser(action, help=f"{action.replace('-', ' ').title()} a protocol")
        p.add_argument("protocol_id", type=int)

    # Steps
    steps = subparsers.add_parser("steps", help="Step commands")
    step_sub = steps.add_subparsers(dest="action")
    step_list = step_sub.add_parser("list", help="List steps for a protocol")
    step_list.add_argument("--protocol", type=int, required=True)

    for action in ("run", "run-qa", "approve"):
        s = step_sub.add_parser(action, help=f"{action.replace('-', ' ').title()} a step by ID")
        s.add_argument("step_id", type=int)

    # Events
    events = subparsers.add_parser("events", help="Events commands")
    ev_sub = events.add_subparsers(dest="action")
    ev_recent = ev_sub.add_parser("recent", help="Show recent events")
    ev_recent.add_argument("--project", type=int, default=None)
    ev_recent.add_argument("--limit", type=int, default=20)

    ev_watch = ev_sub.add_parser("watch", help="Watch events for a protocol")
    ev_watch.add_argument("--protocol", type=int, required=True)
    ev_watch.add_argument("--interval", type=float, default=2.0)

    # Queue
    queues = subparsers.add_parser("queues", help="Queue inspection")
    q_sub = queues.add_subparsers(dest="action")
    q_sub.add_parser("stats", help="Queue stats")
    q_jobs = q_sub.add_parser("jobs", help="List queue jobs")
    q_jobs.add_argument("--status", default=None, choices=["queued", "started", "failed", "finished"])

    # CodeMachine
    cm = subparsers.add_parser("codemachine", help="CodeMachine helpers")
    cm_sub = cm.add_subparsers(dest="action")
    cm_import = cm_sub.add_parser("import", help="Import a CodeMachine workspace")
    cm_import.add_argument("--project", type=int, required=True)
    cm_import.add_argument("--protocol-name", required=True)
    cm_import.add_argument("--workspace-path", required=True)
    cm_import.add_argument("--base-branch", default="main")
    cm_import.add_argument("--description", default=None)
    cm_import.add_argument("--enqueue", action="store_true", help="Enqueue import as a job instead of inline")

    spec = subparsers.add_parser("spec", help="Protocol spec utilities")
    spec_sub = spec.add_subparsers(dest="action")
    spec_validate = spec_sub.add_parser("validate", help="Validate/backfill protocol specs")
    spec_validate.add_argument("--project", type=int, help="Project ID to validate (optional)")
    spec_validate.add_argument("--protocol", type=int, help="Single protocol run ID to validate (optional)")
    spec_validate.add_argument("--backfill-missing", action="store_true", help="Backfill missing specs before validating")

    return parser.parse_args(argv)


def parse_json_arg(value: Optional[str]) -> Optional[Dict[str, Any]]:
    if not value:
        return None
    try:
        return json.loads(value)
    except json.JSONDecodeError as exc:  # pragma: no cover - user input
        raise ValueError(f"Invalid JSON: {exc}") from exc


def format_ts(ts: Optional[str]) -> str:
    if not ts:
        return "-"
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return ts


def print_table(headers: List[str], rows: Iterable[Dict[str, Any]]) -> None:
    rows_list = list(rows)
    widths = [len(h) for h in headers]
    rendered_rows: List[List[str]] = []
    for row in rows_list:
        rendered = []
        for idx, key in enumerate(headers):
            value = row.get(key, "")
            text = str(value)
            rendered.append(text)
            widths[idx] = max(widths[idx], len(text))
        rendered_rows.append(rendered)

    def _fmt(parts: List[str]) -> str:
        return "  ".join(part.ljust(widths[idx]) for idx, part in enumerate(parts))

    print(_fmt(headers))
    print(_fmt(["-" * w for w in widths]))
    for rendered in rendered_rows:
        print(_fmt(rendered))


def build_client(args: argparse.Namespace, *, transport: Optional[Any]) -> APIClient:
    api_base = args.api_base or DEFAULT_API_BASE
    token = args.token or DEFAULT_TOKEN
    project_token = args.project_token or DEFAULT_PROJECT_TOKEN
    return APIClient(api_base, token=token, project_token=project_token, transport=transport)


def handle_projects(client: APIClient, args: argparse.Namespace) -> None:
    if args.action == "list":
        projects = client.get("/projects") or []
        if args.as_json:
            print(json.dumps(projects, indent=2))
            return
        if not projects:
            print("No projects.")
            return
        rows = [
            {"ID": p["id"], "Name": p["name"], "Base": p["base_branch"], "Git": p["git_url"], "Updated": format_ts(p["updated_at"])}
            for p in projects
        ]
        print_table(["ID", "Name", "Base", "Git", "Updated"], rows)
    elif args.action == "create":
        payload = {
            "name": args.name,
            "git_url": args.git_url,
            "base_branch": args.base_branch,
            "ci_provider": args.ci_provider,
            "default_models": parse_json_arg(args.default_models),
        }
        project = client.post("/projects", payload)
        if args.as_json:
            print(json.dumps(project, indent=2))
        else:
            print(f"Created project {project['id']} ({project['name']}). Setup job enqueued.")
    elif args.action == "show":
        project = client.get(f"/projects/{args.project_id}")
        print(json.dumps(project, indent=2) if args.as_json else project)


def handle_protocols(client: APIClient, args: argparse.Namespace) -> None:
    if args.action == "list":
        runs = client.get(f"/projects/{args.project}/protocols") or []
        if args.as_json:
            print(json.dumps(runs, indent=2))
            return
        if not runs:
            print("No protocol runs.")
            return
        rows = [
            {
                "ID": r["id"],
                "Name": r["protocol_name"],
                "Status": r["status"],
                "Branch": r["base_branch"],
                "Spec": r.get("spec_hash") or "-",
                "SpecValid": r.get("spec_validation_status") or "-",
                "SpecAt": format_ts(r.get("spec_validated_at")),
                "Updated": format_ts(r["updated_at"]),
            }
            for r in runs
        ]
        print_table(["ID", "Name", "Status", "Branch", "Spec", "SpecValid", "SpecAt", "Updated"], rows)
    elif args.action == "show":
        run = client.get(f"/protocols/{args.protocol_id}")
        print(json.dumps(run, indent=2) if args.as_json else run)
    elif args.action == "create-and-start":
        payload = {
            "protocol_name": args.name,
            "status": "pending",
            "base_branch": args.base_branch,
            "worktree_path": None,
            "protocol_root": None,
            "description": args.description,
        }
        run = client.post(f"/projects/{args.project}/protocols", payload)
        start_resp = client.post(f"/protocols/{run['id']}/actions/start")
        if args.as_json:
            print(json.dumps({"protocol": run, "start": start_resp}, indent=2))
        else:
            print(f"Protocol {run['protocol_name']} created; planning enqueued (job {start_resp.get('job', {}).get('job_id', '-')}).")
    elif args.action in ("start", "pause", "resume", "cancel", "run-next", "retry-latest", "open-pr"):
        path = args.action.replace("-", "_")
        resp = client.post(f"/protocols/{args.protocol_id}/actions/{path}")
        if args.as_json:
            print(json.dumps(resp, indent=2))
        else:
            msg = resp["message"] if isinstance(resp, dict) and "message" in resp else "OK"
            print(msg)


def handle_steps(client: APIClient, args: argparse.Namespace) -> None:
    if args.action == "list":
        steps = client.get(f"/protocols/{args.protocol}/steps") or []
        if args.as_json:
            print(json.dumps(steps, indent=2))
            return
        if not steps:
            print("No steps.")
            return
        rows = [
            {
                "ID": s["id"],
                "Idx": s["step_index"],
                "Name": s["step_name"],
                "Status": s["status"],
                "Retries": s["retries"],
                "Updated": format_ts(s["updated_at"]),
            }
            for s in steps
        ]
        print_table(["ID", "Idx", "Name", "Status", "Retries", "Updated"], rows)
    elif args.action in ("run", "run-qa", "approve"):
        slug = args.action.replace("-", "_")
        resp = client.post(f"/steps/{args.step_id}/actions/{slug}")
        if args.as_json:
            print(json.dumps(resp, indent=2))
        else:
            if isinstance(resp, dict) and "message" in resp:
                print(resp["message"])
            else:
                print("OK")


def handle_events(client: APIClient, args: argparse.Namespace) -> None:
    if args.action == "recent":
        params = {"limit": args.limit}
        if args.project:
            params["project_id"] = args.project
        events = client.get("/events", params=params) or []
        if args.as_json:
            print(json.dumps(events, indent=2))
            return
        if not events:
            print("No events.")
            return
        rows = [
            {
                "Time": format_ts(e["created_at"]),
                "Type": e["event_type"],
                "Protocol": e.get("protocol_name") or e.get("protocol_run_id"),
                "Step": e.get("step_run_id") or "-",
                "Spec": (e.get("metadata") or {}).get("spec_hash") or "-",
                "Message": e["message"],
            }
            for e in events
        ]
        print_table(["Time", "Type", "Protocol", "Step", "Spec", "Message"], rows)
    elif args.action == "watch":
        last_seen = None
        try:
            while True:
                events = client.get(f"/protocols/{args.protocol}/events") or []
                fresh = [e for e in events if e["id"] != last_seen]
                if fresh:
                    last_seen = fresh[-1]["id"]
                    for e in fresh:
                        ts = format_ts(e["created_at"])
                        spec = (e.get("metadata") or {}).get("spec_hash")
                        spec_suffix = f" [spec:{spec}]" if spec else ""
                        print(f"[{ts}] {e['event_type']}{spec_suffix} :: {e['message']}")
                time.sleep(args.interval)
        except KeyboardInterrupt:  # pragma: no cover - manual stop
            pass


def handle_queues(client: APIClient, args: argparse.Namespace) -> None:
    if args.action == "stats":
        stats = client.get("/queues")
        print(json.dumps(stats, indent=2) if args.as_json else stats)
    elif args.action == "jobs":
        params = {"status": args.status} if args.status else None
        jobs = client.get("/queues/jobs", params=params) or []
        if args.as_json:
            print(json.dumps(jobs, indent=2))
            return
        if not jobs:
            print("No jobs.")
            return
        rows = [
            {
                "ID": j["job_id"],
                "Type": j["job_type"],
                "Status": j["status"],
                "Queue": j["queue"],
            }
            for j in jobs
        ]
        print_table(["ID", "Type", "Status", "Queue"], rows)


def handle_codemachine(client: APIClient, args: argparse.Namespace) -> None:
    if args.action == "import":
        payload = {
            "protocol_name": args.protocol_name,
            "workspace_path": args.workspace_path,
            "base_branch": args.base_branch,
            "description": args.description,
            "enqueue": args.enqueue,
        }
        resp = client.post(f"/projects/{args.project}/codemachine/import", payload)
        if args.as_json:
            print(json.dumps(resp, indent=2))
        else:
            message = resp.get("message") if isinstance(resp, dict) else "OK"
            print(f"{message} Protocol {resp['protocol_run']['protocol_name']}")


def handle_spec(args: argparse.Namespace) -> None:
    config = load_config()
    db = create_database(db_path=config.db_path, db_url=config.db_url, pool_size=config.db_pool_size)
    db.init_schema()
    results = audit_specs(
        db,
        project_id=getattr(args, "project", None),
        protocol_id=getattr(args, "protocol", None),
        backfill_missing=getattr(args, "backfill_missing", False),
    )
    if args.as_json:
        print(json.dumps(results, indent=2))
        return
    if not results:
        print("No matching protocol runs.")
        return
    for res in results:
        status = "ok" if not res["errors"] else "error"
        suffix = " (backfilled)" if res["backfilled"] else ""
        spec_hash = res.get("spec_hash") or "-"
        print(f"{res['protocol_name']} [{status}]{suffix} spec={spec_hash}")
        for err in res["errors"]:
            print(f"  - {err}")


def run_interactive(client: APIClient) -> None:
    state: Dict[str, Optional[int]] = {"project_id": None, "protocol_id": None}
    menu = """
Interactive DeksdenFlow CLI
---------------------------
Current project: {project}
Current protocol: {protocol}
1) List projects
2) Select project
3) Create project
4) List protocols for current project
5) Create+start protocol for current project
6) Run next step on current protocol
7) List steps for current protocol
8) Run QA on latest step
9) Approve latest step
10) Show recent events (current project)
11) Queue stats
12) Import CodeMachine workspace
q) Quit
"""
    while True:
        print(
            menu.format(
                project=state["project_id"] or "-",
                protocol=state["protocol_id"] or "-",
            )
        )
        choice = input("Choose an option: ").strip().lower()
        try:
            if choice == "1":
                projects = client.get("/projects") or []
                if not projects:
                    print("No projects.")
                    continue
                rows = [
                    {"ID": p["id"], "Name": p["name"], "Base": p["base_branch"], "Updated": format_ts(p["updated_at"])}
                    for p in projects
                ]
                print_table(["ID", "Name", "Base", "Updated"], rows)
            elif choice == "2":
                pid = input("Project ID: ").strip()
                state["project_id"] = int(pid) if pid else None
            elif choice == "3":
                name = input("Project name: ").strip()
                git_url = input("Git URL/path: ").strip()
                base_branch = input("Base branch [main]: ").strip() or "main"
                ci_provider = input("CI provider (github/gitlab/blank): ").strip() or None
                default_models_raw = input("Default models JSON (optional): ").strip() or None
                payload = {
                    "name": name,
                    "git_url": git_url,
                    "base_branch": base_branch,
                    "ci_provider": ci_provider,
                    "default_models": parse_json_arg(default_models_raw),
                }
                project = client.post("/projects", payload)
                state["project_id"] = project["id"]
                print(f"Created project {project['id']}.")
            elif choice == "4":
                if not state["project_id"]:
                    print("Select a project first.")
                    continue
                runs = client.get(f"/projects/{state['project_id']}/protocols") or []
                if not runs:
                    print("No protocol runs.")
                    continue
                rows = [
                    {
                        "ID": r["id"],
                        "Name": r["protocol_name"],
                        "Status": r["status"],
                        "Spec": r.get("spec_hash") or "-",
                        "Updated": format_ts(r["updated_at"]),
                    }
                    for r in runs
                ]
                print_table(["ID", "Name", "Status", "Spec", "Updated"], rows)
            elif choice == "5":
                if not state["project_id"]:
                    print("Select a project first.")
                    continue
                name = input("Protocol name (NNNN-task): ").strip()
                base = input("Base branch [main]: ").strip() or "main"
                desc = input("Description (optional): ").strip() or None
                payload = {
                    "protocol_name": name,
                    "status": "pending",
                    "base_branch": base,
                    "worktree_path": None,
                    "protocol_root": None,
                    "description": desc,
                }
                run = client.post(f"/projects/{state['project_id']}/protocols", payload)
                client.post(f"/protocols/{run['id']}/actions/start")
                state["protocol_id"] = run["id"]
                print(f"Protocol {run['protocol_name']} created and planning enqueued.")
            elif choice == "6":
                if not state["protocol_id"]:
                    print("Select a protocol first.")
                    continue
                resp = client.post(f"/protocols/{state['protocol_id']}/actions/run_next_step")
                message = resp["message"] if isinstance(resp, dict) and "message" in resp else "Enqueued."
                print(message)
            elif choice == "7":
                if not state["protocol_id"]:
                    print("Select a protocol first.")
                    continue
                steps = client.get(f"/protocols/{state['protocol_id']}/steps") or []
                if not steps:
                    print("No steps yet.")
                    continue
                rows = [
                    {"ID": s["id"], "Idx": s["step_index"], "Name": s["step_name"], "Status": s["status"]}
                    for s in steps
                ]
                print_table(["ID", "Idx", "Name", "Status"], rows)
            elif choice == "8":
                if not state["protocol_id"]:
                    print("Select a protocol first.")
                    continue
                steps = client.get(f"/protocols/{state['protocol_id']}/steps") or []
                if not steps:
                    print("No steps.")
                    continue
                latest = steps[-1]
                client.post(f"/steps/{latest['id']}/actions/run_qa")
                print(f"QA enqueued for {latest['step_name']}.")
            elif choice == "9":
                if not state["protocol_id"]:
                    print("Select a protocol first.")
                    continue
                steps = client.get(f"/protocols/{state['protocol_id']}/steps") or []
                if not steps:
                    print("No steps.")
                    continue
                latest = steps[-1]
                client.post(f"/steps/{latest['id']}/actions/approve")
                print(f"Approved {latest['step_name']}.")
            elif choice == "10":
                params = {"limit": 20}
                if state["project_id"]:
                    params["project_id"] = state["project_id"]
                events = client.get("/events", params=params) or []
                rows = [
                    {"Time": format_ts(e["created_at"]), "Type": e["event_type"], "Message": e["message"]}
                    for e in events
                ]
                if rows:
                    print_table(["Time", "Type", "Message"], rows)
                else:
                    print("No events.")
            elif choice == "11":
                stats = client.get("/queues")
                print(stats)
            elif choice == "12":
                if not state["project_id"]:
                    print("Select a project first.")
                    continue
                proto_name = input("Protocol name for CodeMachine run: ").strip()
                workspace = input("Workspace path: ").strip()
                base_branch = input("Base branch [main]: ").strip() or "main"
                desc = input("Description (optional): ").strip() or None
                enqueue = input("Enqueue job? [y/N]: ").strip().lower().startswith("y")
                payload = {
                    "protocol_name": proto_name,
                    "workspace_path": workspace,
                    "base_branch": base_branch,
                    "description": desc,
                    "enqueue": enqueue,
                }
                resp = client.post(f"/projects/{state['project_id']}/codemachine/import", payload)
                print(resp.get("message", "Imported."))
                state["protocol_id"] = resp["protocol_run"]["id"]
            elif choice in ("q", "quit", "exit"):
                return
            else:
                print("Unknown choice.")
        except APIClientError as exc:
            print(f"Error: {exc}")
        except ValueError as exc:
            print(f"Invalid input: {exc}")


def run_cli(argv: Optional[List[str]] = None, *, transport: Optional[Any] = None) -> int:
    args = parse_args(argv)
    init_cli_logging(os.environ.get("DEKSDENFLOW_LOG_LEVEL", "INFO"), json_output=json_logging_from_env())
    client = build_client(args, transport=transport)
    try:
        if args.command is None:
            run_interactive(client)
        elif args.command == "projects":
            handle_projects(client, args)
        elif args.command == "protocols":
            handle_protocols(client, args)
        elif args.command == "steps":
            handle_steps(client, args)
        elif args.command == "events":
            handle_events(client, args)
        elif args.command == "queues":
            handle_queues(client, args)
        elif args.command == "codemachine":
            handle_codemachine(client, args)
        elif args.command == "spec":
            handle_spec(args)
        else:  # pragma: no cover - defensive
            print("Unknown command")
            return EXIT_RUNTIME_ERROR
    except APIClientError as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_RUNTIME_ERROR
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_RUNTIME_ERROR
    return EXIT_OK


def main() -> None:
    sys.exit(run_cli())


if __name__ == "__main__":
    main()
