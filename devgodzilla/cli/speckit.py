"""
DevGodzilla SpecKit CLI Commands

Commands for spec-driven development: initialization, spec generation,
planning, and task management.
"""

import json
import sys
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.markdown import Markdown

console = Console()


def get_service_context():
    from devgodzilla.cli.main import get_service_context as _get_ctx
    return _get_ctx()


def get_db():
    from devgodzilla.cli.main import get_db as _get_db
    return _get_db()


def get_specification_service(db=None):
    from devgodzilla.services.specification import SpecificationService
    ctx = get_service_context()
    return SpecificationService(ctx, db)


@click.group(name="spec")
def spec_cli():
    """SpecKit integration commands for spec-driven development."""
    pass


@spec_cli.command(name="init")
@click.argument("directory", default=".")
@click.option("--project-id", "-p", type=int, help="Link to project ID in database")
@click.option("--constitution", "-c", type=click.Path(exists=True), help="Path to custom constitution file")
@click.pass_context
def init(ctx, directory, project_id, constitution):
    """Initialize .specify directory structure.

    Creates the SpecKit directory structure with default templates
    and constitution file.
    """
    db = get_db() if project_id else None
    service = get_specification_service(db)

    constitution_content = None
    if constitution:
        constitution_content = Path(constitution).read_text()

    result = service.init_project(
        directory,
        constitution_content=constitution_content,
        project_id=project_id,
    )

    if ctx.obj and ctx.obj.get("JSON"):
        click.echo(json.dumps({
            "success": result.success,
            "path": result.spec_path,
            "constitution_hash": result.constitution_hash,
            "error": result.error,
        }))
    else:
        if result.success:
            console.print(f"[green]✓ Initialized SpecKit in {directory}[/green]")
            console.print(f"  Path: {result.spec_path}")
            if result.constitution_hash:
                console.print(f"  Constitution hash: {result.constitution_hash}")
            if result.warnings:
                for w in result.warnings:
                    console.print(f"  [yellow]⚠ {w}[/yellow]")
        else:
            console.print(f"[red]✗ Failed: {result.error}[/red]")
            sys.exit(1)


@spec_cli.command(name="constitution")
@click.argument("directory", default=".")
@click.option("--edit", "-e", is_flag=True, help="Open in editor")
@click.pass_context
def show_constitution(ctx, directory, edit):
    """Show or edit the project constitution."""
    service = get_specification_service()
    content = service.get_constitution(directory)

    if content is None:
        console.print("[yellow]No constitution found. Run 'devgodzilla spec init' first.[/yellow]")
        sys.exit(1)

    if edit:
        import tempfile
        import subprocess
        import os

        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write(content)
            temp_path = f.name

        editor = os.environ.get("EDITOR", "nano")
        subprocess.run([editor, temp_path])

        new_content = Path(temp_path).read_text()
        Path(temp_path).unlink()

        if new_content != content:
            result = service.save_constitution(directory, new_content)
            if result.success:
                console.print("[green]✓ Constitution saved[/green]")
            else:
                console.print(f"[red]✗ Failed: {result.error}[/red]")
    else:
        if ctx.obj and ctx.obj.get("JSON"):
            click.echo(json.dumps({"content": content}))
        else:
            console.print(Panel(Markdown(content), title="Project Constitution"))


@spec_cli.command(name="specify")
@click.argument("description")
@click.option("--directory", "-d", default=".", help="Project directory")
@click.option("--name", "-n", help="Feature name (auto-generated if not provided)")
@click.option("--project-id", "-p", type=int, help="Project ID in database")
@click.pass_context
def specify(ctx, description, directory, name, project_id):
    """Generate a feature specification from a description.

    Creates a new spec directory with spec.md file based on the
    provided description.

    Example:
        devgodzilla spec specify "Add user authentication with OAuth2"
    """
    db = get_db() if project_id else None
    service = get_specification_service(db)

    result = service.run_specify(
        directory,
        description,
        feature_name=name,
        project_id=project_id,
    )

    if ctx.obj and ctx.obj.get("JSON"):
        click.echo(json.dumps({
            "success": result.success,
            "spec_path": result.spec_path,
            "spec_number": result.spec_number,
            "feature_name": result.feature_name,
            "error": result.error,
        }))
    else:
        if result.success:
            console.print(f"[green]✓ Created specification #{result.spec_number}[/green]")
            console.print(f"  Feature: {result.feature_name}")
            console.print(f"  Path: {result.spec_path}")
            console.print("\n[dim]Next: Edit the spec, then run 'devgodzilla spec plan'[/dim]")
        else:
            console.print(f"[red]✗ Failed: {result.error}[/red]")
            sys.exit(1)


@spec_cli.command(name="plan")
@click.argument("spec_path", type=click.Path(exists=True))
@click.option("--directory", "-d", default=".", help="Project directory")
@click.option("--project-id", "-p", type=int, help="Project ID in database")
@click.pass_context
def plan(ctx, spec_path, directory, project_id):
    """Generate an implementation plan from a spec.

    Creates plan.md, data-model.md, and contracts/ directory.

    Example:
        devgodzilla spec plan .specify/specs/001-auth/spec.md
    """
    db = get_db() if project_id else None
    service = get_specification_service(db)

    result = service.run_plan(
        directory,
        spec_path,
        project_id=project_id,
    )

    if ctx.obj and ctx.obj.get("JSON"):
        click.echo(json.dumps({
            "success": result.success,
            "plan_path": result.plan_path,
            "data_model_path": result.data_model_path,
            "contracts_path": result.contracts_path,
            "error": result.error,
        }))
    else:
        if result.success:
            console.print("[green]✓ Generated implementation plan[/green]")
            console.print(f"  Plan: {result.plan_path}")
            console.print(f"  Data Model: {result.data_model_path}")
            console.print(f"  Contracts: {result.contracts_path}")
            console.print("\n[dim]Next: Review the plan, then run 'devgodzilla spec tasks'[/dim]")
        else:
            console.print(f"[red]✗ Failed: {result.error}[/red]")
            sys.exit(1)


@spec_cli.command(name="tasks")
@click.argument("plan_path", type=click.Path(exists=True))
@click.option("--directory", "-d", default=".", help="Project directory")
@click.option("--project-id", "-p", type=int, help="Project ID in database")
@click.pass_context
def tasks(ctx, plan_path, directory, project_id):
    """Generate a task list from a plan.

    Creates tasks.md with parallelizable task markers.

    Example:
        devgodzilla spec tasks .specify/specs/001-auth/plan.md
    """
    db = get_db() if project_id else None
    service = get_specification_service(db)

    result = service.run_tasks(
        directory,
        plan_path,
        project_id=project_id,
    )

    if ctx.obj and ctx.obj.get("JSON"):
        click.echo(json.dumps({
            "success": result.success,
            "tasks_path": result.tasks_path,
            "task_count": result.task_count,
            "parallelizable_count": result.parallelizable_count,
            "error": result.error,
        }))
    else:
        if result.success:
            console.print("[green]✓ Generated task list[/green]")
            console.print(f"  Path: {result.tasks_path}")
            console.print(f"  Total tasks: {result.task_count}")
            console.print(f"  Parallelizable: {result.parallelizable_count}")
            console.print("\n[dim]Ready for implementation![/dim]")
        else:
            console.print(f"[red]✗ Failed: {result.error}[/red]")
            sys.exit(1)


@spec_cli.command(name="list")
@click.argument("directory", default=".")
@click.pass_context
def list_specs(ctx, directory):
    """List all specs in a project."""
    service = get_specification_service()
    specs = service.list_specs(directory)

    if ctx.obj and ctx.obj.get("JSON"):
        click.echo(json.dumps(specs))
    else:
        if not specs:
            console.print("[yellow]No specs found. Run 'devgodzilla spec specify' to create one.[/yellow]")
            return

        table = Table(title="Specifications")
        table.add_column("Name", style="cyan")
        table.add_column("Spec", justify="center")
        table.add_column("Plan", justify="center")
        table.add_column("Tasks", justify="center")

        for spec in specs:
            table.add_row(
                spec["name"],
                "✓" if spec["has_spec"] else "-",
                "✓" if spec["has_plan"] else "-",
                "✓" if spec["has_tasks"] else "-",
            )

        console.print(table)


@spec_cli.command(name="status")
@click.argument("directory", default=".")
@click.pass_context
def status(ctx, directory):
    """Show SpecKit status for a project."""
    service = get_specification_service()

    from pathlib import Path
    specify_path = Path(directory) / ".specify"
    initialized = specify_path.exists()

    if ctx.obj and ctx.obj.get("JSON"):
        specs = service.list_specs(directory) if initialized else []
        click.echo(json.dumps({
            "initialized": initialized,
            "spec_count": len(specs),
            "specs": specs,
        }))
    else:
        if not initialized:
            console.print("[yellow]SpecKit not initialized in this directory.[/yellow]")
            console.print("[dim]Run 'devgodzilla spec init' to get started.[/dim]")
            return

        specs = service.list_specs(directory)
        constitution = service.get_constitution(directory)

        console.print(Panel.fit(
            f"[green]✓ SpecKit initialized[/green]\n"
            f"  Specs: {len(specs)}\n"
            f"  Constitution: {'✓' if constitution else '✗'}",
            title="SpecKit Status"
        ))

        if specs:
            console.print("\nRecent specs:")
            for spec in specs[-5:]:
                status_parts = []
                if spec["has_spec"]:
                    status_parts.append("spec")
                if spec["has_plan"]:
                    status_parts.append("plan")
                if spec["has_tasks"]:
                    status_parts.append("tasks")
                status_str = " → ".join(status_parts) if status_parts else "empty"
                console.print(f"  • {spec['name']} [{status_str}]")


@spec_cli.command(name="show")
@click.argument("spec_name")
@click.argument("directory", default=".")
@click.option("--file", "-f", type=click.Choice(["spec", "plan", "tasks", "data-model"]), default="spec")
@click.pass_context
def show_spec(ctx, spec_name, directory, file):
    """Show contents of a spec file.

    Example:
        devgodzilla spec show 001-auth --file plan
    """
    spec_dir = Path(directory) / ".specify" / "specs" / spec_name

    if not spec_dir.exists():
        console.print(f"[red]✗ Spec '{spec_name}' not found[/red]")
        sys.exit(1)

    file_map = {
        "spec": "spec.md",
        "plan": "plan.md",
        "tasks": "tasks.md",
        "data-model": "data-model.md",
    }

    file_path = spec_dir / file_map[file]

    if not file_path.exists():
        console.print(f"[yellow]{file_map[file]} not found for '{spec_name}'[/yellow]")
        sys.exit(1)

    content = file_path.read_text()

    if ctx.obj and ctx.obj.get("JSON"):
        click.echo(json.dumps({"content": content}))
    else:
        console.print(Panel(Markdown(content), title=f"{spec_name}/{file_map[file]}"))
