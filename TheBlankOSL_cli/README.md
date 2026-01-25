# BlankOSL CLI

A Python CLI MCP client that locally replaces Claude Desktop's MCP functionality.

## Features

- **Multi-server support**: Connect to multiple MCP servers simultaneously
- **Tool discovery**: Automatically discover tools from all connected servers
- **Manual tool calls**: Execute specific tools with JSON arguments
- **Interactive chat**: Chat with an LLM that can invoke MCP tools automatically
- **Claude Desktop compatibility**: Uses the same server configuration format

## Installation

```bash
# From the TheBlankOSL_cli directory
pip install -e .
```

## Usage

### List available tools
```bash
blankosl_cli tools
blankosl_cli tools list --verbose
blankosl_cli tools info <tool_name>
```

### Call a tool manually
```bash
blankosl_cli call <tool_name> --args '{"param": "value"}'
```

### Interactive chat mode
```bash
blankosl_cli chat
blankosl_cli chat --model gpt-4
```

### Global options
```bash
blankosl_cli --config /path/to/config.json <command>
blankosl_cli --version
blankosl_cli --help
```

## Configuration

By default, the CLI reads MCP server definitions from Claude Desktop's config file.
You can override this with the `--config` option or `BLANKOSL_CONFIG` environment variable.

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest
```

## License

MIT
