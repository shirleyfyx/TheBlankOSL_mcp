# Project Setup Guide

## Prerequisites
- Python 3.13 or above must be installed on your system.

## Setting Dev Environment with Docker (New Setup)

### Build the Docker Image
1. Open your terminal and navigate to the project directory.
2. Build the Docker image by running:
   ```bash
   docker build -t mcp-server .
   ```
3. Make sure to have the `Dockerfile` in the root directory of the project.

4. Modify the `claude_desktop_config.json` file to look something like this for all the servers:
```json
{
  "mcpServers": {
    "weather": {
      "command": "docker",
      "args": [
        "run",
        "-i",
        "--rm",
        "-v",
        "/Users/design-team-23:/app",
        "mcp-server",
        "python",
        "TheBlankOSL_mcp/mcp_servers/weather.py"
      ]
    },
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
