import asyncio
import json
import os
import uuid
from pathlib import Path
from typing import Dict, List, Any, Optional, Callable, Awaitable

from .mcp_config_parser import McpServerConfig
from .utils import load_mcp_config, console
from .mcp_server import McpServer

# For elicitation UI and sampling approval (same style as chat MCP request panels)
try:
    from rich.prompt import Prompt
    from rich.panel import Panel
except ImportError:
    Prompt = None
    Panel = None


class UserRejectedError(Exception):
    """Raised when user rejects a sampling request or response. Spec error code -1."""

    code = -1


class McpManager:
    """
    High-level orchestrator.
    Manages multiple McpServer instances and routes requests.
    Supports MCP client features: roots and elicitation.
    """

    def __init__(self):
        self.sessions: Dict[str, McpServer] = {}
        # Roots: list of {"uri": "file:///...", "name": "..."}; servers can request via roots/list
        self.roots: List[Dict[str, str]] = []
        # Optional: callable that returns the current LLM client for sampling/createMessage
        self._llm_getter: Optional[Callable[[], Any]] = None

    def set_llm_getter(self, getter: Optional[Callable[[], Any]]) -> None:
        """Set a callable that returns the current LLM client (used for MCP sampling)."""
        self._llm_getter = getter

    async def start_all(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Connects to all enabled servers concurrently.
        Returns a dict with 'success' and 'failed' lists.
        """
        config = load_mcp_config()
        results_summary = {"success": [], "failed": []}

        # Set roots from config or default to current working directory (proper file:// URI)
        if getattr(config, "roots", None) and config.roots:
            self.roots = list(config.roots)
        else:
            self.roots = [{"uri": Path(os.getcwd()).as_uri(), "name": "Workspace"}]

        tasks = {}
        for name, s_cfg in config.servers.items():
            if s_cfg.enabled:
                server = McpServer(name, s_cfg)
                self.sessions[name] = server
                # 10s timeout prevents a single hanging server from blocking the UI
                tasks[name] = asyncio.wait_for(server.start(self), timeout=10.0)

        if not tasks:
            return results_summary

        # Execute all starts in parallel
        results = await asyncio.gather(*tasks.values(), return_exceptions=True)

        for name, result in zip(tasks.keys(), results):
            if isinstance(result, Exception):
                # Try to get stderr from the server if it exists
                error_msg = f"{type(result).__name__}: {str(result)}"
                if name in self.sessions:
                    server = self.sessions[name]
                    if hasattr(server, "_get_stderr_summary"):
                        stderr = server._get_stderr_summary()
                        if stderr:
                            error_msg += f"\n  Stderr: {stderr}"

                results_summary["failed"].append({"name": name, "error": error_msg})
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

    def get_request_handler(self, server_name: str):
        """
        Returns an async handler (method, params) -> result for server requests:
        roots/list, elicitation/create, sampling/createMessage.
        """

        async def handle(method: str, params: Dict[str, Any]) -> Any:
            if method == "roots/list":
                return {"roots": self.roots}
            if method == "elicitation/create":
                return await self._run_elicitation_ui(server_name, params)
            if method == "sampling/createMessage":
                return await self._run_sampling_create_message(server_name, params)
            raise ValueError(f"Method not supported: {method}")

        return handle

    @staticmethod
    def _spec_content_to_string(content: Any) -> str:
        """Convert MCP sampling content (text/image/tool_use/tool_result) to a single string for our LLM."""
        if content is None:
            return ""
        if isinstance(content, str):
            return content
        if isinstance(content, dict):
            kind = content.get("type", "")
            if kind == "text":
                return content.get("text", "")
            if kind == "tool_use":
                name = content.get("name", "")
                inp = content.get("input", {})
                return f"[Tool use id={content.get('id', '')}]: {name}({inp})"
            if kind == "tool_result":
                tid = content.get("toolUseId", "")
                parts = content.get("content", [])
                texts = [
                    p.get("text", "")
                    for p in parts
                    if isinstance(p, dict) and p.get("type") == "text"
                ]
                return f"[Tool result id={tid}]: " + " ".join(texts)
            if kind == "image":
                return "[image]"
            if kind == "audio":
                return "[audio]"
            return ""
        if isinstance(content, list):
            return " ".join(
                McpManager._spec_content_to_string(c) for c in content
            ).strip()
        return ""

    @classmethod
    def _spec_messages_to_chat(
        cls, messages: List[Dict[str, Any]]
    ) -> List[Dict[str, str]]:
        """Convert MCP sampling messages to our chat format [{role, content: str}, ...]."""
        out: List[Dict[str, str]] = []
        for m in messages or []:
            role = m.get("role", "user")
            content = cls._spec_content_to_string(m.get("content"))
            if role in ("user", "assistant", "system"):
                out.append({"role": role, "content": content})
        return out

    async def _run_sampling_create_message(
        self, server_name: str, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Handle sampling/createMessage per MCP spec: run server's request through our LLM,
        optional human-in-the-loop approval, return { role, content, model, stopReason }.
        """
        from .llm import get_client
        from .sampling import run_sampling_turn, format_tools_list_for_llm

        messages_spec = params.get("messages") or []
        system_prompt = (params.get("systemPrompt") or "").strip()
        max_tokens = params.get("maxTokens")
        tools_spec = params.get("tools") or []
        tool_choice = params.get("toolChoice") or {}

        our_messages = self._spec_messages_to_chat(messages_spec)
        if not our_messages and not system_prompt:
            raise ValueError("Missing messages and systemPrompt")

        # Human-in-the-loop: approve request
        def approve_request():
            preview = system_prompt or ""
            for m in our_messages[-3:]:  # last few messages
                preview += f"\n{m.get('role', '')}: {m.get('content', '')[:200]}"
            if len(preview) > 500:
                preview = preview[:500] + "..."
            console.print(f"\n[bold cyan][{server_name}][/bold cyan] Sampling request:")
            console.print(f"[dim]{preview}[/dim]")
            if not Prompt:
                return (
                    input("Approve sampling request? [Y/n]: ").strip().lower() or "y"
                ) in ("y", "yes")
            reply = (
                Prompt.ask("Approve sampling request? [Y/n]", default="Y")
                .strip()
                .lower()
            )
            return reply in ("", "y", "yes")

        try:
            approved = await asyncio.to_thread(approve_request)
        except Exception as e:
            raise UserRejectedError(f"User rejected sampling request: {e}")
        if not approved:
            raise UserRejectedError("User rejected sampling request")

        # Resolve LLM client
        try:
            client = self._llm_getter() if self._llm_getter else get_client("gemini")
        except Exception as e:
            raise RuntimeError(f"LLM not available: {e}") from e
        if client is None:
            raise RuntimeError("LLM client not available")

        model_id = getattr(client, "id", "gemini")

        tools_context = format_tools_list_for_llm(tools_spec) if tools_spec else ""
        use_tools = bool(tools_context) and (tool_choice.get("mode") != "none")

        if use_tools:
            chat_history = our_messages[:-1] if len(our_messages) > 1 else []
            last_content = our_messages[-1].get("content", "") if our_messages else ""
            if system_prompt:
                last_content = system_prompt + "\n\n" + last_content
            reply_text, tool_calls = await run_sampling_turn(
                self, client, chat_history, last_content, tools_context
            )
            if tool_calls:
                content_spec = [
                    {
                        "type": "tool_use",
                        "id": f"call_{uuid.uuid4().hex[:12]}",
                        "name": tc["name"],
                        "input": tc.get("arguments", {}),
                    }
                    for tc in tool_calls
                ]
                result = {
                    "role": "assistant",
                    "content": content_spec,
                    "model": model_id,
                    "stopReason": "toolUse",
                }
            else:
                result = {
                    "role": "assistant",
                    "content": {"type": "text", "text": reply_text or ""},
                    "model": model_id,
                    "stopReason": "endTurn",
                }
        else:
            chat_with_system = []
            if system_prompt:
                chat_with_system.append({"role": "system", "content": system_prompt})
            chat_with_system.extend(our_messages)
            reply_text = await client.chat(chat_with_system)
            result = {
                "role": "assistant",
                "content": {"type": "text", "text": reply_text or ""},
                "model": model_id,
                "stopReason": "endTurn",
            }

        # Human-in-the-loop: approve response (same MCP request 1/N panel style as chat flow)
        def approve_response():
            if isinstance(result.get("content"), list):
                tool_parts = [
                    c for c in result["content"] if c.get("type") == "tool_use"
                ]
                n = len(tool_parts)
                if Panel and n:
                    for i, c in enumerate(tool_parts):
                        title = (
                            f"[bold cyan]MCP request (sampling) {i + 1}/{n}[/bold cyan]"
                        )
                        body = json.dumps(
                            {"name": c.get("name"), "arguments": c.get("input", {})},
                            indent=2,
                        )
                        console.print(Panel(body, title=title, border_style="cyan"))
                else:
                    console.print("[dim]Tool use(s) to return to server[/dim]")
                    for c in tool_parts:
                        console.print(f"  - {c.get('name')}({c.get('input')})")
            else:
                text = (result.get("content") or {}).get("text", "")[:400]
                console.print(f"[dim]{text}[/dim]")
            if not Prompt:
                return (input("Approve response? [Y/n]: ").strip().lower() or "y") in (
                    "y",
                    "yes",
                )
            reply = Prompt.ask("Approve response? [Y/n]", default="Y").strip().lower()
            return reply in ("", "y", "yes")

        try:
            approved = await asyncio.to_thread(approve_response)
        except Exception as e:
            raise UserRejectedError(f"User rejected response: {e}")
        if not approved:
            raise UserRejectedError("User rejected sampling response")

        return result

    async def _run_elicitation_ui(
        self, server_name: str, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Run elicitation UI (form or URL mode). Blocking prompts run in thread.
        Returns {"action": "accept", "content": {...}} or {"action": "decline", "reason": "..."}.
        """
        mode = (params.get("mode") or "form").lower()
        message = params.get("message") or "The server is requesting information."

        if mode == "url":
            return await self._elicitation_url(server_name, message, params)
        return await self._elicitation_form(server_name, message, params)

    async def _elicitation_url(
        self, server_name: str, message: str, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """URL mode: show message and URL, ask user to open; return accept or decline."""
        url = params.get("url") or ""
        if not url:
            return {
                "action": "decline",
                "reason": "Missing url in elicitation request.",
            }

        def prompt_url():
            console.print(f"\n[bold cyan][{server_name}][/bold cyan] {message}")
            console.print(f"[dim]URL: {url}[/dim]")
            if not Prompt:
                console.print("[yellow]Open this URL in your browser? (Y/n)[/yellow]")
                return (input().strip().lower() or "y") in ("y", "yes")
            reply = Prompt.ask("Open URL? [Y/n]", default="Y").strip().lower()
            return reply in ("", "y", "yes")

        try:
            ok = await asyncio.to_thread(prompt_url)
            return (
                {"action": "accept"}
                if ok
                else {"action": "decline", "reason": "User declined."}
            )
        except Exception as e:
            return {"action": "decline", "reason": str(e)}

    async def _elicitation_form(
        self, server_name: str, message: str, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Form mode: build prompts from requestedSchema, collect and validate, return accept with content or decline."""
        schema = params.get("requestedSchema") or {}
        if schema.get("type") != "object":
            schema = {
                "type": "object",
                "properties": schema.get("properties", {}),
                "required": schema.get("required", []),
            }
        properties = schema.get("properties") or {}
        required = schema.get("required") or []

        def prompt_form():
            out = {}
            console.print(f"\n[bold cyan][{server_name}][/bold cyan] {message}")
            for key, prop in properties.items():
                if not isinstance(prop, dict):
                    continue
                desc = prop.get("description") or key
                title = prop.get("title") or key
                ptype = prop.get("type", "string")
                default = prop.get("default")
                enum_vals = prop.get("enum")
                default_str = str(default) if default is not None else ""

                if enum_vals is not None:
                    opts = ", ".join(str(v) for v in enum_vals)
                    prompt_text = f"{title} ({opts})"
                else:
                    prompt_text = title
                if default_str and ptype != "boolean":
                    prompt_text += f" [{default_str}]"

                if ptype == "boolean":
                    if Prompt:
                        reply = (
                            Prompt.ask(prompt_text, default="y" if default else "n")
                            .strip()
                            .lower()
                        )
                    else:
                        reply = input(f"{prompt_text} (y/n): ").strip().lower() or (
                            "y" if default else "n"
                        )
                    out[key] = reply in ("y", "yes", "true", "1")
                elif ptype in ("number", "integer"):
                    if Prompt:
                        reply = Prompt.ask(prompt_text, default=default_str).strip()
                    else:
                        reply = input(f"{prompt_text}: ").strip() or default_str
                    try:
                        out[key] = int(reply) if ptype == "integer" else float(reply)
                    except ValueError:
                        out[key] = reply
                else:
                    if Prompt:
                        # Check if the property name or title contains "password"
                        is_password = (
                            "password" in key.lower() or "password" in title.lower()
                        )
                        reply = Prompt.ask(
                            prompt_text, default=default_str, password=is_password
                        ).strip()
                    else:
                        reply = input(f"{prompt_text}: ").strip() or default_str
                    out[key] = reply

            # Optional: decline option
            if Prompt:
                decline = (
                    Prompt.ask("Submit this form? [Y/n]", default="Y").strip().lower()
                )
            else:
                decline = input("Submit this form? (Y/n): ").strip().lower() or "y"
            if decline in ("n", "no"):
                return None
            return out

        try:
            content = await asyncio.to_thread(prompt_form)
            if content is None:
                return {"action": "decline", "reason": "User declined."}
            return {"action": "accept", "content": content}
        except Exception as e:
            return {"action": "decline", "reason": str(e)}

    async def start_server(self, name: str, s_cfg: McpServerConfig) -> None:
        """Dynamically start a single server and add it to active sessions."""
        if name in self.sessions:
            raise ValueError(f"Server '{name}' is already running.")

        server = McpServer(name, s_cfg)

        # Start the server with a timeout to prevent hanging the CLI
        await asyncio.wait_for(server.start(self), timeout=10.0)

        # If successful, add to active sessions
        self.sessions[name] = server

    async def shutdown(self):
        """Gracefully stops all servers."""
        if self.sessions:
            await asyncio.gather(*(s.stop() for s in self.sessions.values()))
            self.sessions.clear()
