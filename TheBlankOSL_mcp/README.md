# TheBlankOSL - MCP Server & CLI Client

A robust Model Context Protocol (MCP) environment featuring a Python-based CLI client (`blankosl_cli`) and Dockerized server infrastructure.

## Prerequisites
- **Python 3.13+**
- **Docker & Docker Compose**
- **VS Code** (Recommended for Dev Containers)

## Installation

### 1. Build the container
1. Open your terminal and navigate to the project directory.
2. Run "docker compose up -d --build" or "docker compose up -d" if already built.

### 2. Configure VS Code
1. Installs "Dev Containers" extension.
2. Click the >< button in the very bottom-left corner of VS Code.
3. Select "Attach to Running Container...".
4. Choose mcp-shared.

### 3. Configure Claude Desktop
Modify your `claude_desktop_config.json` to connect to the running container using `docker exec`.
You can copy the configuration from `TheBlankOSL_mcp/mcp_client/claude_desktop_config.json`.

Example entry:
```json
{
  "mcpServers": {
    "weather": {
      "command": "docker",
      "args": [
        "exec",
        "-i",
        "mcp-shared",
        "python",
        "TheBlankOSL_mcp/mcp_servers/weather.py"
      ]
    }
  }
}
```
