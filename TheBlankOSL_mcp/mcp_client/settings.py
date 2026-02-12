import json
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass, asdict

@dataclass
class CliSettings:
    """
    Data container for global CLI preferences.
    
    Attributes:
        mcp_config_path: Absolute path to the MCP server JSON configuration.
        default_model: The LLM model identifier used for chat sessions.
        auto_confirm: Whether to skip confirmation prompts for tool calls.
    """
    mcp_config_path: Optional[str] = None
    default_model: str = "claude-3-5-sonnet-20241022"
    auto_confirm: bool = False

class SettingsManager:
    """
    Manages the lifecycle of the global CLI settings file (~/.blankosl_cli/settings.json).
    Handles atomic writes and directory initialization.
    """
    def __init__(self):
        """Initializes the manager and ensures the configuration directory exists."""
        self.config_dir = Path.home() / ".blankosl_cli"
        self.settings_file = self.config_dir / "settings.json"
        self._ensure_storage()

    def _ensure_storage(self) -> None:
        """Creates the hidden directory and default settings file if they do not exist."""
        if not self.config_dir.exists():
            self.config_dir.mkdir(parents=True, exist_ok=True)
        if not self.settings_file.exists():
            self.save(CliSettings())

    def load(self) -> CliSettings:
        """
        Reads settings from disk. 
        
        Returns:
            CliSettings: The loaded settings object or a default object if loading fails.
        """
        try:
            with open(self.settings_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                fields = CliSettings.__dataclass_fields__.keys()
                filtered_data = {k: v for k, v in data.items() if k in fields}
                return CliSettings(**filtered_data)
        except (json.JSONDecodeError, IOError, TypeError):
            return CliSettings()

    def save(self, settings: CliSettings) -> None:
        """
        Performs an atomic write of the settings object to the JSON file.
        
        Args:
            settings: The CliSettings instance to persist.
        """
        temp_file = self.settings_file.with_suffix(".tmp")
        try:
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(asdict(settings), f, indent=4)
            temp_file.replace(self.settings_file)
        finally:
            if temp_file.exists():
                temp_file.unlink()

    def update_mcp_path(self, path: Path) -> None:
        """
        Updates the global MCP configuration path and persists it.
        
        Args:
            path: The Path object pointing to the new MCP config file.
        """
        settings = self.load()
        settings.mcp_config_path = str(path.absolute())
        self.save(settings)
