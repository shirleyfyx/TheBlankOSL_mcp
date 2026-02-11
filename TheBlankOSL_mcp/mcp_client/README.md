# BlankOSL CLI

A Python CLI MCP client that locally replaces Claude Desktop's MCP functionality while managing configurations globally.

## Installation

### From the project root

```bash
# Install the package in development mode
pip install -e ./TheBlankOSL_mcp
```

### Verify installation

```bash
blankosl_cli --version
```

## Commands

### `blankosl_cli`

Enter interactive mode.

### `blankosl_cli --help`

Get a list of most up-to-date cli commands.

### `blankosl_cli config`

Manage and view the MCP server configuration.

```bash
# Set a new global mcp configuration path (persists to ~/.blankosl_cli/settings.json)
blankosl_cli config --mcp-path /path/to/config.json

# Show the client config.
blankosl_cli config --show
```

### `blankosl_cli tools`

List and inspect available MCP tools.

```bash
# List all available tools with optional name filter
blankosl_cli tools list-all [--server weather]

# Show detailed schema information for a specific tool
blankosl_cli tools list <tool_name>
```

### `blankosl_cli call`

Manually execute an MCP tool with JSON arguments.

```bash
# Call a tool with JSON arguments
blankosl_cli call read_file --args '{"path": "/tmp/test.txt"}'
```

## Configuration

The CLI manages its own state in `~/.blankosl_cli/settings.json`. It resolves the MCP configuration using the following priority:

1. **Global Setting**: The MCP path explicitly set via `blankosl_cli config --mcp-path`.
2. **System Default**: If no global path is set, it searches for the Claude Desktop config:

| Platform | Default Path |
|----------|--------------|
| macOS    | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| Windows  | `%APPDATA%/Claude/claude_desktop_config.json` |
| Linux    | `~/.config/Claude/claude_desktop_config.json` |

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run linting
ruff check mcp_client/

# Run tests
pytest
```
