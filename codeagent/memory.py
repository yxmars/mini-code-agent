"""Memory management: context compaction, session persistence, memory file loading."""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Session dataclass
# ---------------------------------------------------------------------------

@dataclass
class Session:
    id: str
    created_at: str
    model: str
    messages: list[dict]
    summary: str = ""
    token_count: int = 0


def _sessions_dir() -> Path:
    d = Path.home() / ".config" / "codeagent" / "sessions"
    d.mkdir(parents=True, exist_ok=True)
    return d


# ---------------------------------------------------------------------------
# Compaction
# ---------------------------------------------------------------------------

def should_compact(
    messages: list[dict],
    token_count: int,
    max_tokens: int = 8192,
    threshold: float = 0.75,
) -> bool:
    if max_tokens <= 0:
        return False
    return (token_count / max_tokens) > threshold


def compact_messages(
    client: Any,
    model: str,
    messages: list[dict],
    system_prompt: str,
) -> tuple[list[dict], str]:
    """Summarize conversation history and rebuild a minimal messages list."""
    # Build a summarization request (strip original system prompt)
    history = [m for m in messages if m.get("role") != "system"]
    summarize_messages = [
        {"role": "system", "content": "You are a helpful assistant. Summarize conversations concisely."},
        *history,
        {
            "role": "user",
            "content": (
                "请用简洁的段落总结以上对话，保留关键决策、已修改的文件、"
                "已执行的命令、重要结论。用中文回答。"
            ),
        },
    ]
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=summarize_messages,
            max_tokens=1024,
        )
        summary = resp.choices[0].message.content or ""
    except Exception as e:
        summary = f"[Compaction failed: {e}]"

    new_messages: list[dict] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"[对话历史摘要]\n{summary}"},
        {"role": "assistant", "content": "好的，我已了解之前的对话背景，请继续。"},
    ]
    return new_messages, summary


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def save_session(session: Session) -> Path:
    path = _sessions_dir() / f"{session.id}.json"
    path.write_text(json.dumps(asdict(session), ensure_ascii=False, indent=2))
    return path


def load_session(session_id: str) -> Session | None:
    path = _sessions_dir() / f"{session_id}.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
        return Session(**data)
    except Exception:
        return None


def list_sessions(limit: int = 10) -> list[Session]:
    sessions_path = _sessions_dir()
    sessions: list[Session] = []
    for p in sessions_path.glob("*.json"):
        try:
            data = json.loads(p.read_text())
            # Load without messages for speed (metadata only)
            s = Session(
                id=data["id"],
                created_at=data["created_at"],
                model=data["model"],
                messages=[],  # omit for listing
                summary=data.get("summary", ""),
                token_count=data.get("token_count", 0),
            )
            sessions.append(s)
        except Exception:
            continue
    sessions.sort(key=lambda s: s.created_at, reverse=True)
    return sessions[:limit]


def new_session_id() -> str:
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Memory files
# ---------------------------------------------------------------------------

def load_memory_files() -> str:
    parts: list[str] = []

    global_mem = Path.home() / ".config" / "codeagent" / "MEMORY.md"
    if global_mem.exists():
        content = global_mem.read_text().strip()
        if content:
            parts.append(f"[Global Memory]\n{content}")

    project_mem = Path.cwd() / ".codeagent" / "MEMORY.md"
    if project_mem.exists():
        content = project_mem.read_text().strip()
        if content:
            parts.append(f"[Project Memory]\n{content}")

    return "\n\n".join(parts)
