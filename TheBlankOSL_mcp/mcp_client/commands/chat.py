import typer
from rich.panel import Panel
from ..utils import console, load_mcp_config

app = typer.Typer(
    help="Interactive chat with LLM-driven tool execution.",
    rich_markup_mode="rich"
)

@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    model: str = typer.Option("claude-3-5-sonnet-20241022", "--model", "-m", help="The LLM model to use."),
) -> None:
    """
    Start an interactive chat session with LLM-driven tool execution.
    
    Initializes the MCP client and establishes a session with the LLM provider.
    """
    # Configuration is retrieved from global settings
    _ = load_mcp_config()

    console.print(
        Panel(
            f"[yellow]Interactive chat using [bold]{model}[/bold] not yet implemented.[/yellow]",
            title="[bold]Chat Mode[/bold]",
            border_style="blue",
        )
    )
