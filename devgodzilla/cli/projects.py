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
def list_projects(limit):
    """List all projects."""
    db = get_db()
    projects = db.list_projects()
    
    table = Table(title="Projects")
    table.add_column("ID", justify="right", style="cyan")
    table.add_column("Name", style="magenta")
    table.add_column("Status", style="green")
    table.add_column("Git URL")
    
    for p in projects[:limit]:
        status = "Active" # p.status if hasattr(p, 'status') else "Active"
        table.add_row(str(p.id), p.name, status, p.git_url)
        
    console.print(table)

@project.command("show")
@click.argument("project_id", type=int)
def show_project(project_id):
    """Show project details."""
    db = get_db()
    try:
        p = db.get_project(project_id)
        console.print(f"[bold]Project: {p.name}[/bold] (ID: {p.id})")
        console.print(f"Git URL: {p.git_url}")
        console.print(f"Base Branch: {p.base_branch}")
        console.print(f"Local Path: {p.local_path}")
        console.print(f"Policy Pack: {p.policy_pack_key}@{p.policy_pack_version}")
    except KeyError:
        console.print(f"[red]Project {project_id} not found[/red]")

@project.command("create")
@click.argument("name")
@click.option("--repo", "git_url", required=True, help="Git repository URL")
@click.option("--branch", "base_branch", default="main", help="Base branch")
def create_project(name, git_url, base_branch):
    """Create a new project."""
    db = get_db()
    try:
        p = db.create_project(name=name, git_url=git_url, base_branch=base_branch)
        console.print(f"[green]Created project {p.name} (ID: {p.id})[/green]")
    except Exception as e:
        console.print(f"[red]Error creating project: {e}[/red]")

@project.command("onboard")
@click.argument("project_id", type=int)
def onboard_project(project_id):
    """Run onboarding for a project."""
    # Placeholder for onboarding logic
    console.print(f"[yellow]Onboarding logic for project {project_id} not yet implemented via CLI[/yellow]")
