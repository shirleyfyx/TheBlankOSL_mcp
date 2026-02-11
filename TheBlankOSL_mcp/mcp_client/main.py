import typer
from .utils import console
from . import __version__
from .commands import config as config_cmd
from .commands import tools as tools_cmd
from .commands import call as call_cmd
from .commands import chat as chat_cmd

app = typer.Typer(
    name="blankosl_cli",
    help="A Python CLI MCP client for terminal-based tool execution.",
    add_completion=False,
    rich_markup_mode="rich",
)

app.add_typer(config_cmd.app, name="config")
app.add_typer(tools_cmd.app, name="tools")
app.add_typer(call_cmd.app, name="call")
app.add_typer(chat_cmd.app, name="chat")

def version_callback(value: bool) -> None:
    """Print version information and exit."""
    if value:
        console.print(f"[bold blue]blankosl_cli[/bold blue] version {__version__}")
        raise typer.Exit()

@app.callback()
def main(
    ctx: typer.Context,
    version: bool = typer.Option(
        False, "--version", "-v", help="Show version and exit.", callback=version_callback, is_eager=True
    ),
) -> None:
    """BlankOSL CLI - Managed MCP client."""
    # We no longer call load_mcp_config here because it blocks 'config --show' 
    # and 'config -mp' when no config exists yet.
    pass

if __name__ == "__main__":
    app()
