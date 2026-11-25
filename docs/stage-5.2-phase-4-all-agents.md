# Stage 5.2 Phase 4 · Graph Agent 调用清单

Graph 将 quick/deep 模型交给各自节点的预算 Runnable，开启时每个节点独立取得其 trade_date。ContextVar 只承载日期，消息和状态继续由各节点持有。Reflection 有自己的请求和当前 UTC 日期。本阶段未改节点拓扑和模型选择。初始 Phase 2 提交的核心尚未接入以下生产路径。

| 调用路径 | 源文件及调用 | 模型层级 | 工具、历史与约束 |
|---|---|---|---|
| Market Analyst | tradingagents/agents/analysts/market_analyst.py → turn.take_turn | quick | 独立消息历史、系统提示与工具，含收尾轮 |
| Sentiment Analyst | tradingagents/agents/analysts/sentiment_analyst.py → structured.invoke_structured_or_freetext | quick | 系统提示、预取证据、历史，结构化 schema 或同样受预算约束的文本路径 |
| News Analyst | tradingagents/agents/analysts/news_analyst.py → turn.take_turn | quick | 独立消息历史、系统提示、工具结果与无工具收尾 |
| Fundamentals Analyst | tradingagents/agents/analysts/fundamentals_analyst.py → turn.take_turn | quick | 独立消息历史、系统提示与工具，含收尾轮 |
| Bull Researcher | tradingagents/agents/researchers/bull_researcher.py → invoke | quick | 含分析报告和研究辩论历史的合成文本 |
| Bear Researcher | tradingagents/agents/researchers/bear_researcher.py → invoke | quick | 含分析报告和研究辩论历史的合成文本 |
| Research Manager | tradingagents/agents/managers/research_manager.py → structured.invoke_structured_or_freetext | deep | 研究辩论、评级与投资约束，schema 或文本 |
| Trader | tradingagents/agents/trader/trader.py → structured.invoke_structured_or_freetext | quick | 投资方案、交易约束，schema 或文本 |
| Aggressive Analyst | tradingagents/agents/risk_mgmt/aggressive_debator.py → invoke | quick | 风险辩论与交易方案，文本 |
| Neutral Analyst | tradingagents/agents/risk_mgmt/neutral_debator.py → invoke | quick | 风险辩论与交易方案，文本 |
| Conservative Analyst | tradingagents/agents/risk_mgmt/conservative_debator.py → invoke | quick | 风险辩论与交易方案，文本 |
| Portfolio Manager | tradingagents/agents/managers/portfolio_manager.py → structured.invoke_structured / invoke | deep | 评级规则、组合、风险辩论和记忆，schema 或文本 |
| Memory Reflection | tradingagents/memory/reflection.py → reflect_on_final_decision / invoke_budget | quick | 系统提示和已结算事实，独立请求，无工具 |
| Jev 社交预筛 | tradingagents/agents/post_screen.py → jev_screen → _ask_each → system_one | TypeSafe | 预算开启时禁用该可选预筛，无可验证计数，零模型 HTTP。原社交数据路径继续运行 |

全 Graph 离线覆盖测试要求上表 12 个 Graph 节点和 Reflection 各自留下计数及 HTTP 证据。验证了实际结构化 schema、工具所属历史、完整决策路径及 StatsCallbackHandler 的用量累计。原分析师并行机制继续使用既有回归测试验证。Jev 有独立零发送测试。Graph 外单独创建的原始 SDK 客户端和非 Agent 的登录／数据检索不由预算模块接管。

预算开启后的供应商支持以 [验收报告](req-context-budget-acceptance.md) 为准。
