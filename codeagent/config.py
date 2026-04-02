"""Configuration loading and AgentConfig dataclass."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path


PROVIDERS: dict[str, dict] = {
    "deepseek": {
        "base_url": "https://api.deepseek.com/v1",
        "env_key": "DEEPSEEK_API_KEY",
        "default_model": "deepseek-chat",
    },
    "openai": {
        "base_url": None,
        "env_key": "OPENAI_API_KEY",
        "default_model": "gpt-4o",
    },
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "env_key": "GROQ_API_KEY",
        "default_model": "llama-3.3-70b-versatile",
    },
    "ollama": {
        "base_url": "http://localhost:11434/v1",
        "env_key": None,
        "default_model": "llama3.2",
    },
}

DEFAULT_SYSTEM_PROMPT = (
    "You are a helpful code agent running in the terminal. "
    "You can read files, write files, edit files, run shell commands, "
    "search the web, and fetch web pages. "
    "Always think step by step. When modifying code, be precise and minimal. "
    "Prefer targeted edits over full rewrites unless asked."
)


@dataclass
class AgentConfig:
    provider: str = "deepseek"
    model: str = "deepseek-chat"
    api_key: str = ""
    base_url: str | None = None
    system_prompt: str = DEFAULT_SYSTEM_PROMPT
    max_tokens: int = 8192
    always_allow: set[str] = field(default_factory=set)
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0


def _read_json(path: Path) -> dict:
    if path.exists():
        try:
            return json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def load_config() -> AgentConfig:
    """Three-layer merge: user config < project config < env vars."""
    cfg = AgentConfig()

    # Layer 1 — user config
    user_cfg_path = Path.home() / ".config" / "codeagent" / "config.json"
    user_cfg = _read_json(user_cfg_path)

    # Layer 2 — project config
    proj_cfg_path = Path.cwd() / ".codeagent" / "config.json"
    proj_cfg = _read_json(proj_cfg_path)

    merged: dict = {**user_cfg, **proj_cfg}

    if "provider" in merged:
        cfg.provider = merged["provider"]
    if "model" in merged:
        cfg.model = merged["model"]
    if "base_url" in merged:
        cfg.base_url = merged["base_url"]
    if "max_tokens" in merged:
        cfg.max_tokens = int(merged["max_tokens"])
    if "system_prompt" in merged:
        cfg.system_prompt = merged["system_prompt"]

    # Defaults from provider table
    pinfo = PROVIDERS.get(cfg.provider, {})
    if not merged.get("model"):
        cfg.model = pinfo.get("default_model", cfg.model)
    if cfg.base_url is None:
        cfg.base_url = pinfo.get("base_url")

    # Layer 3 — environment variables
    env_key_name = pinfo.get("env_key") or ""
    if env_key_name:
        cfg.api_key = os.environ.get(env_key_name, merged.get("api_key", ""))
    else:
        cfg.api_key = "ollama"  # ollama doesn't need a key

    # CODEAGENT.md injection
    codeagent_md = Path.cwd() / "CODEAGENT.md"
    if codeagent_md.exists():
        extra = codeagent_md.read_text().strip()
        if extra:
            cfg.system_prompt = f"{cfg.system_prompt}\n\n---\n{extra}"

    # Memory files injection (imported lazily to avoid circular import)
    try:
        from codeagent.memory import load_memory_files  # noqa: PLC0415
        memory_content = load_memory_files()
        if memory_content:
            cfg.system_prompt = f"{cfg.system_prompt}\n\n---\n[Memory]\n{memory_content}"
    except Exception:
        pass

    return cfg
