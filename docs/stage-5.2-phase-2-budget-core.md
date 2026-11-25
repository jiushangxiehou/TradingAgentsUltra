# Stage 5.2 Phase 2 · Token Budget 核心迁移

结论为 **核心模块与离线验收通过，等待人工批准后接入新闻节点和供应商适配器**。

## 范围与文件

目标仓库为 jiushangxiehou/TradingAgentsUltra，分支为 feature-z，HEAD 为 644676fa346aefdf49eb5723290f335084fb06fa。旧工作区仅作读取，原有 4 个已跟踪修改和 13 个未跟踪文件均保留。

| 文件 | 用途 |
|---|---|
| tradingagents/graph/context_budget.py | 迁入预算核心、结构校验、日期过滤、裁剪、最终计数与一次性发送许可 |
| tests/news_context_budget_fixtures.py | 保留旧测试的合成事实、工具 schema、多轮历史和记忆样本 |
| tests/test_context_budget_core.py | 在 0.7.1 消息对象和 Mock HTTP 上运行预算核心验收及默认关闭回归 |
| docs/stage-5.2-phase-2-budget-core.md | 本轮交付和实测结果 |

## 接口与核心行为

1. 沿用旧接口 resolve_budget、is_budget_enabled、budget_and_send 和 ProviderAdapter 的 supports、prepare、count、send。0.7.1 的 AIMessage／ToolMessage 保留所需的原始与规范化工具调用、tool_call_id 和消息元数据。核心接收已格式化消息，不依赖旧 Graph 状态。
2. 两项预算配置缺省时解析为关闭。部分配置、非法阈值或阈值高于硬上限会失败。新版默认配置无需写入新的值，现有新闻节点继续使用原有路径。
3. 配对按工具调用 ID 验证，拒绝重复、缺失、孤立和原始／规范化参数冲突。日期过滤先于请求准备和计数，只根据明确的 available_at。冲突日期取较晚值，event_date 保持事件含义。若所有关联结果尚不可用，但助手正文可用，保留正文及调用，用占位结果维护配对。
4. 超过压缩阈值时执行最多一次提取式整理。保留锚点、重要助手正文和独立事实。安全去重及裁剪后再准备、计数最终请求。最终计数不可验证或超过硬上限时，零 HTTP。
5. 一次性许可绑定适配器、最终请求对象与已计数正文。复制执行上下文共享同一把消费锁。Mock HTTP 收到的正文必须等于最后一次计数对应的 bytes。未获许可、重复消费及改写已计数正文都在传输前被拒绝。

## 实际验证

| 项目 | 结果 |
|---|---|
| 新增预算核心测试 | 73 通过 |
| 相关既有回归 | 139 通过，1 项真实 DeepSeek 集成测试由项目配置取消选择 |
| 全量 pytest -q | 1485 通过，0 失败，1 跳过，1 取消选择，另有 100 个子测试通过 |
| Phase 1 对比 | 原 1412 通过，本轮增加 73 项通过。失败、跳过和取消选择数量一致 |
| Ruff | 全仓通过 |
| py_compile | 三个新增 Python 文件通过 |
| git diff --check | 通过，另检查未跟踪文件的空白差异 |

测试在空环境、临时 HOME、UTC、本机回环可用且无外部路由的隔离网络命名空间执行。Mock HTTP 覆盖阈值和硬上限边界、首轮及压缩后最终计数、跨轮及交错工具历史、完整新闻事实保真、所有未来工具结果过滤后的正文保留、计数失败零发送及许可并发。NA-17 使用新版记忆接口，NA-18 调用实际 0.7.1 新闻节点，验证默认配置保持原路径。跳过项为缺少可选 Bedrock 依赖，取消选择项为真实 DeepSeek 测试。本轮未读取真实凭据或调用真实 API。

## 后续验收

- 新闻子图普通工具轮和无工具收尾轮的接线，及其检查点恢复兼容性，应在接入阶段验收。
- DeepSeek／CityU 的最终 SDK JSON、reasoning_content、重试与真实发送前 Token 计数仍需供应商适配阶段验证。本轮的确定性 Mock 计数只验证预算控制。
- 缺失明确 available_at 的逐条新闻仍依赖上游日期筛选。逐条溯源和真实 Demo 留待后续阶段。
