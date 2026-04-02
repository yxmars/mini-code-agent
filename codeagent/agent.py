"""Agent loop: streaming responses, tool dispatch, permission management."""
from __future__ import annotations

import json
from typing import Any

import openai
from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel

from codeagent.config import AgentConfig
from codeagent.providers import build_client, get_tool_schemas
from codeagent.tools import (
    TOOL_REGISTRY,
    DESTRUCTIVE_TOOLS,
    render_diff,
)
from pathlib import Path

# Tool result stored in messages is capped to avoid triggering content filters
_MAX_TOOL_RESULT_CHARS = 3000


class Agent:
    def __init__(self, config: AgentConfig) -> None:
        self.config = config
        self.console = Console()
        self.client = build_client(config)
        self.messages: list[dict] = [
            {"role": "system", "content": config.system_prompt}
        ]

    # ------------------------------------------------------------------
    # Streaming response
    # ------------------------------------------------------------------

    def _stream_response(self) -> tuple[dict, list[dict]]:
        """
        Stream a response from the model.
        Returns (assistant_message, tool_calls_list).
        """
        tool_calls_accumulator: dict[int, dict] = {}
        text_parts: list[str] = []

        try:
            stream = self.client.chat.completions.create(
                model=self.config.model,
                messages=self.messages,
                tools=get_tool_schemas(),
                tool_choice="auto",
                max_tokens=self.config.max_tokens,
                stream=True,
                stream_options={"include_usage": True},
            )
        except openai.BadRequestError as e:
            if "Content Exists Risk" in str(e):
                self.console.print(
                    "[yellow]⚠ DeepSeek 内容风控触发（网页内容被过滤）"
                    "，正在清理工具结果并重试…[/yellow]"
                )
                self._strip_web_tool_results()
                # Retry once with cleaned history
                stream = self.client.chat.completions.create(
                    model=self.config.model,
                    messages=self.messages,
                    tools=get_tool_schemas(),
                    tool_choice="auto",
                    max_tokens=self.config.max_tokens,
                    stream=True,
                    stream_options={"include_usage": True},
                )
            else:
                self.console.print(f"[red]API error: {e}[/red]")
                raise
        except Exception as e:
            self.console.print(f"[red]API error: {e}[/red]")
            raise

        with Live(console=self.console, refresh_per_second=10) as live:
            for chunk in stream:
                # Usage chunk has empty choices — update token counts
                if not chunk.choices:
                    if hasattr(chunk, "usage") and chunk.usage:
                        self.config.total_prompt_tokens += chunk.usage.prompt_tokens or 0
                        self.config.total_completion_tokens += chunk.usage.completion_tokens or 0
                    continue

                delta = chunk.choices[0].delta

                # Accumulate text
                if delta.content:
                    text_parts.append(delta.content)
                    live.update(Markdown("".join(text_parts)))

                # Accumulate tool calls
                if delta.tool_calls:
                    for tc_delta in delta.tool_calls:
                        idx = tc_delta.index
                        if idx not in tool_calls_accumulator:
                            tool_calls_accumulator[idx] = {
                                "id": "",
                                "type": "function",
                                "function": {"name": "", "arguments": ""},
                            }
                        entry = tool_calls_accumulator[idx]
                        if tc_delta.id:
                            entry["id"] = tc_delta.id
                        if tc_delta.function:
                            if tc_delta.function.name:
                                entry["function"]["name"] += tc_delta.function.name
                            if tc_delta.function.arguments:
                                entry["function"]["arguments"] += tc_delta.function.arguments

        text_content = "".join(text_parts) or None
        tool_calls_list = [tool_calls_accumulator[i] for i in sorted(tool_calls_accumulator)]

        assistant_message: dict = {"role": "assistant"}
        if text_content:
            assistant_message["content"] = text_content
        else:
            assistant_message["content"] = None
        if tool_calls_list:
            assistant_message["tool_calls"] = tool_calls_list

        return assistant_message, tool_calls_list

    # ------------------------------------------------------------------
    # Permission
    # ------------------------------------------------------------------

    def _ask_permission(self, tool_name: str, args: dict) -> bool:
        if tool_name in self.config.always_allow:
            return True

        self.console.print(
            Panel(
                f"[bold yellow]Tool:[/bold yellow] {tool_name}\n"
                f"[bold yellow]Args:[/bold yellow] {json.dumps(args, ensure_ascii=False, indent=2)}",
                title="[bold]Permission Request[/bold]",
                border_style="yellow",
            )
        )
        while True:
            try:
                answer = input("Allow? [y/n/always] ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                return False
            if answer in ("y", "yes"):
                return True
            if answer in ("n", "no"):
                return False
            if answer == "always":
                self.config.always_allow.add(tool_name)
                return True

    # ------------------------------------------------------------------
    # Tool execution
    # ------------------------------------------------------------------

    def _execute_tool_calls(self, tool_calls: list[dict]) -> list[dict]:
        results: list[dict] = []
        for tc in tool_calls:
            name = tc["function"]["name"]
            raw_args = tc["function"].get("arguments", "{}")
            try:
                args = json.loads(raw_args)
            except json.JSONDecodeError:
                args = {}

            tool_result_content = self._run_single_tool(name, args, tc["id"])
            # Truncate large tool results before storing in message history
            # to avoid triggering DeepSeek content filters
            stored_content = tool_result_content
            if len(stored_content) > _MAX_TOOL_RESULT_CHARS:
                stored_content = (
                    stored_content[:_MAX_TOOL_RESULT_CHARS]
                    + f"\n\n[内容已截断，原始长度 {len(tool_result_content)} 字符]"
                )
            results.append({
                "role": "tool",
                "tool_call_id": tc["id"],
                "content": stored_content,
            })
        return results

    def _run_single_tool(self, name: str, args: dict, call_id: str) -> str:
        func = TOOL_REGISTRY.get(name)
        if func is None:
            return f"Error: unknown tool '{name}'"

        # Show diff before destructive file operations
        if name == "edit_file":
            path = args.get("path", "")
            old_string = args.get("old_string", "")
            new_string = args.get("new_string", "")
            if Path(path).exists():
                try:
                    old_content = Path(path).read_text(errors="replace")
                    new_content = old_content.replace(old_string, new_string, 1)
                    self.console.print(f"\n[dim]Diff for {path}:[/dim]")
                    render_diff(old_content, new_content, path, self.console)
                except OSError:
                    pass

        elif name == "write_file":
            path = args.get("path", "")
            new_content = args.get("content", "")
            p = Path(path)
            if p.exists():
                try:
                    old_content = p.read_text(errors="replace")
                    self.console.print(f"\n[dim]Diff for {path}:[/dim]")
                    render_diff(old_content, new_content, path, self.console)
                except OSError:
                    pass
            else:
                self.console.print(f"\n[dim][new file] {path}[/dim]")
                preview = "\n".join(new_content.splitlines()[:20])
                self.console.print(f"[dim]{preview}[/dim]")

        # Permission gate for destructive tools
        if name in DESTRUCTIVE_TOOLS:
            if not self._ask_permission(name, args):
                return f"Tool '{name}' was denied by the user."

        # Execute
        try:
            result = func(**args)
        except TypeError as e:
            return f"Error calling {name}: {e}"
        except Exception as e:
            return f"Error: {e}"

        self.console.print(f"[dim]Tool {name} → {str(result)[:120]}[/dim]")
        return str(result)

    # ------------------------------------------------------------------
    # Main chat loop
    # ------------------------------------------------------------------

    def chat(self, user_message: str) -> str:
        self.messages.append({"role": "user", "content": user_message})

        while True:
            assistant_msg, tool_calls = self._stream_response()
            self.messages.append(assistant_msg)

            if not tool_calls:
                # Check for context compaction
                self._maybe_compact()
                return assistant_msg.get("content") or ""

            # Execute tools and append results
            tool_results = self._execute_tool_calls(tool_calls)
            self.messages.extend(tool_results)

            # Check for context compaction after each round
            self._maybe_compact()

    def _strip_web_tool_results(self) -> None:
        """Replace web tool results with a placeholder to clear content filter risk."""
        WEB_TOOLS = {"web_fetch", "web_search"}
        # Collect tool_call_ids that belong to web tools
        web_call_ids: set[str] = set()
        for msg in self.messages:
            if msg.get("role") == "assistant" and msg.get("tool_calls"):
                for tc in msg["tool_calls"]:
                    if tc.get("function", {}).get("name") in WEB_TOOLS:
                        web_call_ids.add(tc["id"])

        replaced = 0
        for msg in self.messages:
            if msg.get("role") == "tool" and msg.get("tool_call_id") in web_call_ids:
                msg["content"] = "[网页内容已移除以通过内容审核，请基于已知信息继续回答。]"
                replaced += 1

        if replaced:
            self.console.print(f"[dim]已清理 {replaced} 条网页工具结果[/dim]")

    def _maybe_compact(self) -> None:
        from codeagent import memory  # noqa: PLC0415
        total = self.config.total_prompt_tokens + self.config.total_completion_tokens
        if memory.should_compact(self.messages, total, self.config.max_tokens):
            self.console.print("[dim]Compacting context...[/dim]")
            new_msgs, summary = memory.compact_messages(
                self.client, self.config.model,
                self.messages, self.config.system_prompt,
            )
            old_count = total
            self.messages = new_msgs
            self.config.total_prompt_tokens = 0
            self.config.total_completion_tokens = 0
            self.console.print(
                f"[dim]Context compacted: ~{old_count} → ~{len(new_msgs) * 100} tokens[/dim]"
            )
