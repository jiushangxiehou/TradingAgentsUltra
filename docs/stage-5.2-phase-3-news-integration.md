# Stage 5.2 Phase 3 · 新闻预算接入

起点是 feature-z 上的 Phase 2 提交 f20c6c9e76ff3cd30d3e410c30c07dedad4aed49。本阶段保留 0.7.1 新闻提示词、工具定义、ToolNode 和 Analyst 子图。

## 请求路径

- 常规轮通过 take_turn 绑定原工具，再经预算 Runnable 准备、计数和发送。工具结果回到原子图，下一轮独立执行预算。
- 达到 max_tool_rounds 后，WRAP_UP 使用原来的无工具提示。预算层先处理结构化历史，才按 0.7.1 的规则投影成纯文本。第一次和压缩后的计数均使用投影后的实际 SDK 请求。
- 关闭预算时，Graph 安装原始模型而非预算 Runnable。相同输入的纯新闻 Graph 请求与直接调用原节点的 SDK HTTP 正文字节一致。
- CityU 使用现有 DeepSeekChatOpenAI、隔离的 DEEPSEEK_API_KEY 机制、https://llm.cs.cityu.edu.hk/v1 和 CS5351/DeepSeek-V4-Flash。注入的计数器按最终 JSON bytes 计数。适配器直接向 SDK 传输提交计数后的 bytes，并将 SDK 重试设为 0。
- SDK Mock 验证普通轮回传 reasoning_content，收尾轮采用 0.7.1 的纯文本方式。保留结构化解析器和本地拒绝检查，未识别的结构化形态会阻断。

## 离线证据

真实 0.7.1 Graph 新闻子图加 SDK Mock HTTP 验证普通工具轮、无工具收尾轮、工具 schema、结果 ID、最终报告、首次和最终计数失败的零发送边界。真实新闻数据、真实 CityU HTTP 和发送前计数未在本阶段验证。

检查点测试先中断新闻子图，随后恢复并计数其待执行请求。计数器版本变化时使用不同的检查点身份。预算关闭时省略空预算字段以保留原基线签名。

实际通过数量及保真数据见 [验收报告](req-context-budget-acceptance.md)。
