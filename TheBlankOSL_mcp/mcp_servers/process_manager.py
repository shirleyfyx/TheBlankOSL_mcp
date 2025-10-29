from mcp.server.fastmcp import FastMCP
from typing import List, Optional
import psutil
import anyio

# Initialize MCP server
mcp = FastMCP("process_manager")

@mcp.tool()
async def list_processes() -> List[dict]:
    """List all running processes.

    Returns:
        List of dictionaries with pid and process name.
    """
    def _list() -> List[dict]:
        processes = []
        for proc in psutil.process_iter(['pid', 'name']):
            processes.append({'pid': proc.info['pid'], 'name': proc.info['name']})
        return processes

    return await anyio.to_thread.run_sync(_list)


@mcp.tool()
async def get_process_info(pid: int) -> dict:
    """Get detailed information about a process.

    Args:
        pid: Process ID.

    Returns:
        Dictionary with process info like name, status, CPU and memory usage.

    Raises:
        ValueError: If the process does not exist.
    """
    def _info() -> dict:
        try:
            proc = psutil.Process(pid)
            return {
                'pid': pid,
                'name': proc.name(),
                'status': proc.status(),
                'cpu_percent': proc.cpu_percent(interval=0.1),
                'memory_percent': proc.memory_percent(),
                'exe': proc.exe(),
                'cmdline': proc.cmdline()
            }
        except psutil.NoSuchProcess:
            raise ValueError(f"No process with PID {pid}")

    return await anyio.to_thread.run_sync(_info)

@mcp.tool()
async def start_process(command: list[str] | str) -> dict:
    """Start a new process and return its PID.

    Args:
        command: The command to run, either a list of arguments or a string.

    Returns:
        dict: {
            "pid": <process id>,
            "message": "Process started successfully"
        }
    """
    import subprocess

    def _start():
        if isinstance(command, str):
            # Run in shell mode if string
            proc = subprocess.Popen(command, shell=True)
        else:
            # Run list of args
            proc = subprocess.Popen(command)
        return {"pid": proc.pid, "message": "Process started successfully"}

    return await anyio.to_thread.run_sync(_start)

@mcp.tool()
async def kill_process(pid: int) -> str:
    """Terminate a process by PID.

    Args:
        pid: Process ID.

    Returns:
        Confirmation message.

    Raises:
        ValueError: If the process does not exist or cannot be killed.
    """
    def _kill() -> str:
        try:
            proc = psutil.Process(pid)
            proc.terminate()
            proc.wait(timeout=3)
            return f"Process {pid} terminated successfully"
        except psutil.NoSuchProcess:
            raise ValueError(f"No process with PID {pid}")
        except psutil.TimeoutExpired:
            raise ValueError(f"Process {pid} could not be terminated in time")

    return await anyio.to_thread.run_sync(_kill)


if __name__ == "__main__":
    mcp.run(transport="stdio")
