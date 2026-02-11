import asyncio
import json
import typer
from typing import Optional, Dict, Any
from rich.panel import Panel
from rich.syntax import Syntax

from ..utils import console
from ..mcp_manager import McpManager

app = typer.Typer(
    help="Manually call MCP tools.",
    rich_markup_mode="rich"
)

# --- REUSABLE CORE LOGIC ---
# This function can be imported by main.py for the interactive session
async def call_tool_logic(manager: McpManager, tool_name: str, arguments: Dict[str, Any]):
    """
    Executes a tool using an existing manager connection and prints the result.
    """
    try:
        # The manager handles finding the right server automatically
        result = await manager.call_tool(tool_name, arguments)
        
        # Pretty print the result
        json_str = json.dumps(result, indent=2)
        console.print(Panel(
            Syntax(json_str, "json", theme="monokai", word_wrap=True),
            title=f"[bold green]Result: {tool_name}[/bold green]",
            expand=False,
            border_style="green"
        ))
    except ValueError as ve:
        console.print(f"[yellow]Warning:[/yellow] {ve}")
    except Exception as e:
        console.print(f"[red]Execution Failed:[/red] {e}")

# --- CLI WRAPPER ---
# This runs when you type 'blankosl_cli call ...' from the terminal
async def _run_cli_call(tool_name: str, args_json: Optional[str]):
    # 1. Parse Arguments
    arguments = {}
    if args_json:
        try:
            arguments = json.loads(args_json)
        except json.JSONDecodeError:
            console.print("[red]Error:[/red] --args must be a valid JSON string.")
            return

    # 2. Setup Temporary Connection
    manager = McpManager()
    
    with console.status(f"[bold green]Connecting to servers and calling '{tool_name}'..."):
        try:
            await manager.start_all()
            
            # 3. Use the Reusable Logic
            await call_tool_logic(manager, tool_name, arguments)
            
        except Exception as e:
            console.print(f"[red]Connection Error:[/red] {e}")
        finally:
            await manager.shutdown()

@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    tool_name: Optional[str] = typer.Argument(None, help="The name of the tool to execute."),
    args: Optional[str] = typer.Option(None, "--args", "-a", help="JSON string of arguments."),
) -> None:
    """
    Manually call an MCP tool with JSON arguments.
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

    # Bridge Sync (Typer) to Async (Manager)
    asyncio.run(_run_cli_call(tool_name, args))
