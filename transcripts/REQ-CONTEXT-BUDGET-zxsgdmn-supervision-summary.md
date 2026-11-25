# REQ-CONTEXT-BUDGET · 个人开发与人工监督记录

- 负责范围：TradingAgentsUltra 的上下文输入预算、压缩和模型请求发送保护。
- 关联 GitHub 账号：`zxsgdmn`。正式姓名和学号待本人确认。
- 记录类型：基于会话中的明确指令、本地实施日志、版本提交和测试结果整理的监督摘要。
- 原始记录状态：旧工作区仍保留 `news-analyst-implementation-log.md` 与 `context-retrieval-budget-opencode-log.md`，可作为早期 OpenCode 工作的追溯来源。目前未取得可随本分支交付的原始 `.session.json`。本摘要不能替代课程要求的完整原始会话。

## 开发与监督过程

| 阶段 | 人工干预与理由 | AI 工作与可复核产出 |
|---|---|---|
| 界定新闻试点 | **要求先审测试方案。** 用户要求只从 News Analyst 做隔离试点，优先 Mock，暂缓业务修改。审核时补充最终请求计数、事实保真、硬上限零发送和关闭预算回归，之后才批准实施。 | 旧工作区日志保留 OpenCode 的方案、实施、修复与测试运行记录。此处只列监督节点，不复制完整终端输出。 |
| 独立审查与定向修复 | **要求分轮审核再修复。** 用户先要求只读独立审查，再限定修复日期过滤、工具配对、去重、正文保护和检查点，并要求保留原测试断言。目的是控制试点范围和避免把测试通过当成接口安全已验证。 | 预算核心最终保留工具交换结构、显式可用日期和一次性许可。迁移版的模块与测试证据见 [Phase 2 报告](../docs/stage-5.2-phase-2-budget-core.md)。 |
| 迁移 0.7.1 | **先保护旧工作并建立新版基线。** 用户要求独立克隆、先跑干净基线，再只迁移核心，暂不接入 Graph 和真实 Provider。人工核对后授权保存并推送个人分支。 | Codex 在独立工作区建立基线并迁入预算核心。[Phase 1 基线报告](../docs/stage-5.2-phase-1-baseline.md) · [核心提交](https://github.com/jiushangxiehou/TradingAgentsUltra/commit/f20c6c9e76ff3cd30d3e410c30c07dedad4aed49) |
| 接入模型发送边界 | **要求先验收新闻流程，再推广。** 用户要求验证工具轮、无工具收尾、最终请求计数与 SDK 发送一致，以及检查点、并发和全 Agent 覆盖。 | Codex 接入统一预算入口并运行 SDK Mock HTTP，验证超限零发送。[新闻接入报告](../docs/stage-5.2-phase-3-news-integration.md) · [全 Agent 调用清单](../docs/stage-5.2-phase-4-all-agents.md) · [接入提交](https://github.com/jiushangxiehou/TradingAgentsUltra/commit/3313ad0fed6e2a97ef52068733e4c68edb50deb5) |
| 收敛 CityU 计数口径 | **调整验收要求并审核公开内容。** 用户明确采用现有 CityU 接入和可核查的本地估算，拒绝把供应商内部计数认证作为交付前提。确认发布前，要求更正适配器说明，清楚区分估算和精确计数，再授权提交推送。 | CityU 匹配时使用冻结 JSON 的 UTF-8 字节数作为本地估算，默认关闭保持不变。[功能提交](https://github.com/jiushangxiehou/TradingAgentsUltra/commit/7de8935684c769515e50fa81690252620d091c80) · [个人验收报告](../docs/req-context-budget-acceptance.md) |
| 合版核查与文档交付 | **限定合版验证和文档范围。** 用户要求在独立 `dev` 工作区做离线验证，发现问题只记录；随后授权将六份预算文档基于最新 `dev` 增量交付，保留其他成员内容，ADR 保持 Proposed。 | 合版测试验证预算、Structured Debate、Guardrail 同次运行。只修改六份文档的 [dev 交付提交](https://github.com/jiushangxiehou/TradingAgentsUltra/commit/df4ce0bc8af009eda7852701ef94061e57f522d0) 保留了真实测试边界与个人 AI-use 条目。 |

## 验证结果与未覆盖范围

- 个人功能提交的离线测试为核心 **73 通过**、Agent 集成 **18 通过**。成对合成用例保留 **2/2 条事实和 5/5 项约束**，完整 Mock 请求由 **17,155** 降至 **10,266** 个 UTF-8 字节计量单位。
- 合版 `dev` 在 `a8597af236bbedaa862d7a3a3c1a7d0d2a9984ae` 上全量离线为 **1932 通过、2 失败、1 跳过、1 未选中**。两项失败是团队预算和终止用例中的 `NotImplementedError` 占位。联合 Mock 探针验证了 **21 次预算计数后的 Mock HTTP 请求、10 个通过 schema 校验的辩论轮次**，并确认 Guardrail 放行与追溯成立。
- 本节的 Mock 证据不代表真实 CityU Token、真实模型输出质量或实际费用已经验收。人工对实施及提交的授权也不代表 ADR 正式批准。
- 如需将这段工作纳入 D5 原始会话交付，应由本人核对并提供相应工具的原始导出，再把本页的干预节点对应回原文。未取得原始导出前，本页可用作个人总结与证据索引。
