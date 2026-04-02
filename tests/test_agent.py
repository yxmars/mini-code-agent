"""Agent integration tests — mock OpenAI API."""
from __future__ import annotations

import json
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from codeagent.config import AgentConfig
from codeagent.agent import Agent


# ---------------------------------------------------------------------------
# Helpers to build fake stream chunks
# ---------------------------------------------------------------------------

def _make_delta(**kwargs) -> object:
    d = types.SimpleNamespace(
        content=kwargs.get("content"),
        tool_calls=kwargs.get("tool_calls"),
    )
    return d


def _make_chunk(delta=None, usage=None):
    choice = types.SimpleNamespace(delta=delta or _make_delta())
    chunk = types.SimpleNamespace(
        choices=[choice] if delta is not None else [],
        usage=usage,
    )
    return chunk


def make_text_chunk(content: str):
    return _make_chunk(delta=_make_delta(content=content))


def make_tool_chunk(index: int, call_id: str, name: str, arguments: str):
    tc = types.SimpleNamespace(
        index=index,
        id=call_id,
        function=types.SimpleNamespace(name=name, arguments=arguments),
    )
    delta = _make_delta(tool_calls=[tc])
    return _make_chunk(delta=delta)


def make_usage_chunk(prompt: int = 10, completion: int = 20):
    usage = types.SimpleNamespace(prompt_tokens=prompt, completion_tokens=completion)
    return types.SimpleNamespace(choices=[], usage=usage)


def config_fixture(**kwargs) -> AgentConfig:
    cfg = AgentConfig(
        provider="deepseek",
        model="deepseek-chat",
        api_key="sk-test",
    )
    for k, v in kwargs.items():
        setattr(cfg, k, v)
    return cfg


# ---------------------------------------------------------------------------
# Mock client factory
# ---------------------------------------------------------------------------

class FakeStream:
    def __init__(self, chunks):
        self._chunks = chunks
        self._iter = iter(chunks)

    def __iter__(self):
        return self._iter

    def __enter__(self):
        return self

    def __exit__(self, *a):
        pass


def make_agent_with_mock_stream(chunks_per_call: list[list]) -> tuple[Agent, MagicMock]:
    """Creates an Agent whose client returns pre-specified stream chunks."""
    cfg = config_fixture()
    agent = Agent(cfg)

    call_count = [0]

    def fake_create(**kwargs):
        idx = call_count[0]
        call_count[0] += 1
        if idx < len(chunks_per_call):
            return FakeStream(chunks_per_call[idx])
        return FakeStream([make_usage_chunk()])

    mock_completions = MagicMock()
    mock_completions.create = fake_create
    agent.client = MagicMock()
    agent.client.chat = MagicMock()
    agent.client.chat.completions = mock_completions
    return agent, mock_completions


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_agent_chat_no_tools():
    """Model returns plain text, no tools called."""
    chunks = [make_text_chunk("Hello!"), make_usage_chunk(prompt=10, completion=5)]
    agent, _ = make_agent_with_mock_stream([chunks])

    result = agent.chat("say hello")
    assert "Hello!" in result
    # system + user + assistant
    assert len(agent.messages) == 3
    assert agent.messages[-1]["content"] == "Hello!"


def test_agent_token_tracking():
    """Usage chunks correctly accumulate token counts."""
    chunks = [make_text_chunk("hi"), make_usage_chunk(prompt=100, completion=50)]
    agent, _ = make_agent_with_mock_stream([chunks])
    agent.chat("hi")
    assert agent.config.total_prompt_tokens == 100
    assert agent.config.total_completion_tokens == 50


def test_agent_tool_loop_single_round(tmp_path):
    """Model calls read_file, then returns final answer."""
    f = tmp_path / "test.py"
    f.write_text("x = 1\n")

    tool_args = json.dumps({"path": str(f)})
    round1 = [
        make_tool_chunk(0, "call_1", "read_file", tool_args),
        make_usage_chunk(5, 5),
    ]
    round2 = [
        make_text_chunk("The file contains x=1."),
        make_usage_chunk(10, 8),
    ]
    agent, _ = make_agent_with_mock_stream([round1, round2])
    agent.config.always_allow = {"read_file"}

    result = agent.chat("what's in test.py")
    # system + user + assistant(tool_call) + tool_result + assistant(text)
    assert len(agent.messages) == 5
    assert "x=1" in result or "x = 1" in result.lower() or agent.messages[-1]["content"] == "The file contains x=1."


def test_agent_tool_denial(tmp_path, monkeypatch):
    """User denies write_file; file is not created; model acknowledges."""
    f = tmp_path / "out.txt"
    tool_args = json.dumps({"path": str(f), "content": "hi"})

    round1 = [make_tool_chunk(0, "c1", "write_file", tool_args), make_usage_chunk(5, 5)]
    round2 = [make_text_chunk("OK, I won't write the file."), make_usage_chunk(8, 6)]

    agent, _ = make_agent_with_mock_stream([round1, round2])
    monkeypatch.setattr("builtins.input", lambda _="": "n")

    agent.chat("write out.txt")
    assert not f.exists()
    # Tool result message should mention denial
    tool_result_msg = next(
        m for m in agent.messages if m.get("role") == "tool"
    )
    assert "denied" in tool_result_msg["content"].lower()


def test_agent_multiple_token_rounds():
    """Token counts accumulate over multiple rounds."""
    round1 = [make_text_chunk("step1"), make_usage_chunk(prompt=50, completion=10)]
    round2 = [make_text_chunk("step2"), make_usage_chunk(prompt=60, completion=15)]
    agent, _ = make_agent_with_mock_stream([round1])

    agent.chat("first")
    assert agent.config.total_prompt_tokens == 50
    assert agent.config.total_completion_tokens == 10

    # Reset mock for second call
    agent2, _ = make_agent_with_mock_stream([round2])
    agent2.config.total_prompt_tokens = 50
    agent2.config.total_completion_tokens = 10
    agent2.chat("second")
    assert agent2.config.total_prompt_tokens == 110
    assert agent2.config.total_completion_tokens == 25


def test_agent_always_allow_skips_permission(tmp_path, monkeypatch):
    """Tools in always_allow bypass the permission prompt."""
    f = tmp_path / "safe.txt"
    f.write_text("data")
    tool_args = json.dumps({"path": str(f)})

    round1 = [make_tool_chunk(0, "rc1", "read_file", tool_args), make_usage_chunk()]
    round2 = [make_text_chunk("Read it."), make_usage_chunk()]

    agent, _ = make_agent_with_mock_stream([round1, round2])
    agent.config.always_allow = {"read_file"}

    # input() should never be called — if it is, raise to fail the test
    monkeypatch.setattr("builtins.input", lambda _: (_ for _ in ()).throw(AssertionError("Should not ask permission")))

    result = agent.chat("read safe.txt")
    assert "Read it." in result


def test_agent_unknown_tool_returns_error():
    """Calling an unknown tool returns an error string to the model."""
    tool_args = json.dumps({})
    round1 = [make_tool_chunk(0, "bad1", "nonexistent_tool", tool_args), make_usage_chunk()]
    round2 = [make_text_chunk("I see the tool failed."), make_usage_chunk()]

    agent, _ = make_agent_with_mock_stream([round1, round2])
    agent.config.always_allow = {"nonexistent_tool"}

    agent.chat("call nonexistent_tool")
    tool_result_msg = next(m for m in agent.messages if m.get("role") == "tool")
    assert "unknown tool" in tool_result_msg["content"].lower()
