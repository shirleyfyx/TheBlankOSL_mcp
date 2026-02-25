import asyncio
import typer
from typing import Optional, Dict, Any
from rich.table import Table
from rich.panel import Panel
from rich.syntax import Syntax
import json

from ..utils import console
from ..mcp_manager import McpManager

app = typer.Typer(help="Inspect and list available MCP tools.", rich_markup_mode="rich")

# --- REUSABLE CORE LOGIC ---

async def list_tools_logic(manager: McpManager, server_filter: Optional[str] = None, startup_report: Optional[Dict[str, Any]] = None):
    """
    Fetches all the server tools and display them.
    """
    # Show startup errors if any
    if startup_report:
        failed = startup_report.get("failed", [])
        if failed:
            console.print("[yellow]Warning: Some servers failed to start:[/yellow]")
            for failure in failed:
                console.print(f"  [red]✗[/red] {failure['name']}: {failure['error']}")
            console.print()
    
    try:
        all_tools = await manager.get_all_tools()
    except Exception as e:
        console.print(f"[red]Error fetching tools:[/red] {e}")
        return

    # Filter logic
    if server_filter:
        # Case-insensitive filtering
        all_tools = {k: v for k, v in all_tools.items() if k.lower() == server_filter.lower()}

    # Check if we found anything
    has_tools = any(tools for tools in all_tools.values())
    if not has_tools:
        msg = f"[yellow]No tools found for server:[/yellow] {server_filter}" if server_filter else "[yellow]No tools found on enabled servers.[/yellow]"
        console.print(msg)
        if startup_report and startup_report.get("failed"):
            console.print("\n[dim]Tip: Check the errors above. Servers may have failed to start due to incorrect paths or missing dependencies.[/dim]")
        return

    # Build Table
    table = Table(title="Available MCP Tools", header_style="bold magenta")
    table.add_column("Server", style="cyan")
    table.add_column("Tool Name", style="green")
    table.add_column("Description", style="white")

    for server_name, tools in all_tools.items():
        for tool in tools:
            name = tool.get("name", "Unknown")
            desc = tool.get("description", "") or ""
            table.add_row(server_name, name, desc)

    console.print(table)

async def info_tool_logic(manager: McpManager, target_server: str):
    """
    Finds a specific server and lists the details/schemas of all its tools.
    """
    # Get the cached tool dictionary { "server_name": [tools] }
    all_tools = await manager.get_all_tools()
    
    # 1. Check if the server exists in our connected sessions
    if target_server not in all_tools:
        console.print(f"[red]Error:[/red] Server '{target_server}' not found or has no tools.")
        return

    server_tools = all_tools[target_server]
    
    if not server_tools:
        console.print(f"[yellow]Server '{target_server}' is active but reported 0 tools.[/yellow]")
        return

    console.print(f"\n[bold underline]Tools for Server: {target_server}[/bold underline]\n")

    # 2. Iterate and display every tool found on this server
    for tool in server_tools:
        name = tool.get("name", "Unknown Tool")
        description = tool.get("description", "No description provided.")
        schema = tool.get("inputSchema", {})
        
        # Format the schema for the Syntax highlighter
        schema_str = json.dumps(schema, indent=2)

        # Create a header panel for each tool
        console.print(Panel(
            f"[bold green]Description:[/bold green] {description}\n\n"
            f"[bold cyan]Input Schema:[/bold cyan]",
            title=f"Tool: [bold white]{name}[/bold white]",
            expand=False,
            border_style="blue"
        ))
        
        # Print the JSON schema with syntax highlighting
        console.print(Syntax(schema_str, "json", theme="monokai", word_wrap=True))
        console.print("-" * 40) # Divider between tools


# --- CLI WRAPPERS (Standalone Mode) ---

@app.command("list-all")
def list_cmd(
    server: Optional[str] = typer.Option(None, "--server", "-s", help="Filter tools by server name.")
):
    """
    List all tools available across all enabled MCP servers.
    """
    async def _run():
        manager = McpManager()
        startup_report = None
        with console.status("[bold green]Connecting to servers..."):
            try:
                startup_report = await manager.start_all()
                await list_tools_logic(manager, server, startup_report)
            finally:
                await manager.shutdown()

    asyncio.run(_run())

@app.command("list")
def info_cmd(
    tool_name: str = typer.Argument(..., help="The name of the tool to inspect.")
):
    """
    Show detailed JSON schema for a specific tool.
    """
    async def _run():
        manager = McpManager()
        with console.status(f"[bold green]Locating tool '{tool_name}'..."):
            try:
                await manager.start_all()
                await info_tool_logic(manager, tool_name)
            finally:
                await manager.shutdown()

    asyncio.run(_run())
