import asyncio
import typer
import shlex
import json
from typing import List, Dict, Callable, Any
from rich.prompt import Prompt
from rich.panel import Panel
from rich.table import Table

# Import your modules
from . import __version__
from .utils import console, load_mcp_config, settings_mgr
from .mcp_manager import McpManager
from .commands import config as config_cmd
from .commands import tools as tools_cmd
from .commands import call as call_cmd
from .llm import get_client, list_backends, get_backend_name

# Import reusable logic from subcommands
from .commands.tools import list_tools_logic, info_tool_logic
from .commands.call import call_tool_logic
from .commands.config import show_config_logic

# --- Typer App Setup ---
app = typer.Typer(
    name="blankosl_cli",
    help="A Python CLI MCP client for terminal-based tool execution.",
    add_completion=False,
    rich_markup_mode="rich",
)

app.add_typer(config_cmd.app, name="config")
app.add_typer(tools_cmd.app, name="tools")
app.add_typer(call_cmd.app, name="call")

# --- Interactive Command Handlers ---

async def cmd_tools_list_all(manager: McpManager, args: List[str]):
    """List available tools. Usage: /list-all [filter]"""
    filter_str = args[0] if args else None
    await list_tools_logic(manager, filter_str)

async def cmd_tools_list(manager: McpManager, args: List[str]):
    """Show tool details. Usage: /list <tool_name>"""
    if not args:
        console.print("[red]Usage:[/red] /list <tool_name>")
        return
    await info_tool_logic(manager, args[0])

async def cmd_call(manager: McpManager, args: List[str]):
    """Execute a tool. Usage: /call <tool_name> [json_args]"""
    if not args:
        console.print("[red]Usage:[/red] /call <tool_name> [json_args]")
        return

    tool_name = args[0]
    args_str = " ".join(args[1:]) if len(args) > 1 else "{}"

    try:
        tool_args = json.loads(args_str)
        await call_tool_logic(manager, tool_name, tool_args)
    except json.JSONDecodeError:
        console.print("[red]Error:[/red] Arguments must be valid JSON.")

async def cmd_config_show(manager: McpManager, args: List[str]):
    """Display configuration."""
    show_config_logic()

async def cmd_list_llm(manager: McpManager, args: List[str]):
    """List all available LLM models."""
    backends = list_backends()
    if not backends:
        console.print("[yellow]No LLM backends available.[/yellow]")
        return
    table = Table(title="Available LLMs", show_header=True, header_style="bold cyan")
    table.add_column("ID", style="cyan")
    table.add_column("Name")
    for b in backends:
        table.add_row(b["id"], b["name"])
    console.print(table)
    console.print("To use a different model, run /switch_llm <id>.")

async def cmd_switch_llm(manager: McpManager, args: List[str], current_llm_id: list) -> None:
    """Change the current LLM. Usage: /switch_llm <id>"""
    if not args:
        console.print("[red]Usage:[/red] /switch_llm <id>  (e.g. /switch_llm gemini)")
        console.print("[dim]Use /list_llm to see available IDs.[/dim]")
        return
    backend_id = args[0].lower()
    name = get_backend_name(backend_id)
    if name is None:
        console.print(f"[red]Unknown LLM:[/red] {backend_id}. Use [cyan]/list_llm[/cyan].")
        return
    try:
        kwargs = {"api_key": settings_mgr.load().gemini_api_key} if backend_id == "gemini" else {}
        get_client(backend_id, **kwargs)
    except ValueError as e:
        console.print(f"[red]Cannot use {backend_id}:[/red] {e}")
        return
    current_llm_id[0] = backend_id
    settings_mgr.update_default_llm(backend_id)
    console.print(f"[green]Now using:[/green] {name}")

async def cmd_help(manager: McpManager, args: List[str]):
    """Show available slash commands."""
    table = Table(show_header=False, box=None)
    table.add_column("Command", style="bold cyan")
    table.add_column("Description", style="dim")

    for name, func in INTERACTIVE_COMMANDS.items():
        doc = func.__doc__.split('\n')[0] if func.__doc__ else "No description"
        table.add_row(f"/{name}", doc)
    table.add_row("/list_llm", "List available LLM models.")
    table.add_row("/switch_llm <id>", "Switch to another LLM (e.g. /switch_llm gemini)")
    console.print(table)
    console.print("\n[dim]Any input without a '/' prefix is treated as a chat message.[/dim]")

# --- Command Registry ---
INTERACTIVE_COMMANDS: Dict[str, Callable[..., Any]] = {
    "list-all": cmd_tools_list_all,
    "list": cmd_tools_list,
    "call": cmd_call,
    "config-show": cmd_config_show,
    "config-mcp-path": cmd_config_show,
    "list_llm": cmd_list_llm,
    "help": cmd_help,
}

# --- Interactive Session Loop ---

async def interactive_session():
    manager = McpManager()
    # Current LLM backend id (mutable so /switch_llm can update it)
    saved_llm = (settings_mgr.load().default_llm or "").strip()
    current_llm_id: List[str] = [saved_llm if get_backend_name(saved_llm) else "gemini"]

    console.print("[bold blue]Starting MCP Client Interactive Mode...[/bold blue]")
    
    with console.status("[bold green]Booting MCP Servers...[/bold green]"):
        report = await manager.start_all()

    # Create a status table
    table = Table(show_header=True, header_style="bold magenta", box=None)
    table.add_column("Server", style="cyan")
    table.add_column("Status", justify="right")

    for s in report["success"]:
        table.add_row(s["name"], "[green]✓ Ready[/green]")
    for f in report["failed"]:
        table.add_row(f["name"], f"[red]✗ Failed ({f['error']})[/red]")

    if report["success"] or report["failed"]:
        console.print(table)
    else:
        console.print("[yellow]No servers enabled in configuration.[/yellow]")

    model_name = get_backend_name(current_llm_id[0]) or current_llm_id[0] or "None"
    console.print()
    console.print(f"[bold green]Currently using: {model_name}[/bold green]")
    console.print("Type '/list_llm' to see all available LLM models.")
    console.print("Type '/help' for commands, '/exit' to quit.")

    while True:
        try:
            display_name = get_backend_name(current_llm_id[0]) or current_llm_id[0] or "None"
            prompt_label = f"BLANKOSL ({display_name})"
            user_input = Prompt.ask(f"\n[bold blue]{prompt_label}[/bold blue]")
            if not user_input.strip():
                continue
            
            # 1. Handle Slash Commands
            if user_input.startswith("/"):
                # Remove the slash and split
                raw_cmd = user_input[1:]
                parts = shlex.split(raw_cmd)
                if not parts:
                    continue
                cmd_name = parts[0].lower()
                cmd_args = parts[1:]

                if cmd_name in ("exit", "quit", "q"):
                    break

                if cmd_name == "switch_llm":
                    await cmd_switch_llm(manager, cmd_args, current_llm_id)
                elif cmd_name in INTERACTIVE_COMMANDS:
                    await INTERACTIVE_COMMANDS[cmd_name](manager, cmd_args)
                else:
                    console.print(f"[red]Unknown command:[/red] /{cmd_name}")
            
            # 2. Handle Chat Messages
            else:
                cid = current_llm_id[0]
                if not cid:
                    console.print("[yellow]No LLM selected.[/yellow] Use [cyan]/switch_llm <id>[/cyan] (see [cyan]/list_llm[/cyan]).")
                    continue
                try:
                    kwargs = {"api_key": settings_mgr.load().gemini_api_key} if cid == "gemini" else {}
                    client = get_client(cid, **kwargs)
                except ValueError as e:
                    console.print(f"[red]{e}[/red]")
                    continue
                with console.status("[dim]Thinking...[/dim]"):
                    reply = await client.chat([
                        {"role": "user", "content": user_input.strip()}
                    ])
                console.print(reply)

        except KeyboardInterrupt:
            break
        except Exception as e:
            console.print(f"[red]System Error:[/red] {e}")

    # Cleanup
    with console.status("[bold red]Shutting down servers...[/bold red]"):
        await manager.shutdown()
    console.print("[green]Goodbye![/green]")

# --- Main Entry Point ---

def version_callback(value: bool):
    if value:
        console.print(f"Version: {__version__}")
        raise typer.Exit()

@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: bool = typer.Option(False, "--version", "-v", callback=version_callback),
):
    """
    BlankOSL CLI - Managed MCP client.
    """
    if ctx.invoked_subcommand is None:
        asyncio.run(interactive_session())

if __name__ == "__main__":
    app()
