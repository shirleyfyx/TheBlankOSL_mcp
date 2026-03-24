import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List


@dataclass
class McpServerConfig:
    command: str
    args: List[str] = field(default_factory=list)
    env: Dict[str, str] = field(default_factory=dict)
    enabled: bool = False

    def expand_vars(self):
        """Expands ~ and $VAR in command, args, and env values."""
        self.command = os.path.expandvars(os.path.expanduser(self.command))
        self.args = [os.path.expandvars(os.path.expanduser(a)) for a in self.args]
        self.env = {
            k: os.path.expandvars(os.path.expanduser(v)) for k, v in self.env.items()
        }


@dataclass
class McpConfig:
    servers: Dict[str, McpServerConfig] = field(default_factory=dict)
    # Optional roots: list of {"uri": "file:///path", "name": "Display Name"}
    roots: List[Dict[str, str]] = field(default_factory=list)

    @classmethod
    def load(cls, path: str) -> "McpConfig":
        """
        Loads JSON from path, validates required fields, and expands environment variables.
        Raises FileNotFoundError or ValueError on failure.
        """
        path_obj = Path(path)
        if not path_obj.exists():
            raise FileNotFoundError(f"Config file not found: {path}")

        with open(path_obj, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Expect top-level key "mcpServers"
        servers_data = data.get("mcpServers", {})
        roots_data = data.get("roots", [])
        config = cls()

        if isinstance(roots_data, list):
            for r in roots_data:
                if isinstance(r, dict) and r.get("uri"):
                    config.roots.append(
                        {"uri": str(r["uri"]), "name": str(r.get("name", ""))}
                    )

        for name, s_data in servers_data.items():
            # Validate required fields
            if "command" not in s_data:
                raise ValueError(
                    f"Server '{name}' is missing required field: 'command'"
                )

            # Create object
            server = McpServerConfig(
                command=s_data["command"],
                args=s_data.get("args", []),
                env=s_data.get("env", {}),
                enabled=s_data.get("enabled", True),
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
                    "enabled": s.enabled,
                }
                for name, s in self.servers.items()
            },
            "roots": self.roots,
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=4)
