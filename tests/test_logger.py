"""Unit tests for LLM API call logger — no API required."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from codeagent.logger import write_llm_log


def test_write_llm_log_creates_file(tmp_path):
    write_llm_log(
        call_type="chat",
        provider="deepseek",
        model="deepseek-chat",
        request_messages=[{"role": "user", "content": "hi"}],
        request_tools=None,
        response_message={"role": "assistant", "content": "hello"},
        prompt_tokens=10,
        completion_tokens=5,
        elapsed_ms=100,
        log_dir=str(tmp_path),
    )
    logs = list(tmp_path.glob("*.jsonl"))
    assert len(logs) == 1
    record = json.loads(logs[0].read_text().strip())
    assert record["call_type"] == "chat"
    assert record["provider"] == "deepseek"
    assert record["model"] == "deepseek-chat"
    assert record["request"]["messages"][0]["content"] == "hi"
    assert record["response"]["content"] == "hello"
    assert record["usage"]["prompt_tokens"] == 10
    assert record["usage"]["completion_tokens"] == 5
    assert record["elapsed_ms"] == 100
    assert "ts" in record


def test_write_llm_log_appends(tmp_path):
    """Multiple calls append to the same daily file."""
    for _ in range(3):
        write_llm_log(
            call_type="chat",
            provider="deepseek",
            model="m",
            request_messages=[],
            request_tools=None,
            response_message={"role": "assistant", "content": "x"},
            prompt_tokens=1,
            completion_tokens=1,
            elapsed_ms=10,
            log_dir=str(tmp_path),
        )
    logs = list(tmp_path.glob("*.jsonl"))
    assert len(logs) == 1
    lines = logs[0].read_text().strip().splitlines()
    assert len(lines) == 3


def test_write_llm_log_compact_call_type(tmp_path):
    """compact call type is recorded correctly."""
    write_llm_log(
        call_type="compact",
        provider="openai",
        model="gpt-4o",
        request_messages=[{"role": "system", "content": "sys"}],
        request_tools=None,
        response_message={"role": "assistant", "content": "summary text"},
        prompt_tokens=0,
        completion_tokens=0,
        elapsed_ms=500,
        log_dir=str(tmp_path),
    )
    logs = list(tmp_path.glob("*.jsonl"))
    record = json.loads(logs[0].read_text().strip())
    assert record["call_type"] == "compact"
    assert record["response"]["content"] == "summary text"


def test_write_llm_log_with_tools(tmp_path):
    """request_tools field is stored when provided."""
    tools = [{"type": "function", "function": {"name": "read_file"}}]
    write_llm_log(
        call_type="chat",
        provider="deepseek",
        model="deepseek-chat",
        request_messages=[],
        request_tools=tools,
        response_message={"role": "assistant", "content": None},
        prompt_tokens=5,
        completion_tokens=2,
        elapsed_ms=50,
        log_dir=str(tmp_path),
    )
    logs = list(tmp_path.glob("*.jsonl"))
    record = json.loads(logs[0].read_text().strip())
    assert record["request"]["tools"] == tools


def test_write_llm_log_jsonl_each_line_valid(tmp_path):
    """Each line in the JSONL file must be valid JSON."""
    for i in range(5):
        write_llm_log(
            call_type="chat",
            provider="deepseek",
            model="m",
            request_messages=[{"role": "user", "content": f"msg {i}"}],
            request_tools=None,
            response_message={"role": "assistant", "content": f"reply {i}"},
            prompt_tokens=i,
            completion_tokens=i,
            elapsed_ms=i * 10,
            log_dir=str(tmp_path),
        )
    log_file = list(tmp_path.glob("*.jsonl"))[0]
    for line in log_file.read_text().splitlines():
        obj = json.loads(line)   # raises if not valid JSON
        assert "ts" in obj
