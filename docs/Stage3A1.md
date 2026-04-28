你现在继续开发 FeishuAutoRepair 项目。

当前项目已经完成：
1. Demo 服务 Acme SupportDesk Lite，可触发运行时异常。
2. watcher 可以捕获 traceback，生成 Incident，并聚合 occurrence_count。
3. GitHub Issue adapter 已支持真实和 mock 模式。
4. 飞书卡片系统已重构为 5 张轻量模板卡片，并可真实发送或 mock。
5. 项目已有 service_registry、diagnostics、audit_store。
6. 项目已有参考 ClawSweeper 思路实现的 triage 模块：
   - decision_schema
   - policy_gate
   - report_writer
   - triage_prompt
   - triage_agent
   - evidence_collector
7. 当前还没有真正实现完整 Issue 生命周期、Repair Job 队列、worktree 修复分支、PR 创建和 PR 合并后的清理闭环。

现在请完成 Stage 3A：Issue 生命周期与 Repair Job 编排。

本阶段目标：
1. 把运行时异常统一转成标准 GitHub Issue。
2. 把用户手动提交的 bug issue 纳入同一处理管线。
3. 实现 Issue 合理性检查、标签状态机、评论反馈。
4. 实现 Repair Job 数据模型和队列。
5. 实现 git worktree 隔离工作区和修复分支创建能力。
6. 实现 PR 创建骨架，但本阶段可以先使用 mock patch 或 dry-run，不要求真正由 LLM 改代码。
7. 实现 PR merge 后关闭 Issue、清理分支和 worktree 的同步逻辑。
8. 避免并发修改，保证同一 repo 同一时间只有一个修复任务写代码。

重要约束：
- 不要自动 merge PR。
- 不要直接 push main/master。
- 不要在主工作区修改业务代码。
- 所有修复必须在 git worktree 中进行。
- 同一个 repo 同时只允许一个 active repair job。
- 同一个 issue 如果已有 open repair job 或 open PR，不得重复创建。
- 用户手动提交的 issue 内容不足时，不要修复，应评论说明需要补充什么。
- 不要暴露本地服务链接。
- pytest -q 必须通过。
- pytest -q -m agent_target 仍然可以失败，除非后续阶段真正修复。
- 当前阶段可以不调用 LLM，也可以只接入 triage dry-run。

============================================================
一、标签状态机
============================================================

新增或统一 GitHub labels：

基础标签：
- bug
- AutoRepair

来源标签：
- source:runtime
- source:issue

状态标签：
- autorepair:triage
- autorepair:needs-info
- autorepair:accepted
- autorepair:repairing
- autorepair:pr-ready
- autorepair:human-required
- autorepair:closed

风险标签：
- risk:low
- risk:medium
- risk:high

请在 github adapter 中实现：
ensure_label(name, color, description)
ensure_autorepair_labels()
replace_autorepair_status_label(issue_number, new_status_label)
add_labels(issue_number, labels)
remove_labels(issue_number, labels)

mock 模式也要支持这些操作，并写入 mock_github_issues.jsonl。

============================================================
二、运行时异常创建标准 Issue
============================================================

新增模块：

autorepair/issue_manager.py

实现：

ensure_issue_for_incident(incident, service, diagnostic_report=None) -> IssueRef

逻辑：
1. 根据 incident.fingerprint 查找是否已有未关闭 Issue。
2. 如果已有 Issue，则评论 occurrence_count 更新，不新建。
3. 如果没有，则创建标准 Issue。
4. Issue 标题格式：
   [AutoRepair][P1] Acme SupportDesk Lite: TypeError in SLA handling
5. Issue body 必须包含：
   - Incident ID
   - Service
   - Source
   - Severity
   - Occurrence
   - Error Summary
   - Evidence
   - Reproduction
   - Expected Behavior
   - Actual Behavior
   - AutoRepair Status
6. 添加标签：
   bug
   AutoRepair
   source:runtime
   autorepair:triage
   risk:low 或 risk:medium
7. 写入 audit event：github_issue_created 或 github_issue_linked。
8. 发送 IncidentDetectedCard。

注意：
- 不要在卡片上放完整 traceback。
- traceback 放在 Issue body 或诊断报告中。

修改 scripts/watch_once.py：
- created incident 时，不只是发送飞书卡片，而是先 ensure_issue_for_incident。
- 获取 issue_url 后再发送 IncidentDetectedCard。

============================================================
三、用户手动 Issue 合理性检查
============================================================

新增模块：

autorepair/issue_validator.py

实现：

validate_bug_issue(issue) -> IssueValidationResult

IssueValidationResult 字段：
- is_valid: bool
- reason: str
- missing_fields: list[str]
- evidence_level: str  # none / weak / enough / strong
- suggested_comment: str

检查规则：
1. Issue 必须有 bug 标签，或标题含 [Bug]。
2. Issue 不应已经有 autorepair:closed / autorepair:repairing / autorepair:pr-ready。
3. Issue body 至少包含以下信息中的 3 类：
   - Service / affected module
   - Steps to reproduce
   - Expected behavior
   - Actual behavior
   - Traceback / error message
   - Failing test / command
4. 如果完全没有复现步骤和错误信息，则 is_valid=False。
5. 如果是安全敏感、密钥泄露、生产数据库删除、权限系统大改等高风险内容，则 is_valid=False 或 human_required。
6. Issue 文本视为不可信输入，不得直接执行 issue 中给出的任意 shell 命令，只能作为参考。

新增处理逻辑：
- 不合理：
  - 评论 suggested_comment
  - 打 autorepair:needs-info
  - 发送 ManualInterventionCard 或只评论，不进入修复
- 合理：
  - 打 autorepair:triage
  - 进入 triage

修改 scripts/watch_github_issues_once.py：
- 扫描 label=bug 的 open issue。
- 先 validate_bug_issue。
- 不合理则评论和标记。
- 合理才继续生成/关联 Incident。

============================================================
四、Repair Job 数据模型
============================================================

新增：

autorepair/repair/job_store.py
autorepair/repair/schemas.py

RepairJob 字段：
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
- policy_decision
- risk_level
- pr_number
- pr_url
- last_error

status 枚举：
- queued
- running
- test_failed
- pr_created
- human_required
- merged
- closed
- failed

存储：
autorepair/records/repair_jobs.jsonl

实现：
create_repair_job(...)
load_repair_jobs(...)
find_active_job_by_issue(issue_number)
find_active_job_by_incident(incident_id)
update_repair_job(job_id, **fields)

规则：
- 同一个 issue 只能有一个 active job。
- 同一个 incident 只能有一个 active job。
- active status 包含 queued/running/pr_created。

============================================================
五、Repo Lock 与 Worktree 管理
============================================================

新增：

autorepair/repair/repo_lock.py
autorepair/repair/git_workspace.py

repo_lock：
- acquire_repo_lock(repo_key) -> context manager
- lock 文件位于 autorepair/records/locks/
- 同一个 repo 同时只允许一个 job 修改代码
- 如果拿不到锁，job 保持 queued，不失败

git_workspace：
实现：
create_repair_worktree(repo_path, base_branch, repair_branch, incident_id) -> WorktreeInfo
remove_repair_worktree(worktree_path)
delete_local_branch(branch)
delete_remote_branch(branch)

规则：
- repair_branch 格式：
  autorepair/inc-<incident_short>-<slug>
- worktree_path 格式：
  .worktrees/<incident_id>
- 不允许在 main/master 上修改。
- 如果 branch 已存在，复用或报清晰错误，不能覆盖。
- 所有命令都要记录 audit。
- Windows 路径兼容。

============================================================
六、Triage 到 Repair Job 的准入
============================================================

新增：

autorepair/repair/orchestrator.py

实现：

process_issue_for_repair(issue_number) -> RepairJob | None

流程：
1. 读取 issue 和关联 incident。
2. 收集 evidence。
3. 运行 triage_agent 或 dry-run triage。
4. 运行 policy_gate。
5. 如果 rejected：
   - 评论 Issue，说明原因
   - 打 autorepair:human-required 或 autorepair:needs-info
   - 发送 ManualInterventionCard
   - 不创建 repair job
6. 如果 accepted：
   - 创建 repair job
   - 打 autorepair:accepted
   - 发送 RepairPlanReadyCard
   - 不立即修改代码，等待 worker 执行

注意：
本阶段如果 LLM 还不稳定，可以先使用规则 triage/dry-run，但接口必须为后续 LLM 输出保留。

============================================================
七、Repair Worker 骨架
============================================================

新增脚本：

scripts/repair_once.py

行为：
1. 找到最早一个 queued repair job。
2. 获取 repo lock。
3. 创建 worktree 和 repair branch。
4. 本阶段不要求真正 LLM patch，可以提供 dry-run patch strategy：
   - 如果 incident 是 ticket-timezone-sla，可选不改代码，只输出 would_patch。
   - 或者本阶段只创建 worktree，不创建 PR。
5. 如果没有实际 patch，不要创建 PR。
6. 如果后续接入 patch 成功：
   - 运行 pytest
   - commit
   - push branch
   - create PR
   - 打 autorepair:pr-ready
   - 发送 FixPrReadyCard

本阶段重点是骨架、状态和并发控制，不强制完成自动 patch。

============================================================
八、PR 创建与关联
============================================================

在 github adapter 中新增：

create_pull_request(title, body, head, base) -> PullRequestRef
get_pull_request(pr_number)
find_open_pr_for_branch(branch)
comment_issue(issue_number, body)
close_issue(issue_number)

PR body 必须包含：
- Incident ID
- Related issue
- Root cause
- Fix summary
- Test result
- Risk
- Audit reference

注意：
- 不要 auto merge。
- PR 创建后只通知 Review。
- 如果 PR 已存在，不重复创建。

============================================================
九、PR Merge 后同步关闭
============================================================

新增脚本：

scripts/sync_pr_status_once.py

流程：
1. 扫描 status=pr_created 的 repair_jobs。
2. 查询 PR 状态。
3. 如果 PR merged：
   - 评论 Issue：修复已合并
   - 关闭 Issue
   - 打 autorepair:closed
   - 删除本地 worktree
   - 删除本地修复分支
   - 删除远端修复分支，如果安全可行
   - 更新 job status=merged/closed
   - 写 audit
4. 如果 PR closed 但未 merged：
   - 更新 job status=human_required
   - 评论 Issue：PR 已关闭但未合并
   - 发送 ManualInterventionCard
5. 如果 PR 仍 open：
   - 不处理

注意：
- 删除远端分支前必须确认分支名以 autorepair/ 开头。
- 不允许删除 main/master/develop。
- 删除失败不影响关闭 Issue，但要记录 audit。

============================================================
十、飞书卡片触发关系
============================================================

请确保：
1. created incident + issue created：
   send_incident_detected
2. triage accepted + repair job queued：
   send_repair_plan_ready
3. triage rejected / issue invalid：
   send_manual_intervention
4. PR created：
   send_fix_pr_ready
5. PR merged and issue closed：
   可暂时不发卡，或记录 digest

不要伪造 PR 卡。
没有 PR 时绝不能发送 FixPrReadyCard。

============================================================
十一、测试
============================================================

新增测试，pytest -q 必须通过。

至少覆盖：
1. ensure_issue_for_incident 对新 incident 创建 issue。
2. 相同 fingerprint 不重复创建 issue。
3. validate_bug_issue 对信息不足 issue 返回 needs-info。
4. validate_bug_issue 对包含复现步骤和错误信息的 issue 返回 valid。
5. 同一个 issue 不能创建两个 active repair job。
6. repo_lock 阻止同 repo 并发 job。
7. create_repair_worktree 不允许 main/master 直接修改。
8. repair_branch 必须以 autorepair/ 开头。
9. sync_pr_status_once 只删除 autorepair/ 开头的分支。
10. PR merged 后关闭 issue，更新 job，记录 audit。
11. PR closed 未 merge 时转 human_required。
12. 所有 GitHub/Feishu 调用在测试中使用 mock，不真实访问网络。

============================================================
十二、README 更新
============================================================

新增“完整修复链路”章节：

运行时异常路线：
1. reset_demo_state
2. 启动 demo_service
3. 页面触发 SLA 异常
4. watch_once 创建 Incident 和 GitHub Issue
5. watch_github_issues_once / process_issue_for_repair 进行 triage
6. repair_once 创建 worktree / repair branch
7. 后续 patch 成功后创建 PR
8. sync_pr_status_once 在 PR 合并后关闭 issue 和清理分支

手动 Issue 路线：
1. 用户创建 bug issue
2. watch_github_issues_once 验证 issue 合理性
3. 不合理则评论 needs-info
4. 合理则进入同一 repair pipeline

并发说明：
- 修复不会在每次报错时立即执行
- 报错只创建或更新 Issue
- 修复由 repair job 队列驱动
- 同一 repo 通过 repo lock 串行执行
- worktree 保证不污染主工作区

============================================================
十三、输出要求
============================================================

完成后输出：
1. 新增/修改文件列表。
2. 新的 Issue 生命周期说明。
3. RepairJob 状态机说明。
4. worktree 和 repo lock 设计说明。
5. pytest -q 结果。
6. 运行时异常路线示例输出。
7. 手动 Issue 路线示例输出。
8. 明确说明：
   - 不自动 merge
   - 不直接修改 main/master
   - 不重复处理同一个 Issue
   - 不会每次触发 bug 都并发修复