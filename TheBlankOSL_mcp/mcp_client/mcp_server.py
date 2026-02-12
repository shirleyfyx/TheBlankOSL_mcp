import asyncio
import os
from typing import Optional, Dict, Any, List
from .mcp_transport import McpTransport
from .mcp_config_parser import McpServerConfig

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
        self.capabilities: Dict[str, Any] = {}

    async def start(self):
        """
        Starts the process, attaches transport, and performs handshake.
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
        if not process.stdin or not process.stdout:
            raise RuntimeError(f"Failed to open pipes for {self.name}")

        # 2. Attach Transport & Start Listener
        transport = McpTransport(process.stdout, process.stdin)
        self.transport = transport
        self._listener_task = asyncio.create_task(transport.start_listening())

        # 3. Initialize (Handshake)
        try:
            await self._initialize()
        except Exception as e:
            await self.stop()
            raise RuntimeError(f"Handshake failed for {self.name}: {e}")

    async def _initialize(self):
        """Internal method to perform MCP handshake."""
        # Local variable pin
        transport = self.transport
        if not transport:
            raise RuntimeError("Transport not connected")

        # A. Send capabilities
        response = await transport.send_request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "roots": {"listChanged": True},
                "sampling": {}
            },
            "clientInfo": {"name": "blankosl_cli", "version": "0.1.0"}
        })
        self.capabilities = response.get("capabilities", {})

        # B. Notify initialized
        await transport.send_notification("notifications/initialized", {})

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
        
        # 2. Close pipes
        transport = self.transport
        if transport:
            await transport.close()

        # 3. Kill process
        process = self.process
        if process and process.returncode is None:
            process.terminate()
            try:
                await asyncio.wait_for(process.wait(), timeout=2.0)
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
