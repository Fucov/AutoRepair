# 2. AutoRepair 完整链路应该怎么设计？

我建议你把系统拆成两个入口、一个统一状态机。

## 入口 A：运行时异常入口

```text
服务运行中报错
→ log watcher 捕获 traceback
→ 生成 Incident
→ 去重聚合 fingerprint
→ 若是新问题，创建 GitHub Issue
→ 打标签 bug + AutoRepair + source:runtime
→ 发飞书 IncidentDetectedCard
→ 进入 Issue 扫描 / Triage 阶段
```

这里有个关键点：**运行时异常不要直接修代码**。
运行时异常只负责把问题标准化成 Issue / Incident。真正修复应该交给后续的 Issue 处理流程，这样本地报错和用户手动提交 Issue 可以走同一条修复管线。

---

## 入口 B：用户手动提交 Issue

```text
用户在 GitHub 手动提交 bug issue
→ issue watcher 定时扫描
→ 只处理 label=bug 或 AutoRepair 相关 issue
→ 检查 issue 内容是否完整
→ 不完整则评论原因，打 needs-info 标签
→ 完整则进入 Triage
```

这样你就覆盖了官方说的“bug 提交可以自己模拟，看能做到什么程度”。

---

# 3. 统一状态机

建议所有 bug 都进入同一个生命周期：

```text
RAW_EVENT
→ INCIDENT_CREATED
→ ISSUE_CREATED / ISSUE_LINKED
→ TRIAGE_PENDING
→ TRIAGE_RUNNING
→ NEEDS_INFO / HUMAN_REQUIRED / ACCEPTED
→ REPRODUCING
→ REPAIR_QUEUED
→ REPAIR_RUNNING
→ TESTING
→ PR_READY
→ REVIEWING
→ MERGED
→ CLOSED
→ CLEANED
```

对应标签可以设计成：

```text
bug
AutoRepair

autorepair:triage
autorepair:needs-info
autorepair:accepted
autorepair:repairing
autorepair:pr-ready
autorepair:human-required
autorepair:merged
autorepair:closed

source:runtime
source:issue
risk:low
risk:medium
risk:high
```

标签非常重要，因为它避免重复处理同一个 Issue，也能让演示更有工程感。

---

# 4. 修复代码的时机到底是什么？

不要“每次触发 bug 就立即修”。

也不要“每个 Issue 一出现就立即修”。

正确时机是：

```text
只有当 Issue/Incident 通过 Triage 和 Policy Gate，并且拿到仓库锁之后，才创建 Repair Job 开始修复。
```

更具体：

```text
1. 新 traceback 出现：
   只创建/更新 Incident 和 Issue，不直接修。

2. Issue 被扫描到：
   先检查是否合理、是否重复、是否有足够证据。

3. Triage 判断：
   只有 classification 合理、fixability=auto_fix_candidate、risk<=medium、confidence 足够，才进入修复队列。

4. Repair Worker 获取 repo lock：
   只有拿到对应仓库的锁，才允许创建 worktree 和分支。

5. 修复完成后：
   创建 PR，通知用户 Review。

6. PR 合并后：
   关闭 Issue，删除远端修复分支，删除本地 worktree。
```

这可以避免并发修改。

---

# 5. 并发怎么处理？

必须用 `git worktree`，但只用 worktree 还不够。你还需要 **repo-level lock**。

建议规则：

```text
同一个 repo 同一时间只允许 1 个 Repair Job 写代码。
不同 repo 可以并发。
同一个 incident 只能有 1 个 active repair job。
同一个 issue 如果已有 open PR，不再创建新 PR。
```

实现上可以很简单，用本地文件锁：

```text
autorepair/records/locks/repo_<hash>.lock
```

或者记录在 `repair_jobs.jsonl` 里：

```json
{
  "job_id": "JOB-xxx",
  "incident_id": "INC-xxx",
  "issue_number": 12,
  "repo": "owner/repo",
  "status": "running",
  "branch": "autorepair/inc-xxx",
  "worktree_path": ".worktrees/inc-xxx"
}
```

不要搞复杂队列。初赛本地部署，用 JSONL + 文件锁就够。

---

# 6. 自动修复的具体链路

## 运行时异常链路

```text
用户在 Demo 服务中触发异常
→ app.log 写入 traceback
→ watch_once 扫描到新 fingerprint
→ 创建 Incident
→ 如果该 fingerprint 没有 open issue：
    创建 GitHub Issue
    标签：bug, AutoRepair, source:runtime, autorepair:triage
    Issue body 附带 traceback 摘要、错误位置、复现方式、服务配置、审计引用
→ 发送飞书故障发现卡
→ issue_worker 扫描该 Issue
→ triage_agent 收集证据
→ policy_gate 判断是否允许自动修复
→ 可修复：
    评论 Issue：已通过自动修复准入
    打标签 autorepair:accepted
    创建 Repair Job
→ 不可修复：
    评论 Issue：原因和需要补充的信息
    打标签 autorepair:human-required 或 autorepair:needs-info
    发送人工介入卡
```

---

## 手动 Issue 链路

```text
用户手动提交 Issue，打 bug 标签
→ issue_worker 扫描
→ 解析 title/body/labels
→ 检查是否已有 AutoRepair 状态标签
→ 检查内容完整性：
    是否有服务名
    是否有复现步骤
    是否有期望行为
    是否有实际行为
    是否有 traceback / 测试失败 / 明确现象
→ 内容不足：
    评论：请补充复现步骤 / 日志 / 期望行为
    打 autorepair:needs-info
    不修复
→ 内容充分：
    打 autorepair:triage
    进入 triage
→ 后续和运行时异常完全一致
```

---

# 7. Issue 应该怎么创建？

运行时异常自动创建的 Issue 要标准化，不要只是贴 traceback。

建议 body：

```md
## AutoRepair Incident

Incident ID: INC-20260426-0001  
Service: Acme SupportDesk Lite  
Source: runtime log watcher  
Severity: P1  
Occurrence: 6 times in last 10 minutes  

## Error Summary

TypeError: SLA deadline comparison failed between timezone-aware and naive datetime

Suspected file:
demo_service/ticket_service.py

## Evidence

- Traceback captured from demo_service/logs/app.log
- Healthcheck: passed
- Repo check: passed
- Classification: runtime_exception
- Fixability: auto_fix_candidate

## Reproduction

1. Open Acme SupportDesk Lite
2. Create a P1 Feishu channel ticket with timezone-aware SLA deadline
3. Service returns 500 and writes traceback

## Expected Behavior

Ticket should be created successfully after normalizing SLA deadline time.

## Actual Behavior

Service raises TypeError due to comparing timezone-aware and naive datetime.

## AutoRepair Status

Current status: triage_pending

Audit report:
<report path or URL>
```

标签：

```text
bug
AutoRepair
source:runtime
autorepair:triage
risk:low
```

---

# 8. PR 应该怎么创建？

分支名：

```text
autorepair/inc-20260426-0001-timezone-sla
```

PR 标题：

```text
[AutoRepair] Fix timezone-aware SLA deadline comparison
```

PR body：

```md
## Incident

Fixes or relates to #123  
Incident: INC-20260426-0001

## Root Cause

SLA deadline is parsed as timezone-aware datetime, while current time is generated as naive UTC datetime. Python does not allow comparing aware and naive datetimes.

## Fix

Normalize both values to timezone-aware UTC before comparison.

## Verification

- pytest -q
- pytest -q -m agent_target
- specific test: test_timezone_aware_sla_deadline_should_create_ticket

## Risk

Low. Change is limited to SLA deadline normalization.

## AutoRepair Audit

- Triage decision: auto_fix_candidate
- Policy gate: allowed
- Worktree: .worktrees/INC-20260426-0001
```

是否写 `Fixes #123`？

如果你想 PR 合并后 GitHub 自动关闭 Issue，可以写 `Fixes #123`。
如果你想人工控制关闭，就写 `Related to #123`，然后 merge 后由脚本关闭。初赛演示建议用 `Related to #123`，因为更安全。

---

# 9. PR Review 后如何关闭 Issue 和清理分支？

你不能假设用户一定会点飞书按钮。更稳的是写一个 `sync_pr_status_once.py`：

```text
扫描 autorepair:pr-ready 的 Issue
→ 找到关联 PR
→ 检查 PR 是否 merged
→ 如果 merged：
    评论 Issue：修复已合并
    关闭 Issue
    打 autorepair:closed
    删除远端分支
    删除本地 worktree
    发送闭环卡 / 更新摘要
→ 如果 PR closed 但未 merged：
    评论 Issue：PR 被关闭，需人工处理
    打 autorepair:human-required
```

这样你不需要飞书回调，也不需要暴露本地服务。

---

