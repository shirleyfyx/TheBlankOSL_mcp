import typer
from typing import Optional
from rich.panel import Panel
from ..utils import console, load_mcp_config

app = typer.Typer(
    help="Manually call MCP tools.",
    rich_markup_mode="rich"
)

@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    tool_name: Optional[str] = typer.Argument(None, help="The name of the tool to execute."),
    args: Optional[str] = typer.Option(None, "--args", "-a", help="JSON string of arguments."),
) -> None:
    """
    Manually call an MCP tool with JSON arguments.
    
    If no tool name is provided, displays usage instructions.
    """
    if tool_name is None:
        console.print(
            Panel(
                "[yellow]Usage:[/yellow] blankosl_cli call <tool_name> --args '<json>'",
                title="[bold]Call Tool[/bold]",
                border_style="blue",
            )
        )
        raise typer.Exit()

    # Configuration is retrieved from context or global settings
    _ = load_mcp_config()
    
    console.print(f"[yellow]Tool call for '{tool_name}' not yet implemented.[/yellow]")
    if args:
        console.print(f"  Args: {args}")
