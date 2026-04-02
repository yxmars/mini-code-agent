"""Tool implementations and dispatch registry."""
from __future__ import annotations

import difflib
import re
import subprocess
from pathlib import Path

import requests
import html2text

from rich.console import Console
from rich.syntax import Syntax

# Module-level console used for diff rendering; agent.py may swap in its own.
_console = Console()


# ---------------------------------------------------------------------------
# Diff rendering helper
# ---------------------------------------------------------------------------

def render_diff(old_text: str, new_text: str, filename: str, console: Console | None = None) -> None:
    c = console or _console
    diff = difflib.unified_diff(
        old_text.splitlines(keepends=True),
        new_text.splitlines(keepends=True),
        fromfile=f"a/{filename}",
        tofile=f"b/{filename}",
    )
    diff_str = "".join(diff)
    if diff_str:
        c.print(Syntax(diff_str, "diff", theme="monokai", line_numbers=False))
    else:
        c.print("[dim]No changes.[/dim]")


# ---------------------------------------------------------------------------
# read_file
# ---------------------------------------------------------------------------

def read_file(path: str, offset: int | None = None, limit: int | None = None) -> str:
    p = Path(path)
    if not p.exists():
        return f"Error: file not found: {path}"
    if not p.is_file():
        return f"Error: not a file: {path}"
    try:
        lines = p.read_text(errors="replace").splitlines(keepends=True)
    except OSError as e:
        return f"Error reading file: {e}"

    start = offset if offset is not None else 0
    end = (start + limit) if limit is not None else len(lines)
    selected = lines[start:end]

    numbered = "".join(f"{start + i + 1:4d}\t{line}" for i, line in enumerate(selected))
    total = len(lines)
    header = f"# {path} (lines {start + 1}-{min(end, total)} of {total})\n"
    return header + numbered


# ---------------------------------------------------------------------------
# write_file  (diff shown by agent before calling; tool just writes)
# ---------------------------------------------------------------------------

def write_file(path: str, content: str) -> str:
    p = Path(path)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
        return f"Written {len(content)} bytes to {path}"
    except OSError as e:
        return f"Error writing file: {e}"


# ---------------------------------------------------------------------------
# edit_file  (diff shown by agent before calling; tool validates & writes)
# ---------------------------------------------------------------------------

def edit_file(path: str, old_string: str, new_string: str) -> str:
    p = Path(path)
    if not p.exists():
        return f"Error: file not found: {path}"
    try:
        content = p.read_text(errors="replace")
    except OSError as e:
        return f"Error reading file: {e}"

    count = content.count(old_string)
    if count == 0:
        return f"Error: old_string not found in {path}"
    if count > 1:
        return f"Error: old_string appears {count} times in {path} — must be unique"

    new_content = content.replace(old_string, new_string, 1)
    try:
        p.write_text(new_content)
    except OSError as e:
        return f"Error writing file: {e}"
    return f"Edited {path}"


# ---------------------------------------------------------------------------
# bash
# ---------------------------------------------------------------------------

def bash(command: str, timeout: int = 30) -> str:
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        parts: list[str] = []
        if result.stdout:
            parts.append(result.stdout)
        if result.stderr:
            parts.append(f"[stderr]\n{result.stderr}")
        parts.append(f"[exit code: {result.returncode}]")
        return "\n".join(parts)
    except subprocess.TimeoutExpired:
        return f"Error: command timed out after {timeout}s"
    except Exception as e:
        return f"Error: {e}"


# ---------------------------------------------------------------------------
# glob_tool
# ---------------------------------------------------------------------------

def glob_tool(pattern: str, path: str | None = None) -> str:
    root = Path(path) if path else Path.cwd()
    try:
        matches = sorted(root.glob(pattern))
    except Exception as e:
        return f"Error: {e}"
    if not matches:
        return f"No files matched: {pattern}"
    lines = [str(m.relative_to(root) if m.is_relative_to(root) else m) for m in matches]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# grep_tool
# ---------------------------------------------------------------------------

def grep_tool(
    pattern: str,
    path: str | None = None,
    glob: str | None = None,
    ignore_case: bool = False,
    context: int = 0,
) -> str:
    flags = re.IGNORECASE if ignore_case else 0
    try:
        compiled = re.compile(pattern, flags)
    except re.error as e:
        return f"Error: invalid regex: {e}"

    root = Path(path) if path else Path.cwd()

    if root.is_file():
        files = [root]
    else:
        file_pattern = glob or "**/*"
        files = [f for f in root.glob(file_pattern) if f.is_file()]

    results: list[str] = []
    truncated = False
    MAX_LINES = 200

    for f in sorted(files):
        try:
            lines = f.read_text(errors="replace").splitlines()
        except OSError:
            continue
        for i, line in enumerate(lines):
            if compiled.search(line):
                start = max(0, i - context)
                end = min(len(lines), i + context + 1)
                for j in range(start, end):
                    results.append(f"{f}:{j + 1}: {lines[j]}")
                if context:
                    results.append("---")
                if len(results) >= MAX_LINES:
                    truncated = True
                    break
        if truncated:
            break

    if not results:
        return "No matches found."
    output = "\n".join(results[:MAX_LINES])
    if truncated:
        output += f"\n[truncated at {MAX_LINES} lines]"
    return output


# ---------------------------------------------------------------------------
# web_fetch
# ---------------------------------------------------------------------------

def web_fetch(url: str, prompt: str = "Summarize the main content") -> str:
    try:
        resp = requests.get(
            url,
            timeout=15,
            headers={"User-Agent": "Mozilla/5.0 (compatible; codeagent/0.1)"},
        )
        resp.raise_for_status()
    except requests.RequestException as e:
        return f"Error fetching {url}: {e}"

    content_type = resp.headers.get("content-type", "")
    if "html" in content_type or not content_type:
        converter = html2text.HTML2Text()
        converter.ignore_links = False
        converter.ignore_images = True
        converter.body_width = 0
        text = converter.handle(resp.text)
    else:
        text = resp.text

    # Truncate to avoid overflowing context
    MAX_CHARS = 8000
    if len(text) > MAX_CHARS:
        text = text[:MAX_CHARS] + f"\n\n[truncated — {len(resp.text)} chars total]"

    return f"# Content from {url}\n\n{text}"


# ---------------------------------------------------------------------------
# web_search  (DuckDuckGo Instant Answer API — no key needed)
# ---------------------------------------------------------------------------

def web_search(query: str, num_results: int = 5) -> str:
    try:
        resp = requests.get(
            "https://api.duckduckgo.com/",
            params={"q": query, "format": "json", "no_html": "1", "skip_disambig": "1"},
            timeout=10,
            headers={"User-Agent": "Mozilla/5.0 (compatible; codeagent/0.1)"},
        )
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        return f"Error searching: {e}"
    except Exception as e:
        return f"Error parsing results: {e}"

    items: list[dict] = []

    # Abstract result
    if data.get("AbstractText") and data.get("AbstractURL"):
        items.append({"title": data.get("Heading", ""), "url": data["AbstractURL"], "snippet": data["AbstractText"]})

    # Related topics
    for topic in data.get("RelatedTopics", []):
        if len(items) >= num_results:
            break
        if "Topics" in topic:  # nested group
            for sub in topic["Topics"]:
                if len(items) >= num_results:
                    break
                if sub.get("FirstURL"):
                    items.append({"title": sub.get("Text", ""), "url": sub["FirstURL"], "snippet": sub.get("Text", "")})
        elif topic.get("FirstURL"):
            items.append({"title": topic.get("Text", ""), "url": topic["FirstURL"], "snippet": topic.get("Text", "")})

    if not items:
        return f"No results found for: {query}"

    lines = [f"# Search results for: {query}\n"]
    for i, item in enumerate(items[:num_results], 1):
        lines.append(f"{i}. **{item['title']}**")
        lines.append(f"   {item['url']}")
        if item["snippet"] and item["snippet"] != item["title"]:
            snippet = item["snippet"][:200]
            lines.append(f"   {snippet}")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

TOOL_REGISTRY: dict[str, callable] = {
    "read_file": read_file,
    "write_file": write_file,
    "edit_file": edit_file,
    "bash": bash,
    "glob_tool": glob_tool,
    "grep_tool": grep_tool,
    "web_fetch": web_fetch,
    "web_search": web_search,
}

DESTRUCTIVE_TOOLS: set[str] = {"bash", "write_file", "edit_file"}
