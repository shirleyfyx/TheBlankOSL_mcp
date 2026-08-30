import json
import re
from typing import Any, Dict, List, Optional, Tuple

from .mcp_manager import McpManager

TOOL_CALL_START = "TOOL_CALL"
TOOL_CALL_END = "END_TOOL_CALL"

# Bound context size: long tool descriptions and chat history dominate token use.
DEFAULT_TOOL_DESC_MAX = 160
DEFAULT_SAMPLING_HISTORY_MAX_MESSAGES = 22


def truncate_text(text: str, max_len: int, ellipsis: str = "…") -> str:
    text = (text or "").strip()
    if max_len <= 0 or len(text) <= max_len:
        return text
    return text[: max_len - len(ellipsis)].rstrip() + ellipsis


def compact_tool_line(
    tool: Dict[str, Any],
    *,
    server_label: Optional[str] = None,
    desc_max: int = DEFAULT_TOOL_DESC_MAX,
) -> str:
    """One-line tool summary: name(arg* = required), truncated description."""
    name = tool.get("name", "unknown")
    desc = (tool.get("description") or "").strip() or "—"
    desc = truncate_text(desc, desc_max)
    schema = tool.get("inputSchema") or {}
    props = schema.get("properties") or {}
    required = set(schema.get("required") or [])
    if not props:
        args_hint = "∅"
    else:
        args_hint = ", ".join(f"{k}*" if k in required else k for k in props.keys())
    prefix = f"{server_label}:" if server_label else ""
    return f"- {prefix}{name}({args_hint}) {desc}"


def format_tools_list_for_llm(
    tools: List[Dict[str, Any]], *, desc_max: int = DEFAULT_TOOL_DESC_MAX
) -> str:
    """Format spec-style tools array (name, description, inputSchema) into a string for the LLM."""
    if not tools:
        return ""
    return "\n".join(compact_tool_line(t, desc_max=desc_max) for t in tools)


def trim_chat_messages(
    messages: List[Dict[str, str]], max_messages: int = DEFAULT_SAMPLING_HISTORY_MAX_MESSAGES
) -> List[Dict[str, str]]:
    """Keep only the last N messages to cap prompt growth on long sessions."""
    if max_messages <= 0 or len(messages) <= max_messages:
        return list(messages)
    return list(messages[-max_messages:])


SYSTEM_PROMPT_TEMPLATE = """You use MCP tools via TOOL_CALL blocks. When a listed tool fits the request, output only block(s) below—no "I can't" if a tool applies.

{start}
{{"name": "<exact_name>", "arguments": {{}}}}
{end}

Rules: Multi-step → multiple blocks; fetch data (e.g. weather) before email/other tools that need it. Fetch-then-save: first call only the fetch tool; after you see results, call write_file with real content—never placeholder text in the same turn as fetch. Cities → get_forecast_for_city when available. Paths → ~/Desktop/ or ~/Downloads/. add_contact: include all user-given fields. Coords: approximate lat/lon if only get_forecast exists. No matching tool → plain text only (no TOOL_CALL).

Tools:
{tools_list}
"""


async def build_tools_context(manager: McpManager) -> str:
    """Build a compact string of all MCP tools for the LLM."""
    all_tools = await manager.get_all_tools()
    lines: List[str] = []
    multi_server = len([n for n, t in all_tools.items() if t]) > 1
    for server_name, tools in all_tools.items():
        label = server_name if multi_server else None
        for tool in tools:
            lines.append(compact_tool_line(tool, server_label=label))
    if not lines:
        return ""
    return "\n".join(lines)


def _parse_single_tool_call_json(raw: str) -> Dict[str, Any] | None:
    """If raw is a single tool-call object {"name": str, "arguments": dict}, return it; else None."""
    raw = raw.strip()
    # Allow optional markdown code fence
    if raw.startswith("```"):
        lines = raw.split("\n")
        if lines[0].startswith("```"):
            raw = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    try:
        data = json.loads(raw)
        if not isinstance(data, dict):
            return None
        name = data.get("name")
        arguments = data.get("arguments")
        if not name or not isinstance(name, str):
            return None
        if arguments is None:
            arguments = {}
        if not isinstance(arguments, dict):
            return None
        return {"name": name, "arguments": arguments}
    except (json.JSONDecodeError, TypeError):
        return None


def parse_tool_calls_from_response(response: str) -> List[Dict[str, Any]]:
    """Parse all TOOL_CALL...END_TOOL_CALL blocks; return list of {"name": str, "arguments": dict}.
    Also accepts a single bare JSON object (no delimiters) for LLMs that omit the block format."""
    if not response:
        return []
    out: List[Dict[str, Any]] = []
    if TOOL_CALL_START in response and TOOL_CALL_END in response:
        pattern = re.compile(
            re.escape(TOOL_CALL_START)
            + r"\s*\n?\s*([\s\S]*?)\s*\n?\s*"
            + re.escape(TOOL_CALL_END),
            re.DOTALL,
        )
        for match in pattern.finditer(response):
            tc = _parse_single_tool_call_json(match.group(1))
            if tc:
                out.append(tc)
    if not out:
        tc = _parse_single_tool_call_json(response)
        if tc:
            out.append(tc)
    return out


def strip_tool_call_blocks(response: str) -> str:
    """Remove all TOOL_CALL blocks from the response for display.
    Also strips a single bare JSON tool-call object (no delimiters) so it is not shown to the user."""
    if not response:
        return ""
    if TOOL_CALL_START in response and TOOL_CALL_END in response:
        pattern = re.compile(
            r"\s*"
            + re.escape(TOOL_CALL_START)
            + r".*?"
            + re.escape(TOOL_CALL_END)
            + r"\s*",
            re.DOTALL,
        )
        out = pattern.sub("", response).strip()
        return out
    if _parse_single_tool_call_json(response) is not None:
        return ""
    return response.strip()


async def run_sampling_turn(
    manager: McpManager,
    client: Any,
    chat_history: List[Dict[str, str]],
    user_message: str,
    tools_context: str,
    *,
    max_history_messages: int = DEFAULT_SAMPLING_HISTORY_MAX_MESSAGES,
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
    prior = trim_chat_messages(chat_history, max_history_messages)
    messages = [
        {"role": "system", "content": system_content},
        *prior,
        {"role": "user", "content": user_message},
    ]
    reply = await client.chat(messages)
    tool_calls = parse_tool_calls_from_response(reply)
    reply_clean = strip_tool_call_blocks(reply)
    return (reply_clean, tool_calls)
