# BlankOSL CLI

A Python CLI MCP client that locally replaces Claude Desktop's MCP functionality while managing configurations globally.

## Installation

From the project root, choose one of the options below.

### Option A: Using Docker

Make sure the container is running, run the following command in the terminal:

```bash
docker exec -it mcp-shared bash
```

Now you can run the blankosl cli in your terminal!

### Option B: Local 

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

## LLM API key

The LLM API keys are stored in **CLI config**, so you can set and change them at runtime:

Google Gemini

```bash
blankosl_cli config --gemini-api-key <your_key>
```

Get a key: [Gemini API key](https://ai.google.dev/gemini-api/docs/api-key).

## Configuration

The CLI stores its state in **`~/.blankosl_cli/settings.json`** (the “CLI config” file). That file holds:
- MCP config path
- Default LLM backend
- **Gemini API key** (masked)

View settings in the terminal: `blankosl_cli config --show`. It resolves the MCP configuration using the following priority:

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
