import click
import json
from rich.console import Console
from rich.table import Table

from devgodzilla.cli.main import get_service_context, get_db

console = Console()

@click.group(name="clarify")
def clarification_cli():
    """Clarification commands."""
    pass

@clarification_cli.command(name="list")
@click.option("--project", "-p", type=int, help="Filter by project ID")
@click.option("--protocol", "-r", type=int, help="Filter by protocol run ID")
@click.option("--status", "-s", help="Filter by status (open/answered)")
def list_clarifications(project, protocol, status):
    """List outstanding clarifications."""
    try:
        db = get_db()
        clarifications = db.list_clarifications(
            project_id=project,
            protocol_run_id=protocol,
            status=status,
            limit=50
        )
        
        if not clarifications:
            console.print("No clarifications found.")
            return

        table = Table(title="Clarifications")
        table.add_column("ID", style="cyan")
        table.add_column("Question", style="white")
        table.add_column("Status", style="magenta")
        table.add_column("Scope", style="blue")

        for c in clarifications:
            table.add_row(
                str(c.id), 
                c.question, 
                c.status,
                f"{c.scope}:{c.key}"
            )
        
        console.print(table)
            
    except Exception as e:
        console.print(f"[red]Error listing clarifications: {e}[/red]")

@clarification_cli.command(name="answer")
@click.argument("id", type=int)
@click.argument("answer_text")
def answer_clarification(id, answer_text):
    """Answer a clarification request."""
    try:
        db = get_db()
        # Note: DB interface might need update if it doesn't support update by ID
        # Assuming we can update or the user provided the right lookup keys.
        # For now, implemented as best effort or placeholder if DB doesn't support it directly.
        
        # Check if DB has update_clarification method
        if hasattr(db, 'answer_clarification'):
            db.answer_clarification(id, answer_text)
            console.print(f"[green]Answered clarification {id}[/green]")
        else:
            # Fallback or error if method missing
            console.print("[yellow]DB method 'answer_clarification' not implemented yet.[/yellow]")
            
    except Exception as e:
        console.print(f"[red]Error answering clarification: {e}[/red]")
