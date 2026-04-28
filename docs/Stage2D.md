你现在继续开发 FeishuAutoRepair 项目。

当前项目已经完成 Stage 1 → Stage 2C：
1. FastAPI demo_service 可以通过 Web UI 触发预埋 Bug。
2. 当前已有 TypeError 用户画像 Bug 和 ZeroDivisionError 订单 Bug。
3. 日志会写入 demo_service/logs/app.log。
4. log_parser 可以提取 ErrorSummary。
5. watcher 支持增量扫描、多 traceback 提取、watch_state offset、防重复处理。
6. incident_store 支持按 fingerprint 聚合 occurrence_count。
7. 相同 Bug 只创建一个 Incident，后续重复发生只更新 occurrence_count，不重复发飞书卡片。
8. GitHub Issue adapter 已有真实 API 和 Mock 降级，但当前 Mock Issue 创建后不能被 watcher 扫描到。
9. 飞书 adapter 已有真实发送和 Mock 发送。
10. pytest -q 通过。
11. pytest -q -m agent_target 预期失败。
12. 当前阶段不要修复任何预埋 Bug。

现在请完成 Stage 2D：真实业务场景重塑与离线 Issue 闭环。

本阶段核心目标：
把 Demo 从简单的用户画像/订单异常，升级为更贴近企业研发协作的「Acme SupportDesk Lite 工单与 SLA 服务」场景；同时补齐 Mock GitHub Issue 的离线闭环，并优化 watcher 输出，方便后续录屏演示。

重要约束：
- 不要接入 LLM。
- 不要自动修复代码。
- 不要创建 PR。
- 不要修复任何 agent_target 测试对应的预埋 Bug。
- 不要删除原有 TypeError / ZeroDivisionError 旧场景，除非必要。
- 不要引入数据库。
- 不要引入 React/Vue。
- 不要引入复杂前端工程。
- 保持项目小而美。
- 默认 pytest -q 必须通过。
- pytest -q -m agent_target 仍然应该失败。

## 一、业务场景重塑

请将 Demo 主场景包装为：

Acme SupportDesk Lite

业务背景：
这是一个模拟企业内部服务台的轻量工单系统。它接收来自飞书或 Web 表单的客户问题，创建工单，计算 SLA 截止时间，并在异常时由 AutoRepair Agent 捕获、分析和修复。

请在首页中体现这个业务背景。

页面标题建议：
Acme SupportDesk Lite

说明文案：
“这是一个用于模拟企业内部工单与 SLA 服务的轻量业务控制台。异常操作会触发服务端 Bug，供 AutoRepair Agent 捕获、聚合、通知并在后续阶段自动修复。”

## 二、新增 Ticket 业务模块

新增文件：

demo_service/ticket_repository.py
demo_service/ticket_service.py

可以视需要新增轻量模型，但不要过度拆分。

ticket_repository.py：
- 使用内存 list/dict 存储 ticket
- 提供 create_ticket(data: dict) -> dict
- 提供 get_ticket(ticket_id: str) -> dict | None
- 提供 find_by_idempotency_key(key: str) -> dict | None
- 不要引入数据库

ticket_service.py：
实现 submit_ticket(payload: dict) -> dict。

请求字段：
- customer_id: str
- title: str
- priority: str，例如 P1 / P2
- channel: str，例如 feishu / web
- sla_deadline: str，ISO8601 字符串
- idempotency_key: str | None

返回字段：
- ticket_id
- customer_id
- title
- priority
- channel
- sla_deadline
- status
- created_at
- idempotency_key

## 三、新增 Runtime Bug：SLA 时区比较 Bug

请故意在 ticket_service.py 中预埋一个更真实的 Bug。

错误逻辑示例：

from datetime import datetime

deadline = datetime.fromisoformat(payload["sla_deadline"])
if deadline < datetime.utcnow():
    ...

当 sla_deadline 是带时区的字符串，例如：

2026-04-25T18:00:00+08:00

而 datetime.utcnow() 是 offset-naive datetime 时，会触发：

TypeError: can't compare offset-naive and offset-aware datetimes

这是本阶段新增的主线 Runtime Bug，后续 Agent 会修复它。

注意：不要修复这个 Bug。

## 四、新增接口

在 demo_service/app.py 中新增：

POST /tickets/submit

请求 JSON：

{
  "customer_id": "c_1001",
  "title": "客户反馈无法收到飞书审批通知",
  "priority": "P1",
  "channel": "feishu",
  "sla_deadline": "2026-04-25T18:00:00+08:00",
  "idempotency_key": "evt_demo_001"
}

如果触发时区 Bug，应返回 500，并写入完整 traceback。

另加：

GET /tickets/{ticket_id}

用于查询 ticket。简单实现即可。

## 五、新增业务逻辑 Bug：幂等性 Bug

请在 ticket_service.py 中同时保留一个业务逻辑 Bug：

当同一个 idempotency_key 被重复提交时，当前错误行为是创建两个不同 ticket。

期望行为是：
同一个 idempotency_key 应返回同一个 ticket，不重复创建。

注意：
- 当前阶段不要修复。
- 这个 Bug 主要用于 GitHub Issue / agent_target 测试，不一定触发 traceback。
- 这是为了展示系统不仅能处理运行时异常，也能处理开发者提交的业务缺陷。

## 六、测试

新增：

demo_service/tests/test_ticket_success.py
demo_service/tests/test_ticket_contract.py

默认 pytest -q 必须通过。

test_ticket_success.py：
- 测试一个不触发 timezone bug 的正常 ticket 创建路径。
- 可以使用不带时区的 sla_deadline，例如 "2099-01-01T00:00:00"。
- 断言返回 200 或 201，ticket_id 存在。

test_ticket_contract.py 标记 @pytest.mark.agent_target，包含两个当前预期失败的测试：

1. test_timezone_aware_sla_deadline_should_create_ticket
请求 sla_deadline="2099-01-01T18:00:00+08:00"
期望不返回 500，而是成功创建 ticket。
当前由于预埋 Bug，会失败。

2. test_duplicate_idempotency_key_should_not_create_two_tickets
连续两次提交相同 idempotency_key。
期望返回同一个 ticket_id，或第二次响应中能体现 idempotent=True。
当前由于预埋 Bug，会失败。

注意：不要为了让 agent_target 测试通过而修复业务代码。

## 七、首页 UI 优化

修改 demo_service/app.py 首页。

要求：
- 不引入 React/Vue。
- 保持原生 HTML + JS。
- 去掉和项目无关的水印、竖排文字或奇怪装饰。
- 主标题改为：Acme SupportDesk Lite。
- 保留原有健康检查能力。
- 新增主线按钮：

1. 系统健康检查
2. 提交正常 P2 工单
3. 提交带 +08:00 SLA 的紧急工单（触发时区 Bug）
4. 重复提交同一幂等键工单（模拟业务缺陷）

可以把旧的“查询缺失员工画像”和“提交 0 元异常订单”放到一个“Legacy Bug 场景”区域，或保留为次要按钮，但不要作为页面主视觉。

页面响应区域显示：
- status code
- response body
- 如果返回 500，提示“后台将生成 traceback，可运行 python scripts/watch_once.py 扫描”。

## 八、更新 bug_scenarios.py

在 autorepair/bug_scenarios.py 中新增两个场景：

1. ticket-timezone-sla
标题：带时区 SLA 截止时间导致工单创建失败
错误类型：TypeError
目标测试：
pytest -q demo_service/tests/test_ticket_contract.py::test_timezone_aware_sla_deadline_should_create_ticket -m agent_target

2. ticket-idempotency-duplicate
标题：重复事件导致重复创建工单
错误类型：BusinessLogicError 或 DuplicateTicket
目标测试：
pytest -q demo_service/tests/test_ticket_contract.py::test_duplicate_idempotency_key_should_not_create_two_tickets -m agent_target

用于 create_demo_issue.py 创建演示 Issue。

## 九、补齐 Mock GitHub Issue 离线闭环

当前问题：
scripts/create_demo_issue.py 在 GitHub 配置缺失时只打印 Mock Issue，但 watch_github_issues_once.py 扫不到它。

请修复这个问题。

实现要求：

1. 新增本地 Mock Issue 存储文件：
autorepair/records/mock_github_issues.jsonl

2. 当 GitHub 配置缺失时：
create_demo_issue.py 调用 github adapter 的 create_issue，应将 mock issue 写入 mock_github_issues.jsonl。

3. 当 GitHub 配置缺失时：
watch_github_issues_once.py / github adapter 的 list_open_bug_issues 应从 mock_github_issues.jsonl 读取 open issue。

4. comment_issue 在 mock 模式下：
不要只打印，应把评论追加到 mock issue 的 comments 字段里，或写入 mock_github_issue_comments.jsonl。

5. add_labels 在 mock 模式下：
更新 mock issue 的 labels 字段。

6. 这样即使没有真实 GitHub Token，也要能完整演示：

python scripts/create_demo_issue.py ticket-idempotency-duplicate
python scripts/watch_github_issues_once.py

预期：
- watch 脚本能发现刚才创建的 mock issue
- 生成 source=github_issue 的 Incident
- 写入 incidents.jsonl
- 输出 Mock 飞书卡片
- mock issue 被添加 processing 标签或评论

## 十、优化 watch_once.py 输出

当前 watch_once.py 对每个重复 occurrence 都打印一行 updated，演示时太刷屏。

请优化输出：

- 仍然保留 created 明细。
- updated 可以按 incident_id 聚合输出。
- 最后增加 Scan Summary。

示例：

Scan Summary
- Created incidents: 2
- Updated occurrences: 8
- Feishu cards sent: 2

Details:
[created] INC-xxx TypeError demo_service/ticket_service.py:23 occurrence_count=1
[created] INC-yyy ZeroDivisionError demo_service/order_service.py:22 occurrence_count=1
[updated] INC-xxx occurrence_count 1 -> 5
[updated] INC-yyy occurrence_count 1 -> 4

只有 created 才发送飞书卡片，updated 不重复发送。

## 十一、重置脚本增强

更新 scripts/reset_demo_state.py。

清理以下内容：
- demo_service/logs/app.log
- autorepair/records/incidents.jsonl
- autorepair/records/watch_state.json
- autorepair/records/mock_github_issues.jsonl
- autorepair/records/mock_github_issue_comments.jsonl，如有

不要删除 .gitkeep。
文件不存在时不要报错。

## 十二、README 更新

更新 README，增加 Stage 2D 演示流程。

演示路线 A：运行时异常

1. python scripts/reset_demo_state.py
2. python scripts/run_demo_server.py
3. 打开 http://127.0.0.1:8000/
4. 点击“提交带 +08:00 SLA 的紧急工单”
5. python scripts/watch_once.py

预期：
- 生成 TypeError Incident
- 错误信息包含 can't compare offset-naive and offset-aware datetimes
- 飞书真实通知或 Mock 卡片

演示路线 B：Bug 提交

1. python scripts/reset_demo_state.py
2. python scripts/create_demo_issue.py ticket-idempotency-duplicate
3. python scripts/watch_github_issues_once.py

预期：
- 即使没有真实 GitHub 配置，也能通过 mock issue store 完整闭环
- 生成 source=github_issue 的 Incident
- 输出 Mock 飞书卡片
- mock issue 被评论或标记为 processing

说明：
- 本阶段不接入 LLM
- 本阶段不自动修复
- 本阶段不创建 PR
- 预埋 Bug 不要修复
- 后续 Stage 3 会接入 Doubao 进行根因分析和修复计划生成

## 十三、测试要求

新增或更新测试，pytest -q 必须通过。

至少覆盖：
1. 正常 ticket 创建成功。
2. timezone-aware SLA 的 agent_target 测试当前失败。
3. 重复 idempotency_key 的 agent_target 测试当前失败。
4. mock create_issue 会写入 mock_github_issues.jsonl。
5. mock list_open_bug_issues 能读到刚创建的 mock issue。
6. mock comment_issue 能记录评论。
7. mock add_labels 能更新 labels。
8. watch_github_issues_once 能从 mock issue 生成 Incident。
9. watch_once.py 输出聚合后的 summary，不再为每个 updated 刷屏。

注意：
- 测试不要真实调用 GitHub 或飞书。
- pytest -q 必须通过。
- pytest -q -m agent_target 仍然必须失败。

## 十四、输出要求

完成后请输出：
1. 新增/修改文件列表。
2. pytest -q 结果。
3. pytest -q -m agent_target 结果。
4. Runtime Bug 演示步骤。
5. GitHub Mock Issue 演示步骤。
6. watch_once.py 的新输出示例。
7. 明确说明没有修复任何预埋 Bug，没有接入 LLM，没有创建 PR。