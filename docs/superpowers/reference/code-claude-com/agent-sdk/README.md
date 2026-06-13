# Claude Agent SDK — 本地参考

> 把 Anthropic 官方 `claude-agent-sdk` 文档从 https://code.claude.com/docs/en/agent-sdk 整站爬到本地,供项目内 subagent 离线检索。
>
> 抓取时间:**2026-06-12** | 抓取工具:`curl` + 自写 HTML→markdown 解析器 | SDK 版本对齐:`claude-agent-sdk 0.2.95`(bundled CLI 2.1.170)

## 为什么需要本地镜像

`code.claude.com` 域名对沙箱里的 `WebFetch` 工具不被信任(安全策略拒绝),但 `curl` 走真实网络可达。一次性整站抓取后,subagent 后续只读本地文件,不再每次出网。

## 目录结构

```
docs/superpowers/reference/code-claude-com/agent-sdk/
├── INDEX.md                    # 30 个页面的清单 + 字节数 + 源 URL
├── README.md                   # 本文件
├── raw/                        # 完整 SSR HTML 备份(58 MB,极少用)
│   ├── _seed.html
│   ├── overview.html
│   ├── python.html             # 110 KB
│   ├── typescript.html         # 105 KB
│   └── ...
└── markdown/                   # 净化后的 markdown(652 KB,主用)
    ├── overview.md             # 14 KB
    ├── python.md               # 110 KB — Python API 完整参考
    ├── typescript.md           # 105 KB — TypeScript 镜像
    ├── mcp.md
    ├── hooks.md
    ├── subagents.md
    ├── sessions.md
    └── ... (共 30 份)
```

## 30 个抓取页面(主题)

| 主题 | Slug | 大小 |
|---|---|---|
| 总览 | `overview` `agent-loop` | 14K / 25K |
| 安装 / 快速开始 | `quickstart` `python` `typescript` | 10K / 110K / 105K |
| 工具 / 能力 | `custom-tools` `mcp` `tool-search` `claude-code-features` | 23K / 15K / 6K / 14K |
| Hook / 权限 | `hooks` `permissions` `secure-deployment` | 27K / 11K / 20K |
| 会话 / 状态 | `sessions` `session-storage` | 14K / 10K |
| 子能力 | `subagents` `skills` `slash-commands` `plugins` | 21K / 9K / 10K / 8K |
| 流 / 模式 | `streaming-output` `streaming-vs-single-mode` | 10K / 5K |
| 输入控制 | `user-input` `modifying-system-prompts` | 24K / 18K |
| 数据 / 观测 | `structured-outputs` `cost-tracking` `observability` | 10K / 12K / 13K |
| 状态回滚 / 列表 | `file-checkpointing` `todo-tracking` | 18K / 6K |
| 部署 / 兼容 | `hosting` `migration-guide` `typescript-v2-preview` | 17K / 7K / 8K |

## Subagent

`/root/TAXI/.claude/agents/claude-sdk-docs-researcher.md` — 项目级 subagent,职责:

1. **调研** "怎么用 SDK 的某个 API"(引用本地 mirror + 安装的 SDK 源码)
2. **审查** "项目代码用 SDK 用得对不对"(读 T.A.X.I. backend 文件,对照 doc + SDK 源码)
3. **盘点** "我们漏用了哪些 SDK 特性"(按 doc 主题逐项过)

**Hard rule**:**所有具体 API 声明必须 cite 本地文件路径,不许凭记忆**。SDK 0.2.95 vs 旧版可能差异大,subagent 必须交叉验证 `claude_agent_sdk/__init__.py.__all__` 和 `types.py`。

## 用法示例(给主 agent)

```python
# 启动 subagent 做调研
Agent(
    description="SDK 调研",
    prompt="How do I add a PreToolUse hook that blocks submit_vat_return unless session.taxpayer_id matches? Show me the exact code pattern.",
    subagent_type="general-purpose",  # 用通用类型加载自定义 agent
)

# 启动 subagent 做审查
Agent(
    description="审查新加的 MCP 工具",
    prompt="Review backend/agent/tools.py:332-368 — is our create_sdk_mcp_server usage aligned with markdown/mcp.md recommendations?",
    subagent_type="general-purpose",
)
```

## 重新抓取(若 SDK 升级或 doc 改版)

```bash
# 抓取脚本在 /tmp/crawl_sdk_docs.sh
# 复制到仓库(可选): scripts/crawl_sdk_docs.sh
bash /tmp/crawl_sdk_docs.sh
```

## 已知限制

- HTML→markdown 解析器是简易实现(Mintlify 专属),`pre/code` 块保留为 ``` 围栏,inline `code` 保留为 \`...\`,但**没有**反查内部链接(只有当前页 anchor 跳转)
- 不抓取交叉链接的子页面(若某主题分布在多个 slug,subagent 需自行 grep)
- 不抓 `code.claude.com` 其他非 agent-sdk 段(如 `code/claude-code/*`);如有需要另起一个 mirror 目录
