The user wants me to explain the current codebase and its functions. Let me explore the project structure first.

```delegate_subtask
{"agent_type":"Explore","description":"Explore codebase structure","query":"Explore the entire codebase at /Users/yuanxing/Desktop/agent_demo. I need to understand: 1) The project structure and all files 2) The purpose of each file 3) Key functions and their roles 4) How the components connect together. Be very thorough - read all source files and provide a comprehensive summary."}
```

## 项目解读：codeagent — 终端代码 Agent

这是一个受 Claude Code 启发的轻量级终端代码 Agent，通过 OpenAI 兼容接口支持多种模型提供商（DeepSeek、OpenAI、Groq、Ollama），提供交互式 REPL 和单次命令两种运行模式。

---

### 项目结构

```
codeagent/
├── __init__.py      # 版本号 "0.1.0"
├── config.py        # 配置加载（三层合并）
├── providers.py     # 模型客户端工厂 + 工具 JSON Schema
├── tools.py         # 8 个工具的具体实现
├── memory.py        # 上下文压缩 + 会话持久化 + 记忆文件
├── agent.py         # Agent 核心循环（思考-行动-观察）
└── main.py          # CLI 入口 + REPL + 斜杠命令
tests/               # 单元测试 + 集成测试 + 端到端测试
pyproject.toml       # 构建配置与依赖
```

---

### 各模块核心函数

**`config.py` — 配置管理**
- `load_config()`: 三层配置合并（用户级 → 项目级 → 环境变量），自动注入 `CODEAGENT.md` 和 `MEMORY.md` 到系统提示词
- `AgentConfig`: 数据类，存储 provider、model、api_key、base_url 等运行时配置
- `PROVIDERS` 字典: 定义 4 个提供商的 base_url、环境变量名和默认模型

**`providers.py` — 提供商抽象**
- `build_client(config)`: 根据配置创建统一的 `openai.OpenAI` 客户端
- `get_tool_schemas()`: 返回 8 个工具的 OpenAI function calling JSON Schema 定义

**`tools.py` — 工具实现（Agent 的"手脚"）**

| 工具 | 功能 |
|------|------|
| `read_file` | 读取文件，支持行号偏移和限制 |
| `write_file` | 写入文件，自动创建父目录 |
| `edit_file` | 精确字符串替换（要求唯一匹配） |
| `bash` | 执行 shell 命令，捕获输出+退出码 |
| `glob_tool` | glob 模式文件查找 |
| `grep_tool` | 正则搜索文件内容 |
| `web_fetch` | 抓取网页转 Markdown |
| `web_search` | DuckDuckGo 搜索 |

- `TOOL_REGISTRY`: 工具名→函数的映射字典
- `DESTRUCTIVE_TOOLS`: `{"bash", "write_file", "edit_file"}`，调用前需用户确认

**`memory.py` — 记忆管理**
- `should_compact()` / `compact_messages()`: 当 token 用量超 75% 阈值时，调用模型压缩对话历史
- `save_session()` / `load_session()` / `list_sessions()`: 会话的 JSON 持久化（存储于 `~/.config/codeagent/sessions/`）
- `load_memory_files()`: 加载全局和项目级 `MEMORY.md`

**`agent.py` — 核心引擎**
- `Agent.chat()`: **主循环** — 用户输入 → 模型流式响应 → 有工具调用则执行 → 将结果反馈给模型 → 循环直至返回文本
- `_stream_response()`: 流式接收模型输出，用 Rich Live 实时渲染 Markdown，同时累积 tool_calls
- `_ask_permission()`: 对危险工具弹出 `y/n/always` 确认
- `_execute_tool_calls()`: 批量执行工具，结果截断到 3000 字符
- `_run_single_tool()`: 单个工具执行，修改文件前展示 diff 预览

**`main.py` — CLI 与交互**
- `main()`: CLI 入口，支持 `--provider/-P`、`--model/-m`、`--prompt/-p`（单次模式）、`--auto-approve/-y`
- `_run_repl()`: REPL 循环，使用 `prompt_toolkit` 提供历史记录和快捷键
- `_handle_slash()`: 处理 10 种斜杠命令（`/help`、`/clear`、`/model`、`/cost`、`/save`、`/sessions`、`/resume`、`/memory`、`/run`、`/exit`）

---

### 组件连接关系

```
用户输入 → main.py (CLI/REPL)
              │
              ├─ config.py: load_config() → 合并配置 + 注入记忆
              │
              └─ agent.py: Agent.chat()  ← 核心循环
                    │
                    ├─ providers.py: build_client() → OpenAI 客户端
                    ├─ providers.py: get_tool_schemas() → 工具定义
                    ├─ tools.py: TOOL_REGISTRY → 执行具体工具
                    └─ memory.py → 上下文压缩 / 会话保存恢复
```

整体设计清晰，模块职责分明：`config` 管配置，`providers` 管模型接口，`tools` 管工具实现，`memory` 管上下文和持久化，`agent` 是调度中枢，`main` 是用户入口。

ReportID: fbec0ea7-4815-4209-a298-10d2c0df9e7f
ConversationID: acc9c501-23d9-4a60-934b-2c7c712e4861