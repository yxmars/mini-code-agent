"""LLM API call logger — records raw request and response to JSONL."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


def _log_dir() -> Path:
    d = Path.home() / ".config" / "codeagent" / "logs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def write_llm_log(
    *,
    call_type: str,
    provider: str,
    model: str,
    request_messages: list[dict],
    request_tools: list[dict] | None,
    response_message: dict,
    prompt_tokens: int,
    completion_tokens: int,
    elapsed_ms: int,
    log_dir: str | None = None,
) -> None:
    """Append one JSONL record to today's log file."""
    record = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "call_type": call_type,
        "provider": provider,
        "model": model,
        "elapsed_ms": elapsed_ms,
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
        },
        "request": {
            "messages": request_messages,
            "tools": request_tools,
        },
        "response": response_message,
    }
    base_dir = Path(log_dir) if log_dir else _log_dir()
    base_dir.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now().strftime("%Y-%m-%d")
    log_path = base_dir / f"codeagent_{date_str}.jsonl"
    with log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
