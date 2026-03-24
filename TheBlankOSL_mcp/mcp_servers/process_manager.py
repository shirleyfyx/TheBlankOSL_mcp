from mcp.server.fastmcp import FastMCP
from typing import List
import psutil
import anyio
import asyncio
import subprocess
import time
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Windows-specific imports
if sys.platform == "win32":
    try:
        import winreg
    except ImportError:
        winreg = None
else:
    winreg = None

# Initialize MCP server
mcp = FastMCP("process_manager")


def _find_application_path(app_name: str) -> str | None:
    """Find the executable path for an application by name.

    Args:
        app_name: Name of the application (e.g., "outlook", "notepad", "spotify")

    Returns:
        Full path to the executable if found, None otherwise.
    """
    # Normalize app name (remove .exe if present, make lowercase)
    app_name_lower = app_name.lower().replace(".exe", "")
    app_name_exe = app_name_lower + ".exe"
    app_name_exe_upper = app_name_lower.upper() + ".EXE"

    # 1. Try Windows registry (Windows only)
    if winreg and sys.platform == "win32":
        try:
            # Try with .exe suffix
            key_path = f"SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\App Paths\\{app_name_exe_upper}"
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path)
            app_path = winreg.QueryValue(key, None)
            winreg.CloseKey(key)
            if app_path and os.path.exists(app_path):
                return app_path
        except (FileNotFoundError, OSError):
            pass

        try:
            # Try without .exe suffix
            key_path = f"SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\App Paths\\{app_name_lower}"
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path)
            app_path = winreg.QueryValue(key, None)
            winreg.CloseKey(key)
            if app_path and os.path.exists(app_path):
                return app_path
        except (FileNotFoundError, OSError):
            pass

    # 2. Try common program file paths (Windows)
    if sys.platform == "win32":
        program_paths = [
            os.path.expandvars(r"%ProgramFiles%"),
            os.path.expandvars(r"%ProgramFiles(x86)%"),
            os.path.expandvars(r"%LocalAppData%\Programs"),
        ]

        # Common application directories to search (direct check first, then limited recursive)
        search_dirs = []
        for base in program_paths:
            if not base or not os.path.exists(base):
                continue
            # Direct paths to check
            search_dirs.extend(
                [
                    base,
                    os.path.join(base, app_name_lower),
                    os.path.join(base, app_name_lower.capitalize()),
                ]
            )
            # Common subdirectories where apps are installed
            common_subdirs = [
                "Microsoft Office",
                "Microsoft",
                "Google",
                "Spotify",
                "Adobe",
            ]
            for subdir in common_subdirs:
                subdir_path = os.path.join(base, subdir)
                if os.path.exists(subdir_path):
                    search_dirs.append(subdir_path)

        # Look for the executable in these directories (direct check first)
        for search_dir in search_dirs:
            if not os.path.exists(search_dir):
                continue
            # Check directly in directory
            for exe_name in [app_name_exe, app_name_exe_upper, app_name_lower + ".exe"]:
                exe_path = os.path.join(search_dir, exe_name)
                if os.path.exists(exe_path):
                    return exe_path

        # Limited recursive search only in Program Files (depth 2 for performance)
        for base in [
            os.path.expandvars(r"%ProgramFiles%"),
            os.path.expandvars(r"%ProgramFiles(x86)%"),
        ]:
            if not base or not os.path.exists(base):
                continue
            try:
                for root, dirs, files in os.walk(base):
                    # Limit depth to 2 levels for performance
                    depth = root[len(base) :].count(os.sep)
                    if depth > 2:
                        dirs[:] = []  # Don't recurse deeper
                        continue
                    for file in files:
                        if file.lower() == app_name_exe:
                            exe_path = os.path.join(root, file)
                            if os.path.exists(exe_path):
                                return exe_path
            except (PermissionError, OSError):
                continue

    # 3. Try PATH environment variable
    path_dirs = os.environ.get("PATH", "").split(os.pathsep)
    for path_dir in path_dirs:
        if not path_dir or not os.path.exists(path_dir):
            continue
        for exe_name in [
            app_name_exe,
            app_name_exe_upper,
            app_name_lower + ".exe",
            app_name,
        ]:
            exe_path = os.path.join(path_dir, exe_name)
            if os.path.exists(exe_path):
                return exe_path

    # 4. Fallback: try to find in running processes
    for proc in psutil.process_iter(["name", "exe"]):
        try:
            proc_name = proc.info.get("name", "").lower()
            if app_name_lower in proc_name or proc_name == app_name_exe:
                exe_path = proc.info.get("exe")
                if exe_path and os.path.exists(exe_path):
                    return exe_path
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    return None


@mcp.tool()
async def list_processes() -> List[dict]:
    """List all running processes.

    Returns:
        List of dictionaries with pid and process name.
    """

    def _list() -> List[dict]:
        processes = []
        for proc in psutil.process_iter(["pid", "name"]):
            processes.append({"pid": proc.info["pid"], "name": proc.info["name"]})
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
                "pid": pid,
                "name": proc.name(),
                "status": proc.status(),
                "cpu_percent": proc.cpu_percent(interval=0.1),
                "memory_percent": proc.memory_percent(),
                "exe": proc.exe(),
                "cmdline": proc.cmdline(),
            }
        except psutil.NoSuchProcess:
            raise ValueError(f"No process with PID {pid}")

    return await anyio.to_thread.run_sync(_info)


@mcp.tool()
async def start_process(command: list[str] | str) -> dict:
    """Start a new process and return its PID. Handles complex applications that spawn multiple processes.

    Args:
        command: The command to run, either a list of arguments or a string.

    Returns:
        dict: {
            "pid": <main process id>,
            "child_pids": [<list of child process ids>],
            "total_processes": <total number of related processes>,
            "message": "Process started successfully"
        }
    """

    TIMEOUT = 3.0  # Increased timeout for complex apps
    POLL_INTERVAL = 0.1
    POLL_COUNT = int(TIMEOUT / POLL_INTERVAL)  # Number of polling iterations

    def _get_process_tree(root_pid, visited=None):
        """Recursively get all child processes starting from root_pid."""
        if visited is None:
            visited = set()
        if root_pid in visited:
            return []

        visited.add(root_pid)
        children = []

        try:
            proc = psutil.Process(root_pid)
            for child in proc.children(recursive=True):
                child_pid = child.pid
                if child_pid not in visited:
                    children.append(child_pid)
                    visited.add(child_pid)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

        return children

    def _find_application_processes(
        exe_name, before_pids, launch_time, timeout=TIMEOUT
    ):
        """Find all processes matching the application name created after launch_time."""
        deadline = time.time() + timeout
        matching_processes = []
        all_related_pids = set()

        # Poll multiple times to catch processes that spawn later
        poll_count = 0
        while time.time() < deadline and poll_count < POLL_COUNT:
            for p in psutil.process_iter(
                ["pid", "name", "exe", "create_time", "ppid", "cmdline"]
            ):
                pid = p.info["pid"]

                # Skip if it existed before launch
                if pid in before_pids:
                    continue

                # Skip if we've already processed it
                if pid in all_related_pids:
                    continue

                try:
                    proc = psutil.Process(pid)
                    name = (proc.name() or "").lower()
                    exe = (proc.exe() or "").lower() if hasattr(proc, "exe") else ""
                    cmdline_str = " ".join(proc.cmdline() or []).lower()

                    # Check if process name matches (case-insensitive partial match)
                    name_match = (
                        exe_name.lower() in name
                        or exe_name.lower() in exe
                        or exe_name.lower() in cmdline_str
                    )

                    # Also check if it's a child of a matching process
                    is_child = False
                    try:
                        ppid = proc.ppid()
                        if ppid in all_related_pids:
                            is_child = True
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass

                    if name_match or is_child:
                        matching_processes.append((pid, proc, name, exe))
                        all_related_pids.add(pid)

                        # Also add all children of this process
                        try:
                            children = _get_process_tree(pid)
                            all_related_pids.update(children)
                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            pass

                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

            time.sleep(POLL_INTERVAL)
            poll_count += 1

        return list(all_related_pids), matching_processes

    def _find_main_process(
        popen_pid, exe_name=None, before_pids=None, launch_time=None, timeout=TIMEOUT
    ):
        """Find the main process by name matching and process tree."""
        if launch_time is None:
            launch_time = time.time()

        # First, try to find processes by name matching
        all_pids, matching_procs = _find_application_processes(
            exe_name, before_pids, launch_time, timeout
        )

        # Also check the Popen process and its direct tree
        if popen_pid not in all_pids:
            try:
                tree_pids = _get_process_tree(popen_pid)
                all_pids.extend([popen_pid] + tree_pids)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                all_pids.append(popen_pid)

        # Remove duplicates
        all_pids = list(set(all_pids))

        # Find the main process
        main_pid = popen_pid
        max_children = -1
        best_match_score = -1

        for pid in all_pids:
            try:
                proc = psutil.Process(pid)
                children_count = len(proc.children(recursive=True))

                # Score based on name matching and children count
                name = (proc.name() or "").lower()
                exe = (proc.exe() or "").lower() if hasattr(proc, "exe") else ""
                cmdline_str = " ".join(proc.cmdline() or []).lower()

                match_score = 0
                if exe_name:
                    # Exact name match gets highest score
                    if (
                        exe_name.lower() == name
                        or exe_name.lower() == exe.split("\\")[-1].split("/")[-1]
                    ):
                        match_score = 100
                    elif exe_name.lower() in name or exe_name.lower() in exe:
                        match_score = 50
                    elif exe_name.lower() in cmdline_str:
                        match_score = 25

                # Combine match score with children count
                total_score = match_score + children_count

                if total_score > best_match_score or (
                    total_score == best_match_score and children_count > max_children
                ):
                    main_pid = pid
                    max_children = children_count
                    best_match_score = total_score

            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        # Get all child PIDs (excluding the main process itself)
        child_pids = [pid for pid in all_pids if pid != main_pid]

        return main_pid, child_pids

    def _start():
        # Determine the executable name for process matching
        if isinstance(command, str):
            exe_name = command.split()[0] if " " in command else command
            # Extract executable name from command string
            if "\\" in exe_name or "/" in exe_name:
                exe_name = exe_name.split("\\")[-1].split("/")[-1]
            original_command = command
        else:
            exe_name = command[0] if command else None
            if exe_name and ("\\" in exe_name or "/" in exe_name):
                exe_name = exe_name.split("\\")[-1].split("/")[-1]
            original_command = command

        # If command doesn't look like a full path, try to find the executable
        actual_command = original_command
        if isinstance(original_command, str):
            # Extract just the executable part (first word) to check if it's a path
            cmd_exe = (
                original_command.split()[0]
                if " " in original_command
                else original_command
            )
            # Check if it's already a full path or exists in current directory
            if not os.path.isabs(cmd_exe) and not os.path.exists(cmd_exe):
                # Try to find the application path
                found_path = _find_application_path(exe_name)
                if found_path:
                    # If there were arguments in the original command, preserve them
                    if " " in original_command:
                        args = original_command.split()[1:]
                        actual_command = [found_path] + args
                    else:
                        actual_command = found_path
        elif isinstance(original_command, list) and original_command:
            # Check if first element is a full path or exists
            first_arg = original_command[0]
            if not os.path.isabs(first_arg) and not os.path.exists(first_arg):
                # Try to find the application path
                found_path = _find_application_path(exe_name)
                if found_path:
                    # Replace first element with found path, keep rest of arguments
                    actual_command = [found_path] + original_command[1:]

        # snapshot existing processes
        before = {p.pid for p in psutil.process_iter()}
        launch_time = time.time()

        # launch (don't force shell unless you need it)
        # Use shell=True only if actual_command is a string and we couldn't find a path
        use_shell = (
            isinstance(actual_command, str)
            and not os.path.isabs(actual_command)
            and not os.path.exists(actual_command)
        )
        proc = subprocess.Popen(actual_command, shell=use_shell)
        popen_pid = proc.pid

        # Find the main process and all related processes
        # This will poll multiple times to catch processes that spawn later
        main_pid, child_pids = _find_main_process(
            popen_pid,
            exe_name=exe_name,
            before_pids=before,
            launch_time=launch_time,
            timeout=TIMEOUT,
        )

        return main_pid, child_pids

    result = await anyio.to_thread.run_sync(_start)
    main_pid, child_pids = result

    return {
        "pid": main_pid,
        "child_pids": child_pids,
        "total_processes": len(child_pids) + 1,
        "message": f"Process started successfully with {len(child_pids)} child process(es)",
    }


@mcp.tool()
async def start_process_delayed(command: list[str] | str, delay: float) -> dict:
    """Start a new process after a specified delay. Returns immediately, allowing other work during the delay.

    Args:
        command: The command to run, either a list of arguments or a string.
        delay: The delay in seconds before starting the process (e.g., 30.0 for 30 seconds).

    Returns:
        dict: {
            "message": "Process scheduled to start after delay"
        }

    Note:
        The process will start in the background after the specified delay.
        The function returns immediately so you can continue with other work.
    """

    async def _delayed_start():
        """Background task that waits for delay and then starts the process."""
        await anyio.sleep(delay)
        await start_process(command)

    # Start the background task without awaiting it (fire-and-forget)
    asyncio.create_task(_delayed_start())

    return {"message": f"Process scheduled to start after {delay} second(s) delay."}


@mcp.tool()
async def start_process_at_time(command: list[str] | str, target_time: str) -> dict:
    """Start a new process at a specific date/time. Returns immediately, allowing other work until the scheduled time.

    Args:
        command: The command to run, either a list of arguments or a string.
        target_time: The target date/time in ISO format. Can be:
                     - UTC with 'Z' suffix (e.g., "2024-12-25T22:00:00Z")
                     - UTC with offset (e.g., "2024-12-25T22:00:00-05:00" for Eastern Time)
                     - Local time without timezone (e.g., "2024-12-25T22:00:00" - assumes local timezone with DST)

    Returns:
        dict: {
            "message": "Process scheduled to start at specified time"
        }

    Raises:
        ValueError: If the target time is not in the future or if the format is invalid.

    Note:
        The process will start in the background at the specified time.
        The function returns immediately so you can continue with other work.
        If no timezone is specified, local timezone is assumed (accounts for daylight savings).
    """
    # Parse the target time (accepts 'Z' suffix, offset, or timezone-naive formats)
    try:
        # Handle 'Z' suffix (UTC) - convert to +00:00 format for fromisoformat
        if target_time.endswith("Z"):
            target_dt = datetime.fromisoformat(target_time.replace("Z", "+00:00"))
        # Handle offset format (e.g., -05:00, +00:00) - check if it ends with offset pattern
        elif (
            len(target_time) >= 6
            and target_time[-6:].startswith(("+", "-"))
            and ":" in target_time[-6:]
        ):
            target_dt = datetime.fromisoformat(target_time)
        # Handle timezone-naive format - will assume local timezone
        else:
            target_dt = datetime.fromisoformat(target_time)
    except ValueError as e:
        raise ValueError(
            f"Invalid datetime format: {target_time}. Use ISO format (e.g., '2024-12-25T22:00:00', '2024-12-25T22:00:00Z', or '2024-12-25T22:00:00-05:00'). Error: {e}"
        )

    # If timezone-naive, assume local timezone (accounts for DST automatically)
    if target_dt.tzinfo is None:
        # Get local timezone
        local_now = datetime.now().astimezone()
        local_tz = local_now.tzinfo

        # Apply local timezone to the naive datetime
        # For pytz timezones, use localize() which correctly handles DST
        if hasattr(local_tz, "localize"):
            target_dt = local_tz.localize(target_dt)
        else:
            # For standard library timezones, construct the datetime with tzinfo
            # This will automatically apply the correct DST offset for the target date
            target_dt = datetime(
                target_dt.year,
                target_dt.month,
                target_dt.day,
                target_dt.hour,
                target_dt.minute,
                target_dt.second,
                target_dt.microsecond,
                tzinfo=local_tz,
            )

    # Convert target time to UTC for comparison
    target_dt_utc = target_dt.astimezone(timezone.utc)

    # Get current time in UTC
    now = datetime.now(timezone.utc)

    # Assert that the time is in the future
    if target_dt_utc <= now:
        raise ValueError(
            f"Target time {target_time} must be in the future. Current UTC time is {now.isoformat().replace('+00:00', 'Z')}."
        )

    # Calculate delay in seconds (using UTC times)
    delay_seconds = (target_dt_utc - now).total_seconds()

    async def _scheduled_start():
        """Background task that waits until target time and then starts the process."""
        await anyio.sleep(delay_seconds)
        await start_process(command)

    # Start the background task without awaiting it (fire-and-forget)
    asyncio.create_task(_scheduled_start())

    return {
        "message": f"Process scheduled to start at {target_dt.isoformat()} (in {delay_seconds:.1f} seconds)."
    }


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
