"""REPL entry point, CLI argument parsing, slash commands."""
from __future__ import annotations

import argparse
import datetime
import os
import sys

from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.key_binding import KeyBindings
from rich.console import Console
from rich.markdown import Markdown
from rich.table import Table

from codeagent.config import load_config, PROVIDERS
from codeagent.agent import Agent
from codeagent import memory as mem


def _history_path() -> str:
    d = os.path.expanduser("~/.config/codeagent")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, "history")


def _handle_slash(cmd: str, agent: Agent, console: Console, session_state: dict) -> bool:
    """Handle slash commands. Returns True if handled, False if it's a normal message."""
    parts = cmd.strip().split(maxsplit=1)
    name = parts[0].lower()
    arg = parts[1] if len(parts) > 1 else ""

    if name == "/help":
        t = Table(title="Commands", show_header=True, header_style="bold cyan")
        t.add_column("Command", style="bold")
        t.add_column("Description")
        rows = [
            ("/help", "Show this help"),
            ("/clear", "Reset conversation (keep system prompt)"),
            ("/model [name]", "Show or switch model"),
            ("/cost", "Show token usage and estimated cost"),
            ("/save", "Save current session to disk"),
            ("/resume [id]", "Load a previous session"),
            ("/sessions", "List recent sessions"),
            ("/memory", "Show injected memory content"),
            ('/run "<desc>"', "Autonomous mode: auto-approve all tools"),
            ("/exit, /quit", "Exit the REPL"),
        ]
        for r in rows:
            t.add_row(*r)
        console.print(t)
        return True

    if name == "/clear":
        agent.messages = [{"role": "system", "content": agent.config.system_prompt}]
        agent.config.total_prompt_tokens = 0
        agent.config.total_completion_tokens = 0
        console.clear()
        console.print("[green]Conversation cleared.[/green]")
        return True

    if name == "/model":
        if arg:
            agent.config.model = arg
            console.print(f"[green]Model switched to: {arg}[/green]")
        else:
            console.print(f"Current model: [bold]{agent.config.model}[/bold]")
        return True

    if name == "/cost":
        pt = agent.config.total_prompt_tokens
        ct = agent.config.total_completion_tokens
        # Rough cost estimate (deepseek pricing as default)
        cost = (pt * 0.27 + ct * 1.10) / 1_000_000
        console.print(
            f"Prompt tokens: [bold]{pt}[/bold]  "
            f"Completion tokens: [bold]{ct}[/bold]  "
            f"Est. cost: [bold]${cost:.4f}[/bold]"
        )
        return True

    if name == "/save":
        import uuid  # noqa: PLC0415
        sid = session_state.get("id") or str(uuid.uuid4())
        session_state["id"] = sid
        s = mem.Session(
            id=sid,
            created_at=datetime.datetime.now().isoformat(),
            model=agent.config.model,
            messages=agent.messages,
            token_count=agent.config.total_prompt_tokens + agent.config.total_completion_tokens,
        )
        path = mem.save_session(s)
        console.print(f"Session saved: {sid}\n[dim]{path}[/dim]")
        return True

    if name == "/sessions":
        sessions = mem.list_sessions(10)
        if not sessions:
            console.print("No saved sessions.")
        else:
            t = Table(title="Recent Sessions", show_header=True, header_style="bold cyan")
            t.add_column("ID")
            t.add_column("Created")
            t.add_column("Model")
            t.add_column("Tokens")
            t.add_column("Summary", no_wrap=False, max_width=40)
            for s in sessions:
                t.add_row(
                    s.id[:8] + "…",
                    s.created_at[:19],
                    s.model,
                    str(s.token_count),
                    (s.summary[:60] + "…") if len(s.summary) > 60 else s.summary,
                )
            console.print(t)
        return True

    if name == "/resume":
        sid = arg.strip()
        if not sid:
            sessions = mem.list_sessions(10)
            if not sessions:
                console.print("No saved sessions to resume.")
                return True
            console.print("Recent sessions:")
            for i, s in enumerate(sessions):
                console.print(f"  [{i}] {s.id} ({s.created_at[:19]}) — {s.model}")
            try:
                idx = int(input("Select index: "))
                sid = sessions[idx].id
            except (ValueError, IndexError, EOFError):
                console.print("[red]Cancelled.[/red]")
                return True

        loaded = mem.load_session(sid)
        if loaded is None:
            console.print(f"[red]Session not found: {sid}[/red]")
        else:
            agent.messages = loaded.messages
            agent.config.model = loaded.model
            session_state["id"] = loaded.id
            console.print(f"[green]Resumed session: {sid}[/green]")
        return True

    if name == "/memory":
        content = mem.load_memory_files()
        if content:
            console.print(Markdown(content))
        else:
            console.print("[dim]No memory files found.[/dim]")
        return True

    if name == "/run":
        task = arg.strip().strip('"').strip("'")
        if not task:
            console.print("[red]Usage: /run \"<task description>\"[/red]")
            return True
        old_allow = agent.config.always_allow.copy()
        agent.config.always_allow = {"bash", "write_file", "edit_file", "read_file",
                                      "glob_tool", "grep_tool", "web_fetch", "web_search"}
        console.print(f"[yellow]Autonomous mode: running — {task}[/yellow]")
        try:
            agent.chat(task)
        finally:
            agent.config.always_allow = old_allow
        return True

    if name in ("/exit", "/quit"):
        console.print("[dim]Bye![/dim]")
        sys.exit(0)

    return False  # not a slash command or unrecognised → treat as normal input


def _run_repl(agent: Agent, config, console: Console) -> None:
    session_state: dict = {}
    kb = KeyBindings()

    @kb.add("c-d")
    def _exit(event):
        console.print("\n[dim]Bye![/dim]")
        sys.exit(0)

    ps = PromptSession(
        history=FileHistory(_history_path()),
        key_bindings=kb,
    )

    console.print(
        f"[bold green]codeagent[/bold green] v0.1.0  "
        f"model=[bold]{config.model}[/bold]  "
        f"provider=[bold]{config.provider}[/bold]\n"
        "Type [bold]/help[/bold] for commands. Ctrl-D to exit.\n"
    )

    while True:
        try:
            user_input = ps.prompt(">>> ").strip()
        except KeyboardInterrupt:
            continue
        except EOFError:
            console.print("\n[dim]Bye![/dim]")
            break

        if not user_input:
            continue

        if user_input.startswith("/"):
            _handle_slash(user_input, agent, console, session_state)
            continue

        try:
            agent.chat(user_input)
        except KeyboardInterrupt:
            console.print("\n[yellow]Interrupted.[/yellow]")
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="codeagent",
        description="Minimal code agent powered by DeepSeek/OpenAI/Groq/Ollama",
    )
    parser.add_argument("--provider", "-P", help="Provider: deepseek/openai/groq/ollama")
    parser.add_argument("--model", "-m", help="Model name override")
    parser.add_argument("--no-color", action="store_true", help="Disable color output")
    parser.add_argument("--prompt", "-p", help="Non-interactive single prompt")
    parser.add_argument(
        "--auto-approve", "-y",
        action="store_true",
        help="Auto-approve all destructive tools (use with -p)",
    )
    args = parser.parse_args()

    config = load_config()
    if args.provider:
        config.provider = args.provider
        from codeagent.config import PROVIDERS  # noqa: PLC0415
        pinfo = PROVIDERS.get(args.provider, {})
        if not args.model:
            config.model = pinfo.get("default_model", config.model)
        config.base_url = pinfo.get("base_url")
        env_key = pinfo.get("env_key") or ""
        if env_key:
            config.api_key = os.environ.get(env_key, "")
        else:
            config.api_key = "ollama"
    if args.model:
        config.model = args.model

    console = Console(no_color=args.no_color)

    if args.prompt:
        # Non-interactive single-shot mode
        if args.auto_approve or os.environ.get("CODEAGENT_AUTO_APPROVE"):
            config.always_allow = {"bash", "write_file", "edit_file", "read_file",
                                    "glob_tool", "grep_tool", "web_fetch", "web_search"}
        agent = Agent(config)
        try:
            agent.chat(args.prompt)
        except KeyboardInterrupt:
            pass
        pt = config.total_prompt_tokens
        ct = config.total_completion_tokens
        console.print(f"\n[dim]Done. Tokens used: prompt={pt}, completion={ct}[/dim]")
        sys.exit(0)

    agent = Agent(config)
    _run_repl(agent, config, console)


if __name__ == "__main__":
    main()
