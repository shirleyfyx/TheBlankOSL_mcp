import typer
from typing import Optional
from rich.panel import Panel
from ..utils import console, load_mcp_config

app = typer.Typer(
    help="List and inspect available MCP tools.",
    rich_markup_mode="rich"
)

@app.callback(invoke_without_command=True)
def main(ctx: typer.Context) -> None:
    """
    Default callback for tool inspection.
    """
    if ctx.invoked_subcommand is None:
        console.print(
            Panel(
                "[yellow]Tool listing not yet implemented.[/yellow]\n\n"
                "Use [bold]list[/bold] to see tools or [bold]info[/bold] for details.",
                title="[bold]Available Tools[/bold]",
                border_style="blue",
            )
        )

@app.command("list")
def list_tools(
    server: Optional[str] = typer.Option(None, "--server", "-s", help="Filter tools by server name."),
    verbose: bool = typer.Option(False, "--verbose", "-V", help="Show expanded tool definitions."),
) -> None:
    """
    List all available tools from connected MCP servers.
    """
    _ = load_mcp_config()
    console.print(f"[yellow]Tool listing{' for ' + server if server else ''} not yet implemented.[/yellow]")

@app.command("info")
def info(tool_name: str = typer.Argument(..., help="The name of the tool to inspect.")) -> None:
    """
    Show detailed information and argument schemas for a specific tool.
    """
    _ = load_mcp_config()
    console.print(f"[yellow]Tool info for '{tool_name}' not yet implemented.[/yellow]")
