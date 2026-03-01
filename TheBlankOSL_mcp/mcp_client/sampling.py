import json
import re
from typing import Any, Dict, List, Tuple

from .mcp_manager import McpManager

TOOL_CALL_START = "TOOL_CALL"
TOOL_CALL_END = "END_TOOL_CALL"


def format_tools_list_for_llm(tools: List[Dict[str, Any]]) -> str:
    """Format spec-style tools array (name, description, inputSchema) into a string for the LLM."""
    if not tools:
        return ""
    lines: List[str] = []
    for tool in tools:
        name = tool.get("name", "unknown")
        desc = (tool.get("description") or "").strip() or "No description."
        schema = tool.get("inputSchema") or {}
        props = schema.get("properties") or {}
        required = schema.get("required") or []
        args_hint = ", ".join(
            f'{k}{" (required)" if k in required else " (optional)"}' for k in props.keys()
        )
        if not args_hint:
            args_hint = "no arguments"
        lines.append(f"- {name}: {desc}. Arguments: {args_hint}")
    return "\n".join(lines)

SYSTEM_PROMPT_TEMPLATE = """You are a helpful assistant with access to MCP (Model Context Protocol) tools. You MUST use these tools when the user asks for something the tools can do—do not refuse or reply with only text when a tool can perform the action.
When the user's request matches any tool below, respond with one or more tool call blocks (no other text). Each block on its own:

{start}
{{"name": "<tool_name>", "arguments": {{ ... }}}}
{end}

RULE: If the user asks for weather, files, contacts, alerts, or to save/write something, and a tool below can do it, you MUST output the corresponding TOOL_CALL block(s). Do not say "I cannot" or give only a text answer when a tool exists for the request.

IMPORTANT - Multiple actions: If the user asks for MORE THAN ONE thing (e.g. "send an email AND tell me the weather", "email X and include the weather for SF"), you MUST output MULTIPLE TOOL_CALL blocks—one per action. Put the block that fetches data first (e.g. get_forecast_for_city) before the block that uses it (e.g. send_email). Example: user says "email John with the weather in SF" -> output first TOOL_CALL get_forecast_for_city with location "San Francisco", then second TOOL_CALL for the email tool with recipient and a body that mentions including the weather (you can write the body text; the actual weather will be filled in when tools run in order).
CRITICAL - Saving fetched data to a file: If the user asks to fetch something AND save it (e.g. "get weather for X and save to my desktop"), do NOT output write_file in the same turn as the fetch. You do not have the fetched content yet. Output ONLY the tool(s) that fetch the data (e.g. get_forecast_for_city). You will receive the result in a follow-up step; then output write_file with the actual fetched content as the "content" argument. So: first turn = get_forecast_for_city only; after you see the forecast result, next turn = write_file with path "~/Desktop/..." and content = that forecast text.
Use the exact "name" from the list. For "arguments", use a JSON object matching the tool's schema (use {{}} if none needed).
For tools that need latitude/longitude (e.g. get_forecast), use approximate coordinates when the user gives a city name. Prefer get_forecast_for_city(location) when the user names a city.
For add_contact: include every field the user provides (name, address, phone, email, etc.).
For saving to the user's Downloads or Desktop: use path "~/Downloads/filename" or "~/Desktop/filename" (the ~ expands to the user's home). Do NOT guess paths like /root/Desktop—use ~ so it works on any system. Or call get_home_directory first, then in a follow-up use write_file with path "<home>/Desktop/filename".
If the request does not match any tool, respond with normal helpful text and do NOT output any tool call block.

Available MCP tools:
{tools_list}
"""


async def build_tools_context(manager: McpManager) -> str:
    """Build a string description of all MCP tools for the LLM (text-based fallback)."""
    all_tools = await manager.get_all_tools()
    lines: List[str] = []
    for server_name, tools in all_tools.items():
        for tool in tools:
            name = tool.get("name", "unknown")
            desc = (tool.get("description") or "").strip() or "No description."
            schema = tool.get("inputSchema") or {}
            props = schema.get("properties") or {}
            required = schema.get("required") or []
            args_hint = ", ".join(
                f'{k}{" (required)" if k in required else " (optional)"}' for k in props.keys()
            )
            if not args_hint:
                args_hint = "no arguments"
            lines.append(f"- {name} [server: {server_name}]: {desc}. Arguments: {args_hint}")
    if not lines:
        return ""
    return "\n".join(lines)


def parse_tool_calls_from_response(response: str) -> List[Dict[str, Any]]:
    """Parse all TOOL_CALL...END_TOOL_CALL blocks; return list of {"name": str, "arguments": dict}."""
    if not response or TOOL_CALL_START not in response or TOOL_CALL_END not in response:
        return []
    pattern = re.compile(
        re.escape(TOOL_CALL_START) + r"\s*\n?\s*([\s\S]*?)\s*\n?\s*" + re.escape(TOOL_CALL_END),
        re.DOTALL,
    )
    out: List[Dict[str, Any]] = []
    for match in pattern.finditer(response):
        try:
            raw = match.group(1).strip()
            data = json.loads(raw)
            name = data.get("name")
            arguments = data.get("arguments")
            if not name or not isinstance(name, str):
                continue
            if arguments is None:
                arguments = {}
            if not isinstance(arguments, dict):
                continue
            out.append({"name": name, "arguments": arguments})
        except (json.JSONDecodeError, AttributeError):
            continue
    return out


def strip_tool_call_blocks(response: str) -> str:
    """Remove all TOOL_CALL blocks from the response for display."""
    if TOOL_CALL_START not in response or TOOL_CALL_END not in response:
        return response.strip()
    pattern = re.compile(
        r"\s*" + re.escape(TOOL_CALL_START) + r".*?" + re.escape(TOOL_CALL_END) + r"\s*",
        re.DOTALL,
    )
    return pattern.sub("", response).strip()


async def run_sampling_turn(
    manager: McpManager,
    client: Any,
    chat_history: List[Dict[str, str]],
    user_message: str,
    tools_context: str,
) -> Tuple[str, List[Dict[str, Any]]]:
    """
    One sampling turn: send user message + tools to LLM. Returns (reply_text, list of tool_calls).
    Uses text-based TOOL_CALL block parsing. Each tool_call is {"name": str, "arguments": dict}.
    """
    if not tools_context:
        return ("", [])

    # Text-based TOOL_CALL block parsing
    system_content = SYSTEM_PROMPT_TEMPLATE.format(
        start=TOOL_CALL_START,
        end=TOOL_CALL_END,
        tools_list=tools_context,
    )
    user_content = (
        f"[Use MCP tools when the request matches. Respond with TOOL_CALL block(s) if any tool above can fulfill this; otherwise reply in text.]\n\n{user_message}"
    )
    messages = [
        {"role": "system", "content": system_content},
        *chat_history,
        {"role": "user", "content": user_content},
    ]
    reply = await client.chat(messages)
    tool_calls = parse_tool_calls_from_response(reply)
    reply_clean = strip_tool_call_blocks(reply)
    return (reply_clean, tool_calls)
