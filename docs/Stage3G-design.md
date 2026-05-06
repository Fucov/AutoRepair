# Stage 3G 设计文档：Spec-Guided Repair Agent

**日期**: 2026-05-06
**状态**: 待审批
**方案选择**: 渐进增强法（在现有 MiniRepairAgent 上叠加五层增强）

---

## 1. 架构总览

```
executor.py
  ├─ collect_repair_context (existing)
  ├─ build_repair_case (NEW)         → RepairCase
  ├─ build_repair_spec (NEW)         → RepairSpec
  ├─ select_repair_skills (NEW)      → list[RepairSkill]
  ├─ build_validation_plan (NEW)     → ValidationPlan
  ├─ collect_history_context (NEW)   → HistoryContext
  ├─ try_apply_known_playbook (enhanced)
  │   ├─ Skill-backed matching
  │   └─ ValidationPlan verification
  └─ MiniRepairAgent.run (enhanced)
      ├─ Phase: REPRODUCE (1 step)
      ├─ Phase: UNDERSTAND (3 steps)
      ├─ Phase: PLAN (1 step)
      ├─ Phase: EDIT (3 steps)
      ├─ Phase: VALIDATE (3 steps)
      └─ Phase: FINALIZE (1 step)
```

新增文件清单：

```
autorepair/repair_agent/
  ├─ repair_case.py          (RepairCase + build_repair_case)
  ├─ spec_builder.py         (RepairSpec + build_repair_spec)
  ├─ validator.py            (ValidationPlan + ValidationResult)
  ├─ history_context.py      (HistoryContext + collect_history_context)
  └─ skills/
      ├─ __init__.py
      ├─ base.py             (RepairSkill Protocol)
      ├─ datetime_timezone.py
      ├─ null_guard.py
      ├─ zero_division.py
      ├─ idempotency.py
      ├─ name_error.py
      ├─ import_scope.py
      └─ router.py           (select_repair_skills)
```

修改文件清单：

```
autorepair/repair_agent/
  ├─ loop.py                 (阶段式循环改造)
  ├─ playbooks.py            (Skill-backed Playbook)
  ├─ prompts.py              (注入 RepairSpec/Skill/ValidationPlan)
  ├─ schemas.py              (新增 RepairPlanLite 等 schema)
  └─ tools.py                (新增 allowed_files 校验)
autorepair/repair/
  └─ executor.py             (串联五层增强)
```

---

## 2. RepairCase（repair_case.py）

### 数据模型

```python
class RepairCase(BaseModel):
    case_id: str                     # UUID
    incident_id: str
    issue_number: int | None = None
    scenario_id: str | None = None
    bug_type: str                    # 标准化错误类型
    entrypoint: str | None = None    # API 入口
    suspected_files: list[str] = []
    allowed_files: list[str] = []    # 非空
    forbidden_files: list[str] = []
    target_tests: list[str] = []
    regression_tests: list[str] = []
    expected_behavior: str = ""
    current_failure: str = ""
    confidence: float = 0.0
```

### build_repair_case(context, issue=None) -> RepairCase

核心规则：

1. 根据 incident.error_type、error_message、scenario_id、issue body 推断 case。
2. allowed_files 必须非空。如果无法确定，confidence < 0.4。
3. 如果 suspected_file 是 app.py 但 traceback/tests 指向业务服务层，纠正为 service 文件。
4. 默认 forbidden_files 包含：`.env`、`.git`、`pyproject.toml`、`requirements.txt`、所有测试目录。
5. Demo bug 显式映射：
   - `user-missing-profile` → `demo_service/service.py`
   - `order-zero-division` → `demo_service/order_service.py`
   - `ticket-nameerror-overdue` → `demo_service/ticket_service.py`
   - `ticket-idempotency-duplicate` → `demo_service/ticket_service.py`
   - timezone/offset-aware/offset-naive → `demo_service/ticket_service.py`
6. target_tests 根据 scenario_id 映射到最具体测试函数。
7. forbidden_files 默认包含 `tests/`，除非 allow_test_edit=True。

---

## 3. RepairSpec（spec_builder.py）

### 数据模型

```python
class RepairSpec(BaseModel):
    spec_id: str
    incident_id: str
    case_id: str
    function_under_repair: str | None = None
    caller_expectation: str
    preconditions: list[str]
    postconditions: list[str]
    invariants: list[str]
    violation: str
    acceptance_tests: list[str]
```

### build_repair_spec(case, context, code_excerpt, issue_body) -> RepairSpec

纯规则映射，4 个 demo bug 有硬编码模板：

**timezone**:
- caller_expectation: "submit_ticket 接受带时区的 sla_deadline，返回创建的工单"
- preconditions: ["sla_deadline 是 ISO 8601 格式字符串"]
- postconditions: ["fromisoformat 结果必须为 timezone-aware datetime", "naive/aware 比较必须统一到 UTC aware"]
- invariants: ["不得使用 datetime.utcnow() 与 aware datetime 比较"]
- violation: "从 naive datetime 来源解析的 deadline 与 utcnow() 的 aware datetime 比较导致 TypeError"

**idempotency**:
- caller_expectation: "相同 idempotency_key 重复提交返回同一 ticket_id"
- postconditions: ["find_by_idempotency_key 查询到已有 ticket 时直接返回", "新 key 正常创建工单"]
- violation: "submit_ticket 省略了 idempotency_key 检查，每次都创建新工单"

**zero_division**:
- caller_expectation: "calculate_order_discount 在 total_amount<=0 时返回业务错误"
- postconditions: ["total_amount <= 0 返回 400 Invalid order amount", "正常订单逻辑不受影响"]
- violation: "total_amount=0 直接做除法，抛 ZeroDivisionError"

**missing_profile**:
- caller_expectation: "build_user_profile 在用户不存在时返回安全错误"
- postconditions: ["用户不存在返回 404 User not found", "不抛 NoneType 错误"]
- violation: "get_user_by_id 返回 None 后直接访问字典属性，抛 TypeError"

未知 bug 时 fallback 到 LLM 生成 JSON，必须输出上述字段并校验。

---

## 4. RepairSkill（skills/）

### Protocol 定义（base.py）

```python
class RepairSkill(Protocol):
    name: str
    def match(self, case: RepairCase, spec: RepairSpec) -> bool: ...
    def prompt_hint(self, case: RepairCase, spec: RepairSpec) -> str: ...
    def allowed_files_hint(self, case: RepairCase) -> list[str]: ...
    def success_criteria(self, spec: RepairSpec) -> list[str]: ...
```

### 6 个技能实现

| 技能类 | 文件 | 匹配条件 | prompt_hint 概要 |
|---|---|---|---|
| DateTimeTimezoneSkill | datetime_timezone.py | error_message 含 offset-naive/offset-aware/timezone/datetime.utcnow | 使用 timezone.utc，fromisoformat 后统一 astimezone |
| NullGuardSkill | null_guard.py | NoneType / object is not subscriptable / user missing | 检查 None，返回 404，不吞异常 |
| ZeroDivisionSkill | zero_division.py | ZeroDivisionError | 除法前检查分母，走业务错误路径 |
| IdempotencySkill | idempotency.py | idempotency_key / duplicate / same ticket_id | 查询已有 ticket 并返回，不重复创建 |
| NameErrorSkill | name_error.py | NameError | 判断未定义符号是否应是字符串字面量 |
| ImportScopeSkill | import_scope.py | UnboundLocalError / local variable import shadowing | 将局部 import 提升到函数顶部 |

### router.py

```python
def select_repair_skills(case: RepairCase, spec: RepairSpec) -> list[RepairSkill]:
```

遍历所有技能类，收集 match() 返回 True 的技能。如果没有匹配，仍可进入通用 Agent 但 risk_level 提高。

---

## 5. ValidationPlan（validator.py）

### 数据模型

```python
class ValidationPlan(BaseModel):
    reproduce_command: str | None
    target_commands: list[str]
    related_commands: list[str]
    full_command: str = "pytest -q"

class FailureSummary(BaseModel):
    failed_command: str
    failure_type: str           # assertion_error / runtime_error / etc.
    relevant_output: str        # 截取关键输出，不超过 1500 字符
    violated_spec_item: str     # 违反 RepairSpec 的哪条 postcondition/invariant

class ValidationResult(BaseModel):
    phase: Literal["before", "after"]
    reproduce_ok: bool | None
    target_ok: bool | None
    related_ok: bool | None
    full_ok: bool | None
    failure_summary: FailureSummary | None = None
```

### 核心流程

1. **修复前（before）**: 运行 target test，确认失败。如果已通过 → not_reproducible。
2. **修复后（after）**: 依次运行 target → related → full。target 失败则不继续 full。
3. **失败时**: 生成 FailureSummary，明确指出违反了 RepairSpec 的哪条。
4. 测试输出截断处理，不超过 1500 字符。

---

## 6. HistoryContext（history_context.py）

```python
class HistoryContext(BaseModel):
    file: str
    recent_commits: list[str]       # git log -n 5
    blame_around_line: str | None   # git blame ±5 行
    last_modifier_summary: str

def collect_history_context(worktree_path, files, line_no=None) -> HistoryContext
```

- git 命令失败时静默忽略
- 输出截断（每项 ≤ 500 字符）
- 只作为 prompt 补充

---

## 7. 阶段式 Agent 循环（loop.py 改造）

### AgentPhase 枚举

```python
class AgentPhase(Enum):
    REPRODUCE   # 1 step
    UNDERSTAND  # 3 steps
    PLAN        # 1 step
    EDIT        # 3 steps
    VALIDATE    # 3 steps
    FINALIZE    # 1 step
```

总步数最多 12 步。

### 各阶段行为

**REPRODUCE (1 step)**:
- 运行 ValidationPlan 的 target test
- 确认失败 → 进入 UNDERSTAND
- 已通过 → 返回 not_reproducible

**UNDERSTAND (3 steps)**:
- 读取 allowed_files
- 搜索相关函数
- 读取测试文件（只读，不允许修改）
- 产出对代码的理解

**PLAN (1 step)**:
- LLM 必须输出 RepairPlanLite JSON：
  ```json
  {
    "root_cause": "...",
    "edit_files": ["..."],
    "strategy": "...",
    "spec_items_to_satisfy": [...]
  }
  ```
- edit_files 必须是 allowed_files 的子集，否则报错

**EDIT (3 steps)**:
- 只允许 apply_replace / rewrite_file 修改 allowed_files
- 每次修改后自动 git_diff
- 工具层校验 allowed_files

**VALIDATE (3 steps)**:
- 运行 target → related → full tests
- 失败时生成 SpecViolationFeedback
- 连续两次修改无改善 → rollback 到上一个 checkpoint
- checkpoint = EDIT 阶段开始前的 git diff / 文件快照

**FINALIZE (1 step)**:
- 测试通过 → 返回 fixed
- 未通过 → test_failed / needs_human

### Checkpoint 机制

- 每次 EDIT 前保存文件快照（复制到内存或 git stash）
- 如果 VALIDATE 更差（测试通过数减少），回滚到 checkpoint
- 不在坏 diff 上继续乱修

---

## 8. Prompt 重构（prompts.py）

### System Prompt 必须包含：

1. 你是安全的代码修复 Agent
2. 目标不是让报错消失，而是满足 RepairSpec
3. 只能修改 allowed_files
4. 默认禁止修改测试
5. 不要删除功能，不要绕过测试
6. 优先最小修改
7. 每次修改必须说明满足哪条 postcondition / invariant
8. 如果无法满足规格，调用 finish needs_human
9. 输出必须是 JSON ToolCall，不要 markdown

### User Prompt 注入内容：

- RepairCase（allowed_files / forbidden_files / expected_behavior）
- RepairSpec（caller_expectation / postconditions / invariants / violation）
- selected RepairSkills（名称 + prompt_hint）
- ValidationPlan
- HistoryContext
- traceback
- initial target test output

### 测试失败反馈 Prompt 注入：

- failed_command
- failure_summary
- violated_spec_item
- current_diff
- changed_files
- remaining_retry_budget

---

## 9. Playbook 升级（playbooks.py）

### 增强点

1. Playbook 必须基于 RepairCase + RepairSpec + RepairSkill 匹配
2. Playbook 成功后必须跑 ValidationPlan 验证
3. Playbook 失败后把失败原因作为 Agent 初始上下文
4. 新增 / 强化 playbook：
   - `datetime_timezone`：已有，增强匹配逻辑和验证
   - `name_error`：已有，增强匹配逻辑
   - `zero_division`：新增
   - `null_guard`：新增
5. idempotency 不做 deterministic playbook，交给 Agent + IdempotencySkill

### Playbook 签名变更

```python
def try_apply_known_playbook(
    case: RepairCase,
    spec: RepairSpec,
    skills: list[RepairSkill],
    validation_plan: ValidationPlan,
    tools: MiniRepairTools,
) -> RepairResult | None
```

---

## 10. Tools 增强（tools.py）

### 新增 allowed_files 校验

在 `apply_replace` 和 `rewrite_file` 中：
1. 检查 path 是否在 allowed_files 中
2. 检查 path 是否在 forbidden_files 中
3. 默认拒绝修改测试文件

MiniRepairTools 新增属性：
- `allowed_files: set[str]`
- `forbidden_files: set[str]`

初始化时由 RepairCase 传入。

---

## 11. Executor 集成（executor.py）

### 修改 execute_next_repair_job 流程

```
collect_repair_context
  → build_repair_agent_context
  → build_repair_case
  → check confidence >= 0.4, else needs_human
  → build_repair_spec
  → select_repair_skills
  → build_validation_plan
  → collect_history_context
  → try_apply_known_playbook(case, spec, skills, validation_plan, tools)
  → if not fixed:
      SpecGuidedMiniRepairAgent(llm, case, spec, skills, validation_plan).run(context)
  → if fixed: commit / push / create PR
  → if failed: 修复尝试报告 + ManualInterventionCard
```

### RepairJob 新增字段

```python
case_id: str | None = None
selected_skills: list[str] = []
spec_id: str | None = None
validation_summary: str | None = None
transcript_path: str | None = None
```

---

## 12. 安全约束总结

| 约束 | 实现位置 |
|---|---|
| 只能修改 allowed_files | tools.py apply_replace/rewrite_file 校验 |
| 默认不改测试 | RepairCase.forbidden_files 包含 tests/ |
| 不执行任意 shell 命令 | safety.py validate_test_command 只允许 pytest |
| 测试失败不创建 PR | executor.py 只在 status=="fixed" 时创建 PR |
| confidence < 0.4 转 human | build_repair_case 返回低 confidence → executor 跳过 |
| rollback 到 checkpoint | loop.py VALIDATE 阶段比较前后测试结果 |
| 不读取 .env/.git/credentials | safety.py is_sensitive_path |
| LLM 不决定修改哪些文件 | RepairCase 预先确定 allowed_files |

---

## 13. 测试策略

### 新增测试文件

```
autorepair/tests/repair_agent/
  ├─ test_repair_case.py      (build_repair_case 对 4 个 demo bug)
  ├─ test_spec_builder.py     (build_repair_spec 生成规格)
  ├─ test_skills.py           (select_repair_skills 匹配)
  ├─ test_validator.py        (ValidationPlan 流程)
  └─ test_history_context.py  (HistoryContext 容错)
```

### 核心测试用例

1. build_repair_case 能识别 4 个 demo bug
2. build_repair_case 对 timezone bug 生成 allowed_files=demo_service/ticket_service.py
3. build_repair_spec 生成 preconditions/postconditions/invariants
4. select_repair_skills 匹配 4 个 Skill
5. ValidationPlan 修复前 target 已通过时返回 not_reproducible
6. ValidationPlan target 失败时不继续 full test
7. HistoryContext git 命令失败时不崩溃
8. Agent 只能修改 allowed_files
9. Agent 不能修改测试文件
10. Agent 测试失败后能生成 SpecViolationFeedback
11. Agent 验证更差时 rollback
12. timezone Playbook 或 Agent 能修复 timezone bug
13. zero_division 简单场景能被修复
14. idempotency 场景修不了时输出 needs_human
15. executor fixed 后创建 PR
16. executor failed 后不创建 PR

---

## 14. 数据流图

```
Bug Trigger
  │
  ▼
Incident (error_type, error_message, suspected_file, traceback)
  │
  ▼
RepairJob (queued)
  │
  ▼
collect_repair_context → RepairContext (code_snippets, tests, target_test)
  │
  ▼
build_repair_agent_context → RepairAgentContext
  │
  ▼
build_repair_case → RepairCase (allowed_files, forbidden_files, confidence)
  │  └─ confidence < 0.4 → needs_human
  ▼
build_repair_spec → RepairSpec (postconditions, invariants, violation)
  │
  ▼
select_repair_skills → list[RepairSkill]
  │
  ▼
build_validation_plan → ValidationPlan (target, related, full commands)
  │
  ▼
collect_history_context → HistoryContext
  │
  ▼
try_apply_known_playbook
  │  ├─ matched & tests pass → fixed → PR
  │  └─ not matched / failed ↓
  ▼
MiniRepairAgent.run (phased)
  ├─ REPRODUCE: 确认 target test 失败
  ├─ UNDERSTAND: 读代码，理解业务
  ├─ PLAN: 输出 RepairPlanLite
  ├─ EDIT: 修改 allowed_files
  ├─ VALIDATE: 运行测试，SpecViolationFeedback
  └─ FINALIZE: fixed / test_failed / needs_human
    │
    ├─ fixed → commit / push / PR
    └─ failed → 修复报告 + ManualInterventionCard
```
