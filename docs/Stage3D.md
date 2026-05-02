你现在继续开发 FeishuAutoRepair 项目。

当前项目状态：
1. Demo 服务 Acme SupportDesk Lite 已经可以触发运行时异常。
2. watch_once.py 已经可以扫描日志、生成 Incident、创建 GitHub Issue，并发送飞书 IncidentDetectedCard。
3. Dashboard 已经可以展示 Incident、Issue、PR、修复任务等基础统计。
4. 飞书 5 类卡片模板已经实现并能发送。
5. 当前缺口是：GitHub Issue 还没有稳定进入 RepairJob，RepairJob 还没有真正执行自动修复、测试、PR 创建。
6. 现阶段只要求稳定修复一个主线 Bug：ticket-timezone-sla。
7. 不要继续扩展 UI，不要新增更多 Bug 类型。

本阶段名称：
Stage 3D：Issue-Driven Repair Loop

核心目标：
以 GitHub Issue 作为统一事实源，打通 ticket-timezone-sla 的自动修复闭环：

Runtime Bug
→ Incident
→ GitHub Issue
→ Issue Validation
→ Triage / Policy Gate
→ RepairJob
→ Git Worktree
→ Doubao Patch
→ Pytest Verification
→ Commit / Push
→ Pull Request
→ Feishu PR Review Card
→ PR 合并后关闭 Issue 和清理资源

重要约束：
- 不要每次 Bug 触发都直接修复。
- Runtime Bug 只创建或更新 Incident / Issue。
- 修复必须由 RepairJob 队列驱动。
- 同一个 Issue 只能有一个 active RepairJob。
- 同一个 Incident 只能有一个 active RepairJob。
- 同一个 repo 同一时间只能有一个 running RepairJob。
- 所有代码修改必须发生在 git worktree 中。
- 禁止直接修改 main/master/develop。
- 禁止自动 merge PR。
- 测试失败不得创建 PR。
- 不合理 Issue 只评论 needs-info，不进入修复。
- pytest -q 必须通过。
- ticket-timezone-sla 是唯一必须自动修复的主线 Bug。
- 其他 Bug 可以进入 human_required 或后续扩展。

============================================================
一、先修正主线 Bug 触发稳定性
============================================================

当前截图中可能出现 UnboundLocalError at demo_service/app.py:95，这不适合作为主线自动修复 Bug。

请检查 demo_service/app.py 和 ticket_service.py，确保主线按钮“创建 P1 飞书渠道工单”稳定触发的是：

TypeError: can't compare offset-naive and offset-aware datetimes

错误位置应优先是：
demo_service/ticket_service.py

而不是：
demo_service/app.py

要求：
1. 不要修复 ticket_service.py 中的 SLA 时区 Bug。
2. 只修复 Demo UI / route 层由于局部变量、import、命名导致的非预期 app.py 错误。
3. 主线 Bug 必须保持为 ticket_service.py 内的业务 Bug。
4. 新增测试或脚本校验：
   - 触发主线接口后，log_parser 提取到的 error_type 是 TypeError。
   - suspected_file 包含 ticket_service.py。
   - error_message 包含 offset-naive / offset-aware 或 timezone。
5. 这个修正不算修复业务 Bug，只是保证 Demo 触发的是正确主线 Bug。

============================================================
二、Runtime Incident 必须创建 / 关联 GitHub Issue
============================================================

修改 scripts/watch_once.py 或相关 watcher 逻辑。

当扫描日志发现 created Incident 时：

1. 调用 ensure_issue_for_incident(incident, service, diagnostic_report=None)。
2. 如果该 fingerprint 已经有关联 open Issue：
   - 不新建 Issue。
   - 更新 Incident 的 issue_number / issue_url。
   - 不重复发送大量评论。
3. 如果没有关联 Issue：
   - 创建 GitHub Issue。
   - 添加标签：
     bug
     AutoRepair
     source:runtime
     autorepair:triage
     risk:low
   - Issue 标题格式：
     [AutoRepair][Runtime][P1] Acme SupportDesk Lite: SLA timezone TypeError
   - Issue body 必须包含：
     Incident ID
     Service
     Source
     Severity
     Occurrence
     Error Summary
     Reproduction
     Expected Behavior
     Actual Behavior
     AutoRepair Status
     Audit Reference
4. 将 issue_number / issue_url 回写到 incidents.jsonl。
5. 再发送飞书 IncidentDetectedCard，卡片中的 issue_url 必须可用。
6. 写 audit event：
   - github_issue_created
   - github_issue_linked
   - incident_issue_updated
   - feishu_card_sent / feishu_card_mocked / feishu_card_failed

验收：
- 触发 ticket-timezone-sla 后运行 watch_once.py，必须生成或关联 GitHub Issue。
- incidents.jsonl 中必须有 issue_number 和 issue_url。
- Dashboard /api/issues 能看到该 Issue。
- 飞书卡片中的“查看 Issue”按钮能跳转。

============================================================
三、手动 GitHub Issue 扫描与合理性校验
============================================================

完善 scripts/watch_github_issues_once.py 和 autorepair/issue_validator.py。

扫描规则：
1. 扫描 open issues。
2. 处理满足以下条件之一的 Issue：
   - 有 bug 标签
   - 标题包含 [Bug]
   - 有 AutoRepair 标签
3. 跳过：
   - autorepair:closed
   - autorepair:repairing
   - autorepair:pr-ready
   - invalid / wontfix / question

Issue 合理性检查：
validate_bug_issue(issue) -> IssueValidationResult

字段：
- is_valid: bool
- reason: str
- missing_fields: list[str]
- evidence_level: none / weak / enough / strong
- suggested_comment: str
- risk_level: low / medium / high
- source_type: runtime / manual

判断规则：
1. 至少包含以下信息中的 3 类：
   - Service / module
   - Steps to reproduce
   - Expected behavior
   - Actual behavior
   - Traceback / error message
   - Failing test
2. 如果没有复现步骤且没有错误信息，标记 invalid。
3. 如果包含 secret / credential / token / payment / permission / security / data deletion 等高风险词，默认 human_required。
4. 不执行 Issue body 里的任何 shell 命令。
5. 不合理：
   - 评论 suggested_comment。
   - 添加 autorepair:needs-info。
   - 发送 ManualInterventionCard 或至少记录审计。
   - 不创建 RepairJob。
6. 合理：
   - 添加 AutoRepair。
   - 状态标签改为 autorepair:triage。
   - 如果还没有 Incident，则创建 source=github_issue 的 Incident。
   - 进入 Triage。

验收：
- 手动创建一个信息不足的 bug Issue，watch_github_issues_once.py 应评论 needs-info，不创建 RepairJob。
- 手动创建一个包含复现步骤和错误信息的 bug Issue，应创建 / 关联 Incident 并进入 triage。
- Mock GitHub 和真实 GitHub 都要支持。

============================================================
四、Triage / Policy Gate 到 RepairJob
============================================================

完善 autorepair/repair/orchestrator.py。

实现：

process_issue_for_repair(issue_number) -> RepairJob | None

流程：
1. 读取 Issue。
2. 找到或创建关联 Incident。
3. 收集 Evidence：
   - Issue body
   - Incident error_summary
   - raw_traceback
   - service config
   - target test command
4. 调用 Triage Agent。
   - 如果 Ark / Doubao 配置存在，调用真实 LLM。
   - 如果 LLM 不可用，允许规则 dry-run，但必须明确记录 mode=dry_run。
5. 运行 Policy Gate。
6. 如果结果为 need_info / human_required / high risk：
   - 评论 Issue 原因。
   - 状态标签改为 autorepair:human-required 或 autorepair:needs-info。
   - 发送 ManualInterventionCard。
   - 写 audit。
   - 不创建 RepairJob。
7. 如果结果为 auto_fix_candidate 且 policy passed：
   - 检查是否已有 active RepairJob。
   - 没有则创建 RepairJob，status=queued。
   - 标签改为 autorepair:accepted。
   - 发送 RepairPlanReadyCard。
   - 写 audit。

RepairJob active statuses：
- queued
- running
- pr_created

验收：
- 合理 Issue 能创建 queued RepairJob。
- 同一个 Issue 重复扫描不会重复创建 RepairJob。
- 不合理 Issue 不会创建 RepairJob。

============================================================
五、RepairJob Store 与并发控制
============================================================

完善 autorepair/repair/job_store.py、repo_lock.py。

RepairJob 字段至少包括：
- job_id
- incident_id
- issue_number
- repo_owner
- repo_name
- base_branch
- repair_branch
- worktree_path
- status
- created_at
- updated_at
- risk_level
- pr_number
- pr_url
- last_error

实现：
- create_repair_job
- load_repair_jobs
- update_repair_job
- find_active_job_by_issue
- find_active_job_by_incident
- find_next_queued_job

并发规则：
1. 同一个 Issue 只能有一个 active job。
2. 同一个 Incident 只能有一个 active job。
3. 同一个 repo 同一时间只有一个 running job。
4. 如果 repair_once.py 拿不到 repo lock：
   - job 保持 queued。
   - 输出 repo locked。
   - 不标记失败。

验收：
- 单测覆盖同一个 issue 不能重复创建 active job。
- 单测覆盖 repo lock 能阻止同 repo 并发 job。

============================================================
六、ticket-timezone-sla 自动修复执行
============================================================

新增或完善：

autorepair/adapters/ark.py
autorepair/repair/context_collector.py
autorepair/repair/patch_schema.py
autorepair/repair/patch_prompt.py
autorepair/repair/patch_applier.py
autorepair/repair/test_runner.py
autorepair/repair/executor.py
scripts/repair_once.py

Patch 方案：
1. repair_once.py 从 queued jobs 中取一个任务。
2. 获取 repo lock。
3. 创建 git worktree 和 repair branch。
4. 读取 worktree 中的：
   - demo_service/ticket_service.py
   - demo_service/tests/test_ticket_contract.py
   - demo_service/tests/test_ticket_success.py
5. 调用 Doubao 生成 JSON PatchPlan。
6. PatchPlan 只支持 replace：

{
  "summary": "...",
  "files": [
    {
      "path": "demo_service/ticket_service.py",
      "operation": "replace",
      "old": "...",
      "new": "..."
    }
  ],
  "tests_to_run": [
    "pytest -q demo_service/tests/test_ticket_contract.py::test_timezone_aware_sla_deadline_should_create_ticket -m agent_target",
    "pytest -q"
  ],
  "risk_level": "low",
  "confidence": 0.88
}

7. apply_patch_plan 只能修改 worktree 内文件。
8. 禁止修改：
   - .env
   - .git
   - credentials
   - secrets
9. old 文本必须唯一匹配，否则失败。
10. 测试命令只允许 pytest 开头。
11. 先运行目标测试，再运行 pytest -q。
12. 如果目标测试或全量测试失败：
    - job status=test_failed。
    - 评论 Issue。
    - 发送 ManualInterventionCard。
    - 不创建 PR。
13. 如果测试通过：
    - git commit
    - git push repair branch
    - create Pull Request
    - 更新 job status=pr_created
    - 写入 pr_number / pr_url
    - Issue 标签改为 autorepair:pr-ready
    - 评论 Issue
    - 发送 FixPrReadyCard

PR title：
[AutoRepair] Fix timezone-aware SLA deadline comparison

PR body 必须包含：
- Incident ID
- Related Issue
- Root Cause
- Fix Summary
- Tests
- Risk
- Audit Reference

验收：
- repair_once.py 能从 queued job 走到 pr_created。
- worktree 中目标测试通过。
- 主工作区不能被修改。
- PR 创建后飞书发送 FixPrReadyCard。
- 如果 GitHub 配置缺失，可 mock PR，但输出必须明确 mode=mock。

============================================================
七、PR 合并后关闭 Issue 和清理
============================================================

新增或完善：

scripts/sync_pr_status_once.py

逻辑：
1. 扫描 status=pr_created 的 RepairJob。
2. 查询 PR 状态。
3. 如果 PR merged：
   - 评论 Issue：修复已合并。
   - 关闭 Issue。
   - 标签改为 autorepair:closed。
   - 删除本地 worktree。
   - 删除本地修复分支。
   - 删除远端修复分支。
   - 更新 job status=closed。
   - 写 audit。
4. 如果 PR closed 但未 merged：
   - job status=human_required。
   - 评论 Issue。
   - 发送 ManualInterventionCard。
5. 如果 PR open：
   - 不处理。

安全规则：
- 只允许删除 autorepair/ 开头的分支。
- 禁止删除 main/master/develop。
- 删除失败记录 audit，不中断流程。

验收：
- mock merged PR 后 sync_pr_status_once.py 能关闭 Issue 并更新 job。
- 分支名不以 autorepair/ 开头时不得删除。

============================================================
八、Dashboard 补齐
============================================================

Dashboard 需要反映完整闭环状态。

请补齐：
1. /api/issues 返回真实或 mock Issue，包括 labels/status/issue_url。
2. /api/repair_jobs 返回 job_id/status/issue_number/pr_url/branch。
3. /api/prs 返回 open/merged/closed PR。
4. 操作按钮：
   - 扫描日志：调用完整 watch_once 链路。
   - 扫描 Issue：调用完整 issue validation + triage。
   - 执行修复：调用 repair_once。
   - 同步 PR：调用 sync_pr_status_once。
   - 发送摘要：发送 PeriodicDigestCard。
5. Dashboard 页面显示：
   - open issues 数。
   - queued/running/pr_created jobs。
   - pending review PR。
   - 最近一次链路状态。

验收：
- 点击 Dashboard 的“扫描日志”后能创建 Issue。
- 点击“扫描 Issue”后能创建 RepairJob。
- 点击“执行修复”后能创建 PR 或 mock PR。
- 点击“同步 PR”后能关闭 merged PR。

============================================================
九、演示前置检查脚本
============================================================

新增：

scripts/run_e2e_demo_check.py

检查：
1. Feishu ready / mock。
2. GitHub ready / mock。
3. Ark ready / mock。
4. 当前工作区是否干净。
5. demo service 是否可访问。
6. services.yaml 是否可读取。
7. template IDs 是否配置。
8. repo lock 是否可用。
9. 是否存在未清理 worktree。
10. ticket-timezone-sla 主线 Bug 是否能被正确触发为 ticket_service.py 的 TypeError。

输出 pass / warn / fail。

============================================================
十、测试要求
============================================================

pytest -q 必须通过。

至少新增测试：
1. Runtime incident 创建 Issue，并回写 issue_url。
2. 相同 fingerprint 不重复创建 Issue。
3. 信息不足 Issue 被标记 needs-info，不创建 RepairJob。
4. 合理 Issue 创建 queued RepairJob。
5. 同一 Issue 不重复创建 active RepairJob。
6. repo_lock 防止并发修复同一 repo。
7. PatchPlan schema 校验。
8. patch_applier 禁止修改 .env。
9. patch_applier old 不存在或多次出现会失败。
10. test_runner 只允许 pytest 命令。
11. repair_once 在 mock Ark + mock GitHub 下能 queued → pr_created。
12. 测试失败时不创建 PR，发送人工介入卡。
13. sync_pr_status_once merged 后关闭 Issue、更新 job、清理 worktree。
14. Dashboard API 操作按钮调用正确链路。
15. 外部 API 测试全部 monkeypatch，不真实请求网络。

============================================================
十一、文档更新
============================================================

更新 README 和 technical-whitepaper.md。

必须明确：
1. 当前系统已完成 ticket-timezone-sla 单场景端到端闭环。
2. 触发 Runtime Bug 不会立即修复，只会创建 / 更新 Issue。
3. 修复由 Issue + RepairJob 队列驱动。
4. worktree + repo lock 防止并发修改。
5. PR 需要人工 Review，不自动 merge。
6. PR 合并后由 sync_pr_status_once 关闭 Issue 和清理分支。
7. 手动 Issue 会先进行合理性检查，不合理会评论 needs-info。
8. 其他复杂 Bug 暂作为后续扩展或人工介入场景。

============================================================
十二、输出要求
============================================================

完成后输出：
1. 新增/修改文件列表。
2. 端到端链路图。
3. pytest -q 结果。
4. ticket-timezone-sla 演示步骤。
5. watch_once 示例输出。
6. watch_github_issues_once 示例输出。
7. repair_once 示例输出。
8. 生成的 Issue URL、RepairJob ID、分支名、PR URL。
9. 飞书发送的卡片类型。
10. Dashboard 上能看到哪些状态。
11. 明确说明：
    - 不自动 merge。
    - 不直接修改 main/master。
    - 不会每次 Bug 触发都并发修复。
    - 同一 Issue 不会重复创建 RepairJob。
    - 测试失败不会创建 PR。