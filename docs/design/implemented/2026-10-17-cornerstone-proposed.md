---
status: accepted
confirmed: 2026-10-17 用户确认
---
# 项目筑基草案（增量，oh-my-team fb88fc1）

未确认前不创建其余文件、不 commit。

## 现状
- 已有：AGENTS.md（业务规则，保留）、.gitignore、docs/
- 缺失：AGENTS.md 的 oh_my_team/project_knowledge 段；.gitignore 缺 !.env.example、CLAUDE.local.md、AGENTS.local.md、.claude/settings.local.json、.omt/（.claude/ 已整体忽略）；.env.example；.harness/claude-code/mcp.json（空 mcpServers）
- 冲突（需确认）：CLAUDE.md 是多行说明而非单行 @AGENTS.md → 建议改为 @AGENTS.md；AGENTS.md 写了具体模型名与分工（layout 要求移到 AGENTS.local.md）
- 不建：docs/decisions|memory|learnings 空目录、CI、skill 软链

## AGENTS.md 将追加的段落
```yaml
oh_my_team:
  source: /workspace/oh-my-team
  entry: ROUTING.md
  exclude: []
  capabilities: [git, shell, api]

project_knowledge:
  decisions: docs/decisions/
  memory: docs/memory/
  learnings: docs/learnings/
```
```markdown
## oh-my-team

- 任务开始先读 `/workspace/oh-my-team/ROUTING.md`，按意图选择流程、技能和知识，只打开选中的文件；`exclude` 里的技能不读。
- 同名或同用途时以 oh-my-team 为准，全局技能只用于它没有覆盖的场景。
- 读的是本机 checkout 的当前内容。路径不可读或路由指向的文件不存在时停止并报告，不改用全局副本、旧缓存或其他项目的上下文。
- 只使用 `capabilities` 声明的能力；生产部署另需明确授权。
- 用户消息以 `omt:` 开头时，按 `ROUTING.md` 的「`omt:` 快捷触发」组合技能：先输出一行计划，再按阶段执行。
- 调研结束、找到根因、交付完成或方案含通用部分时，按 oh-my-team 的 `codify` 技能向用户提议沉淀：零散内容整理成系统化文档，项目专属的写进本仓 `project_knowledge`，跨项目成立的写回 oh-my-team；用户确认大纲后才写。
```
