# MCP Servers
This repository contains all the mcp servers. If you want to add a new feature to the OSL, you must create a new mcp server here.

## Getting Started
Before running any server, ensure that your environement is set up correctly.

Follow the official MCP [documentation](https://modelcontextprotocol.io/docs/develop/build-server) for installation and setup.

## Running a Server
Each server runs independently. Navigate into the server’s directory and use the appropriate command:
```bash
uv run server.py
```

## Connecting to Claude Desktop
To register a server with Claude Desktop, edit:
```bash
~/Library/Application Support/Claude/claude_desktop_config.json
```
Example configuration entry:
```bash
{
  "mcpServers": {
    "weather": {
      "command": "uv",
      "args": [
        "--directory",
        "/ABSOLUTE/PATH/TO/PARENT/FOLDER/weather",
        "run",
        "weather.py"
      ]
    }
  }
}
```
Restart Claude Desktop after editing.