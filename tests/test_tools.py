"""Unit tests for tool functions — no API required."""
from __future__ import annotations

from pathlib import Path

import pytest

from codeagent.tools import (
    read_file,
    write_file,
    edit_file,
    bash,
    glob_tool,
    grep_tool,
    web_fetch,
    web_search,
)


# ---------------------------------------------------------------------------
# read_file
# ---------------------------------------------------------------------------

def test_read_file_full(tmp_path):
    f = tmp_path / "a.txt"
    f.write_text("line1\nline2\nline3\n")
    result = read_file(str(f))
    assert "line1" in result
    assert "line2" in result
    assert "line3" in result


def test_read_file_offset_limit(tmp_path):
    f = tmp_path / "a.txt"
    f.write_text("\n".join(f"L{i}" for i in range(10)))
    result = read_file(str(f), offset=3, limit=2)
    assert "L3" in result
    assert "L2" not in result
    assert "L5" not in result


def test_read_file_not_found():
    result = read_file("/nonexistent/path/does_not_exist.txt")
    assert "Error" in result


# ---------------------------------------------------------------------------
# write_file
# ---------------------------------------------------------------------------

def test_write_file_creates_dirs(tmp_path):
    p = str(tmp_path / "a" / "b" / "c.txt")
    result = write_file(p, "hello")
    assert Path(p).read_text() == "hello"
    assert "Written" in result


def test_write_file_overwrites(tmp_path):
    f = tmp_path / "existing.txt"
    f.write_text("old content")
    write_file(str(f), "new content")
    assert f.read_text() == "new content"


# ---------------------------------------------------------------------------
# edit_file
# ---------------------------------------------------------------------------

def test_edit_file_success(tmp_path):
    f = tmp_path / "code.py"
    f.write_text("x = 1\ny = 2\n")
    result = edit_file(str(f), "x = 1", "x = 99")
    assert f.read_text() == "x = 99\ny = 2\n"
    assert "Edited" in result


def test_edit_file_not_found_raises_error(tmp_path):
    f = tmp_path / "code.py"
    f.write_text("x = 1\n")
    result = edit_file(str(f), "z = 9", "z = 0")
    assert "Error" in result
    assert "not found" in result


def test_edit_file_ambiguous_raises_error(tmp_path):
    f = tmp_path / "code.py"
    f.write_text("x = 1\nx = 1\n")
    result = edit_file(str(f), "x = 1", "x = 2")
    assert "Error" in result
    assert "2 times" in result


def test_edit_file_missing_file():
    result = edit_file("/nonexistent/path/file.py", "foo", "bar")
    assert "Error" in result


# ---------------------------------------------------------------------------
# bash
# ---------------------------------------------------------------------------

def test_bash_success():
    result = bash("echo hello")
    assert "hello" in result


def test_bash_stderr_captured():
    result = bash("ls /nonexistent_path_xyz_99999 2>&1 || true")
    assert len(result) > 0  # stderr captured


def test_bash_timeout():
    result = bash("sleep 10", timeout=1)
    assert "timed out" in result.lower()


def test_bash_exit_code():
    result = bash("exit 42")
    assert "42" in result


def test_bash_multiline():
    result = bash("echo line1\necho line2")
    assert "line1" in result


# ---------------------------------------------------------------------------
# glob_tool
# ---------------------------------------------------------------------------

def test_glob_finds_files(tmp_path):
    (tmp_path / "a.py").write_text("")
    (tmp_path / "b.py").write_text("")
    (tmp_path / "c.txt").write_text("")
    result = glob_tool("*.py", str(tmp_path))
    assert "a.py" in result
    assert "b.py" in result
    assert "c.txt" not in result


def test_glob_no_match(tmp_path):
    result = glob_tool("*.xyz", str(tmp_path))
    assert "No files" in result


def test_glob_recursive(tmp_path):
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "nested.py").write_text("")
    result = glob_tool("**/*.py", str(tmp_path))
    assert "nested.py" in result


# ---------------------------------------------------------------------------
# grep_tool
# ---------------------------------------------------------------------------

def test_grep_finds_match(tmp_path):
    f = tmp_path / "src.py"
    f.write_text("def foo():\n    pass\ndef bar():\n    pass\n")
    result = grep_tool("def foo", str(f))
    assert "def foo" in result


def test_grep_no_match(tmp_path):
    f = tmp_path / "src.py"
    f.write_text("hello world\n")
    result = grep_tool("nonexistent_xyz_pattern", str(f))
    assert "No matches" in result


def test_grep_ignore_case(tmp_path):
    f = tmp_path / "src.py"
    f.write_text("Hello World\n")
    result = grep_tool("hello world", str(f), ignore_case=True)
    assert "Hello World" in result


def test_grep_context_lines(tmp_path):
    f = tmp_path / "src.py"
    f.write_text("line1\nTARGET\nline3\n")
    result = grep_tool("TARGET", str(f), context=1)
    assert "line1" in result
    assert "line3" in result


# ---------------------------------------------------------------------------
# web_fetch (mock requests)
# ---------------------------------------------------------------------------

def test_web_fetch_returns_markdown(monkeypatch):
    import requests

    class FakeResp:
        status_code = 200
        headers = {"content-type": "text/html"}
        text = "<html><body><h1>Title</h1><p>Content here.</p></body></html>"

        def raise_for_status(self):
            pass

    monkeypatch.setattr(requests, "get", lambda *a, **kw: FakeResp())
    result = web_fetch("https://example.com")
    assert "Title" in result or "Content" in result


def test_web_fetch_network_error(monkeypatch):
    import requests

    def raise_exc(*a, **kw):
        raise requests.RequestException("timeout")

    monkeypatch.setattr(requests, "get", raise_exc)
    result = web_fetch("https://example.com")
    assert "Error" in result


def test_web_fetch_truncates_long_content(monkeypatch):
    import requests

    class FakeResp:
        status_code = 200
        headers = {"content-type": "text/plain"}
        text = "A" * 20000

        def raise_for_status(self):
            pass

    monkeypatch.setattr(requests, "get", lambda *a, **kw: FakeResp())
    result = web_fetch("https://example.com")
    assert len(result) < 15000  # should be truncated


# ---------------------------------------------------------------------------
# web_search (mock requests)
# ---------------------------------------------------------------------------

def test_web_search_returns_results(monkeypatch):
    import requests

    fake_data = {
        "AbstractText": "",
        "AbstractURL": "",
        "Heading": "",
        "RelatedTopics": [
            {"Text": "Python install guide", "FirstURL": "https://python.org"},
            {"Text": "pip install docs", "FirstURL": "https://pip.pypa.io"},
        ],
    }

    class FakeResp:
        status_code = 200

        def raise_for_status(self):
            pass

        def json(self):
            return fake_data

    monkeypatch.setattr(requests, "get", lambda *a, **kw: FakeResp())
    result = web_search("python install")
    assert "python.org" in result


def test_web_search_empty_results(monkeypatch):
    import requests

    fake_data = {"AbstractText": "", "AbstractURL": "", "Heading": "", "RelatedTopics": []}

    class FakeResp:
        status_code = 200

        def raise_for_status(self):
            pass

        def json(self):
            return fake_data

    monkeypatch.setattr(requests, "get", lambda *a, **kw: FakeResp())
    result = web_search("xyzunlikelysearchquery12345")
    assert "No results" in result


def test_web_search_error(monkeypatch):
    import requests

    def raise_exc(*a, **kw):
        raise requests.RequestException("network error")

    monkeypatch.setattr(requests, "get", raise_exc)
    result = web_search("anything")
    assert "Error" in result
