import asyncio
from typing import Dict, List, Any, Optional
from .utils import load_mcp_config
from .mcp_server import McpServer

class McpManager:
    """
    High-level orchestrator. 
    Manages multiple McpServer instances and routes requests.
    """
    def __init__(self):
        self.sessions: Dict[str, McpServer] = {}

    async def start_all(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Connects to all enabled servers concurrently.
        Returns a dict with 'success' and 'failed' lists.
        """
        config = load_mcp_config()
        results_summary = {"success": [], "failed": []}
        
        tasks = {}
        for name, s_cfg in config.servers.items():
            if s_cfg.enabled:
                server = McpServer(name, s_cfg)
                self.sessions[name] = server
                # 10s timeout prevents a single hanging server from blocking the UI
                tasks[name] = asyncio.wait_for(server.start(), timeout=10.0)

        if not tasks:
            return results_summary

        # Execute all starts in parallel
        results = await asyncio.gather(*tasks.values(), return_exceptions=True)

        for name, result in zip(tasks.keys(), results):
            if isinstance(result, Exception):
                results_summary["failed"].append({
                    "name": name,
                    "error": f"{type(result).__name__}: {str(result)}"
                })
                # Remove from active sessions
                if name in self.sessions:
                    del self.sessions[name]
            else:
                results_summary["success"].append({"name": name})

        return results_summary

    async def get_all_tools(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Returns a dict: { "server_name": [tool1, tool2, ...] }
        """
        results = {}
        for name, server in self.sessions.items():
            try:
                tools = await server.list_tools()
                results[name] = tools
            except Exception as e:
                # Log error but don't crash app
                print(f"Failed to list tools for {name}: {e}")
                results[name] = []
        return results

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """
        Finds the server that owns 'tool_name' and executes it.
        """
        target_server = None
        
        # Discovery Phase: Find which server has the tool
        # (In a production app, cache this mapping)
        for server in self.sessions.values():
            try:
                tools = await server.list_tools()
                for tool in tools:
                    if tool["name"] == tool_name:
                        target_server = server
                        break
            except Exception:
                continue
            
            if target_server:
                break
        
        if not target_server:
            raise ValueError(f"Tool '{tool_name}' not found on any active server.")

        # Execution Phase
        return await target_server.call_tool(tool_name, arguments)

    async def shutdown(self):
        """Gracefully stops all servers."""
        if self.sessions:
            await asyncio.gather(*(s.stop() for s in self.sessions.values()))
            self.sessions.clear()
