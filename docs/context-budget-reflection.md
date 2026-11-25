# D6 · Individual Contribution and Reflection — REQ-CONTEXT-BUDGET

**Student name / student ID:** ZhuXuan (60377218)
**GitHub account:** `zxsgdmn`
**Owned element:** REQ-CONTEXT-BUDGET (ADR-001 / ADR-007)
**Source:** the individual draft is integrated into `Report.md` §6.3; this file keeps the longer draft for the record.

This AI-assisted draft is for the author's review before inclusion in the team report.

## Individual contribution

I was responsible for REQ-CONTEXT-BUDGET, which controls the input assembled for each agent model request. I contributed the News Analyst pilot, migration of the budget core to TradingAgents 0.7.1, and integration of the budget boundary across graph agents and Reflection. The implementation preserves tool-call/result pairing, filters explicitly future evidence, compacts eligible history, and rechecks the final request before allowing HTTP transmission. I also contributed the CityU local estimation path, the offline acceptance evidence, and the requirements, architecture, and traceability documentation. The work reused the project's existing retrieval and SDK paths.

| Contribution | Evidence |
|---|---|
| Budget core and 0.7.1 migration | [Core implementation commit](https://github.com/jiushangxiehou/TradingAgentsUltra/commit/f20c6c9e76ff3cd30d3e410c30c07dedad4aed49) |
| All-agent integration and request/transport tests | [Agent integration commit](https://github.com/jiushangxiehou/TradingAgentsUltra/commit/3313ad0fed6e2a97ef52068733e4c68edb50deb5) |
| CityU local estimation and personal acceptance | [Implementation commit](https://github.com/jiushangxiehou/TradingAgentsUltra/commit/7de8935684c769515e50fa81690252620d091c80) · [Acceptance report](req-context-budget-acceptance.md) |
| Delivery documentation and human oversight evidence | [Team documentation commit](https://github.com/jiushangxiehou/TradingAgentsUltra/commit/df4ce0bc8af009eda7852701ef94061e57f522d0) · [Personal supervision summary](../transcripts/REQ-CONTEXT-BUDGET-zxsgdmn-supervision-summary.md) |

## Individual reflection (English)

I started with the News Analyst because its tool loop made the context problem visible. Each round could carry prior messages, tool results, and tool definitions into the next request. Our goal was to bound that input without removing evidence or constraints that the analyst needed. Starting with one node also gave us a way to review the behavior before taking on the wider graph.

The hardest part was deciding what to measure and where to enforce the limit. Measuring only the prompt text would omit tool schemas and request framing. The implementation instead prepares the complete request, freezes its body, and uses a one-time permission to send the body that was counted. We also narrowed the CityU requirement to a reproducible local estimate based on UTF-8 bytes. This changed how I described the result: an enforced local budget is useful, while the provider's token count remains a separate observation after the call.

Compression raised a second difficulty. Removing text is easy, but deleting a tool result on its own can break the conversation, and deleting conditions from a prompt can change the decision. The implementation groups calls with their results, protects standing constraints, and checks explicit availability dates. When the remaining input cannot fit, it stops the request. In a paired synthetic test, the complete request fell from 17,155 to 10,266 byte-based units while retaining two unique facts and five standing constraints. The personal branch recorded 73 passing core cases and 18 passing integration cases. These results support the local guard and the tested input fidelity; they leave real model-output quality open.

OpenCode supported the early pilot, and Codex assisted migration, review, tests, and documentation. Human review affected the work directly: the test plan was reviewed before implementation, the scope started with news, and later reviews required a clear separation between Mock HTTP results and actual API evidence. The ADR remained Proposed because implementation approval did not establish architecture sign-off. I learned to carry the measurement rule, the code boundary, the test assertion, and the remaining uncertainty into the same delivery record. That made it easier to explain what was complete and what the team could still verify.

## 中文对照

我从新闻分析师开始，因为它的工具循环能直接体现上下文增长的问题。每一轮都可能将此前的消息、工具结果和工具定义带进下一次请求。目标是在限制输入规模的同时，保留分析所需的证据和约束。先从单个节点做起，也让我们能在接入整个 Graph 之前审核实际行为。

最难的部分是确定计量对象，以及在哪个位置执行上限。只统计提示词会漏掉工具 schema 和请求格式。实现先准备完整请求，冻结正文，再通过一次性许可发送同一正文。我们也把 CityU 的要求收敛为可复现的 UTF-8 字节本地估算。这改变了我描述结果的方式：本地上限可以执行，而供应商 Token 用量属于调用后的独立观测。

压缩带来了第二个难点。删除文字很容易，但单独删除工具结果可能破坏对话，删掉提示词中的条件则可能改变决策。实现将调用与结果一起处理，保留固定约束，并检查明确的可用日期。如果剩余输入经过最终检查仍超限，就阻止发送。在同一份合成输入的成对测试中，完整请求从 17,155 降至 10,266 个本地字节单位，同时保留两条独立事实和五项固定约束。个人分支有 73 项核心测试和 18 项集成测试通过。这些结果支持本地预算控制和已测输入的保真，但真实模型输出质量仍待验证。

早期试点用了 OpenCode，迁移、审查、测试和文档工作借助了 Codex。人工审核直接影响了过程：先审核测试方案再实现，范围从新闻节点起步，之后要求清楚区分 Mock HTTP 结果和真实 API 证据。ADR 仍处于 Proposed，因为允许实现交付不等于正式批准架构。我学到，要在同一份交付记录中说明计量规则、代码边界、测试断言和剩余不确定性。这样更容易向团队说明哪些已经完成，哪些还有待验证。