import platform
import os
import typer
from pathlib import Path
from typing import Optional
from rich.console import Console
from .mcp_config_parser import McpConfig
from .settings import SettingsManager

console = Console()
settings_mgr = SettingsManager()


def load_mcp_config() -> McpConfig:
    """
    Finds and loads the MCP configuration.
    Priority:
    1. Stored global setting (set via config -mp)
    2. OS-specific Claude Desktop defaults
    3. Current Working Directory (for Docker/Dev environments)
    """
    stored = settings_mgr.load().mcp_config_path
    path = None

    # 1. Try the stored path
    if stored:
        path = Path(stored).resolve()

    # 2. Try OS defaults if no stored path or stored path is invalid
    if not path or not path.exists():
        sys_name = platform.system()
        home = Path.home()
        if sys_name == "Darwin":
            base = home / "Library/Application Support/Claude"
        elif sys_name == "Windows":
            base = Path(os.environ.get("APPDATA", "")) / "Claude"
        else:
            base = home / ".config/Claude"

        default_path = (base / "claude_desktop_config.json").resolve()

        # If default exists, use it. If not, check CWD as a last ditch effort.
        if default_path.exists():
            path = default_path
        else:
            # Check if the file is just sitting in the current directory
            cwd_path = Path.cwd() / "claude_desktop_config.json"
            if cwd_path.exists():
                path = cwd_path

    # 3. Final check
    if not path or not path.exists():
        console.print("[red]Error:[/red] MCP config not found.")
        console.print(f"[dim]Checked: {stored if stored else 'System Defaults'}[/dim]")
        console.print(
            "[yellow]Hint:[/yellow] Run: [bold]blankosl_cli config -mp /app/TheBlankOSL_mcp/claude_desktop_config.json[/bold]"
        )
        raise typer.Exit(1)

    try:
        return McpConfig.load(str(path.absolute()))
    except Exception as e:
        console.print(f"[red]Error loading {path}:[/red] {e}")
        raise typer.Exit(1)
