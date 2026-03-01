import asyncio
import os
from typing import Optional, Dict, Any, List, TYPE_CHECKING
from .mcp_transport import McpTransport
from .mcp_config_parser import McpServerConfig

if TYPE_CHECKING:
    from .mcp_manager import McpManager


class McpServer:
    """
    Manages a single server's process, transport, and lifecycle.
    """
    def __init__(self, name: str, config: McpServerConfig):
        self.name = name
        self.config = config
        self.process: Optional[asyncio.subprocess.Process] = None
        self.transport: Optional[McpTransport] = None
        self._listener_task: Optional[asyncio.Task] = None
        self._stderr_task: Optional[asyncio.Task] = None
        self._stderr_buffer: List[str] = []
        self.capabilities: Dict[str, Any] = {}

    async def start(self, manager: Optional["McpManager"] = None):
        """
        Starts the process, attaches transport, and performs handshake.
        If manager is provided, registers handler for server requests (roots/list, elicitation/create).
        """
        if not self.config.enabled:
            return

        env = {**os.environ, **self.config.env}

        # 1. Spawn Process
        try:
            # Assign to local variable first to satisfy linter
            process = await asyncio.create_subprocess_exec(
                self.config.command,
                *self.config.args,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env
            )
            self.process = process
        except FileNotFoundError:
            raise FileNotFoundError(f"Command not found: {self.config.command}")

        # Strict check on the local variable 'process'
        if not process.stdin or not process.stdout or not process.stderr:
            raise RuntimeError(f"Failed to open pipes for {self.name}")

        # 2. Start stderr reader to capture errors
        self._stderr_buffer = []
        self._stderr_task = asyncio.create_task(self._read_stderr(process.stderr))

        # 3. Attach Transport & Start Listener
        transport = McpTransport(process.stdout, process.stdin)
        self.transport = transport
        if manager:
            transport.set_request_handler(manager.get_request_handler(self.name))
        self._listener_task = asyncio.create_task(transport.start_listening())

        # 4. Initialize (Handshake)
        try:
            await self._initialize()
        except Exception as e:
            # Include stderr output in error message if available
            stderr_msg = self._get_stderr_summary()
            error_msg = f"Handshake failed for {self.name}: {e}"
            if stderr_msg:
                error_msg += f"\nServer stderr: {stderr_msg}"
            await self.stop()
            raise RuntimeError(error_msg)

    async def _initialize(self):
        """Internal method to perform MCP handshake."""
        # Local variable pin
        transport = self.transport
        if not transport:
            raise RuntimeError("Transport not connected")

        # A. Send capabilities (roots, elicitation, sampling per MCP client-concepts)
        response = await transport.send_request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "roots": {"listChanged": True},
                "elicitation": {"form": {}, "url": {}},
                "sampling": {"tools": {}}
            },
            "clientInfo": {"name": "blankosl_cli", "version": "0.1.0"}
        })
        self.capabilities = response.get("capabilities", {})

        # B. Notify initialized
        await transport.send_notification("notifications/initialized", {})

    async def _read_stderr(self, stderr: asyncio.StreamReader):
        """Background task to read stderr and buffer it."""
        try:
            while True:
                line = await stderr.readline()
                if not line:
                    break
                self._stderr_buffer.append(line.decode('utf-8', errors='replace').rstrip())
        except Exception:
            pass  # Process may have terminated

    def _get_stderr_summary(self, max_lines: int = 5) -> str:
        """Get a summary of stderr output."""
        if not self._stderr_buffer:
            return ""
        lines = self._stderr_buffer[-max_lines:] if len(self._stderr_buffer) > max_lines else self._stderr_buffer
        return "\n".join(lines)

    async def list_tools(self) -> List[Dict[str, Any]]:
        """Fetch tools available on this server."""
        # Local variable pin
        transport = self.transport
        if not transport:
            raise RuntimeError(f"Server {self.name} is not connected.")
        
        response = await transport.send_request("tools/list", {})
        
        # Ensure correct type return
        tools = response.get("tools", [])
        if isinstance(tools, list):
            return tools
        return []

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Execute a tool on this server."""
        # Local variable pin
        transport = self.transport
        if not transport:
            raise RuntimeError(f"Server {self.name} is not connected.")
            
        response = await transport.send_request("tools/call", {
            "name": tool_name,
            "arguments": arguments
        })
        return response

    async def stop(self):
        """Clean shutdown."""
        # 1. Cancel listener
        if self._listener_task:
            self._listener_task.cancel()
            try:
                await self._listener_task
            except asyncio.CancelledError:
                pass

        # 2. Cancel stderr reader
        if self._stderr_task:
            self._stderr_task.cancel()
            try:
                await self._stderr_task
            except asyncio.CancelledError:
                pass
        
        # 3. Close pipes
        transport = self.transport
        if transport:
            await transport.close()

        # 4. Kill process
        process = self.process
        if process and process.returncode is None:
            process.terminate()
            try:
                await asyncio.wait_for(process.wait(), timeout=2.0)
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
