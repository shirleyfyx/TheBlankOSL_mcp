# Project Setup Guide

## Prerequisites
- Python 3.13 or above must be installed on your system.

## Setting Dev Environment with Docker (New Setup)

### 1. Start the Shared Container
1. Open your terminal and navigate to the project directory.
2. Run the startup script (this builds the image and starts the container):
   ```bash
   ./start_docker.sh
   ```
   *Note: You only need to run this once to start the background container.*

### 2. Configure Claude Desktop
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



## Setting Up the Virtual Environment (Old Setup)

### Using `venv`
1. Open your terminal and navigate to the project directory.
2. Create a virtual environment by running:
   ```bash
   python -m venv venv
   ```
3. Activate the virtual environment:
    - On Windows:
      ```bash
      venv\Scripts\activate
      ```
    - On macOS/Linux:
      ```bash
      source venv/bin/activate
      ```
### Using `conda`
1. Open your terminal and navigate to the project directory.
2. Create a new conda environment with Python 3.13 or above:
   ```bash
   conda create -n myenv python=3.13
   ```
3. Activate the conda environment:
   ```bash
    conda activate myenv
    ```
## Installing Requirements
Once the virtual environment is activated, install the required packages by running:
```bash
uv pip install -r requirements.txt
# pip install -r requirements.txt
```
This will install all the necessary dependencies for the project.
