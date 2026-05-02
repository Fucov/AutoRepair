你现在继续开发 FeishuAutoRepair 项目。

当前状态：
1. 已完成 Runtime Bug → Incident → GitHub Issue → 飞书故障卡片。
2. Dashboard 已能展示 Incident、Issue、PR、修复任务统计。
3. 飞书卡片 5 类轻量模板已完成。
4. 当前问题：
   - 点击扫描 Issue 后，会发送修复计划卡，但诊断报告按钮没有真实飞书文档链接。
   - 扫描 Issue 生成的修复计划内容过于泛化，没有完整修复策略报告。
   - 修复阶段提示 “Incident ISSUE-7 not found”，说明 Issue Number 和 Incident ID 混用。
   - 需要明确：检测 Bug / 扫描 Issue 可以并发，但修复代码和提交 PR 必须单线程。
   - 现在还没有稳定的 RepairJob queued → repair_once → PR 闭环。

本阶段名称：
Stage 3E：Feishu Doc Report + Issue-Driven Repair Queue

核心目标：
1. 修复 Issue ↔ Incident 映射，彻底解决 Incident ISSUE-7 not found。
2. 扫描 Issue 时生成完整飞书文档诊断报告，并把 report_url 传入 RepairPlanReadyCard。
3. 扫描 Issue 通过合理性检查后创建 RepairJob queued。
4. 明确并实现并发模型：检测和扫描可并发，修复代码单线程。
5. 为下一步 repair_once 自动修复和 PR 创建打好基础。

重要约束：
- 不要把 ISSUE-7 当作 incident_id。
- 不要在扫描 Issue 时直接修改代码。
- 扫描 Issue 只负责诊断、报告、创建 RepairJob queued。
- 修复代码只能由 repair_once.py 单线程执行。
- 同一个 Issue 只能有一个 active RepairJob。
- 同一个 Incident 只能有一个 active RepairJob。
- 同一个 repo 同一时间只能有一个 running RepairJob。
- 不要自动 merge PR。
- 不要直接修改 main/master/develop。
- pytest -q 必须通过。

============================================================
一、修复 Issue 与 Incident 映射
============================================================

请新增或完善：

autorepair/incident_store.py

实现：

find_incident_by_issue_number(issue_number: int) -> Incident | None
find_incident_by_issue_url(issue_url: str) -> Incident | None
create_incident_from_issue(issue: GitHubIssue, service: TargetService | None = None) -> Incident

规则：
1. Incident ID 永远使用 INC- 开头。
2. Issue 只作为字段：
   - issue_number
   - issue_url
   - issue_title
3. 不允许生成 incident_id = ISSUE-7。
4. 当处理手动 GitHub Issue 时：
   - 如果已有 issue_number 对应 Incident，则复用。
   - 如果没有，则创建 source=github_issue 的 Incident。
5. source=github_issue 的 Incident 可以没有 raw_traceback，但必须有：
   - incident_id
   - source
   - service_name
   - issue_number
   - issue_url
   - issue_title
   - status
   - created_at
6. 修复所有调用 load_incident("ISSUE-7") 的地方，改为先通过 issue_number 查找或创建 Incident。

验收：
- 扫描 Issue #7 时不再报 Incident ISSUE-7 not found。
- incidents.jsonl 中能看到 issue_number=7 对应的 INC-xxx。
- 修复计划卡中的事件ID显示 INC-xxx，而不是 ISSUE-7。

============================================================
二、飞书文档诊断报告 Client
============================================================

新增：

autorepair/adapters/feishu_docx.py

实现：

class FeishuDocxClient:
    def create_document(self, title: str, folder_token: str | None = None) -> FeishuDocRef
    def append_blocks(self, document_id: str, blocks: list[dict]) -> None
    def add_view_permission(self, document_token: str, member_id: str, member_type: str = "openid") -> None
    def make_public_readable(self, document_token: str) -> bool
    def create_diagnostic_report(self, report: DiagnosticReportData) -> FeishuDocRef

配置项：
FEISHU_DOC_FOLDER_TOKEN 可选，用于指定文档创建目录
FEISHU_DOC_PUBLIC_READABLE=false/true
FEISHU_DOC_SHARE_MEMBER_ID 可选
FEISHU_DOC_SHARE_MEMBER_TYPE=open_id/openid/email/chat_id，按实际实现选择一种稳定方案

API 要求：
1. 创建文档：
   POST {FEISHU_API_BASE_URL}/docx/v1/documents
2. 写入内容：
   POST {FEISHU_API_BASE_URL}/docx/v1/documents/{document_id}/blocks/{block_id}/children
   root block_id 可以先使用 document_id。
3. 添加权限：
   POST {FEISHU_API_BASE_URL}/drive/v1/permissions/{token}/members?type=docx
4. 如果权限 API 失败，不要中断主流程：
   - report_url 仍然返回文档 URL
   - 记录 audit event
   - 控制台提示权限可能不足

注意：
- 不要在报告中写入 .env、token、secret。
- Traceback 可以截断，最多保留 120 行。
- 写入飞书文档失败时，fallback 为本地 Markdown 报告路径，但卡片 report_url 可为空或指向 GitHub Issue。
- 所有外部 API 测试必须 monkeypatch，不真实请求飞书。

FeishuDocRef 字段：
- document_id
- document_token
- url
- title

URL 格式可以先使用：
https://{tenant_domain}/docx/{document_id}
如果没有 tenant_domain，则从 API 返回值中获取 URL；若 API 不返回 URL，则在配置中新增 FEISHU_DOC_BASE_URL。

============================================================
三、诊断报告数据结构
============================================================

新增：

autorepair/reports/schemas.py

class DiagnosticReportData:
    report_id: str
    incident_id: str
    issue_number: int | None
    issue_url: str | None
    service_name: str
    error_brief: str
    evidence_summary: str
    validation_result: str
    root_cause: str
    repair_strategies: list[str]
    risk_level: str
    policy_result: str
    next_steps: list[str]
    traceback_excerpt: str | None
    created_at: str

新增：

autorepair/reports/diagnostic_report_builder.py

实现：

build_diagnostic_report(issue, incident, validation_result, triage_result, policy_result) -> DiagnosticReportData
render_diagnostic_report_markdown(report: DiagnosticReportData) -> str
render_diagnostic_report_blocks(report: DiagnosticReportData) -> list[dict]

报告内容必须包含：
1. 基本信息
2. Issue 信息
3. Incident 信息
4. 错误摘要
5. 证据摘要
6. 合理性检查结果
7. 根因判断
8. 修复策略，至少 3 条：
   - 最小修复策略
   - 测试验证策略
   - 风险控制策略
9. 风险等级
10. 准入结论
11. 下一步动作
12. Traceback 摘要

============================================================
四、扫描 Issue 时生成报告 + RepairJob
============================================================

修改：

scripts/watch_github_issues_once.py
autorepair/repair/orchestrator.py

处理流程：

1. 扫描 open Issue。
2. 跳过：
   - autorepair:closed
   - autorepair:repairing
   - autorepair:pr-ready
   - invalid/wontfix/question
3. validate_bug_issue(issue)。
4. 如果不合理：
   - 通过 find_or_create_incident_for_issue 获取 Incident。
   - 生成 DiagnosticReportData。
   - 创建飞书诊断报告文档。
   - 发送 ManualInterventionCard，report_url 指向文档。
   - 评论 GitHub Issue：说明缺少什么信息，并附报告链接。
   - 打标签 autorepair:needs-info。
   - 不创建 RepairJob。
5. 如果合理：
   - find_or_create_incident_for_issue。
   - 运行 triage / policy gate。
   - 生成完整 DiagnosticReportData。
   - 创建飞书诊断报告文档。
   - 发送 RepairPlanReadyCard，report_url 指向文档。
   - 评论 GitHub Issue：已完成诊断，附报告链接。
   - 创建 RepairJob，status=queued。
   - 打标签 autorepair:accepted。
   - 写 audit event：
     diagnostic_report_created
     repair_plan_generated
     repair_job_created

RepairPlanReadyCard 的变量：
- incident_id 必须是 INC-xxx
- service_name
- diagnosis_brief
- fix_strategy 只放一句摘要
- risk_level
- policy_result
- report_url 必须是飞书文档 URL 或 fallback URL

验收：
- 点击扫描 Issue 后，飞书修复计划卡里的“查看完整诊断报告”按钮可打开飞书文档。
- GitHub Issue 下有评论，包含诊断报告链接。
- repair_jobs.jsonl 出现 queued job。
- 同一个 Issue 重复扫描不会重复创建报告和 RepairJob，除非状态发生变化。

============================================================
五、多线程检测，单线程修复
============================================================

新增或完善：

autorepair/scheduler.py

实现一个轻量调度器，不需要复杂框架。

允许并发任务：
- scan_logs
- scan_issues
- send_digest
- dashboard refresh

单线程任务：
- repair_worker
- sync_pr_status

设计：
1. scan_logs 和 scan_issues 可以并发运行。
2. scan_logs 只创建 Incident/Issue/Card。
3. scan_issues 只创建诊断报告和 RepairJob。
4. repair_worker 使用全局 repair lock。
5. repair_worker 每次只取一个 queued job。
6. repo_lock 再保证同一 repo 串行。
7. Dashboard 的“执行修复”按钮只能触发一次 repair_once，不得并发执行多个 repair_once。

新增：
autorepair/records/locks/repair_worker.lock

如果 repair_once.py 检测到已有 repair_worker.lock：
- 输出 “repair worker already running”
- 不执行
- 不标记 job 失败

验收：
- 同时触发两次 repair_once.py，只有一个执行。
- scan_logs 和 scan_issues 可以连续点击，不影响 repair lock。
- 同一 Issue 不会生成两个 queued job。

============================================================
六、RepairJob 创建规则
============================================================

完善：

autorepair/repair/job_store.py

create_repair_job_from_issue(incident, issue, report_url, policy_result) -> RepairJob

规则：
1. 如果 find_active_job_by_issue(issue.number) 存在，直接返回已有 job。
2. 如果 find_active_job_by_incident(incident.incident_id) 存在，直接返回已有 job。
3. 新 job 状态为 queued。
4. job 中必须保存：
   - job_id
   - incident_id
   - issue_number
   - issue_url
   - report_url
   - service_name
   - repo_owner
   - repo_name
   - base_branch
   - status=queued
   - created_at
5. 写 audit event repair_job_created。

active statuses:
- queued
- running
- pr_created

验收：
- 同一个 Issue 重复扫描，只返回已有 job。
- Dashboard 待处理 Issue / RepairJob 统计正确。

============================================================
七、Dashboard 调整
============================================================

修改 Dashboard：

1. 最近 Incident 表格增加：
   - issue_url
   - report_url
2. RepairJob 列表增加：
   - job_id
   - incident_id
   - issue_number
   - status
   - report_url
   - pr_url
3. 操作中心：
   - 扫描日志：可并发
   - 扫描 Issue：可并发
   - 执行修复：单线程
   - 同步 PR：单线程
   - 发送统计摘要
4. 点击扫描 Issue 后，页面应刷新并显示 queued RepairJob。
5. 详情弹窗可选；如果时间紧，先用链接跳转 GitHub Issue 和飞书文档。

============================================================
八、测试要求
============================================================

pytest -q 必须通过。

至少新增测试：

1. find_incident_by_issue_number 能找到 Incident。
2. create_incident_from_issue 创建 INC-xxx，不创建 ISSUE-7。
3. 扫描 Issue 不再出现 Incident ISSUE-x not found。
4. build_diagnostic_report 至少包含 3 条 repair_strategies。
5. render_diagnostic_report_markdown 包含 Issue、Incident、根因、策略、下一步。
6. FeishuDocxClient.create_document monkeypatch 测试请求路径正确。
7. FeishuDocxClient.append_blocks monkeypatch 测试写入 blocks。
8. 飞书文档创建失败时 fallback 不阻断扫描 Issue。
9. 合理 Issue 扫描后创建 queued RepairJob。
10. 不合理 Issue 扫描后 needs-info，不创建 RepairJob。
11. 同一个 Issue 重复扫描不重复创建 RepairJob。
12. repair_worker.lock 防止并发 repair_once。
13. Dashboard /api/repair_jobs 返回 report_url。
14. 所有 Feishu/GitHub 网络调用在测试中 monkeypatch。

============================================================
九、README 更新
============================================================

更新 README，说明新的节点：

运行时异常路线：
1. 触发 Bug。
2. watch_once 创建 Incident + Issue + 故障卡。
3. watch_github_issues_once 扫描 Issue。
4. 生成飞书诊断报告文档。
5. 发送修复计划卡。
6. 创建 RepairJob queued。
7. repair_once 单线程执行修复。
8. PR 创建后发送 PR Review 卡。

手动 Issue 路线：
1. 用户提交 bug Issue。
2. scan_issues 检查合理性。
3. 不合理：评论 needs-info + 诊断报告 + 人工介入卡。
4. 合理：创建 Incident + 诊断报告 + RepairJob queued。
5. 后续同 repair_once。

并发说明：
- 检测和扫描可以并发。
- 修复代码和 PR 创建单线程。
- worktree + repo lock 防止仓库污染。
- 不自动 merge。

============================================================
十、输出要求
============================================================

完成后输出：
1. 修改文件列表。
2. Issue ↔ Incident 映射修复说明。
3. 飞书文档诊断报告 API 使用说明。
4. watch_github_issues_once 示例输出。
5. 生成的 report_url 示例。
6. repair_jobs.jsonl 示例。
7. Dashboard 新增展示项。
8. pytest -q 结果。
9. 明确说明：
   - 扫描 Issue 不再把 ISSUE-7 当 incident_id。
   - 扫描 Issue 会生成飞书文档诊断报告。
   - 扫描 Issue 只创建 RepairJob queued，不直接修代码。
   - repair_once 单线程执行。