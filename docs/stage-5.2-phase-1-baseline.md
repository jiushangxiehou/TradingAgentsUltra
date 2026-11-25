# Stage 5.2 Phase 1 · TradingAgents 0.7.1 基线验收

日期为 2026-11-25。结论为**通过环境与离线基线验收，可以在人工批准后开始迁移**。本阶段未迁移业务代码，未提交、推送或合并。

## 仓库与分支

- 新仓库为 https://github.com/jiushangxiehou/TradingAgentsUltra.git，克隆到独立的 Ubuntu 工作区 TradingAgentsUltra-071。
- GitHub 连接账号为 zxsgdmn。仓库元数据返回 pull=true 和 push=true。克隆使用 HTTPS；连接账号查询与本地 Git 推送凭据是独立的，未试推或验证分支规则。
- origin 的 fetch 和 push 均指向新仓库。当前 feature-z 跟踪 origin/feature-z。
- HEAD、origin/feature-z 和 origin/dev 都是 644676fa346aefdf49eb5723290f335084fb06fa，提交说明为 vendor: TradingAgents 0.7.1 pinned baseline。feature-z 相对 dev 领先 0、落后 0。
- 克隆后与写报告前工作区干净。交付时只有本报告未跟踪，无已跟踪源码或配置变更。未修改 dev 和其他团队分支。
- 旧的 Ubuntu 工作区 TradingAgentsUltra 仍在 zhuxuan/context-retrieval-budget，HEAD 为 7df97449ba4453c1135406832011b021e3923952，origin 仍指向 Ellie2021141461073/TradingAgentsUltra。前后状态均为 4 个已跟踪文件修改、13 个未跟踪文件。

## Python 与依赖环境

使用 Ubuntu 的 Python 3.14.4，在新仓库创建独立 .venv。按项目 CI 安装 editable 包及 dev extra，命令为 .venv/bin/python -m pip --isolated install -e ".[dev]"。pip check 通过。未手工更改依赖声明或加入额外约束。

| 包 | 实际版本 |
|---|---|
| tradingagents | 0.7.1 |
| langchain-core / langchain-openai | 1.8.4 / 1.8.5 |
| langchain-anthropic / langchain-google-genai | 1.7.12 / 4.5.2 |
| langgraph / langgraph-checkpoint / langgraph-checkpoint-sqlite | 1.2.24 / 4.3.2 / 3.1.3 |
| openai / httpx | 3.59.0 / 0.28.1 |
| pandas / yfinance | 3.1.1 / 1.8.0 |
| pytest / pytest-subtests / Ruff | 9.2.0 / 0.15.0 / 0.17.6 |

## 实际运行结果

pytest 使用项目现有配置运行。进程从空环境启动，使用临时 HOME、UTC、关闭 dotenv 自动加载和 LangSmith tracing。网络命名空间只有本机回环接口，无外部路由。未读取真实 API Key，未访问模型或外部数据源。

| 检查 | 结果 |
|---|---|
| .venv/bin/python -m pytest -q | 收集 1414 项，选择 1413 项。1412 通过、0 失败、1 跳过、1 取消选择，另有 100 个子测试通过，24 条警告，耗时 10.56 秒 |
| .venv/bin/ruff check --no-cache . | 通过 |
| compileall -q tradingagents cli tests main.py | 通过，字节码写入 /tmp 下独立目录 |
| git diff --check | 通过 |

跳过项位于 tests/test_bedrock_provider.py:74，默认 dev extra 未安装可选的 langchain_aws。取消选择项来自项目 pytest 配置排除 integration 标记，涉及 tests/test_deepseek_reasoning.py 中的真实 DeepSeek 测试。

首次运行时隔离命名空间的回环接口尚未启用，tests/test_chatgpt_auth.py::test_the_browser_answer_reaches_the_loopback_and_strays_are_ignored 因连接 127.0.0.1 报 Network is unreachable 失败。首次结果为 1411 通过、1 失败、1 跳过、1 取消选择。仅在隔离命名空间中启用 lo 后完整重跑，最终无失败，源码、测试和断言均未修改。

本次在 Ubuntu 临时日志目录保留了首次 pytest 运行和启用回环后的全量重跑日志。

## 迁移放行条件

以本报告实测结果作为后续阶段的 0.7.1 离线对照。在 feature-z 获批后迁移，比较失败全名与断言，后续通过 PR 向 dev 交付。本报告未验收真实 CityU Token 计数。
