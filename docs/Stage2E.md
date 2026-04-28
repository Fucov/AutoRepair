你现在继续开发 FeishuAutoRepair 项目。

当前项目已经完成 Stage 1 → Stage 2D：
1. demo_service 是 FastAPI 服务，首页为 Acme SupportDesk Lite。
2. 支持工单与 SLA 场景。
3. 已有 Runtime Bug：带 +08:00 SLA 的工单会触发 TypeError: can't compare offset-naive and offset-aware datetimes。
4. 已有业务逻辑 Bug：重复 idempotency_key 会重复创建工单。
5. watcher 支持增量日志扫描、多个 traceback 提取、fingerprint 聚合、occurrence_count 更新、防刷屏通知。
6. GitHub Issue 支持真实 API 和 Mock Issue Store。
7. 飞书支持真实发送和 Mock 发送。
8. pytest -q 通过。
9. pytest -q -m agent_target 预期失败。
10. 当前不要修复任何预埋 Bug。

现在请完成 Stage 2E：产品化 Demo UI + 解耦式服务注册 + 多轮诊断审计框架。

本阶段核心目标：
1. 让 Demo 页面更像真实的企业工单管理系统，但仍然保持轻量，不引入前端框架。
2. 让 AutoRepair Agent 与 demo_service 强解耦，不再写死 demo_service，而是通过服务注册配置监控任意目标服务。
3. 在自动修复前加入多轮核查与审计记录，为后续 LLM 分析和自动修复做准备。

重要约束：
- 不要接入 LLM。
- 不要自动修复代码。
- 不要创建 PR。
- 不要修复任何 agent_target 测试对应的预埋 Bug。
- 不要引入数据库。
- 不要引入 React/Vue。
- 不要引入复杂前端工程。
- 保持项目小而美。
- pytest -q 必须通过。
- pytest -q -m agent_target 仍然应该失败。

## 一、Demo UI 产品化

修改 demo_service/app.py 中的首页 HTML。

目标：
把页面从“按钮面板”升级为一个 mock 的企业工单系统，但不要做复杂前端。

页面标题：
Acme SupportDesk Lite

页面副标题：
企业客户支持工单与 SLA 管理平台

页面结构建议：

1. 顶部统计卡片：
- 今日工单：128
- P1 紧急工单：7
- SLA 风险工单：3
- 飞书渠道占比：64%

这些数据可以是静态 mock。

2. 主操作区：
- 系统健康检查
- 提交正常 P2 工单
- 提交带 +08:00 SLA 的紧急工单（触发时区 Bug）
- 重复提交同一飞书事件（模拟幂等性缺陷）

3. 工单列表区：
展示 4-6 条 mock 工单数据，字段包括：
- 工单编号
- 客户
- 来源
- 优先级
- SLA 截止时间
- 状态

4. 最近事件流：
展示 mock 事件，例如：
- 飞书渠道收到客户反馈
- P1 工单进入 SLA 风险
- AutoRepair 正在监听服务异常

5. 响应结果区：
展示当前点击按钮后的 status code 和 response body。
当返回 500 时，提示：
“后台已生成 traceback，可运行 python scripts/watch_once.py 扫描并生成 Incident。”

要求：
- 使用原生 HTML + CSS + JS。
- 不引入 React/Vue。
- 不引入构建工具。
- 真实有效逻辑只保留必要按钮，其余列表和指标可以 mock。
- 页面视觉要干净专业，不要奇怪水印或无关元素。

## 二、服务注册配置

新增目录和文件：

autorepair/config/services.yaml

内容示例：

services:
  - service_id: supportdesk-lite
    name: Acme SupportDesk Lite
    description: 企业内部工单与 SLA 服务
    language: python
    framework: fastapi
    base_url: http://127.0.0.1:8000
    healthcheck_url: http://127.0.0.1:8000/health
    repo_path: .
    log_paths:
      - demo_service/logs/app.log
    test_command: pytest -q
    agent_target_test_command: pytest -q -m agent_target
    github:
      owner_env: GITHUB_OWNER
      repo_env: GITHUB_REPO
      base_branch_env: GITHUB_BASE_BRANCH

注意：
- 这个配置用于证明 AutoRepair Agent 与 demo_service 解耦。
- 后续其他服务只要增加一段 service 配置，就可以接入监控。
- watcher 不应该再强依赖硬编码的 demo_service/logs/app.log。

## 三、服务配置加载器

新增：

autorepair/service_registry.py

实现：

load_services(config_path: str | None = None) -> list[TargetService]
get_service(service_id: str, config_path: str | None = None) -> TargetService
get_default_service(config_path: str | None = None) -> TargetService

要求：
- 使用 PyYAML 或简单 yaml 解析。如果项目未引入 PyYAML，可以添加轻量依赖 pyyaml。
- config_path 默认指向 autorepair/config/services.yaml。
- repo_path 和 log_paths 支持相对路径，并解析为项目根目录下路径。
- 配置缺失时给出清晰错误。

## 四、数据结构增强

修改 autorepair/schemas.py。

新增：

class TargetService(BaseModel):
    service_id: str
    name: str
    description: str | None = None
    language: str = "python"
    framework: str | None = None
    base_url: str | None = None
    healthcheck_url: str | None = None
    repo_path: str
    log_paths: list[str]
    test_command: str | None = None
    agent_target_test_command: str | None = None

新增：

class DiagnosticCheck(BaseModel):
    name: str
    status: str   # passed / failed / skipped
    detail: str | None = None

class DiagnosticReport(BaseModel):
    incident_id: str
    service_id: str
    checks: list[DiagnosticCheck]
    classification: str | None = None
    fixability: str | None = None
    summary: str | None = None
    created_at: str

增强 Incident：
- 增加 service_id: str | None
- 增加 service_name: str | None
- 保持兼容已有 service 字段

## 五、改造 watcher

修改 autorepair/watcher.py。

要求：
- 保留现有 scan_new_log_events_once 兼容旧调用。
- 新增：

scan_service_logs_once(service: TargetService) -> list[tuple[Incident, str]]

逻辑：
1. 遍历 service.log_paths。
2. 对每个 log_path 使用现有 offset 机制读取新增日志。
3. 提取 traceback blocks。
4. 创建 Incident 时写入：
   - service_id
   - service_name
   - service 或 service_name
5. 继续使用 fingerprint 聚合。
6. 返回 created / updated 结果。

修改 scripts/watch_once.py：
- 默认读取 get_default_service()
- 调用 scan_service_logs_once(service)
- 输出中显示 service_name。
- 仍然只有 created 才发送飞书卡片。
- 保留 summary 聚合输出。

## 六、多轮诊断器

新增：

autorepair/diagnostics.py

实现：

run_basic_diagnostics(incident: Incident, service: TargetService) -> DiagnosticReport

诊断步骤：

1. service_config_check
- repo_path 是否存在
- log_paths 是否配置
- healthcheck_url 是否配置

2. healthcheck
- 如果 healthcheck_url 存在，使用 httpx GET，超时 2 秒
- 2xx 则 passed
- 失败则 failed
- 无配置则 skipped

3. repo_check
- repo_path 是否存在
- 是否能找到 .git 目录，可选
- passed / failed

4. log_evidence_check
- incident.raw_traceback 是否存在
- error_summary 是否存在

5. test_command_check
- test_command 是否配置
- 不要在本阶段自动运行测试，只检查是否配置

6. classification
使用简单规则分类：
- 如果 error_summary.error_type 包含 ModuleNotFoundError 或 ImportError：dependency_missing
- 如果 source == github_issue 且没有 traceback：business_logic_bug
- 如果有 traceback：runtime_exception
- 否则 unknown

7. fixability
使用简单规则判断：
- runtime_exception 且 repo_path 存在：auto_fix_candidate
- business_logic_bug 且有 agent_target_test_command：auto_fix_candidate
- dependency_missing：human_required
- healthcheck failed 且无 traceback：human_required
- 其他：needs_more_info

注意：
- 本阶段不要调用 LLM。
- 诊断报告只是规则生成，后续 Stage 3 会交给 Doubao 进一步分析。

## 七、审计记录

新增：

autorepair/audit_store.py

实现：

append_audit_event(event_type: str, incident_id: str | None, payload: dict) -> None
load_audit_events(path: str | None = None) -> list[dict]

默认文件：

autorepair/records/audit_events.jsonl

要求：
- 自动创建 records 目录
- 每条记录包含：
  - event_id
  - event_type
  - incident_id
  - payload
  - created_at

在以下位置写审计记录：
- 创建 incident 时：incident_created
- 更新 occurrence 时：incident_updated
- 发送飞书卡片时：feishu_card_sent 或 feishu_card_mocked
- GitHub Issue 接收时：github_issue_received
- 诊断完成时：diagnostic_completed

保持简单，不要引入数据库。

## 八、watch_once 集成诊断

修改 scripts/watch_once.py。

当 action == "created" 时：
1. 发送飞书卡片。
2. 运行 run_basic_diagnostics。
3. 记录 audit。
4. 在输出中展示诊断摘要。

输出示例：

[created] INC-xxx TypeError Acme SupportDesk Lite demo_service/ticket_service.py:35 occurrence_count=1
  diagnosis: runtime_exception / auto_fix_candidate
  healthcheck: passed
  repo_check: passed

[updated] INC-xxx occurrence_count 1 -> 3

Scan Summary
- Service: Acme SupportDesk Lite
- Created incidents: 1
- Updated occurrences: 2
- Feishu cards sent: 1
- Diagnostics completed: 1

注意：
- 如果 healthcheck 失败，不要中断流程。
- 如果诊断失败，要记录错误并继续。

## 九、飞书卡片增强

修改 autorepair/adapters/feishu.py。

卡片中增加：
- service_name
- service_id
- 当前阶段：diagnosed 或 incident_created
- classification
- fixability
- occurrence_count
- 下一步提示：
  “系统已完成基础核查，后续将由 Doubao Agent 生成修复计划。”

如果当前 send_incident_card 在诊断前调用，可以先不展示诊断结果；也可以新增 send_diagnostic_card 或在 Mock 输出里展示诊断摘要。保持实现简单。

## 十、重置脚本增强

修改 scripts/reset_demo_state.py，清理：
- incidents.jsonl
- watch_state.json
- audit_events.jsonl
- mock_github_issues.jsonl
- mock_github_issue_comments.jsonl
- demo_service/logs/app.log

文件不存在时不要报错。

## 十一、测试

新增或修改测试，pytest -q 必须通过。

至少覆盖：

1. service_registry 能加载 services.yaml。
2. get_default_service 返回 supportdesk-lite。
3. scan_service_logs_once 能使用 TargetService 的 log_paths，而不是硬编码 demo_service。
4. run_basic_diagnostics 对 runtime traceback 返回 classification=runtime_exception。
5. run_basic_diagnostics 对 github_issue 且无 traceback 返回 business_logic_bug。
6. dependency_missing 类型能被分类为 dependency_missing。
7. fixability 对 runtime_exception + repo_path 存在返回 auto_fix_candidate。
8. audit_store 能 append/load。
9. watch_once 的 summary 能展示 service_name 和 diagnostic 结果。
10. 默认 pytest -q 通过。
11. pytest -q -m agent_target 仍然失败，不要修复预埋 Bug。

测试不要真实调用飞书、GitHub 或外部服务。
healthcheck 可通过 monkeypatch mock httpx.get。

## 十二、README 更新

更新 README，增加 Stage 2E 说明：

1. AutoRepair Agent 与 demo_service 解耦。
2. 目标服务通过 autorepair/config/services.yaml 注册。
3. 支持两种接入模式：
   - 黑盒模式：配置 base_url、healthcheck_url、repo_path、log_paths、test_command。
   - 可选 SDK/Middleware 模式：后续可通过业务服务嵌入标准异常事件上报。
4. 当前 Stage 2E 会在发现 Incident 后执行基础诊断：
   - healthcheck
   - repo check
   - log evidence check
   - test command check
   - classification
   - fixability
5. 本阶段不调用 LLM、不修复代码、不创建 PR。
6. 后续 Stage 3 将接入 Doubao 生成根因分析和修复计划。

## 十三、输出要求

完成后请输出：
1. 新增/修改文件列表。
2. pytest -q 结果。
3. pytest -q -m agent_target 结果。
4. 新 Demo UI 说明。
5. services.yaml 示例。
6. watch_once.py 新输出示例。
7. DiagnosticReport 示例。
8. audit_events.jsonl 示例。
9. 明确说明没有修复任何预埋 Bug，没有接入 LLM，没有创建 PR。