import json
import os
import platform
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional


def get_default_config_path() -> Optional[Path]:
    """
    Returns the default Claude Desktop config path for the current platform.

    - macOS: ~/Library/Application Support/Claude/claude_desktop_config.json
    - Windows: %APPDATA%/Claude/claude_desktop_config.json
    - Linux: ~/.config/Claude/claude_desktop_config.json
    """
    system = platform.system()

    if system == "Darwin":  # macOS
        base = Path.home() / "Library" / "Application Support" / "Claude"
    elif system == "Windows":
        appdata = os.environ.get("APPDATA", "")
        base = Path(appdata) / "Claude" if appdata else None
    else:  # Linux and others
        base = Path.home() / ".config" / "Claude"

    if base is None:
        return None

    config_path = base / "claude_desktop_config.json"
    return config_path if config_path.exists() else None

@dataclass
class ServerConfig:
    command: str
    args: List[str] = field(default_factory=list)
    env: Dict[str, str] = field(default_factory=dict)
    enabled: bool = True

    def expand_vars(self):
        """Expands ~ and $VAR in command, args, and env values."""
        self.command = os.path.expandvars(os.path.expanduser(self.command))
        self.args = [os.path.expandvars(os.path.expanduser(a)) for a in self.args]
        self.env = {k: os.path.expandvars(os.path.expanduser(v)) for k, v in self.env.items()}

@dataclass
class McpConfig:
    servers: Dict[str, ServerConfig] = field(default_factory=dict)

    @classmethod
    def load(cls, path: str):
        """Loads JSON, validates 'command' exists, and expands env vars."""
        if not os.path.exists(path):
            raise FileNotFoundError(f"Config file not found: {path}")

        with open(path, 'r') as f:
            data = json.load(f)

        # Expect top-level key "mcpServers"
        servers_data = data.get("mcpServers", {})
        config = cls()

        for name, s_data in servers_data.items():
            # Validate required fields
            if "command" not in s_data:
                raise ValueError(f"Server '{name}' is missing required field: 'command'")

            # Create object
            server = ServerConfig(
                command=s_data["command"],
                args=s_data.get("args", []),
                env=s_data.get("env", {}),
                enabled=s_data.get("enabled", True)
            )

            # Expand variables immediately upon load
            server.expand_vars()
            config.servers[name] = server

        return config

    def save(self, path: str):
        """Saves current config to JSON."""
        output = {
            "mcpServers": {
                name: {
                    "command": s.command,
                    "args": s.args,
                    "env": s.env,
                    "enabled": s.enabled
                }
                for name, s in self.servers.items()
            }
        }
        with open(path, 'w') as f:
            json.dump(output, f, indent=4)
