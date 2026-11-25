# REQ-CONTEXT-BUDGET · 离线实施与验收

## 配置、计数和请求保护

在 TradingAgentsGraph 的 config 中设置 context_input_hard_cap_tokens 与 context_input_compaction_threshold_tokens。两项都默认为 None；显式启用时均须为正整数，阈值不高于硬上限。仅支持项目的 Python 配置字典传递，本次没有新增环境变量。max_tokens 保持输出上限语义。

构造 Graph 时通过 context_adapters 按 quick/deep 传入已认可的计数适配器。未配置或不支持相应模型时，启用预算会阻止模型请求，并且不初始化该 tier 的 SDK 客户端。当前没有随项目发布的真实 Token 计数器。

计数与发送以完整最终请求为单位。工具 schema、系统提示、历史、约束和实际模型字段保留在准备后的请求中。最多一次整理和两次计数。一次性许可绑定 Adapter、对象、正文及 SHA-256；传输必须消费许可并直接使用返回的 bytes。当前经过验证的适配器不自动重试。诊断为内容安全的计数字段、原因、节点名称和模型名称。计数器的准确性属于适配器契约，Mock 仅验证该机制和发送边界。

## 压缩与保真边界

1. 配对原始和规范化工具调用，按明确 available_at 在首次计数前排除未来证据。日期按 UTC 日末解释；精确时间戳需要时区偏移。冲突取较晚时刻。缺少该元数据的证据继续依赖工具的 as-of 查询。event_date 只代表事件日期。
2. 按用户轮次去重。只对有明确 fact_id 的工具证据归一行尾空白，工具参数和完整 provenance 仍须一致。显式无关交换可整块裁剪；之后对仍保留的合格低优先级工具结果生成结构化摘要。摘要要求可逐行匹配的事实字段和明确来源，按固定顺序提取原文，保留配对、来源、Ticker、发布时间、可用时间、金额及因果措辞。无注释的供应商纯文本保守保留，可能超限阻断。
3. System/User 锚点以原文和原角色进入重新组装的请求，避免重复注入。既有 instrument、portfolio、评级和交易约束保留在原提示中。明确标记为未来的锚点不能发送。锚点独自超限时返回 mandatory_context_over_cap；保留证据共同超限时返回 over_after_compaction。粗粒度裁剪选择使用消息大小比例，硬上限只由最终计数裁定。

## Paired Faithfulness

同一 0.7.1 新闻子图和合成输入分别在关闭预算和启用压缩时采集 SDK Mock 请求。按 fact_id 和原始字段逐一比较 Subject、Event Date、Amount + Currency、Source、Causality，另核对 Ticker、日期与五条约束。首份请求三条工具证据含一个重复事实，压缩后两条。实际数据来自 test_paired_news_faithfulness_on_sdk_wire。

| 指标 | 实测 |
|---|---:|
| 基线／压缩后唯一事实 | 2 / 2 |
| 完整保留事实 | 2 |
| 事实保留率 | 100% |
| 约束保留率 | 5 / 5，100% |
| 事实错误／跨标的污染／未来信息泄漏 | 0 / 0 / 0 |
| 压缩前／后 Mock 计数 | 17155 / 10266 |
| Mock 请求规模减少率 | 40.16% |

Mock 计数使用完整 JSON 的 UTF-8 字节数。这是相同请求体的离线比对指标。真实 Token 压缩率、质量阈值和更大语料的外推仍待团队审批与验证。未来泄漏防线另外通过显式未来证据与 UTC 时分秒测试验证。

## Provider 状态

| Provider | 当前状态 |
|---|---|
| DeepSeek 官方 Chat Completions | 提供同一 SDK 传输适配器，需注入经过独立验证的计数器；官方真实端点与 Token 均未验收 |
| CityU DeepSeek | SDK Mock HTTP 已验证 model/base URL、到达 SDK 的完整 JSON、工具 schema、reasoning_content、结构化输出、计数前置与零发送、SDK 禁止重试；供应商真实 Token 未验收 |
| OpenAI／ChatGPT／Azure | 没有已验证的发送前计数与传输适配，预算开启时不放行；OpenAI 默认关闭行为保留 |
| Anthropic／Google／Bedrock | 同上 |
| xAI、Qwen、GLM、MiniMax、OpenRouter、Mistral、Kimi、Groq、NVIDIA、Ollama、openai_compatible | 同上，兼容 Chat Completions 本身不能证明计数一致 |
| TypeSafe Jev | 未支持，预算开启时跳过可选预筛 |

## 实测与剩余验收

- python -m pytest tests/test_context_budget_core.py -q，73 通过。
- python -m pytest tests/test_budget_agent_integration.py -q，13 通过。
- python -m pytest -q，1498 通过、0 失败、1 跳过、1 未选中；100 个子测试通过。Phase 1 为 1412 通过，Phase 2 为 1485。跳过为可选 Bedrock 依赖，未选中为真实 DeepSeek 集成测试。
- ruff check .、python -m compileall -q tradingagents cli tests、git diff --check 通过。依赖版本与 Phase 1 相同。测试只使用无外网隔离网络及合成数据。
- 中间运行发现 7 项检查点回归，原因是签名读取了旧的最小实例未初始化的属性。签名改为从配置判定预算状态后全量重跑通过。原有测试和断言均未调整。
- 待验收包括真实 CityU 或官方 DeepSeek 的发送前 Token 计数、真实端点协议和拒绝行为、逐条供应商 provenance 与获批的保真阈值。自由文本聚合提示会保守整体保留，超限时阻断。该范围不对真实端点启用硬预算。

[新闻接入](stage-5.2-phase-3-news-integration.md) · [Agent 调用清单](stage-5.2-phase-4-all-agents.md)
