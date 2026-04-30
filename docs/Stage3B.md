你现在继续开发 FeishuAutoRepair 项目。

当前项目状态：
1. Demo 服务 Acme SupportDesk Lite 已完成，能够触发多个预埋 Bug。
2. 其中主线 Bug 为 ticket-timezone-sla：
   - 带 +08:00 SLA 的工单会触发 TypeError
   - 错误原因是 timezone-aware datetime 与 naive datetime 直接比较
3. watcher 已支持日志扫描、Incident 创建、fingerprint 去重、occurrence_count 聚合。
4. GitHub Issue adapter 已支持 Issue、label、comment、PR 的基础能力或 mock 能力。
5. 飞书卡片系统已完成 5 张轻量模板卡，能够发送 IncidentDetectedCard、RepairPlanReadyCard、FixPrReadyCard、ManualInterventionCard。
6. triage 模块已包含 decision_schema、policy_gate、report_writer、triage_prompt、triage_agent、evidence_collector。
7. repair 模块已有 job_store、repo_lock、git_workspace、orchestrator 的基础设计。
8. 当前缺口是：LLM 真实生成 patch、在 worktree 中应用 patch、运行测试、commit/push、创建 PR、发送 PR 待 Review 卡片。

本阶段名称：
Stage 3B：Single-Bug Auto Repair PR Loop

本阶段目标：
只针对 ticket-timezone-sla 这一条主线 Bug，打通完整自动修复闭环：

Runtime Bug
→ Incident
→ GitHub Issue
→ Triage
→ RepairJob
→ git worktree
→ Doubao 生成 patch
→ 应用 patch
→ pytest 验证
→ commit + push
→ 创建 PR
→ 飞书发送 PR 待 Review 卡

重要约束：
- 只要求稳定修复 ticket-timezone-sla，不要求一次修复所有 Bug。
- 不要自动 merge PR。
- 不要直接修改 main/master。
- 所有代码修改必须在 git worktree 中进行。
- 同一个 repo 同时只能有一个 running repair job。
- 同一个 issue / incident 如果已有 active job 或 open PR，不得重复创建。
- LLM 输出必须是 JSON，不接受自然语言 patch。
- Patch 必须经过测试验证才能 commit。
- 测试失败不得创建 PR。
- 所有关键动作必须写 audit event。
- pytest -q 必须通过。
- pytest -q -m agent_target 中非主线 Bug 仍可失败，但 ticket-timezone-sla 目标测试应在 worktree 中通过。

============================================================
一、Ark / Doubao Client
============================================================

新增或完善：

autorepair/adapters/ark.py

实现：

class ArkClient:
    def chat_json(self, messages: list[dict], model: str | None = None, temperature: float = 0.1) -> dict:
        ...

要求：
1. 读取环境变量：
   - ARK_API_KEY
   - ARK_BASE_URL
   - ARK_MODEL_REPAIR
2. 不要打印 API Key。
3. 请求失败时抛出清晰异常。
4. 返回必须是 dict。
5. 如果模型返回 markdown 代码块，尝试提取 JSON。
6. 测试中必须 monkeypatch，不真实调用 Ark。

如果当前已有 ArkClient，请按以上要求补齐即可。

============================================================
二、Repair Context 收集
============================================================

新增：

autorepair/repair/context_collector.py

实现：

collect_repair_context(job: RepairJob, incident: Incident, worktree_path: str) -> RepairContext

RepairContext 字段：
- incident_id
- issue_number
- service_name
- error_type
- error_message
- suspected_file
- line_no
- raw_traceback
- target_test_command
- full_test_command
- code_snippets
- existing_tests

收集逻辑：
1. 根据 incident.error_summary.suspected_file 在 worktree 中读取相关文件。
2. 读取错误行前后 50 行。
3. 对 ticket-timezone-sla，额外读取：
   - demo_service/ticket_service.py
   - demo_service/tests/test_ticket_contract.py
   - demo_service/tests/test_ticket_success.py
4. 不读取 .env、密钥、.git 目录。
5. 如果文件不存在，记录 warning，不崩溃。

============================================================
三、Patch Schema
============================================================

新增：

autorepair/repair/patch_schema.py

定义：

class FilePatch(BaseModel):
    path: str
    operation: Literal["replace"]
    old: str
    new: str

class PatchPlan(BaseModel):
    summary: str
    files: list[FilePatch]
    tests_to_run: list[str]
    risk_level: Literal["low", "medium", "high"]
    confidence: float

约束：
- path 不允许包含 .env、.git、secrets、credentials。
- operation 本阶段只支持 replace。
- old 和 new 都不能为空。
- files 数量建议 1~3 个。
- confidence 必须 0~1。

============================================================
四、Patch Prompt
============================================================

新增：

autorepair/repair/patch_prompt.py

实现：

build_patch_prompt(context: RepairContext) -> list[dict]

Prompt 要求：
1. 你是谨慎的代码修复 Agent。
2. 只修复 ticket-timezone-sla 相关问题。
3. 不要修改无关文件。
4. 不要放宽测试。
5. 不要删除现有测试。
6. 不要读取或修改密钥文件。
7. 输出必须是 JSON，严格匹配 PatchPlan。
8. 只能使用 replace patch：
   - old 必须是原文件中存在的连续文本
   - new 是替换后的文本
9. 必须包含测试命令。
10. 对 SLA timezone bug，优先策略：
   - 使用 datetime.now(timezone.utc)
   - 将 fromisoformat 得到的 deadline 统一转成 timezone-aware UTC
   - naive deadline 可补 timezone.utc
   - aware deadline 用 astimezone(timezone.utc)

输出 JSON 示例：
{
  "summary": "Normalize SLA deadline and current time to timezone-aware UTC before comparison.",
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

============================================================
五、Patch 应用器
============================================================

新增：

autorepair/repair/patch_applier.py

实现：

apply_patch_plan(patch_plan: PatchPlan, worktree_path: str) -> PatchApplyResult

逻辑：
1. 遍历 files。
2. 校验 path 安全：
   - 必须在 worktree_path 内
   - 禁止 .env、.git、credentials、secret
3. 读取文件。
4. 查找 old 文本。
5. 如果 old 出现 0 次，失败。
6. 如果 old 出现多次，失败，避免误改。
7. 替换为 new。
8. 写回文件。
9. 返回修改文件列表。

PatchApplyResult：
- ok: bool
- changed_files: list[str]
- error: str | None

测试覆盖：
- 成功 replace
- old 不存在失败
- old 出现多次失败
- 禁止修改 .env
- 禁止越界路径

============================================================
六、测试运行器
============================================================

新增：

autorepair/repair/test_runner.py

实现：

run_command_in_worktree(command: str, worktree_path: str, timeout: int = 120) -> CommandResult

CommandResult：
- command
- returncode
- stdout
- stderr
- duration_seconds

要求：
1. 在 worktree_path 下执行。
2. 捕获 stdout/stderr。
3. 超时返回失败。
4. Windows 兼容。
5. 不执行来自 GitHub Issue 的任意命令，只执行 PatchPlan 或服务配置中允许的 pytest 命令。
6. 对 tests_to_run 做 allowlist：
   - 只允许 pytest 开头
   - 或允许配置中的 test_command / agent_target_test_command

============================================================
七、Git Commit / Push / PR
============================================================

完善 github adapter 和 git_workspace。

实现或确认：

git_commit_all(worktree_path, message) -> commit_sha
git_push_branch(worktree_path, branch) -> None
create_pull_request(title, body, head, base) -> PullRequestRef
find_open_pr_for_branch(branch) -> PullRequestRef | None

规则：
1. 如果没有文件变化，不 commit，不 PR。
2. commit message 格式：
   fix: normalize SLA deadline timezone comparison

   Incident: INC-xxx
   Issue: #123
   Test: pytest -q ...
3. PR title：
   [AutoRepair] Fix timezone-aware SLA deadline comparison
4. PR body 包含：
   - Incident ID
   - Related Issue
   - Root Cause
   - Fix Summary
   - Tests
   - Risk
   - Audit Reference
5. 如果同一 branch 已有 open PR，复用，不重复创建。
6. 不自动 merge。

============================================================
八、Repair Worker
============================================================

修改或新增：

scripts/repair_once.py
autorepair/repair/executor.py

实现：

execute_next_repair_job() -> RepairExecutionResult

流程：
1. 从 repair_jobs.jsonl 找到最早 queued job。
2. 检查同 issue / incident 是否已有 pr_created。
3. 获取 repo lock。
4. 创建 worktree 和 repair branch。
5. 更新 job status=running。
6. collect_repair_context。
7. 调 ArkClient 生成 PatchPlan。
8. 校验 PatchPlan。
9. apply_patch_plan。
10. 运行目标测试：
    - ticket-timezone-sla 的目标测试
11. 如果目标测试失败：
    - 允许最多 1 次 retry：
      将测试失败输出追加给 LLM，请求修正 PatchPlan。
    - 仍失败则 job status=test_failed。
    - 评论 Issue。
    - 发送 ManualInterventionCard。
    - 不创建 PR。
12. 目标测试通过后，运行 pytest -q。
13. 全部测试通过后：
    - commit
    - push branch
    - create PR
    - 更新 job status=pr_created
    - 写 pr_number/pr_url
    - 给 Issue 打 autorepair:pr-ready
    - 评论 Issue
    - 发送 FixPrReadyCard
14. 释放 repo lock。

注意：
- 如果真实 GitHub 配置缺失，可以 mock PR，但输出必须明确 mode=mock。
- 真实演示建议使用真实 GitHub。
- 不要在主工作区改代码。

============================================================
九、Issue / Job 串联
============================================================

确认以下脚本能顺序跑通：

1. python scripts/reset_demo_state.py
2. 启动 demo server
3. 浏览器触发 SLA timezone bug
4. python scripts/watch_once.py
   - 创建 Incident
   - 创建/关联 GitHub Issue
   - 发送 IncidentDetectedCard
5. python scripts/watch_github_issues_once.py
   - 验证 Issue
   - triage
   - policy gate
   - 创建 RepairJob queued
   - 发送 RepairPlanReadyCard
6. python scripts/repair_once.py
   - 创建 worktree
   - Doubao 生成 patch
   - 应用 patch
   - 运行测试
   - 创建 PR
   - 发送 FixPrReadyCard

如果当前 watch_github_issues_once.py 已经做了部分逻辑，请不要重复实现，只补齐缺失的串联。

============================================================
十、同步 PR 合并状态
============================================================

如果已有 sync_pr_status_once.py，请补齐；没有则新增。

scripts/sync_pr_status_once.py：

1. 扫描 pr_created 状态的 RepairJob。
2. 查询 PR 状态。
3. 如果 merged：
   - 评论 Issue：修复已合并
   - 关闭 Issue
   - 打 autorepair:closed
   - 清理 worktree
   - 删除本地 branch
   - 删除远端 autorepair/ 开头的 branch
   - 更新 job status=closed
   - 写 audit
4. 如果 closed 但未 merged：
   - job status=human_required
   - 评论 Issue
   - 发送 ManualInterventionCard
5. 如果 open：
   - 不处理

安全规则：
- 只允许删除 autorepair/ 开头的分支。
- 禁止删除 main/master/develop。
- 删除失败记录 audit，不中断。

============================================================
十一、测试要求
============================================================

新增测试，pytest -q 必须通过。

至少覆盖：

1. ArkClient.chat_json 能解析 monkeypatch 返回 JSON。
2. PatchPlan schema 校验。
3. patch_applier 成功替换。
4. patch_applier old 不存在失败。
5. patch_applier old 多次出现失败。
6. patch_applier 禁止修改 .env。
7. test_runner 只允许 pytest 命令。
8. execute_next_repair_job 在 mock Ark + mock GitHub 下能：
   - queued → running → pr_created
   - 写入 pr_url
   - 发送 FixPrReadyCard
9. 测试失败时：
   - job status=test_failed
   - 不创建 PR
   - 发送 ManualInterventionCard
10. 同一个 issue 已有 active job 时不重复创建。
11. repo lock 生效。
12. sync_pr_status_once merged 后关闭 issue 并清理 worktree。
13. 所有外部 API 在测试中 monkeypatch，不真实请求网络。

============================================================
十二、README / 白皮书更新
============================================================

更新 README 和 technical-whitepaper.md。

明确标注：
1. 当前已打通 ticket-timezone-sla 单 Bug 自动修复闭环。
2. 其他 Bug 场景仍作为后续扩展。
3. 修复不会在每次日志触发时立即执行。
4. 运行时异常先转 Issue。
5. 修复由 RepairJob 队列驱动。
6. worktree + repo lock 防止并发修改。
7. PR 需要人工 Review，不自动 merge。
8. PR 合并后由 sync_pr_status_once 关闭 Issue 和清理分支。

============================================================
十三、输出要求
============================================================

完成后输出：

1. 新增/修改文件列表。
2. 完整链路状态机说明。
3. pytest -q 结果。
4. ticket-timezone-sla 的端到端演示步骤。
5. watch_once.py 示例输出。
6. watch_github_issues_once.py 示例输出。
7. repair_once.py 示例输出。
8. 创建的分支名、PR 标题、PR URL。
9. 飞书发送的卡片类型。
10. 明确说明：
   - 没有自动 merge
   - 没有直接修改 main/master
   - 所有修改都发生在 worktree
   - 同一 repo 有 repo lock
   - 同一 issue 不重复创建 repair job