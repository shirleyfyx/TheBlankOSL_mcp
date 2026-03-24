from mcp.server.fastmcp import FastMCP
from typing import Optional, Dict, Any, List, Union
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
import threading
import time
import uuid
import json
import os
import subprocess

# Initialize MCP server
mcp = FastMCP("task-scheduler")

Command = Union[str, List[str]]


@dataclass
class Task:
    id: str
    name: str
    message: str
    delay_seconds: int
    start_monotonic: float
    end_monotonic: float
    start_time_utc: str
    end_time_utc: str
    timer: threading.Timer
    cancelled: bool = False
    done: bool = False
    # NEW: optional command to run at fire time
    command: Optional[Command] = None
    cwd: Optional[str] = None
    env: Optional[Dict[str, str]] = None


TASKS: Dict[str, Task] = {}
NAME_INDEX: Dict[str, str] = {}  # name -> id


def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _secs_left(task: Task) -> int:
    if task.done or task.cancelled:
        return 0
    remain = int(round(task.end_monotonic - time.monotonic()))
    return max(0, remain)


def _exec_command(
    cmd: Command, cwd: Optional[str], env: Optional[Dict[str, str]]
) -> Dict[str, Any]:
    """
    Execute a command. If cmd is a string -> shell=True. If list -> shell=False.
    Returns a dict with returncode/stdout/stderr.
    """
    try:
        if isinstance(cmd, str):
            proc = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                cwd=cwd,
                env=(os.environ | env) if env else None,
            )
        else:
            proc = subprocess.run(
                cmd,
                shell=False,
                capture_output=True,
                text=True,
                cwd=cwd,
                env=(os.environ | env) if env else None,
            )
        return {
            "ok": proc.returncode == 0,
            "returncode": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


def _on_fire(task_id: str):
    task = TASKS.get(task_id)
    if not task or task.cancelled:
        return
    task.done = True

    result: Dict[str, Any] = {}
    # Execute stored command if present
    if task.command is not None:
        result = _exec_command(task.command, task.cwd, task.env)

    # Always log an event so the client sees what happened
    print(
        json.dumps(
            {
                "event": "task_fired",
                "id": task.id,
                "name": task.name,
                "fired_at": _now_utc_iso(),
                "message": task.message,
                "command": task.command,
                "cwd": task.cwd,
                "result": result,
            }
        )
    )


@mcp.tool()
def schedule_in(name: str, message: str, delay_seconds: int) -> Dict[str, Any]:
    """
    Schedule a simple one-shot reminder (no command).
    """
    return _schedule_core(
        name=name,
        message=message,
        delay_seconds=delay_seconds,
        command=None,
        cwd=None,
        env=None,
    )


@mcp.tool()
def schedule_in_command(
    name: str,
    delay_seconds: int,
    command: Command,
    cwd: Optional[str] = None,
    env: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """
    Schedule a one-shot task that executes 'command' when the countdown ends.
    - If 'command' is a string, it runs with shell=True (convenient but riskier).
    - If it's a list, it runs with shell=False (safer): e.g. ["bash","-lc","echo hi"].
    """
    return _schedule_core(
        name=name,
        message=f"Run command: {command}",
        delay_seconds=delay_seconds,
        command=command,
        cwd=cwd,
        env=env,
    )


def _schedule_core(
    name: str,
    message: str,
    delay_seconds: int,
    command: Optional[Command],
    cwd: Optional[str],
    env: Optional[Dict[str, str]],
) -> Dict[str, Any]:
    if delay_seconds <= 0:
        return {"error": "delay_seconds must be > 0"}

    task_id = str(uuid.uuid4())
    start_m = time.monotonic()
    end_m = start_m + delay_seconds

    t = threading.Timer(delay_seconds, _on_fire, args=[task_id])
    t.daemon = True
    t.start()

    start_utc = datetime.now(timezone.utc)
    eta_utc = start_utc + timedelta(seconds=delay_seconds)

    task = Task(
        id=task_id,
        name=name,
        message=message,
        delay_seconds=delay_seconds,
        start_monotonic=start_m,
        end_monotonic=end_m,
        start_time_utc=start_utc.isoformat(),
        end_time_utc=eta_utc.isoformat(),
        timer=t,
        command=command,
        cwd=cwd,
        env=env,
    )
    TASKS[task_id] = task
    NAME_INDEX[name] = task_id

    return {
        "id": task_id,
        "name": name,
        "delay_seconds": delay_seconds,
        "seconds_left": delay_seconds,
        "start_time_utc": task.start_time_utc,
        "eta_utc": task.end_time_utc,
        "has_command": command is not None,
        "command": command,
        "cwd": cwd,
    }


@mcp.tool()
def countdown_status(task_id: str) -> Dict[str, Any]:
    task = TASKS.get(task_id)
    if not task:
        return {"error": "task not found"}
    return {
        "id": task.id,
        "name": task.name,
        "seconds_left": _secs_left(task),
        "total_seconds": task.delay_seconds,
        "started_at": task.start_time_utc,
        "eta_utc": task.end_time_utc,
        "cancelled": task.cancelled,
        "done": task.done,
        "has_command": task.command is not None,
        "command": task.command,
        "cwd": task.cwd,
    }


@mcp.tool()
def cancel(id_or_name: str) -> Dict[str, Any]:
    task = TASKS.get(id_or_name)
    if not task:
        tid = NAME_INDEX.get(id_or_name)
        if tid:
            task = TASKS.get(tid)
    if not task:
        return {"error": "task not found"}

    if not task.done and not task.cancelled:
        try:
            task.timer.cancel()
        except Exception:
            pass
        task.cancelled = True

    return {
        "id": task.id,
        "name": task.name,
        "cancelled": task.cancelled,
        "done": task.done,
    }


@mcp.tool()
def list_tasks() -> Dict[str, Any]:
    out = []
    for t in TASKS.values():
        out.append(
            {
                "id": t.id,
                "name": t.name,
                "seconds_left": _secs_left(t),
                "total_seconds": t.delay_seconds,
                "started_at": t.start_time_utc,
                "eta_utc": t.end_time_utc,
                "cancelled": t.cancelled,
                "done": t.done,
                "has_command": t.command is not None,
                "command": t.command,
                "cwd": t.cwd,
            }
        )
    return {"tasks": out}


if __name__ == "__main__":
    mcp.run(transport="stdio")
