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
from .commands.call import main as call_main
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
app.command(name="call")(call_main)

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
        console.print("[dim]Example: /call get_alerts '{\"state\":\"CA\"}'[/dim]")
        console.print("[dim]Note: In interactive mode, don't use --args flag. Just provide JSON directly.[/dim]")
        return

    tool_name = args[0]
    
    # Filter out CLI flags that users might accidentally include
    json_args = [arg for arg in args[1:] if arg not in ('--args', '-a')]
    
    # If no JSON provided, use empty dict
    if not json_args:
        args_str = "{}"
    else:
        # Join remaining arguments and try to parse as JSON
        args_str = " ".join(json_args)
        # If it looks like they used --args flag, show helpful error
        if '--args' in args or '-a' in args:
            console.print("[yellow]Note:[/yellow] In interactive mode, don't use --args or -a flags.")
            console.print("[yellow]Just provide the JSON directly:[/yellow] /call <tool_name> '<json>'")

    try:
        tool_args = json.loads(args_str)
        await call_tool_logic(manager, tool_name, tool_args)
    except json.JSONDecodeError as e:
        console.print(f"[red]Error:[/red] Invalid JSON: {e}")
        console.print(f"[dim]You provided: {args_str}[/dim]")
        console.print("[yellow]Example:[/yellow] /call get_alerts '{\"state\":\"CA\"}'")

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

async def cmd_switch_llm(manager: McpManager, args: List[str]) -> None:
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
        get_client(backend_id)
    except ValueError as e:
        console.print(f"[red]Cannot use {backend_id}:[/red] {e}")
        return
        
    # Persist directly to config!
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
    console.print(table)
    console.print("\n[dim]Any input without a '/' prefix is treated as a chat message.[/dim]")

# --- Command Registry ---
INTERACTIVE_COMMANDS: Dict[str, Callable[[McpManager, List[str]], Any]] = {
    "list-all": cmd_tools_list_all,
    "list": cmd_tools_list,
    "call": cmd_call,
    "config-show": cmd_config_show,
    "config-mcp-path": cmd_config_show,
    "list_llm": cmd_list_llm,
    "switch_llm": cmd_switch_llm,
    "help": cmd_help,
}

# --- Interactive Session Loop ---

async def interactive_session():
    manager = McpManager()
    
    # Helper to always fetch the latest LLM from config
    def get_current_llm() -> str:
        saved = settings_mgr.load().default_llm
        return saved.strip() if saved and get_backend_name(saved.strip()) else "gemini"

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

    # Initial display
    initial_llm = get_current_llm()
    model_name = get_backend_name(initial_llm) or initial_llm
    console.print()
    console.print(f"[bold green]Currently using: {model_name}[/bold green]")
    console.print("Type '/help' for commands, '/exit' to quit.")

    chat_history: List[dict] = []
    cached_client: Any = None
    cached_cid: str = ""

    while True:
        try:
            # Re-fetch config value on every loop iteration
            current_cid = get_current_llm()
            display_name = get_backend_name(current_cid) or current_cid
            
            prompt_label = f"BLANKOSL ({display_name})"
            user_input = Prompt.ask(f"\n[bold blue]{prompt_label}[/bold blue]")
            
            if not user_input.strip():
                continue
            
            # 1. Handle Slash Commands
            if user_input.startswith("/"):
                raw_cmd = user_input[1:]
                parts = shlex.split(raw_cmd)
                if not parts:
                    continue
                cmd_name = parts[0].lower()
                cmd_args = parts[1:]

                if cmd_name in ("exit", "quit", "q"):
                    break

                # The awkward if-branch is gone! Everything routes dynamically.
                if cmd_name in INTERACTIVE_COMMANDS:
                    await INTERACTIVE_COMMANDS[cmd_name](manager, cmd_args)
                else:
                    console.print(f"[red]Unknown command:[/red] /{cmd_name}")
            
            # 2. Handle Chat Messages
            else:
                if not current_cid:
                    console.print("[yellow]No LLM selected.[/yellow] Use [cyan]/switch_llm <id>[/cyan].")
                    continue
                    
                try:
                    # Update client cache only if the config changed
                    if cached_client is None or cached_cid != current_cid:
                        cached_client = get_client(current_cid)
                        cached_cid = current_cid
                    client = cached_client
                except ValueError as e:
                    console.print(f"[red]{e}[/red]")
                    continue
                
                chat_history.append({"role": "user", "content": user_input.strip()})
                with console.status("[dim]Thinking...[/dim]"):
                    reply = await client.chat(chat_history)
                chat_history.append({"role": "assistant", "content": reply})
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
