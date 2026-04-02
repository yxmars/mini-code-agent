"""Unit tests for memory management — no API required."""
from __future__ import annotations

import datetime
from pathlib import Path

import pytest

from codeagent.memory import (
    Session,
    should_compact,
    save_session,
    load_session,
    list_sessions,
    load_memory_files,
)


# ---------------------------------------------------------------------------
# should_compact
# ---------------------------------------------------------------------------

def test_should_compact_below_threshold():
    assert not should_compact([], 3000, max_tokens=8192, threshold=0.75)


def test_should_compact_above_threshold():
    assert should_compact([], 7000, max_tokens=8192, threshold=0.75)


def test_should_compact_exactly_at_threshold():
    # 0.75 * 8192 = 6144; exactly at boundary is NOT above
    assert not should_compact([], 6144, max_tokens=8192, threshold=0.75)


def test_should_compact_zero_max_tokens():
    assert not should_compact([], 100, max_tokens=0)


# ---------------------------------------------------------------------------
# save / load session
# ---------------------------------------------------------------------------

def test_save_load_session(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    session = Session(
        id="test-id-001",
        created_at="2026-04-02T10:00:00",
        model="deepseek-chat",
        messages=[{"role": "user", "content": "hello"}],
    )
    path = save_session(session)
    assert path.exists()

    loaded = load_session("test-id-001")
    assert loaded is not None
    assert loaded.messages[0]["content"] == "hello"
    assert loaded.model == "deepseek-chat"


def test_save_session_preserves_summary(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    session = Session(
        id="test-id-002",
        created_at="2026-04-02T11:00:00",
        model="gpt-4o",
        messages=[],
        summary="We discussed Python async patterns.",
        token_count=1234,
    )
    save_session(session)
    loaded = load_session("test-id-002")
    assert loaded is not None
    assert loaded.summary == "We discussed Python async patterns."
    assert loaded.token_count == 1234


def test_load_session_not_found(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    assert load_session("nonexistent-id") is None


# ---------------------------------------------------------------------------
# list_sessions
# ---------------------------------------------------------------------------

def test_list_sessions_sorted(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    timestamps = ["2026-01-01T00:00:00", "2026-03-01T00:00:00", "2026-04-01T00:00:00"]
    for i, ts in enumerate(timestamps):
        save_session(Session(id=f"s{i}", created_at=ts, model="m", messages=[]))
    sessions = list_sessions(limit=10)
    # Most recent first
    assert sessions[0].id == "s2"
    assert sessions[1].id == "s1"
    assert sessions[2].id == "s0"


def test_list_sessions_limit(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    for i in range(5):
        save_session(Session(
            id=f"sess-{i}",
            created_at=f"2026-0{i+1}-01T00:00:00",
            model="m",
            messages=[],
        ))
    sessions = list_sessions(limit=3)
    assert len(sessions) == 3


def test_list_sessions_empty(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    sessions = list_sessions()
    assert sessions == []


# ---------------------------------------------------------------------------
# load_memory_files
# ---------------------------------------------------------------------------

def test_load_memory_files_global(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    mem_dir = tmp_path / ".config" / "codeagent"
    mem_dir.mkdir(parents=True)
    (mem_dir / "MEMORY.md").write_text("Always use type hints.")
    result = load_memory_files()
    assert "Always use type hints" in result


def test_load_memory_files_project(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".codeagent").mkdir()
    (tmp_path / ".codeagent" / "MEMORY.md").write_text("This is a Django project.")
    result = load_memory_files()
    assert "Django" in result


def test_load_memory_files_both(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    mem_dir = tmp_path / ".config" / "codeagent"
    mem_dir.mkdir(parents=True)
    (mem_dir / "MEMORY.md").write_text("Global note.")
    (tmp_path / ".codeagent").mkdir()
    (tmp_path / ".codeagent" / "MEMORY.md").write_text("Project note.")
    result = load_memory_files()
    assert "Global note" in result
    assert "Project note" in result


def test_load_memory_files_none(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    result = load_memory_files()
    assert result == ""
