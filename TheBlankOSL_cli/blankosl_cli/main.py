"""
BlankOSL CLI - Main entry point.

A Python CLI MCP client that locally replaces Claude Desktop's MCP functionality.
"""

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from blankosl_cli import __version__
from blankosl_cli.config_parser import McpConfig, get_default_config_path

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


def load_config(config_path: Optional[Path] = None) -> McpConfig:
    """
    Load MCP configuration from the specified path or default Claude Desktop config.

    Args:
        config_path: Optional path to config file. If None, uses Claude Desktop default.

    Returns:
        McpConfig object with loaded server configurations.

    Raises:
        typer.Exit: If no config file is found.
    """
    if config_path is None:
        config_path = get_default_config_path()

    if config_path is None:
        console.print(
            "[red]Error:[/red] No config file found.\n\n"
            "Provide a config file with [bold]--config[/bold] or ensure Claude Desktop "
            "is installed with a valid configuration.",
            style="red",
        )
        raise typer.Exit(1)

    try:
        return McpConfig.load(str(config_path))
    except FileNotFoundError:
        console.print(f"[red]Error:[/red] Config file not found: {config_path}")
        raise typer.Exit(1)
    except ValueError as e:
        console.print(f"[red]Error:[/red] Invalid config: {e}")
        raise typer.Exit(1)


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
    # Config will be loaded by subcommands as needed
    pass


# ============================================================================
# CONFIG Subcommand
# ============================================================================
@app.command("config")
def config_show(
    config: Optional[Path] = CONFIG_OPTION,
    validate: bool = typer.Option(
        False,
        "--validate",
        help="Validate that all server commands exist.",
    ),
) -> None:
    """
    Show the current MCP server configuration.

    Displays all configured MCP servers from Claude Desktop or custom config file.
    """
    # Determine config path
    config_path = config if config else get_default_config_path()

    if config_path is None:
        console.print(
            "[yellow]No configuration file found.[/yellow]\n\n"
            "Expected locations:\n"
            "  • macOS: ~/Library/Application Support/Claude/claude_desktop_config.json\n"
            "  • Windows: %APPDATA%/Claude/claude_desktop_config.json\n"
            "  • Linux: ~/.config/Claude/claude_desktop_config.json\n\n"
            "Use [bold]--config[/bold] to specify a custom config file."
        )
        raise typer.Exit(1)

    console.print(f"[dim]Config file:[/dim] {config_path}\n")

    # Load and display config
    mcp_config = load_config(config_path)

    if not mcp_config.servers:
        console.print("[yellow]No MCP servers configured.[/yellow]")
        raise typer.Exit()

    # Create table
    table = Table(title="MCP Servers", show_header=True, header_style="bold blue")
    table.add_column("Server", style="cyan")
    table.add_column("Command")
    table.add_column("Args")
    table.add_column("Status", justify="center")

    import shutil

    for name, server in mcp_config.servers.items():
        # Check if enabled
        if not server.enabled:
            status = "[dim]disabled[/dim]"
        elif validate:
            # Check if command exists
            cmd_exists = shutil.which(server.command) is not None
            status = "[green]✓[/green]" if cmd_exists else "[red]✗ not found[/red]"
        else:
            status = "[green]enabled[/green]"

        args_str = " ".join(server.args[:3])
        if len(server.args) > 3:
            args_str += " ..."

        table.add_row(name, server.command, args_str or "[dim]none[/dim]", status)

    console.print(table)

    # Show env vars if any
    servers_with_env = [(n, s) for n, s in mcp_config.servers.items() if s.env]
    if servers_with_env:
        console.print("\n[bold]Environment Variables:[/bold]")
        for name, server in servers_with_env:
            console.print(f"  [cyan]{name}[/cyan]:")
            for key, value in server.env.items():
                # Mask sensitive values
                display_value = value[:4] + "..." if len(value) > 8 else value
                console.print(f"    {key}={display_value}")


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
