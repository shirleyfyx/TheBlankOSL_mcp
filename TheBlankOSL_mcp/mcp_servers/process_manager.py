from mcp.server.fastmcp import FastMCP
from typing import List, Optional
import psutil
import anyio
import subprocess
import time

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

    TIMEOUT = 5.0
    POLL_INTERVAL = 0.05

    def _find_new_process(exe_name=None, before_pids=None, timeout=TIMEOUT, poll_interval=POLL_INTERVAL):
        """Poll for a new process not present in before_pids. Optionally filter by exe_name."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            for p in psutil.process_iter(["pid", "name", "exe", "create_time", "cmdline"]):
                pid = p.info["pid"]
                if before_pids and pid in before_pids:
                    continue
                if exe_name:
                    # match by name or full exe path if available
                    name = (p.info.get("name") or "").lower()
                    exe = (p.info.get("exe") or "").lower()
                    if exe_name.lower() not in (name, exe):
                        continue
                # found a candidate
                return p
            time.sleep(poll_interval)
        return None

    def _start():
        if isinstance(command, str):
            exe_name = command
        else:
            exe_name = "".join(command)

        # snapshot existing processes
        before = {p.pid for p in psutil.process_iter()}
        start_time = time.time()

        # launch (don't force shell unless you need it)
        proc = subprocess.Popen(command, shell=isinstance(command, str))
        # Immediately try to find a new process that wasn't present before
        new_proc = _find_new_process(exe_name=exe_name, before_pids=before, timeout=TIMEOUT)
        if new_proc:
            return new_proc.pid, new_proc
            
        # fallback: maybe the process is a child of the Popen that exited quickly (rare), try by cmdline
        # final fallback: return the Popen pid (may be shell)
        return proc.pid, None

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
