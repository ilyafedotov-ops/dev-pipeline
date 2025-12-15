"""
DevGodzilla CLI

Click-based command-line interface for DevGodzilla.
Provides commands for managing protocols, steps, and quality assurance.
"""

import click
import json
import sys
from pathlib import Path
from typing import Optional

from devgodzilla.logging import get_logger, init_cli_logging

logger = get_logger(__name__)

# Banner for display
BANNER = r"""
██████╗ ███████╗██╗   ██╗ ██████╗  ██████╗ ██████╗ ███████╗██╗██╗     ██╗      █████╗ 
██╔══██╗██╔════╝██║   ██║██╔════╝ ██╔═══██╗██╔══██╗╚══███╔╝██║██║     ██║     ██╔══██╗
██║  ██║█████╗  ██║   ██║██║  ███╗██║   ██║██║  ██║  ███╔╝ ██║██║     ██║     ███████║
██║  ██║██╔══╝  ╚██╗ ██╔╝██║   ██║██║   ██║██║  ██║ ███╔╝  ██║██║     ██║     ██╔══██║
██████╔╝███████╗ ╚████╔╝ ╚██████╔╝╚██████╔╝██████╔╝███████╗██║███████╗███████╗██║  ██║
╚═════╝ ╚══════╝  ╚═══╝   ╚═════╝  ╚═════╝ ╚═════╝ ╚══════╝╚═╝╚══════╝╚══════╝╚═╝  ╚═╝
"""


def get_service_context():
    """Create a ServiceContext for CLI operations."""
    from devgodzilla.config import load_config
    from devgodzilla.services.base import ServiceContext
    
    config = load_config()
    return ServiceContext(config=config)


def get_db():
    """Get database connection."""
    from devgodzilla.db.database import Database
    from devgodzilla.config import load_config
    
    config = load_config()
    db_path = Path(config.db_path) if hasattr(config, 'db_path') else Path.home() / ".devgodzilla" / "db.sqlite"
    return Database(db_path)


# =============================================================================
# Main CLI Group
# =============================================================================

@click.group()
@click.option("-v", "--verbose", is_flag=True, help="Enable verbose output")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
@click.pass_context
def cli(ctx, verbose, json_output):
    """DevGodzilla - AI Development Pipeline."""
    ctx.ensure_object(dict)
    ctx.obj["VERBOSE"] = verbose
    ctx.obj["JSON"] = json_output
    
    if verbose:
        init_cli_logging(level="DEBUG")

    # Load configuration and agents
    from devgodzilla.config import load_config
    config = load_config()
    
    # Load agent configurations if available
    if config.agent_config_path and config.agent_config_path.exists():
        try:
            from devgodzilla.services.agent_config import AgentConfigService
            from devgodzilla.services.base import ServiceContext
            agent_config = AgentConfigService(ServiceContext(config=config), str(config.agent_config_path))
            agent_config.load_config()
        except Exception as e:
            if verbose:
                click.echo(f"Warning: Failed to load agent config: {e}", err=True)

from devgodzilla.cli.projects import project
from devgodzilla.cli.agents import agent
from devgodzilla.cli.speckit import spec_cli
from devgodzilla.cli.clarifications import clarification_cli

cli.add_command(project)
cli.add_command(agent)
cli.add_command(spec_cli)
cli.add_command(clarification_cli)


@cli.command()
def version():
    """Show version information."""
    click.echo("DevGodzilla v0.1.0")


@cli.command()
def banner():
    """Show the DevGodzilla banner."""
    click.echo(BANNER)


# =============================================================================
# Protocol Commands
# =============================================================================

@cli.group()
def protocol():
    """Protocol management commands."""
    pass


@protocol.command('create')
@click.argument('project_id', type=int)
@click.argument('name')
@click.option('--description', '-d', help='Protocol description')
@click.option('--branch', '-b', help='Base branch')
@click.pass_context
def protocol_create(ctx, project_id, name, description, branch):
    """Create a new protocol run."""
    try:
        context = get_service_context()
        db = get_db()
        
        from devgodzilla.services.orchestrator import OrchestratorService
        
        orchestrator = OrchestratorService(context=context, db=db)
        result = orchestrator.create_protocol_run(
            project_id=project_id,
            protocol_name=name,
            base_branch=branch,
            description=description,
        )
        
        if ctx.obj.get('json_output'):
            click.echo(json.dumps({
                'success': True,
                'protocol_run_id': result.id if hasattr(result, 'id') else None,
                'message': 'Protocol created',
            }))
        else:
            click.echo(f"✓ Created protocol run: {name}")
            if hasattr(result, 'id'):
                click.echo(f"  ID: {result.id}")
                
    except Exception as e:
        logger.exception("Failed to create protocol")
        click.echo(f"✗ Error: {e}", err=True)
        sys.exit(1)


@protocol.command('start')
@click.argument('protocol_id', type=int)
@click.pass_context
def protocol_start(ctx, protocol_id):
    """Start a protocol run."""
    try:
        context = get_service_context()
        db = get_db()
        
        from devgodzilla.services.orchestrator import OrchestratorService
        
        orchestrator = OrchestratorService(context=context, db=db)
        result = orchestrator.start_protocol_run(protocol_id)
        
        if ctx.obj.get('json_output'):
            click.echo(json.dumps({
                'success': result.success,
                'job_id': result.job_id,
                'message': result.message,
            }))
        else:
            if result.success:
                click.echo(f"✓ Started protocol {protocol_id}")
                if result.job_id:
                    click.echo(f"  Job ID: {result.job_id}")
            else:
                click.echo(f"✗ Failed: {result.error or result.message}", err=True)
                sys.exit(1)
                
    except Exception as e:
        logger.exception("Failed to start protocol")
        click.echo(f"✗ Error: {e}", err=True)
        sys.exit(1)


@protocol.command('status')
@click.argument('protocol_id', type=int)
@click.pass_context
def protocol_status(ctx, protocol_id):
    """Get protocol status."""
    try:
        db = get_db()
        run = db.get_protocol_run(protocol_id)
        
        if not run:
            click.echo(f"✗ Protocol {protocol_id} not found", err=True)
            sys.exit(1)
        
        if ctx.obj.get('json_output'):
            click.echo(json.dumps({
                'id': run.id,
                'name': run.protocol_name,
                'status': run.status,
                'created_at': str(run.created_at) if hasattr(run, 'created_at') else None,
            }))
        else:
            click.echo(f"Protocol: {run.protocol_name}")
            click.echo(f"  Status: {run.status}")
            click.echo(f"  ID: {run.id}")
            
    except Exception as e:
        logger.exception("Failed to get protocol status")
        click.echo(f"✗ Error: {e}", err=True)
        sys.exit(1)


@protocol.command('cancel')
@click.argument('protocol_id', type=int)
@click.option('--force', '-f', is_flag=True, help='Force cancellation')
@click.pass_context
def protocol_cancel(ctx, protocol_id, force):
    """Cancel a running protocol."""
    try:
        context = get_service_context()
        db = get_db()
        
        from devgodzilla.services.orchestrator import OrchestratorService
        
        orchestrator = OrchestratorService(context=context, db=db)
        result = orchestrator.cancel_protocol(protocol_id)
        
        if ctx.obj.get('json_output'):
            click.echo(json.dumps({
                'success': result.success,
                'message': result.message,
            }))
        else:
            if result.success:
                click.echo(f"✓ Cancelled protocol {protocol_id}")
            else:
                click.echo(f"✗ Failed: {result.error or result.message}", err=True)
                sys.exit(1)
                
    except Exception as e:
        logger.exception("Failed to cancel protocol")
        click.echo(f"✗ Error: {e}", err=True)
        sys.exit(1)


@protocol.command('list')
@click.option('--project', '-p', type=int, help='Filter by project ID')
@click.option('--status', '-s', help='Filter by status')
@click.option('--limit', '-n', type=int, default=20, help='Max results')
@click.pass_context
def protocol_list(ctx, project, status, limit):
    """List protocol runs."""
    try:
        db = get_db()
        runs = db.list_protocol_runs(
            project_id=project,
            status=status,
            limit=limit,
        ) if hasattr(db, 'list_protocol_runs') else []
        
        if ctx.obj.get('json_output'):
            click.echo(json.dumps([
                {'id': r.id, 'name': r.protocol_name, 'status': r.status}
                for r in runs
            ]))
        else:
            if not runs:
                click.echo("No protocols found")
            else:
                for r in runs:
                    status_icon = "●" if r.status == "running" else "○"
                    click.echo(f"  {status_icon} [{r.id}] {r.protocol_name} ({r.status})")
                    
    except Exception as e:
        logger.exception("Failed to list protocols")
        click.echo(f"✗ Error: {e}", err=True)
        sys.exit(1)


# =============================================================================
# Step Commands
# =============================================================================

@cli.group()
def step():
    """Step management commands."""
    pass


@step.command('run')
@click.argument('step_id', type=int)
@click.pass_context
def step_run(ctx, step_id):
    """Execute a step."""
    try:
        context = get_service_context()
        db = get_db()
        
        from devgodzilla.services.orchestrator import OrchestratorService
        
        orchestrator = OrchestratorService(context=context, db=db)
        result = orchestrator.run_step(step_id)
        
        if ctx.obj.get('json_output'):
            click.echo(json.dumps({
                'success': result.success,
                'job_id': result.job_id,
                'message': result.message,
            }))
        else:
            if result.success:
                click.echo(f"✓ Started step {step_id}")
                if result.job_id:
                    click.echo(f"  Job ID: {result.job_id}")
            else:
                click.echo(f"✗ Failed: {result.error or result.message}", err=True)
                sys.exit(1)
                
    except Exception as e:
        logger.exception("Failed to run step")
        click.echo(f"✗ Error: {e}", err=True)
        sys.exit(1)


@step.command('qa')
@click.argument('step_id', type=int)
@click.option('--gates', '-g', multiple=True, help='Specific gates to run')
@click.pass_context
def step_qa(ctx, step_id, gates):
    """Run QA on a step."""
    try:
        context = get_service_context()
        db = get_db()
        
        from devgodzilla.services.quality import QualityService
        
        quality = QualityService(context=context, db=db)
        result = quality.run_qa(step_run_id=step_id)
        
        if ctx.obj.get('json_output'):
            click.echo(json.dumps({
                'step_run_id': result.step_run_id,
                'verdict': result.verdict.value if hasattr(result.verdict, 'value') else str(result.verdict),
                'gate_results': [
                    {'gate_id': g.gate_id, 'verdict': g.verdict.value}
                    for g in result.gate_results
                ],
            }))
        else:
            verdict_icon = "✓" if result.passed else "✗"
            click.echo(f"{verdict_icon} QA Verdict: {result.verdict}")
            
            for g in result.gate_results:
                gate_icon = "✓" if g.passed else "✗"
                click.echo(f"  {gate_icon} {g.gate_name}: {g.verdict}")
                for f in g.findings:
                    click.echo(f"      - {f.message}")
                    
    except Exception as e:
        logger.exception("Failed to run QA")
        click.echo(f"✗ Error: {e}", err=True)
        sys.exit(1)


@step.command('status')
@click.argument('step_id', type=int)
@click.pass_context
def step_status(ctx, step_id):
    """Get step status."""
    try:
        db = get_db()
        step = db.get_step_run(step_id)
        
        if not step:
            click.echo(f"✗ Step {step_id} not found", err=True)
            sys.exit(1)
        
        if ctx.obj.get('json_output'):
            click.echo(json.dumps({
                'id': step.id,
                'name': step.step_name,
                'status': step.status,
            }))
        else:
            click.echo(f"Step: {step.step_name}")
            click.echo(f"  Status: {step.status}")
            click.echo(f"  ID: {step.id}")
            
    except Exception as e:
        logger.exception("Failed to get step status")
        click.echo(f"✗ Error: {e}", err=True)
        sys.exit(1)


@step.command('retry')
@click.argument('step_id', type=int)
@click.pass_context
def step_retry(ctx, step_id):
    """Retry a failed or blocked step."""
    try:
        context = get_service_context()
        db = get_db()
        
        from devgodzilla.services.orchestrator import OrchestratorService
        
        orchestrator = OrchestratorService(context=context, db=db)
        result = orchestrator.retry_step(step_id)
        
        if ctx.obj.get('json_output'):
            click.echo(json.dumps({
                'success': result.success,
                'message': result.message,
            }))
        else:
            if result.success:
                click.echo(f"✓ Retrying step {step_id}")
            else:
                click.echo(f"✗ Failed: {result.error or result.message}", err=True)
                sys.exit(1)
                
    except Exception as e:
        logger.exception("Failed to retry step")
        click.echo(f"✗ Error: {e}", err=True)
        sys.exit(1)


# =============================================================================
# QA Commands
# =============================================================================

@cli.group()
def qa():
    """Quality assurance commands."""
    pass


@qa.command('evaluate')
@click.argument('workspace', type=click.Path(exists=True))
@click.argument('step_name')
@click.option('--gates', '-g', multiple=True, help='Specific gates to run')
@click.pass_context
def qa_evaluate(ctx, workspace, step_name, gates):
    """Evaluate QA gates standalone (without database)."""
    try:
        context = get_service_context()
        
        from devgodzilla.services.quality import QualityService
        from devgodzilla.qa.gates.common import TestGate, LintGate, TypeGate
        
        # Create service without DB for standalone evaluation
        quality = QualityService(
            context=context,
            db=None,
            default_gates=[TestGate(), LintGate(), TypeGate()],
        )
        
        result = quality.evaluate_step(
            workspace_root=Path(workspace),
            step_name=step_name,
        )
        
        if ctx.obj.get('json_output'):
            click.echo(json.dumps({
                'verdict': str(result.verdict),
                'duration_seconds': result.duration_seconds,
                'gate_results': [
                    {
                        'gate_id': g.gate_id,
                        'gate_name': g.gate_name,
                        'verdict': str(g.verdict),
                        'findings_count': len(g.findings),
                    }
                    for g in result.gate_results
                ],
            }))
        else:
            verdict_icon = "✓" if result.passed else "✗"
            click.echo(f"{verdict_icon} QA Verdict: {result.verdict}")
            
            if result.duration_seconds:
                click.echo(f"  Duration: {result.duration_seconds:.2f}s")
            
            click.echo("\nGate Results:")
            for g in result.gate_results:
                gate_icon = "✓" if g.passed else ("⚠" if g.verdict.value == "warn" else "✗")
                click.echo(f"  {gate_icon} {g.gate_name}: {g.verdict.value}")
                for f in g.findings[:5]:  # Limit findings shown
                    loc = f"{f.file_path}:{f.line_number}" if f.file_path else ""
                    click.echo(f"      [{f.severity}] {f.message} {loc}")
                if len(g.findings) > 5:
                    click.echo(f"      ... and {len(g.findings) - 5} more findings")
                    
    except Exception as e:
        logger.exception("Failed to evaluate QA")
        click.echo(f"✗ Error: {e}", err=True)
        sys.exit(1)


@qa.command('gates')
@click.pass_context
def qa_gates(ctx):
    """List available QA gates."""
    gates_info = [
        {'id': 'test', 'name': 'Test Gate', 'description': 'Runs pytest tests'},
        {'id': 'lint', 'name': 'Lint Gate', 'description': 'Runs ruff linter'},
        {'id': 'type', 'name': 'Type Gate', 'description': 'Runs mypy type checker'},
        {'id': 'checklist', 'name': 'Checklist Gate', 'description': 'Validates required files'},
        {'id': 'constitutional', 'name': 'Constitutional Gate', 'description': 'Checks constitution compliance'},
    ]
    
    if ctx.obj.get('json_output'):
        click.echo(json.dumps(gates_info))
    else:
        click.echo("Available QA Gates:\n")
        for g in gates_info:
            click.echo(f"  {g['id']:15} - {g['name']}")
            click.echo(f"                    {g['description']}")


# =============================================================================
# Entry Point
# =============================================================================

def main():
    """CLI entry point."""
    cli(obj={})


if __name__ == '__main__':
    main()
