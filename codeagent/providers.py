"""Provider factory and tool JSON schemas."""
from __future__ import annotations

import openai

from codeagent.config import AgentConfig, PROVIDERS


def build_client(config: AgentConfig) -> openai.OpenAI:
    kwargs: dict = {"api_key": config.api_key or "sk-placeholder"}
    if config.base_url:
        kwargs["base_url"] = config.base_url
    return openai.OpenAI(**kwargs)


def get_tool_schemas() -> list[dict]:
    return [
        {
            "type": "function",
            "function": {
                "name": "read_file",
                "description": "Read a file from the filesystem. Returns file contents with line numbers.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Absolute or relative path to the file."},
                        "offset": {"type": "integer", "description": "Line number to start reading from (0-indexed)."},
                        "limit": {"type": "integer", "description": "Maximum number of lines to read."},
                    },
                    "required": ["path"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "write_file",
                "description": "Write content to a file, creating parent directories as needed.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "File path to write."},
                        "content": {"type": "string", "description": "Content to write."},
                    },
                    "required": ["path", "content"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "edit_file",
                "description": "Edit a file by replacing an exact unique string with a new string.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "File path to edit."},
                        "old_string": {"type": "string", "description": "Exact string to find and replace (must appear exactly once)."},
                        "new_string": {"type": "string", "description": "Replacement string."},
                    },
                    "required": ["path", "old_string", "new_string"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "bash",
                "description": "Execute a shell command and return stdout + stderr + exit code.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "command": {"type": "string", "description": "Shell command to run."},
                        "timeout": {"type": "integer", "description": "Timeout in seconds (default 30)."},
                    },
                    "required": ["command"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "glob_tool",
                "description": "Find files matching a glob pattern.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "pattern": {"type": "string", "description": "Glob pattern, e.g. '**/*.py'."},
                        "path": {"type": "string", "description": "Root directory to search from (default: current directory)."},
                    },
                    "required": ["pattern"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "grep_tool",
                "description": "Search file contents using a regex pattern.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "pattern": {"type": "string", "description": "Regex pattern to search."},
                        "path": {"type": "string", "description": "File or directory to search."},
                        "glob": {"type": "string", "description": "File glob filter, e.g. '*.py'."},
                        "ignore_case": {"type": "boolean", "description": "Case-insensitive search."},
                        "context": {"type": "integer", "description": "Lines of context around each match."},
                    },
                    "required": ["pattern"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "web_fetch",
                "description": "Fetch a web page and return its content as Markdown.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "url": {"type": "string", "description": "URL to fetch."},
                        "prompt": {"type": "string", "description": "What to look for in the page."},
                    },
                    "required": ["url"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "web_search",
                "description": "Search the web using DuckDuckGo and return result summaries.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query."},
                        "num_results": {"type": "integer", "description": "Number of results to return (default 5)."},
                    },
                    "required": ["query"],
                },
            },
        },
    ]
