import typer
from pathlib import Path
from typing import Optional
from rich.table import Table
from dataclasses import asdict

from ..utils import console, load_mcp_config, settings_mgr

app = typer.Typer(help="Manage MCP server configuration.", rich_markup_mode="rich")

# --- REUSABLE LOGIC ---
def set_mcp_path_logic(mcp_path: Path):
    """
    Validates and updates the global MCP configuration path.
    """
    if not mcp_path.exists():
        console.print(f"[red]Error:[/red] Path {mcp_path} does not exist.")
        return False

    settings_mgr.update_mcp_path(mcp_path)
    console.print(f"[green]Global MCP config path updated to:[/green] {mcp_path}")
    return True

def show_config_logic():
    """
    Loads and displays the current CLI settings and MCP server status.
    """
    # 1. Global CLI Settings
    settings = settings_mgr.load()
    settings_dict = asdict(settings)
    
    table_settings = Table(title="[bold blue]CLI Global Settings[/bold blue]", show_header=True, header_style="bold cyan")
    table_settings.add_column("Setting")
    table_settings.add_column("Value")

    # Mask any API key / secret field when displaying
    for key, value in settings_dict.items():
        if "api_key" in key or key.endswith("_secret"):
            display_value = "*** set ***" if value else "Not Set"
        else:
            display_value = str(value) if value is not None else "[dim]Not Set[/dim]"
        table_settings.add_row(key, display_value)
        
    console.print(table_settings)
    console.print()  # Spacer

    # 2. MCP Server Status
    try:
        mcp_config = load_mcp_config()
    except Exception as e:
        console.print(f"[yellow]Could not load MCP config:[/yellow] {e}")
        return

    if not mcp_config.servers:
        console.print("[yellow]No MCP servers configured.[/yellow]")
        return

    table_servers = Table(title="MCP Servers", show_header=True, header_style="bold blue")
    table_servers.add_column("Server", style="cyan")
    table_servers.add_column("Command")
    table_servers.add_column("Status", justify="center")

    for name, server in mcp_config.servers.items():
        if not server.enabled:
            status = "[dim]disabled[/dim]"
        else:
            status = "[green]enabled[/green]"
            
        table_servers.add_row(name, server.command, status)

    console.print(table_servers)


# --- CLI WRAPPER ---

@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    mcp_path: Optional[Path] = typer.Option(
        None, "--mcp-path", "-mp", help="Update the global MCP config path and exit."
    ),
    gemini_api_key: Optional[str] = typer.Option(
        None, "--gemini-api-key", help="Set the Gemini API key in CLI config and exit."
    ),
    groq_api_key: Optional[str] = typer.Option(
        None, "--groq-api-key", help="Set the Groq API key in CLI config and exit."
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
        success = set_mcp_path_logic(mcp_path)
        if not success:
            raise typer.Exit(1)
        raise typer.Exit()

    # 2. Action: Set Gemini API key
    if gemini_api_key is not None:
        settings_mgr.update_gemini_api_key(gemini_api_key)
        console.print("[green]Gemini API key saved to CLI config.[/green]")
        raise typer.Exit()

    # 2b. Action: Set Groq API key
    if groq_api_key is not None:
        settings_mgr.update_groq_api_key(groq_api_key)
        console.print("[green]Groq API key saved to CLI config.[/green]")
        raise typer.Exit()

    # 3. Action: Show settings (or default behavior if no args provided)
    if show_settings:
        show_config_logic()
        raise typer.Exit()
