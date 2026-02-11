import shutil
import typer
from pathlib import Path
from typing import Optional
from rich.table import Table
from rich.panel import Panel
from dataclasses import asdict

from ..utils import console, load_mcp_config, settings_mgr

app = typer.Typer(help="Manage MCP server configuration.", rich_markup_mode="rich")

@app.callback(invoke_without_command=True)
def show(
    ctx: typer.Context,
    mcp_path: Optional[Path] = typer.Option(
        None, "--mcp-path", "-mp", help="Update the global MCP config path and exit."
    ),
    validate: bool = typer.Option(
        False, "--validate", help="Check if server commands exist in system PATH."
    ),
    show_settings: bool = typer.Option(
        False, "--show", help="Display all CLI global settings and exit."
    ),
) -> None:
    """
    Manage the MCP server configuration and CLI settings.
    """
    if ctx.invoked_subcommand is not None:
        return
    
    # 1. Action: Update global path
    if mcp_path:
        if not mcp_path.exists():
            console.print(f"[red]Error:[/red] Path {mcp_path} does not exist.")
            raise typer.Exit(1)
        settings_mgr.update_mcp_path(mcp_path)
        console.print(f"[green]Global MCP config path updated.[/green]")
        raise typer.Exit()

    # 2. Action: Show ALL CLI global settings
    if show_settings:
        settings = settings_mgr.load()
        settings_dict = asdict(settings)
        
        table = Table(title="[bold blue]CLI Global Settings[/bold blue]", show_header=True, header_style="bold cyan")
        table.add_column("Setting")
        table.add_column("Value")

        for key, value in settings_dict.items():
            display_value = str(value) if value is not None else "[dim]Not Set[/dim]"
            table.add_row(key, display_value)
            
        console.print(table)
        raise typer.Exit()

    # 3. Default Action: Display MCP Server Table
    mcp_config = load_mcp_config()

    if not mcp_config.servers:
        console.print("[yellow]No MCP servers configured.[/yellow]")
        raise typer.Exit()

    table = Table(title="MCP Servers", show_header=True, header_style="bold blue")
    table.add_column("Server", style="cyan")
    table.add_column("Command")
    table.add_column("Status", justify="center")

    for name, server in mcp_config.servers.items():
        if not server.enabled:
            status = "[dim]disabled[/dim]"
        elif validate:
            status = "[green]✓[/green]" if shutil.which(server.command) else "[red]✗[/red]"
        else:
            status = "[green]enabled[/green]"
            
        table.add_row(name, server.command, status)

    console.print(table)
