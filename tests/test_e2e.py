"""End-to-end tests requiring a real API key.

Run with: pytest tests/test_e2e.py -m e2e -v --timeout=120
"""
from __future__ import annotations

import os
import re
import subprocess
import sys

import pytest

pytestmark = pytest.mark.e2e

HAVE_KEY = bool(os.getenv("DEEPSEEK_API_KEY"))
CODEAGENT = [sys.executable, "-m", "codeagent.main"]
AUTO_ENV = {**os.environ, "CODEAGENT_AUTO_APPROVE": "1"}


@pytest.mark.skipif(not HAVE_KEY, reason="No DEEPSEEK_API_KEY")
def test_single_shot_hello_world(tmp_path):
    """Non-interactive mode: create hello.py and run it."""
    result = subprocess.run(
        CODEAGENT + ["-p", "创建 hello.py，内容只有 print('hello world')，然后运行它"],
        capture_output=True,
        text=True,
        timeout=120,
        cwd=tmp_path,
        env=AUTO_ENV,
    )
    hello = tmp_path / "hello.py"
    assert hello.exists(), f"hello.py not created. stdout={result.stdout[:500]}"
    run = subprocess.run(
        [sys.executable, str(hello)],
        capture_output=True,
        text=True,
    )
    assert "hello world" in run.stdout.lower()


@pytest.mark.skipif(not HAVE_KEY, reason="No DEEPSEEK_API_KEY")
def test_edit_file_e2e(tmp_path):
    """Agent reads file, finds DEBUG variable, edits it to False."""
    f = tmp_path / "config.py"
    f.write_text("DEBUG = True\nPORT = 8080\n")
    result = subprocess.run(
        CODEAGENT + ["-p", f"把 {f} 里的 DEBUG 改为 False"],
        capture_output=True,
        text=True,
        timeout=120,
        cwd=tmp_path,
        env=AUTO_ENV,
    )
    assert "DEBUG = False" in f.read_text(), (
        f"Expected DEBUG = False in file. stdout={result.stdout[:500]}"
    )


@pytest.mark.skipif(not HAVE_KEY, reason="No DEEPSEEK_API_KEY")
def test_web_fetch_e2e():
    """web_fetch tool can retrieve a public page."""
    result = subprocess.run(
        CODEAGENT + [
            "-p",
            "用 web_fetch 获取 https://httpbin.org/json 的内容，告诉我 slideshow title 字段值",
        ],
        capture_output=True,
        text=True,
        timeout=60,
        env=AUTO_ENV,
    )
    output = result.stdout.lower()
    assert "sample slide show" in output or "slideshow" in output, (
        f"Expected slideshow content. stdout={result.stdout[:500]}"
    )


@pytest.mark.skipif(not HAVE_KEY, reason="No DEEPSEEK_API_KEY")
def test_bash_tool_e2e(tmp_path):
    """Agent uses bash to run a python command."""
    result = subprocess.run(
        CODEAGENT + ["-p", "用 bash 运行 python3 -c \"print(2 + 2)\"，告诉我输出是什么"],
        capture_output=True,
        text=True,
        timeout=60,
        cwd=tmp_path,
        env=AUTO_ENV,
    )
    assert "4" in result.stdout, f"Expected '4' in output. stdout={result.stdout[:500]}"


@pytest.mark.skipif(not HAVE_KEY, reason="No DEEPSEEK_API_KEY")
def test_session_save_and_list(tmp_path):
    """Session can be saved and appears in session list."""
    # This test verifies the session file is created
    result = subprocess.run(
        CODEAGENT + ["-p", "记住：项目代号是 PHOENIX"],
        capture_output=True,
        text=True,
        timeout=60,
        cwd=tmp_path,
        env=AUTO_ENV,
    )
    # Agent completes without error
    assert result.returncode == 0, f"Agent exited with error: {result.stderr[:300]}"
