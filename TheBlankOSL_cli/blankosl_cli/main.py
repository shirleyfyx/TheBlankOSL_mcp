"""
BlankOSL CLI - Main entry point.

A Python CLI MCP client that locally replaces Claude Desktop's MCP functionality.
"""

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel

from blankosl_cli import __version__

# Initialize Typer app
app = typer.Typer(
    name="blankosl_cli",
    help="A Python CLI MCP client for terminal-based tool execution.",
    add_completion=False,
    rich_markup_mode="rich",
)

# Rich console for pretty output
console = Console()

# Global config option
CONFIG_OPTION = typer.Option(
    None,
    "--config",
    "-c",
    help="Path to MCP server configuration file (defaults to Claude Desktop config).",
    envvar="BLANKOSL_CONFIG",
)


def version_callback(value: bool) -> None:
    """Print version and exit."""
    if value:
        console.print(f"[bold blue]blankosl_cli[/bold blue] version {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False,
        "--version",
        "-v",
        help="Show version and exit.",
        callback=version_callback,
        is_eager=True,
    ),
    config: Optional[Path] = CONFIG_OPTION,
) -> None:
    """
    BlankOSL CLI - A Python MCP client for terminal-based tool execution.

    This CLI replaces Claude Desktop's MCP functionality, allowing you to:

    • List available tools from MCP servers
    • Manually call specific tools with JSON arguments
    • Chat with an LLM that can invoke MCP tools automatically
    """
    # Store config in context for subcommands
    if config:
        # Will be used by subcommands
        pass


# ============================================================================
# TOOLS Subcommand
# ============================================================================
tools_app = typer.Typer(
    name="tools",
    help="List and inspect available MCP tools.",
    rich_markup_mode="rich",
)
app.add_typer(tools_app, name="tools")


@tools_app.callback(invoke_without_command=True)
def tools_main(
    ctx: typer.Context,
    config: Optional[Path] = CONFIG_OPTION,
) -> None:
    """
    List and inspect available MCP tools from all connected servers.

    Run without subcommands to list all available tools.
    """
    if ctx.invoked_subcommand is None:
        # Default behavior: list all tools
        console.print(
            Panel(
                "[yellow]Tool listing not yet implemented.[/yellow]\n\n"
                "This will show all available tools from connected MCP servers.",
                title="[bold]Available Tools[/bold]",
                border_style="blue",
            )
        )


@tools_app.command("list")
def tools_list(
    config: Optional[Path] = CONFIG_OPTION,
    server: Optional[str] = typer.Option(
        None,
        "--server",
        "-s",
        help="Filter tools by specific server name.",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-V",
        help="Show detailed tool information including parameters.",
    ),
) -> None:
    """List all available tools from connected MCP servers."""
    console.print("[yellow]Tool listing not yet implemented.[/yellow]")


@tools_app.command("info")
def tools_info(
    tool_name: str = typer.Argument(..., help="Name of the tool to inspect."),
    config: Optional[Path] = CONFIG_OPTION,
) -> None:
    """Show detailed information about a specific tool."""
    console.print(f"[yellow]Tool info for '{tool_name}' not yet implemented.[/yellow]")


# ============================================================================
# CALL Subcommand
# ============================================================================
call_app = typer.Typer(
    name="call",
    help="Manually call MCP tools.",
    rich_markup_mode="rich",
)
app.add_typer(call_app, name="call")


@call_app.callback(invoke_without_command=True)
def call_main(
    ctx: typer.Context,
    tool_name: Optional[str] = typer.Argument(None, help="Name of the tool to call."),
    args: Optional[str] = typer.Option(
        None,
        "--args",
        "-a",
        help="JSON string of arguments to pass to the tool.",
    ),
    config: Optional[Path] = CONFIG_OPTION,
    timeout: int = typer.Option(
        30,
        "--timeout",
        "-t",
        help="Timeout in seconds for tool execution.",
    ),
    confirm: bool = typer.Option(
        True,
        "--confirm/--no-confirm",
        help="Prompt for confirmation before executing risky tools.",
    ),
) -> None:
    """
    Manually call an MCP tool with JSON arguments.

    Example:
        blankosl_cli call read_file --args '{"path": "/tmp/test.txt"}'
    """
    if tool_name is None:
        console.print(
            Panel(
                "[yellow]Usage:[/yellow] blankosl_cli call <tool_name> --args '<json>'\n\n"
                "Example:\n"
                "  blankosl_cli call read_file --args '{\"path\": \"/tmp/test.txt\"}'",
                title="[bold]Call Tool[/bold]",
                border_style="blue",
            )
        )
        raise typer.Exit()

    console.print(f"[yellow]Tool call for '{tool_name}' not yet implemented.[/yellow]")
    if args:
        console.print(f"  Args: {args}")


# ============================================================================
# CHAT Subcommand
# ============================================================================
chat_app = typer.Typer(
    name="chat",
    help="Interactive chat with LLM-driven tool execution.",
    rich_markup_mode="rich",
)
app.add_typer(chat_app, name="chat")


@chat_app.callback(invoke_without_command=True)
def chat_main(
    ctx: typer.Context,
    config: Optional[Path] = CONFIG_OPTION,
    model: str = typer.Option(
        "claude-3-5-sonnet-20241022",
        "--model",
        "-m",
        help="LLM model to use for chat.",
    ),
    system_prompt: Optional[str] = typer.Option(
        None,
        "--system",
        "-s",
        help="Custom system prompt for the LLM.",
    ),
    auto_confirm: bool = typer.Option(
        False,
        "--auto-confirm",
        "-y",
        help="Automatically confirm tool executions without prompting.",
    ),
) -> None:
    """
    Start an interactive chat session with LLM-driven tool execution.

    The LLM can discover and invoke MCP tools automatically based on your requests.
    """
    console.print(
        Panel(
            "[yellow]Interactive chat not yet implemented.[/yellow]\n\n"
            "This will start a REPL where you can chat with an LLM\n"
            "that has access to all MCP tools.",
            title="[bold]Chat Mode[/bold]",
            border_style="blue",
        )
    )


# ============================================================================
# Entry point for direct execution
# ============================================================================
if __name__ == "__main__":
    app()
