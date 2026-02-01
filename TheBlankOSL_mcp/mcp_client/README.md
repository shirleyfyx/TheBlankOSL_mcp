# BlankOSL CLI

A Python CLI MCP client that locally replaces Claude Desktop's MCP functionality.

## Installation

### From the project root (recommended)

```bash
# Activate your conda environment
conda activate blankosl

# Install the package in development mode
pip install -e ./TheBlankOSL_mcp
```

### Verify installation

```bash
blankosl_cli --version
```

## Commands

### `blankosl_cli config`

Show the current MCP server configuration from Claude Desktop.

```bash
# Show all configured servers
blankosl_cli config

# Validate that all server commands exist
blankosl_cli config --validate

# Use a custom config file
blankosl_cli config --config /path/to/config.json
```

### `blankosl_cli tools`

List and inspect available MCP tools.

```bash
# List all available tools
blankosl_cli tools list

# Filter by server
blankosl_cli tools list --server weather

# Show detailed info for a specific tool
blankosl_cli tools info <tool_name>
```

### `blankosl_cli call`

Manually call an MCP tool with JSON arguments.

```bash
# Call a tool with arguments
blankosl_cli call read_file --args '{"path": "/tmp/test.txt"}'

# With timeout
blankosl_cli call slow_tool --args '{}' --timeout 60
```

### `blankosl_cli chat`

Start an interactive chat session with LLM-driven tool execution.

```bash
# Start chat with default model
blankosl_cli chat

# Use a specific model
blankosl_cli chat --model claude-3-5-sonnet-20241022

# Auto-confirm tool executions
blankosl_cli chat --auto-confirm
```

## Configuration

The CLI automatically detects Claude Desktop's config file:

| Platform | Default Path |
|----------|--------------|
| macOS    | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| Windows  | `%APPDATA%/Claude/claude_desktop_config.json` |
| Linux    | `~/.config/Claude/claude_desktop_config.json` |

You can also specify a custom config file:

```bash
blankosl_cli --config /path/to/config.json <command>
```

Or set the `BLANKOSL_CONFIG` environment variable:

```bash
export BLANKOSL_CONFIG=/path/to/config.json
blankosl_cli config
```

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run linting
ruff check mcp_client/

# Run tests
pytest
```
