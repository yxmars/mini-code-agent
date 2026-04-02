# codeagent

A minimal but complete code agent for the terminal, inspired by Claude Code's core design. Supports DeepSeek, OpenAI, Groq, and Ollama via a unified OpenAI-compatible interface.

## Features

- **REPL interaction** with readline history and Ctrl-C/D handling
- **Agentic tool loop**: the model calls tools, observes results, and iterates until done
- **Streaming output** with real-time Markdown rendering
- **Permission management**: dangerous tools require `y/n/always` confirmation
- **Diff previews** before any file write or edit
- **Context compaction**: automatic summarization when token usage exceeds 75% of max
- **Session persistence**: save/resume conversations across terminal sessions
- **Memory injection**: global and project-level `MEMORY.md` files injected into system prompt
- **Multi-provider**: DeepSeek, OpenAI, Groq, Ollama

## Installation

```bash
# From the agent_demo directory:
pip install -e .

# With dev dependencies (for tests):
pip install -e ".[dev]"
```

## Quick Start

```bash
# Set your API key
export DEEPSEEK_API_KEY="sk-..."

# Start interactive REPL
codeagent

# Single-shot non-interactive mode
codeagent -p "写一个冒泡排序的 Python 实现并测试它"

# Use a different provider
codeagent --provider openai --model gpt-4o

# Auto-approve all tools (use with care)
codeagent -p "创建 hello.py 并运行它" -y
```

## Providers

| Provider | Environment Variable | Default Model |
|---|---|---|
| `deepseek` (default) | `DEEPSEEK_API_KEY` | `deepseek-chat` |
| `openai` | `OPENAI_API_KEY` | `gpt-4o` |
| `groq` | `GROQ_API_KEY` | `llama-3.3-70b-versatile` |
| `ollama` | _(none)_ | `llama3.2` |

## REPL Commands

| Command | Description |
|---|---|
| `/help` | Show all commands |
| `/clear` | Reset conversation, keep system prompt |
| `/model [name]` | Show or switch model |
| `/cost` | Token usage and cost estimate |
| `/save` | Save session to disk |
| `/resume [id]` | Resume a previous session |
| `/sessions` | List recent sessions |
| `/memory` | Show injected memory content |
| `/run "<task>"` | Autonomous mode: auto-approve all tools |
| `/exit` `/quit` | Exit |

## Tools

| Tool | Type | Description |
|---|---|---|
| `read_file` | Safe | Read file with line numbers, offset, limit |
| `write_file` | Destructive | Write file, create parent dirs, show diff |
| `edit_file` | Destructive | Unique-string replacement with diff preview |
| `bash` | Destructive | Run shell command, capture stdout+stderr |
| `glob_tool` | Safe | Find files by glob pattern |
| `grep_tool` | Safe | Regex search with context lines |
| `web_fetch` | Safe | Fetch URL, convert HTML to Markdown |
| `web_search` | Safe | DuckDuckGo search, no API key required |

## Configuration

Three-layer configuration merge (lowest to highest priority):

1. `~/.config/codeagent/config.json` — user defaults
2. `.codeagent/config.json` — project overrides
3. Environment variables — highest priority

Example `config.json`:
```json
{
  "provider": "deepseek",
  "model": "deepseek-chat",
  "max_tokens": 8192
}
```

### Custom System Prompt

Place a `CODEAGENT.md` in your project root — it will be appended to the system prompt automatically.

### Memory Files

- `~/.config/codeagent/MEMORY.md` — global memory (e.g., coding style preferences)
- `.codeagent/MEMORY.md` — project-level memory

Both are injected into the system prompt at startup.

## Running Tests

```bash
# Unit tests (no API key required, fast)
pytest tests/ -m "not e2e" -v

# End-to-end tests (requires DEEPSEEK_API_KEY)
export DEEPSEEK_API_KEY="sk-..."
pytest tests/test_e2e.py -m e2e -v --timeout=120
```

## Project Structure

```
codeagent/
├── __init__.py      # version
├── main.py          # CLI entry point, REPL loop, slash commands
├── agent.py         # Agent loop, streaming, tool dispatch, permission gate
├── tools.py         # 8 tool implementations + TOOL_REGISTRY
├── providers.py     # Multi-provider client factory + tool JSON schemas
├── config.py        # Configuration loading, AgentConfig dataclass
└── memory.py        # Context compaction, session persistence, memory files
```

## Known Limitations

- **DeepSeek content filter**: web page content fetched via `web_fetch` / `web_search`
  may trigger DeepSeek's `Content Exists Risk` filter. The agent handles this automatically
  by stripping web tool results and retrying. Use `/clear` if the session gets stuck.
- `web_search` uses the DuckDuckGo Instant Answer API which may return limited results
  for some queries. For richer results, configure a provider with better web access.
# mini-code-agent
