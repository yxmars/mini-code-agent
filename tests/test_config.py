"""Unit tests for configuration loading."""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from codeagent.config import load_config, AgentConfig


def test_load_config_default_provider(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.chdir(tmp_path)
    cfg = load_config()
    assert cfg.provider == "deepseek"


def test_load_config_default_model(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    cfg = load_config()
    assert cfg.model == "deepseek-chat"


def test_load_config_env_key(monkeypatch, tmp_path):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test-123")
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    cfg = load_config()
    assert cfg.api_key == "sk-test-123"


def test_load_config_project_overrides_user(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))

    user_cfg = tmp_path / ".config" / "codeagent" / "config.json"
    user_cfg.parent.mkdir(parents=True)
    user_cfg.write_text(json.dumps({"provider": "openai", "model": "gpt-4o"}))

    proj_dir = tmp_path / "myproject"
    proj_dir.mkdir()
    (proj_dir / ".codeagent").mkdir()
    (proj_dir / ".codeagent" / "config.json").write_text(json.dumps({"model": "gpt-4o-mini"}))
    monkeypatch.chdir(proj_dir)

    cfg = load_config()
    assert cfg.provider == "openai"       # inherited from user
    assert cfg.model == "gpt-4o-mini"     # overridden by project


def test_load_config_user_config_only(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)

    user_cfg = tmp_path / ".config" / "codeagent" / "config.json"
    user_cfg.parent.mkdir(parents=True)
    user_cfg.write_text(json.dumps({"provider": "groq", "model": "llama-3.3-70b-versatile"}))

    cfg = load_config()
    assert cfg.provider == "groq"
    assert cfg.model == "llama-3.3-70b-versatile"


def test_codeagent_md_injected(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    (tmp_path / "CODEAGENT.md").write_text("This project uses asyncio.")
    cfg = load_config()
    assert "asyncio" in cfg.system_prompt


def test_codeagent_md_not_present(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    cfg = load_config()
    # Should not raise, should have default system prompt
    assert "code agent" in cfg.system_prompt.lower()


def test_load_config_ollama_no_key(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)

    user_cfg = tmp_path / ".config" / "codeagent" / "config.json"
    user_cfg.parent.mkdir(parents=True)
    user_cfg.write_text(json.dumps({"provider": "ollama"}))

    cfg = load_config()
    assert cfg.provider == "ollama"
    assert cfg.api_key == "ollama"  # placeholder, no real key needed
    assert "localhost" in (cfg.base_url or "")


def test_agent_config_defaults():
    cfg = AgentConfig()
    assert cfg.provider == "deepseek"
    assert cfg.max_tokens == 8192
    assert isinstance(cfg.always_allow, set)
    assert cfg.total_prompt_tokens == 0
    assert cfg.total_completion_tokens == 0


def test_load_config_max_tokens_override(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)

    user_cfg = tmp_path / ".config" / "codeagent" / "config.json"
    user_cfg.parent.mkdir(parents=True)
    user_cfg.write_text(json.dumps({"max_tokens": 4096}))

    cfg = load_config()
    assert cfg.max_tokens == 4096
