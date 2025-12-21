import json
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from devgodzilla.cli.main import get_db, get_service_context

console = Console()

@click.group()
def project():
    """Project management commands."""
    pass


@project.command("list")
@click.option("--limit", default=20, help="Number of projects to show")
@click.pass_context
def list_projects(ctx, limit):
    """List all projects."""
    db = get_db()
    projects = db.list_projects()

    if ctx.obj and ctx.obj.get("JSON"):
        click.echo(
            json.dumps(
                [
                    {
                        "id": p.id,
                        "name": p.name,
                        "git_url": p.git_url,
                        "base_branch": p.base_branch,
                        "local_path": p.local_path,
                    }
                    for p in projects[:limit]
                ]
            )
        )
        return

    table = Table(title="Projects")
    table.add_column("ID", justify="right", style="cyan")
    table.add_column("Name", style="magenta")
    table.add_column("Status", style="green")
    table.add_column("Git URL")

    for p in projects[:limit]:
        status = "Active"  # p.status if hasattr(p, 'status') else "Active"
        table.add_row(str(p.id), p.name, status, p.git_url)

    console.print(table)


@project.command("show")
@click.argument("project_id", type=int)
@click.pass_context
def show_project(ctx, project_id):
    """Show project details."""
    db = get_db()
    try:
        p = db.get_project(project_id)
        if ctx.obj and ctx.obj.get("JSON"):
            click.echo(
                json.dumps(
                    {
                        "id": p.id,
                        "name": p.name,
                        "git_url": p.git_url,
                        "base_branch": p.base_branch,
                        "local_path": p.local_path,
                        "policy_pack_key": p.policy_pack_key,
                        "policy_pack_version": p.policy_pack_version,
                    }
                )
            )
            return

        console.print(f"[bold]Project: {p.name}[/bold] (ID: {p.id})")
        console.print(f"Git URL: {p.git_url}")
        console.print(f"Base Branch: {p.base_branch}")
        console.print(f"Local Path: {p.local_path}")
        console.print(f"Policy Pack: {p.policy_pack_key}@{p.policy_pack_version}")
    except KeyError:
        if ctx.obj and ctx.obj.get("JSON"):
            click.echo(json.dumps({"success": False, "error": "project_not_found"}))
        else:
            console.print(f"[red]Project {project_id} not found[/red]")


@project.command("create")
@click.argument("name")
@click.option("--repo", "git_url", required=True, help="Git repository URL")
@click.option("--branch", "base_branch", default="main", help="Base branch")
@click.option("--local-path", default=None, help="Optional local repo path (already cloned)")
@click.option("--no-onboard", is_flag=True, help="Skip auto onboarding (Windmill)")
@click.option("--no-discovery", is_flag=True, help="Disable auto discovery during onboarding")
@click.pass_context
def create_project(ctx, name, git_url, base_branch, local_path, no_onboard, no_discovery):
    """Create a new project."""
    db = get_db()
    context = get_service_context()
    if not no_onboard and not getattr(context.config, "windmill_enabled", False):
        raise click.ClickException("Windmill integration not configured; use --no-onboard to skip")

    try:
        p = db.create_project(name=name, git_url=git_url, base_branch=base_branch, local_path=local_path)
        onboarding_job_id = None
        if not no_onboard:
            from devgodzilla.services.onboarding_queue import enqueue_project_onboarding

            result = enqueue_project_onboarding(
                context,
                db,
                project_id=p.id,
                branch=base_branch,
                run_discovery_agent=not no_discovery,
            )
            onboarding_job_id = result.windmill_job_id

        payload = {
            "success": True,
            "project_id": p.id,
            "name": p.name,
            "git_url": p.git_url,
            "base_branch": p.base_branch,
            "local_path": p.local_path,
            "onboarding_queued": not no_onboard,
            "onboarding_job_id": onboarding_job_id,
        }
        if ctx.obj and ctx.obj.get("JSON"):
            click.echo(json.dumps(payload))
        else:
            console.print(f"[green]Created project {p.name} (ID: {p.id})[/green]")
            if onboarding_job_id:
                console.print(f"[green]Queued onboarding job {onboarding_job_id}[/green]")
    except Exception as e:
        if ctx.obj and ctx.obj.get("JSON"):
            click.echo(json.dumps({"success": False, "error": str(e)}))
        else:
            console.print(f"[red]Error creating project: {e}[/red]")


@project.command("discover")
@click.argument("project_id", type=int)
@click.option("--output-dir", default=None, help="Write discovery artifacts here (default: <repo>/.devgodzilla)")
@click.option("--agent", "use_agent", is_flag=True, help="Run discovery via AI agent prompt(s) (writes tasksgodzilla/*)")
@click.option("--pipeline/--single", default=True, help="Use multi-stage discovery pipeline (default: pipeline)")
@click.option("--engine", "engine_id", default="opencode", help="Engine ID for agent discovery (default: opencode)")
@click.option("--model", default=None, help="Model for agent discovery (default: engine default)")
@click.option("--timeout-seconds", type=int, default=900, help="Agent timeout in seconds")
@click.option("--stage", "stages", multiple=True, help="Discovery stage(s): inventory, architecture, api_reference, ci_notes")
@click.pass_context
def discover_project(
    ctx,
    project_id: int,
    output_dir: str | None,
    use_agent: bool,
    pipeline: bool,
    engine_id: str,
    model: str | None,
    timeout_seconds: int,
    stages: tuple[str, ...],
) -> None:
    """Generate repository discovery artifacts."""
    db = get_db()
    context = get_service_context(project_id=project_id)

    project_row = db.get_project(project_id)
    if not project_row.local_path:
        raise click.ClickException("Project has no local_path; provide it at create time or set it in DB.")

    repo_root = Path(project_row.local_path).expanduser()
    if not repo_root.exists():
        raise click.ClickException(f"local_path does not exist: {repo_root}")

    if use_agent:
        from devgodzilla.services.discovery_agent import DiscoveryAgentService

        svc = DiscoveryAgentService(context)
        result = svc.run_discovery(
            repo_root=repo_root,
            engine_id=engine_id,
            model=model,
            pipeline=pipeline,
            stages=list(stages) if stages else None,
            timeout_seconds=timeout_seconds,
            strict_outputs=True,
            project_id=project_id,
        )
        payload = {
            "success": result.success,
            "engine_id": result.engine_id,
            "model": result.model,
            "repo_root": str(result.repo_root),
            "log_path": str(result.log_path),
            "stages": [
                {
                    "stage": s.stage,
                    "prompt_path": str(s.prompt_path),
                    "success": s.success,
                    "error": s.error,
                }
                for s in result.stages
            ],
            "outputs_expected": [str(p) for p in result.expected_outputs],
            "outputs_missing": [str(p) for p in result.missing_outputs],
            "error": result.error,
        }
    else:
        from devgodzilla.services.planning import PlanningService

        planning = PlanningService(context, db)
        snapshot = planning.build_repo_snapshot(project_row, repo_root)

        out_dir = Path(output_dir).expanduser() if output_dir else (repo_root / ".devgodzilla")
        out_dir.mkdir(parents=True, exist_ok=True)
        md_path = out_dir / "discovery.md"
        meta_path = out_dir / "discovery.json"
        md_path.write_text(snapshot, encoding="utf-8")

        # Best-effort commit SHA.
        commit = None
        try:
            import subprocess

            commit = (
                subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo_root, text=True).strip()  # noqa: S603,S607
            )
        except Exception:
            commit = None

        meta = {
            "project_id": project_id,
            "git_url": project_row.git_url,
            "repo_root": str(repo_root),
            "commit": commit,
            "snapshot_path": str(md_path),
        }
        meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")

        payload = {"success": True, "discovery_md": str(md_path), "discovery_json": str(meta_path), "commit": commit}
    if ctx.obj and ctx.obj.get("JSON"):
        click.echo(json.dumps(payload))
    else:
        if use_agent:
            console.print(f"[green]✓ Agent discovery complete[/green]")
            console.print(f"  Log: {payload.get('log_path')}")
        else:
            console.print(f"[green]✓ Discovery written[/green]")
            console.print(f"  {md_path}")
            console.print(f"  {meta_path}")


@project.command("onboard")
@click.argument("project_id", type=int)
@click.option("--branch", default=None, help="Branch to checkout (defaults to project base branch)")
@click.option("--no-discovery", is_flag=True, help="Disable auto discovery during onboarding")
def onboard_project(project_id, branch, no_discovery):
    """Queue onboarding for a project (Windmill)."""
    context = get_service_context(project_id=project_id)
    if not getattr(context.config, "windmill_enabled", False):
        raise click.ClickException("Windmill integration not configured")

    db = get_db()
    try:
        from devgodzilla.services.onboarding_queue import enqueue_project_onboarding

        result = enqueue_project_onboarding(
            context,
            db,
            project_id=project_id,
            branch=branch,
            run_discovery_agent=not no_discovery,
        )
        console.print(f"[green]Queued onboarding job {result.windmill_job_id}[/green]")
    except Exception as e:
        console.print(f"[red]Error enqueueing onboarding: {e}[/red]")
