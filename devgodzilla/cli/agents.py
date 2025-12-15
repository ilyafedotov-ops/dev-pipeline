import click
from rich.console import Console
from rich.table import Table

from devgodzilla.engines.registry import get_registry

console = Console()

@click.group()
def agent():
    """Agent management commands."""
    pass

@agent.command("list")
def list_agents():
    """List available agents."""
    registry = get_registry()
    agents = registry.list_metadata()
    
    table = Table(title="Available Agents")
    table.add_column("ID", style="cyan")
    table.add_column("Name", style="magenta")
    table.add_column("Kind", style="green")
    
    if not agents:
        console.print("[yellow]No agents registered[/yellow]")
        return

    for a in agents:
        table.add_row(a.id, a.display_name, str(a.kind))
        
    console.print(table)
    
@agent.command("test")
@click.argument("agent_id")
def test_agent(agent_id):
    """Test agent availability."""
    registry = get_registry()
    try:
        engine = registry.get(agent_id)
        is_available = engine.check_availability()
        if is_available:
            console.print(f"[green]Agent {agent_id} is available[/green]")
        else:
            console.print(f"[red]Agent {agent_id} is unavailable[/red]")
    except Exception as e:
        console.print(f"[red]Error testing agent: {e}[/red]")
