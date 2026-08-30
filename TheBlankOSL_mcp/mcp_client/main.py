import asyncio
import re
import typer
import shlex
import json
from typing import List, Dict, Callable, Any
from rich.prompt import Prompt
from rich.panel import Panel
from rich.table import Table

from prompt_toolkit import PromptSession
from prompt_toolkit.history import InMemoryHistory

# Import your modules
from . import __version__
from .utils import console, load_mcp_config, settings_mgr
from .mcp_manager import McpManager
from .commands import config as config_cmd
from .commands import tools as tools_cmd
from .commands.call import main as call_main
from .llm import get_client, list_backends, get_backend_name
from .sampling import build_tools_context, run_sampling_turn, trim_chat_messages

# Import reusable logic from subcommands
from .commands.tools import list_tools_logic, info_tool_logic
from .commands.call import call_tool_logic
from .commands.config import show_config_logic

NON_IDEMPOTENT_TOOLS = {"send_email"}


def _looks_like_placeholder_content(s: str) -> bool:
    """True if write_file content is a placeholder instead of real data."""
    if not s or not isinstance(s, str):
        return True
    lower = s.lower()
    return (
        "will be inserted" in lower
        or "inserted here" in lower
        or "after the forecast is retrieved" in lower
        or "after ... is retrieved" in lower
        or "details will be inserted" in lower
        or "(weather details" in lower
    )


def _substitute_placeholder_results(text: str, results: List[str]) -> str:
    """Replace any {{...}} placeholders in text with actual tool result content. Not hardcoded to step_1."""
    if not results or "{{" not in text or "}}" not in text:
        return text
    # Extract content after "toolname: " for each result (the actual result body)
    contents = [r.split(":", 1)[-1].strip() if ":" in r else r for r in results]

    def repl(match: re.Match) -> str:
        inner = match.group(1).strip()
        # step_1 -> index 0, step_2 -> index 1, etc.
        m = re.search(r"step_(\d+)", inner, re.IGNORECASE)
        if m:
            idx = int(m.group(1)) - 1
            if 0 <= idx < len(contents):
                return contents[idx]
        return contents[0]

    return re.sub(r"\{\{([^}]+)\}\}", repl, text)


# --- Typer App Setup ---
app = typer.Typer(
    name="blankosl_cli",
    help="A Python CLI MCP client for terminal-based tool execution.",
    add_completion=False,
    rich_markup_mode="rich",
)

app.add_typer(config_cmd.app, name="config")
app.add_typer(tools_cmd.app, name="tools")
app.command(name="call")(call_main)

# --- Interactive Command Handlers ---


async def cmd_tools_list_all(manager: McpManager, args: List[str]):
    """List available tools. Usage: /list-all [filter]"""
    filter_str = args[0] if args else None
    await list_tools_logic(manager, filter_str)


async def cmd_tools_list(manager: McpManager, args: List[str]):
    """Show tool details. Usage: /list <tool_name>"""
    if not args:
        console.print("[red]Usage:[/red] /list <tool_name>")
        return
    await info_tool_logic(manager, args[0])


async def cmd_call(manager: McpManager, args: List[str]):
    """Execute a tool. Usage: /call <tool_name> [json_args]"""
    if not args:
        console.print("[red]Usage:[/red] /call <tool_name> [json_args]")
        console.print('[dim]Example: /call get_alerts \'{"state":"CA"}\'[/dim]')
        console.print(
            "[dim]Note: In interactive mode, don't use --args flag. Just provide JSON directly.[/dim]"
        )
        return

    tool_name = args[0]

    # Filter out CLI flags that users might accidentally include
    json_args = [arg for arg in args[1:] if arg not in ("--args", "-a")]

    # If no JSON provided, use empty dict
    if not json_args:
        args_str = "{}"
    else:
        # Join remaining arguments and try to parse as JSON
        args_str = " ".join(json_args)
        # If it looks like they used --args flag, show helpful error
        if "--args" in args or "-a" in args:
            console.print(
                "[yellow]Note:[/yellow] In interactive mode, don't use --args or -a flags."
            )
            console.print(
                "[yellow]Just provide the JSON directly:[/yellow] /call <tool_name> '<json>'"
            )

    try:
        tool_args = json.loads(args_str)
        await call_tool_logic(manager, tool_name, tool_args)
    except json.JSONDecodeError as e:
        console.print(f"[red]Error:[/red] Invalid JSON: {e}")
        console.print(f"[dim]You provided: {args_str}[/dim]")
        console.print('[yellow]Example:[/yellow] /call get_alerts \'{"state":"CA"}\'')


async def cmd_config_show(manager: McpManager, args: List[str]):
    """Display configuration."""
    show_config_logic()


async def cmd_list_llm(manager: McpManager, args: List[str]):
    """List all available LLM models."""
    backends = list_backends()
    if not backends:
        console.print("[yellow]No LLM backends available.[/yellow]")
        return
    table = Table(title="Available LLMs", show_header=True, header_style="bold cyan")
    table.add_column("ID", style="cyan")
    table.add_column("Name")
    for b in backends:
        table.add_row(b["id"], b["name"])
    console.print(table)
    console.print("To use a different model, run /switch_llm <id>.")


async def cmd_switch_llm(manager: McpManager, args: List[str]) -> None:
    """Change the current LLM. Usage: /switch_llm <id>"""
    if not args:
        console.print("[red]Usage:[/red] /switch_llm <id>  (e.g. /switch_llm gemini)")
        console.print("[dim]Use /list_llm to see available IDs.[/dim]")
        return
    backend_id = args[0].lower()
    name = get_backend_name(backend_id)
    if name is None:
        console.print(
            f"[red]Unknown LLM:[/red] {backend_id}. Use [cyan]/list_llm[/cyan]."
        )
        return
    try:
        get_client(backend_id)
    except ValueError as e:
        console.print(f"[red]Cannot use {backend_id}:[/red] {e}")
        return

    # Persist directly to config!
    settings_mgr.update_default_llm(backend_id)
    console.print(f"[green]Now using:[/green] {name}")


async def cmd_roots(manager: McpManager, args: List[str]):
    """Show current MCP roots (filesystem boundaries exposed to servers)."""
    if not manager.roots:
        console.print(
            "[dim]No roots configured. Servers will get default workspace root.[/dim]"
        )
        return
    table = Table(title="MCP Roots", show_header=True, header_style="bold cyan")
    table.add_column("URI", style="cyan")
    table.add_column("Name")
    for r in manager.roots:
        table.add_row(r.get("uri", ""), r.get("name", "") or "(no name)")
    console.print(table)
    console.print(
        '[dim]Configure roots in your MCP config JSON under top-level \'roots\': [{"uri": "file:///path", "name": "..."}][/dim]'
    )


async def cmd_help(manager: McpManager, args: List[str]):
    """Show available slash commands."""
    table = Table(show_header=False, box=None)
    table.add_column("Command", style="bold cyan")
    table.add_column("Description", style="dim")

    table.add_row(
        "/add-server",
        "Dynamically start a new MCP server. Usage: /add-server <name> <cmd> [args...]",
    )

    for name, func in INTERACTIVE_COMMANDS.items():
        doc = func.__doc__.split("\n")[0] if func.__doc__ else "No description"
        table.add_row(f"/{name}", doc)
    console.print(table)
    console.print(
        "\n[dim]Any input without a '/' prefix is treated as a chat message.[/dim]"
    )


# --- Command Registry ---
INTERACTIVE_COMMANDS: Dict[str, Callable[[McpManager, List[str]], Any]] = {
    "list-all": cmd_tools_list_all,
    "list": cmd_tools_list,
    "call": cmd_call,
    "config-show": cmd_config_show,
    "config-mcp-path": cmd_config_show,
    "roots": cmd_roots,
    "list_llm": cmd_list_llm,
    "switch_llm": cmd_switch_llm,
    "help": cmd_help,
}

# --- Interactive Session Loop ---


async def interactive_session():
    manager = McpManager()

    # Helper to always fetch the latest LLM from config
    def get_current_llm() -> str:
        saved = settings_mgr.load().default_llm
        return saved.strip() if saved and get_backend_name(saved.strip()) else "gemini"

    # So servers can request LLM sampling via sampling/createMessage (same model as chat)
    manager.set_llm_getter(lambda: get_client(get_current_llm()))

    console.print("[bold blue]Starting MCP Client Interactive Mode...[/bold blue]")
    with console.status("[bold green]Booting MCP Servers...[/bold green]"):
        report = await manager.start_all()

    # Create a status table
    table = Table(show_header=True, header_style="bold magenta", box=None)
    table.add_column("Server", style="cyan")
    table.add_column("Status", justify="right")

    for s in report["success"]:
        table.add_row(s["name"], "[green]✓ Ready[/green]")
    for f in report["failed"]:
        table.add_row(f["name"], f"[red]✗ Failed ({f['error']})[/red]")

    if report["success"] or report["failed"]:
        console.print(table)
    else:
        console.print("[yellow]No servers enabled in configuration.[/yellow]")

    # Initial display
    initial_llm = get_current_llm()
    model_name = get_backend_name(initial_llm) or initial_llm
    console.print()
    console.print(f"[bold green]Currently using: {model_name}[/bold green]")
    console.print("Type '/help' for commands, '/exit' to quit.")

    tools_context: str = ""
    if report["success"]:
        with console.status("[dim]Loading MCP tools for sampling...[/dim]"):
            tools_context = await build_tools_context(manager)
        if tools_context:
            console.print(
                "[dim]Sampling enabled: you can ask the LLM to run MCP tools (e.g. weather, list files).[/dim]"
            )

    chat_history: List[dict] = []
    cached_client: Any = None
    cached_cid: str = ""
    pt_session = PromptSession(history=InMemoryHistory())

    while True:
        try:
            # Re-fetch config value on every loop iteration
            current_cid = get_current_llm()
            display_name = get_backend_name(current_cid) or current_cid

            prompt_label = f"BLANKOSL ({display_name})"
            # Styled prompt (bold blue) + UP/DOWN history via prompt_toolkit
            formatted_prompt = [("bold fg:ansiblue", f"\n{prompt_label} ")]
            try:
                user_input = await asyncio.to_thread(
                    pt_session.prompt, formatted_prompt
                )
            except EOFError:
                break

            if not user_input.strip():
                continue

            # 1. Handle Slash Commands
            if user_input.startswith("/"):
                raw_cmd = user_input[1:]
                parts = shlex.split(raw_cmd)
                if not parts:
                    continue
                cmd_name = parts[0].lower()
                cmd_args = parts[1:]

                if cmd_name in ("exit", "quit", "q"):
                    break

                if cmd_name == "add-server":
                    if len(cmd_args) < 2:
                        console.print(
                            "[red]Usage:[/red] /add-server <name> <command> [args...]"
                        )
                        continue

                    server_name = cmd_args[0]
                    server_cmd = cmd_args[1]
                    server_args = cmd_args[2:]

                    from .mcp_config_parser import McpServerConfig

                    s_cfg = McpServerConfig(
                        command=server_cmd, args=server_args, enabled=True
                    )
                    s_cfg.expand_vars()

                    try:
                        with console.status(
                            f"[bold green]Starting server '{server_name}'...[/bold green]"
                        ):
                            await manager.start_server(server_name, s_cfg)
                        console.print(
                            f"[green]✓ Server '{server_name}' connected successfully![/green]"
                        )

                        # Rebuild tools context so the LLM knows about the new tools
                        with console.status("[dim]Reloading LLM tool context...[/dim]"):
                            tools_context = await build_tools_context(manager)
                    except Exception as e:
                        console.print(
                            f"[red]Failed to start server '{server_name}':[/red] {e}"
                        )

                    continue

                # The awkward if-branch is gone! Everything routes dynamically.
                if cmd_name in INTERACTIVE_COMMANDS:
                    await INTERACTIVE_COMMANDS[cmd_name](manager, cmd_args)
                else:
                    console.print(f"[red]Unknown command:[/red] /{cmd_name}")

            # 2. Handle Chat Messages
            else:
                if not current_cid:
                    console.print(
                        "[yellow]No LLM selected.[/yellow] Use [cyan]/switch_llm <id>[/cyan]."
                    )
                    continue

                try:
                    # Update client cache only if the config changed
                    if cached_client is None or cached_cid != current_cid:
                        cached_client = get_client(current_cid)
                        cached_cid = current_cid
                    client = cached_client
                except ValueError as e:
                    console.print(f"[red]{e}[/red]")
                    continue

                user_message = user_input.strip()
                if tools_context:
                    # Sampling: LLM may return one or more tool calls; show request/response JSON with confirmation
                    with console.status("[dim]Thinking...[/dim]"):
                        reply_text, tool_calls = await run_sampling_turn(
                            manager, client, chat_history, user_message, tools_context
                        )
                    chat_history.append({"role": "user", "content": user_message})
                    chat_history.append(
                        {"role": "assistant", "content": reply_text or "(tool call)"}
                    )
                    if reply_text:
                        console.print(reply_text)
                    if tool_calls:
                        n = len(tool_calls)
                        for i, tc in enumerate(tool_calls):
                            request_json = json.dumps(
                                {"name": tc["name"], "arguments": tc["arguments"]},
                                indent=2,
                            )
                            title = f"[bold cyan]MCP request {i + 1}/{n}[/bold cyan]"
                            console.print(
                                Panel(
                                    request_json,
                                    title=title,
                                    border_style="cyan",
                                )
                            )
                        while True:
                            confirm = (
                                Prompt.ask(
                                    f"Send {n} tool(s) to MCP backend? [Y/n]",
                                    default="Y",
                                )
                                .strip()
                                .lower()
                            )
                            if confirm in ("", "y", "yes"):
                                do_send = True
                                break
                            if confirm in ("n", "no"):
                                do_send = False
                                break
                            console.print(
                                "[yellow]Please enter Y (yes) or N (no).[/yellow]"
                            )
                        if do_send:
                            results_summary: List[str] = []
                            raw_result_texts: List[
                                str
                            ] = []  # full text from each tool for write_file substitution
                            for i, tc in enumerate(tool_calls):
                                name, arguments = (
                                    tc["name"],
                                    dict(tc["arguments"])
                                    if tc.get("arguments")
                                    else {},
                                )
                                # If write_file content is a placeholder, use the previous tool result that has the actual content (longest = usually the fetched data)
                                if name == "write_file" and raw_result_texts:
                                    content = arguments.get("content") or ""
                                    if _looks_like_placeholder_content(content):
                                        arguments["content"] = (
                                            max(raw_result_texts, key=len)
                                            or raw_result_texts[0]
                                        )
                                try:
                                    result = await manager.call_tool(name, arguments)
                                    summary = ""
                                    full_text = ""
                                    if isinstance(result, dict):
                                        sc = result.get("structuredContent")
                                        if isinstance(sc, dict) and "result" in sc:
                                            full_text = str(sc["result"])
                                            summary = full_text[:800]
                                        elif (
                                            isinstance(result.get("content"), list)
                                            and result["content"]
                                        ):
                                            first = result["content"][0]
                                            if (
                                                isinstance(first, dict)
                                                and "text" in first
                                            ):
                                                full_text = str(first["text"])
                                                summary = full_text[:800]
                                    if not summary:
                                        full_text = str(result)
                                        summary = full_text[:800]
                                    results_summary.append(f"{name}: {summary}")
                                    raw_result_texts.append(full_text)
                                except Exception as e:
                                    results_summary.append(f"{name}: error - {e}")
                                    raw_result_texts.append("")

                            if results_summary:
                                summary_ctx = "\n\n".join(results_summary)
                                hist = trim_chat_messages(chat_history) + [
                                    {
                                        "role": "user",
                                        "content": (
                                            f"Tool results:\n{summary_ctx}\n\n"
                                            "Reply in 1–3 short sentences. Use values from results; "
                                            "no {{...}} placeholders. No tool calls."
                                        ),
                                    },
                                ]
                                with console.status("[dim]Summarizing...[/dim]"):
                                    llm_summary = await client.chat(hist)
                                summary_text = (llm_summary or "").strip() or "Done."
                                summary_text = _substitute_placeholder_results(
                                    summary_text, results_summary
                                )
                                console.print(summary_text)
                                # Keep assistant reply as the summary (replace the placeholder we added earlier)
                                if (
                                    chat_history
                                    and chat_history[-1].get("role") == "assistant"
                                ):
                                    chat_history[-1] = {
                                        "role": "assistant",
                                        "content": summary_text,
                                    }
                                else:
                                    chat_history.append(
                                        {"role": "assistant", "content": summary_text}
                                    )

                            # Chain: one follow-up turn so LLM can suggest more tools using the results (e.g. send_email with weather).
                            # Skip when we ran only one tool to avoid an extra LLM call for simple requests (no hardcoded tool list).
                            if results_summary and n > 1 and n <= 3:
                                chain_msg = (
                                    "Tool results from previous step:\n"
                                    + "\n".join(results_summary)
                                    + f"\n\nUser request: {user_message}\n"
                                    "Need more tools (e.g. send_email, write_file)? Output TOOL_CALL block(s). "
                                    "write_file → ~/Desktop/ or ~/Downloads/ only. Else plain text, no TOOL_CALL."
                                )
                                with console.status(
                                    "[dim]Checking for follow-up actions...[/dim]"
                                ):
                                    chain_reply, chain_calls = await run_sampling_turn(
                                        manager,
                                        client,
                                        chat_history,
                                        chain_msg,
                                        tools_context,
                                    )
                                # Drop follow-up tool calls that duplicate what we just ran (LLMs sometimes repeat the same call)
                                _executed_sigs = {
                                    (
                                        tc["name"],
                                        json.dumps(
                                            tc.get("arguments") or {}, sort_keys=True
                                        ),
                                    )
                                    for tc in tool_calls
                                }
                                chain_calls = [
                                    tc
                                    for tc in chain_calls
                                    if (
                                        tc["name"],
                                        json.dumps(
                                            tc.get("arguments") or {}, sort_keys=True
                                        ),
                                    )
                                    not in _executed_sigs
                                ]

                                executed_names = {tc["name"] for tc in tool_calls}
                                chain_calls = [
                                    tc
                                    for tc in chain_calls
                                    if not (
                                        tc["name"] in NON_IDEMPOTENT_TOOLS
                                        and tc["name"] in executed_names
                                    )
                                ]
                                if chain_calls:
                                    chat_history.append(
                                        {"role": "user", "content": chain_msg}
                                    )
                                    chat_history.append(
                                        {
                                            "role": "assistant",
                                            "content": chain_reply or "(tool call)",
                                        }
                                    )
                                    nc = len(chain_calls)
                                    for i, tc in enumerate(chain_calls):
                                        req_json = json.dumps(
                                            {
                                                "name": tc["name"],
                                                "arguments": tc["arguments"],
                                            },
                                            indent=2,
                                        )
                                        console.print(
                                            Panel(
                                                req_json,
                                                title=f"[bold cyan]MCP request (follow-up) {i + 1}/{nc}[/bold cyan]",
                                                border_style="cyan",
                                            )
                                        )
                                    while True:
                                        confirm = (
                                            Prompt.ask(
                                                f"Send {nc} follow-up tool(s)? [Y/n]",
                                                default="Y",
                                            )
                                            .strip()
                                            .lower()
                                        )
                                        if confirm in ("", "y", "yes"):
                                            do_chain = True
                                            break
                                        if confirm in ("n", "no"):
                                            do_chain = False
                                            break
                                        console.print(
                                            "[yellow]Please enter Y (yes) or N (no).[/yellow]"
                                        )
                                    if do_chain:
                                        chain_results = []
                                        for i, tc in enumerate(chain_calls):
                                            name, arguments = (
                                                tc["name"],
                                                tc["arguments"],
                                            )
                                            try:
                                                result = await manager.call_tool(
                                                    name, arguments
                                                )
                                                summary = ""
                                                if isinstance(result, dict):
                                                    sc = result.get("structuredContent")
                                                    if (
                                                        isinstance(sc, dict)
                                                        and "result" in sc
                                                    ):
                                                        summary = str(sc["result"])[
                                                            :800
                                                        ]
                                                    elif (
                                                        isinstance(
                                                            result.get("content"), list
                                                        )
                                                        and result["content"]
                                                    ):
                                                        first = result["content"][0]
                                                        if (
                                                            isinstance(first, dict)
                                                            and "text" in first
                                                        ):
                                                            summary = str(
                                                                first["text"]
                                                            )[:800]
                                                chain_results.append(
                                                    f"{name}: {summary or str(result)[:800]}"
                                                )
                                            except Exception as e:
                                                chain_results.append(
                                                    f"{name}: error - {e}"
                                                )
                                        if chain_results:
                                            chain_ctx = "\n\n".join(chain_results)
                                            hist2 = trim_chat_messages(chat_history) + [
                                                {
                                                    "role": "user",
                                                    "content": (
                                                        f"Follow-up tool results:\n{chain_ctx}\n\n"
                                                        "1–2 sentences for the user. No placeholders. No tool calls."
                                                    ),
                                                },
                                            ]
                                            with console.status(
                                                "[dim]Summarizing...[/dim]"
                                            ):
                                                chain_summary = await client.chat(hist2)
                                            if chain_summary and chain_summary.strip():
                                                cs = _substitute_placeholder_results(
                                                    chain_summary.strip(), chain_results
                                                )
                                                console.print(cs)
                                                if (
                                                    chat_history
                                                    and chat_history[-1].get("role")
                                                    == "assistant"
                                                ):
                                                    chat_history[-1] = {
                                                        "role": "assistant",
                                                        "content": cs,
                                                    }
                        else:
                            console.print("[dim]Skipped.[/dim]")
                else:
                    # No tools: plain LLM reply only
                    chat_history.append({"role": "user", "content": user_message})
                    with console.status("[dim]Thinking...[/dim]"):
                        reply = await client.chat(trim_chat_messages(chat_history))
                    chat_history.append({"role": "assistant", "content": reply})
                    console.print(reply)

        except KeyboardInterrupt:
            break
        except Exception as e:
            console.print(f"[red]System Error:[/red] {e}")

    # Cleanup
    with console.status("[bold red]Shutting down servers...[/bold red]"):
        await manager.shutdown()
    console.print("[green]Goodbye![/green]")


# --- Main Entry Point ---


def version_callback(value: bool):
    if value:
        console.print(f"Version: {__version__}")
        raise typer.Exit()


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: bool = typer.Option(False, "--version", "-v", callback=version_callback),
):
    """
    BlankOSL CLI - Managed MCP client.
    """
    if ctx.invoked_subcommand is None:
        asyncio.run(interactive_session())


if __name__ == "__main__":
    app()
