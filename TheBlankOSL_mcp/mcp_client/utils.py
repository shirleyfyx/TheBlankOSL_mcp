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
    Checks global settings first, then falls back to OS defaults.
    """
    stored = settings_mgr.load().mcp_config_path
    path = Path(stored) if stored else None

    if not path:
        sys_name = platform.system()
        home = Path.home()
        if sys_name == "Darwin":
            base = home / "Library/Application Support/Claude"
        elif sys_name == "Windows":
            base = Path(os.environ.get("APPDATA", "")) / "Claude"
        else:
            base = home / ".config/Claude"
        
        path = base / "claude_desktop_config.json"

    # Fixed error message to match your new flag
    if not path or not path.exists():
        console.print("[red]Error:[/red] No MCP config found. Set it via [bold]config -mp <path>[/bold].")
        raise typer.Exit(1)

    try:
        return McpConfig.load(str(path.absolute()))
    except Exception as e:
        console.print(f"[red]Error loading {path}:[/red] {e}")
        raise typer.Exit(1)
