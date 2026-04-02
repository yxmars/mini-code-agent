# codeagent

一个轻量但完整的终端代码 Agent，灵感来源于 Claude Code 的核心设计。通过统一的 OpenAI 兼容接口支持 DeepSeek、OpenAI、Groq 和 Ollama。

## 功能特性

- **REPL 交互**：支持 readline 历史记录及 Ctrl-C/D 处理
- **工具调用循环**：模型调用工具、观察结果并迭代，直到任务完成
- **流式输出**：实时 Markdown 渲染
- **权限管理**：危险工具需要 `y/n/always` 确认
- **差异预览**：任何文件写入或编辑前展示 diff
- **上下文压缩**：当 token 用量超过最大值的 75% 时自动摘要
- **会话持久化**：跨终端会话保存/恢复对话
- **记忆注入**：全局和项目级 `MEMORY.md` 文件自动注入系统提示词
- **多模型提供商**：DeepSeek、OpenAI、Groq、Ollama

## 安装

```bash
# 在 agent_demo 目录下执行：
pip install -e .

# 安装开发依赖（用于测试）：
pip install -e ".[dev]"
```

## 快速开始

```bash
# 设置 API 密钥
export DEEPSEEK_API_KEY="sk-..."

# 启动交互式 REPL
codeagent

# 单次非交互模式
codeagent -p "写一个冒泡排序的 Python 实现并测试它"

# 使用其他提供商
codeagent --provider openai --model gpt-4o

# 自动批准所有工具（谨慎使用）
codeagent -p "创建 hello.py 并运行它" -y
```

## 支持的提供商

| 提供商 | 环境变量 | 默认模型 |
|---|---|---|
| `deepseek`（默认）| `DEEPSEEK_API_KEY` | `deepseek-chat` |
| `openai` | `OPENAI_API_KEY` | `gpt-4o` |
| `groq` | `GROQ_API_KEY` | `llama-3.3-70b-versatile` |
| `ollama` | _（无需密钥）_ | `llama3.2` |

## REPL 命令

| 命令 | 说明 |
|---|---|
| `/help` | 显示所有命令 |
| `/clear` | 重置对话，保留系统提示词 |
| `/model [名称]` | 查看或切换模型 |
| `/cost` | 查看 token 用量和费用估算 |
| `/save` | 将会话保存到磁盘 |
| `/resume [id]` | 恢复之前的会话 |
| `/sessions` | 列出最近的会话 |
| `/memory` | 显示已注入的记忆内容 |
| `/run "<任务>"` | 自主模式：自动批准所有工具 |
| `/exit` `/quit` | 退出 |

## 工具列表

| 工具 | 类型 | 说明 |
|---|---|---|
| `read_file` | 安全 | 读取文件，支持行号、偏移量、限制行数 |
| `write_file` | 危险 | 写入文件，自动创建父目录，展示 diff |
| `edit_file` | 危险 | 唯一字符串替换，带 diff 预览 |
| `bash` | 危险 | 执行 shell 命令，捕获 stdout+stderr |
| `glob_tool` | 安全 | 通过 glob 模式查找文件 |
| `grep_tool` | 安全 | 正则搜索，支持上下文行 |
| `web_fetch` | 安全 | 抓取 URL，将 HTML 转换为 Markdown |
| `web_search` | 安全 | DuckDuckGo 搜索，无需 API 密钥 |

## 配置

三层配置合并（优先级从低到高）：

1. `~/.config/codeagent/config.json` — 用户默认配置
2. `.codeagent/config.json` — 项目级覆盖配置
3. 环境变量 — 最高优先级

`config.json` 示例：
```json
{
  "provider": "deepseek",
  "model": "deepseek-chat",
  "max_tokens": 8192
}
```

### 自定义系统提示词

在项目根目录放置 `CODEAGENT.md`，其内容将自动追加到系统提示词中。

### 记忆文件

- `~/.config/codeagent/MEMORY.md` — 全局记忆（如编码风格偏好）
- `.codeagent/MEMORY.md` — 项目级记忆

两个文件均在启动时注入到系统提示词中。

## 运行测试

```bash
# 单元测试（无需 API 密钥，速度快）
pytest tests/ -m "not e2e" -v

# 端到端测试（需要 DEEPSEEK_API_KEY）
export DEEPSEEK_API_KEY="sk-..."
pytest tests/test_e2e.py -m e2e -v --timeout=120
```

## 项目结构

```
codeagent/
├── __init__.py      # 版本信息
├── main.py          # CLI 入口，REPL 循环，斜杠命令
├── agent.py         # Agent 循环、流式输出、工具调度、权限管理
├── tools.py         # 8 个工具实现 + TOOL_REGISTRY
├── providers.py     # 多提供商客户端工厂 + 工具 JSON Schema
├── config.py        # 配置加载，AgentConfig 数据类
└── memory.py        # 上下文压缩、会话持久化、记忆文件
```

## 已知限制

- **DeepSeek 内容过滤**：通过 `web_fetch` / `web_search` 获取的网页内容可能触发 DeepSeek 的 `Content Exists Risk` 过滤器。Agent 会自动处理——剥离网页工具结果后重试。如果会话卡住，请使用 `/clear`。
- `web_search` 使用 DuckDuckGo Instant Answer API，对某些查询可能返回有限结果。如需更丰富的结果，请配置支持更好网络访问的提供商。
