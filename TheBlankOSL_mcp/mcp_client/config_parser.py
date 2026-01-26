import json
import os
from dataclasses import dataclass, field
from typing import Dict, List

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
