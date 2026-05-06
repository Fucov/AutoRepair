你现在继续开发 FeishuAutoRepair 项目。

当前项目状态：
1. 故障发现链路已经打通：
   Bug 触发 → 日志扫描 → Incident → GitHub Issue → 飞书卡片 → RepairJob queued。
2. 修复执行链路已经具备基础：
   RepairJob → repo lock → worktree → Playbook → MiniRepairAgent → 测试 → PR / 人工介入。
3. 当前 MiniRepairAgent 是 ReAct 工具调用模式，工具包括：
   read_file、get_file_excerpt、search_text、run_tests、apply_replace、rewrite_file、git_diff、finish。
4. 当前最大问题是修复成功率差：
   - 复杂 Bug 达到最大步骤数仍失败。
   - Agent 容易只看 traceback 局部位置，不理解正确业务行为。
   - Agent 偶尔修改错误文件，例如 app.py，而真正业务逻辑在 service 层。
   - 测试失败后缺乏规格级归因。
5. 你不要重写全链路，只增强 repair_agent 层。

本阶段名称：
Stage 3F：Spec-Guided Repair Agent

核心目标：
借鉴 FM-Agent 的“从调用方期望生成函数规格、再验证实现是否违反规格”的思想，把当前 MiniRepairAgent 从 Traceback-driven 升级为 Spec-guided。
实现 RepairCase、RepairSpec、RepairSkill、ValidationPlan、HistoryContext 五个增强层，提高修复成功率。

重要约束：
- 不要直接修改主工作区。
- 所有修改仍必须发生在 git worktree 中。
- 不要自动 merge PR。
- 不要直接修改 main/master/develop。
- 不要读取或修改 .env、.git、credentials、secrets、token、key、password。
- 不要执行任意 shell 命令，只允许运行 pytest / python -m pytest。
- 不要让 LLM 自己决定要改哪些任意文件。
- 每个 RepairJob 必须有 allowed_files。
- 默认禁止修改测试文件。
- 测试失败不得创建 PR。
- pytest -q 必须通过。
- 所有 LLM 调用在测试中 monkeypatch。

============================================================
一、RepairCase：显式识别修复任务
============================================================

新增：

autorepair/repair_agent/repair_case.py

定义：

class RepairCase(BaseModel):
    case_id: str
    incident_id: str
    issue_number: int | None = None
    scenario_id: str | None = None
    bug_type: str
    entrypoint: str | None = None
    suspected_files: list[str] = []
    allowed_files: list[str] = []
    forbidden_files: list[str] = []
    target_tests: list[str] = []
    regression_tests: list[str] = []
    expected_behavior: str
    current_failure: str
    confidence: float = 0.0

实现：

build_repair_case(context: RepairAgentContext, issue=None) -> RepairCase

规则：
1. 根据 incident.error_type、error_message、suspected_file、issue body、bug_scenarios.py 推断 case。
2. allowed_files 必须非空。
3. 如果 suspected_file 是 app.py，但 issue / traceback / tests 指向业务服务层，则应把 service 文件加入 allowed_files。
4. 默认 forbidden_files 包含：
   - .env
   - .git
   - pyproject.toml
   - requirements.txt
   - tests，除非明确 allow_test_edit=True
5. 对 demo bug 做显式映射：
   - user-missing-profile → demo_service/service.py
   - order-zero-division → demo_service/order_service.py
   - ticket-nameerror-overdue → demo_service/ticket_service.py
   - ticket-idempotency-duplicate → demo_service/ticket_service.py
   - timezone / offset-aware / offset-naive → demo_service/ticket_service.py
6. target_tests 根据 scenario_id 或 error_type 映射到最具体测试。
7. 如果无法确定 allowed_files，返回 confidence < 0.4，后续转 human_required，不让 Agent 乱修。

验收：
- AttributeError at demo_service/app.py:94 不应默认让 Agent 无限修 app.py，除非 scenario 明确是 app.py bug。
- ticket timezone bug 的 allowed_files 必须包含 demo_service/ticket_service.py。
- ticket-idempotency-duplicate 的 allowed_files 必须包含 demo_service/ticket_service.py。

============================================================
二、RepairSpec：FM-lite 自然语言规格
============================================================

新增：

autorepair/repair_agent/spec_builder.py

定义：

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

实现：

build_repair_spec(case: RepairCase, context: RepairAgentContext, code_excerpt: str | None, issue_body: str | None) -> RepairSpec

要求：
1. 规格从以下信息推导：
   - Issue 描述
   - agent_target 测试
   - API 入口函数
   - 调用方期望
   - Traceback
2. 不要从当前 buggy implementation 直接生成规格。
3. RepairSpec 必须包含：
   - caller_expectation
   - preconditions
   - postconditions
   - invariants
   - violation
   - acceptance_tests
4. 对 demo bug 给出明确规格：
   - timezone：带时区 SLA deadline 应能创建工单；naive/aware 时间比较必须统一到 UTC aware。
   - idempotency：相同 idempotency_key 重复提交应返回同一 ticket_id，不创建重复工单。
   - zero division：total_amount <= 0 应返回业务错误或安全降级，不抛 ZeroDivisionError。
   - missing profile：用户不存在时应返回 404 / None-safe 响应，不抛 NoneType 错误。
5. 规格生成可以先用规则，不强制 LLM；若用 LLM，必须输出 JSON 并校验。

验收：
- 每个 RepairCase 都能生成 RepairSpec。
- 失败报告中必须包含 RepairSpec。
- Agent prompt 必须注入 RepairSpec。

============================================================
三、RepairSkill：结构化修复技能
============================================================

新增目录：

autorepair/repair_agent/skills/

新增文件：
- __init__.py
- base.py
- datetime_timezone.py
- null_guard.py
- zero_division.py
- idempotency.py
- name_error.py
- import_scope.py
- router.py

base.py 定义：

class RepairSkill(Protocol):
    name: str
    def match(self, case: RepairCase, spec: RepairSpec) -> bool: ...
    def prompt_hint(self, case: RepairCase, spec: RepairSpec) -> str: ...
    def allowed_files_hint(self, case: RepairCase) -> list[str]: ...
    def success_criteria(self, spec: RepairSpec) -> list[str]: ...

实现以下技能：

1. DateTimeTimezoneSkill
匹配：
- error_message 包含 offset-naive / offset-aware / timezone / datetime.utcnow
策略提示：
- 使用 datetime.now(timezone.utc)
- fromisoformat 结果：
  naive → replace(tzinfo=timezone.utc)
  aware → astimezone(timezone.utc)
- 不要用 datetime.utcnow() 与 aware datetime 比较

2. NullGuardSkill
匹配：
- NoneType / object is not subscriptable / user missing
策略提示：
- 在访问字典或对象前检查 None
- 按业务约定返回 404 或明确错误
- 不要吞掉异常返回错误成功

3. ZeroDivisionSkill
匹配：
- ZeroDivisionError
策略提示：
- 除法前检查分母
- total_amount <= 0 走业务错误路径
- 保持正常订单逻辑不变

4. IdempotencySkill
匹配：
- idempotency_key / duplicate / same ticket_id
策略提示：
- 持久层按 idempotency_key 查询已有 ticket
- 已存在则返回已有 ticket
- 不要创建重复工单
- 正常新 key 仍创建新工单

5. NameErrorSkill
匹配：
- NameError
策略提示：
- 判断未定义符号是否应是字符串字面量
- 不要引入无关变量

6. ImportScopeSkill
匹配：
- UnboundLocalError / local variable import shadowing
策略提示：
- 将局部 import 提升到模块或函数顶部
- 避免条件分支里局部变量遮蔽全局变量

router.py 实现：
select_repair_skills(case, spec) -> list[RepairSkill]

验收：
- 4 个 demo bug 至少能匹配一个 RepairSkill。
- Agent prompt 中必须展示选中的 skill 名称和 prompt_hint。
- 如果没有匹配 skill，仍可进入通用 Agent，但 risk_level 提高。

============================================================
四、ValidationPlan：更稳的测试策略
============================================================

新增：

autorepair/repair_agent/validator.py

定义：

class ValidationPlan(BaseModel):
    reproduce_command: str | None
    target_commands: list[str]
    related_commands: list[str]
    full_command: str = "pytest -q"

实现：

build_validation_plan(case: RepairCase, spec: RepairSpec, context: RepairAgentContext) -> ValidationPlan
run_validation_plan(tools, plan, phase: Literal["before", "after"]) -> ValidationResult

规则：
1. 修复前必须运行 reproduce / target test。
2. 如果修复前 target test 已通过，返回 not_reproducible，不修。
3. 修复后依次运行：
   - target_commands
   - related_commands
   - full_command
4. target 失败不得继续 full test。
5. 测试失败时返回结构化 failure_summary：
   - failed_command
   - failure_type
   - relevant_output
   - violated_spec_item

验收：
- 不再只把 pytest stderr 原样丢给 LLM。
- 测试失败后 prompt 中必须包含“违反了 RepairSpec 的哪条 postcondition / invariant”。

============================================================
五、HistoryContext：低成本历史上下文
============================================================

新增：

autorepair/repair_agent/history_context.py

实现：

collect_history_context(worktree_path: str, files: list[str], line_no: int | None = None) -> HistoryContext

内容：
- git log -n 5 -- <file>
- git blame around line_no ±5
- 最近一次修改该文件的 commit summary

要求：
1. 如果 git 命令失败，不中断。
2. 输出截断。
3. 只作为 prompt 补充，不作为硬规则。

验收：
- Prompt 可包含 HistoryContext。
- 没有 git 历史时不影响修复。

============================================================
六、分阶段 Agent 循环，替代无限 ReAct
============================================================

修改：

autorepair/repair_agent/loop.py

当前最大步数 8、重试 2 次。请改为阶段式预算：

class AgentPhase(Enum):
    REPRODUCE
    UNDERSTAND
    PLAN
    EDIT
    VALIDATE
    FINALIZE

默认预算：
- REPRODUCE: 1 step
- UNDERSTAND: 3 steps
- PLAN: 1 step
- EDIT: 3 steps
- VALIDATE: 3 steps
- FINALIZE: 1 step

总步数最多 12。

流程：
1. REPRODUCE：
   - 运行 ValidationPlan 的 target test，确认失败。
2. UNDERSTAND：
   - 读取 allowed_files。
   - 搜索相关函数。
   - 读取测试文件，但默认不允许修改测试。
3. PLAN：
   - LLM 必须输出 RepairPlanLite：
     {
       "root_cause": "...",
       "edit_files": ["..."],
       "strategy": "...",
       "spec_items_to_satisfy": [...]
     }
   - edit_files 必须是 allowed_files 子集。
4. EDIT：
   - 只允许 apply_replace / rewrite_file 修改 allowed_files。
   - 每次修改后自动 git_diff。
5. VALIDATE：
   - 运行 target + related + full tests。
   - 失败时生成 SpecViolationFeedback，再给 LLM 一次修正机会。
   - 如果连续两次修改都没有改善，rollback 到上一个 checkpoint。
6. FINALIZE：
   - 测试通过返回 fixed。
   - 未通过返回 test_failed / needs_human。

新增 checkpoint：
- 每次 EDIT 前保存 git diff 或复制文件快照。
- 如果验证更差，回滚到上一个 checkpoint。
- 不要在坏 diff 上继续乱修。

验收：
- Agent 不再在 8 步内盲目循环。
- 每次修复失败报告包含：
  - 当前阶段
  - 违反的 spec item
  - 已尝试文件
  - 测试失败命令
  - 是否 rollback

============================================================
七、Playbook 升级：从硬编码变为 Skill-backed Playbook
============================================================

修改：

autorepair/repair_agent/playbooks.py

要求：
1. Playbook 仍优先执行。
2. Playbook 必须基于 RepairCase + RepairSpec + RepairSkill 匹配。
3. Playbook 成功后必须跑 ValidationPlan。
4. Playbook 失败后把失败原因作为 Agent 初始上下文。
5. 新增或强化 playbook：
   - datetime_timezone
   - name_error
   - zero_division
   - null_guard
6. idempotency 可先不做 deterministic playbook，交给 Agent，但要有 IdempotencySkill。

验收：
- timezone bug 可以通过 Playbook 或 Agent 稳定修复。
- name_error 可以通过 Playbook 快速修复。
- zero_division 至少有 Playbook 尝试。
- Playbook 不允许修改测试。

============================================================
八、Prompt 重构
============================================================

修改：

autorepair/repair_agent/prompts.py

System Prompt 必须包含：

1. 你是安全的代码修复 Agent。
2. 你的目标不是让报错消失，而是满足 RepairSpec。
3. 只能修改 allowed_files。
4. 默认禁止修改测试。
5. 不要删除功能，不要绕过测试。
6. 优先最小修改。
7. 每次修改必须说明满足哪条 postcondition / invariant。
8. 如果无法满足规格，调用 finish needs_human。
9. 输出必须是 JSON ToolCall，不要 markdown。

User Prompt 必须注入：
- RepairCase
- RepairSpec
- selected RepairSkills
- ValidationPlan
- HistoryContext
- traceback
- initial target test output
- allowed_files
- forbidden_files

测试失败反馈 Prompt 必须注入：
- failed_command
- failure_summary
- violated_spec_item
- current_diff
- changed_files
- remaining_retry_budget

============================================================
九、接入 executor.py
============================================================

修改 executor.py：

1. collect_repair_context 后：
   - build_repair_agent_context
   - build_repair_case
   - build_repair_spec
   - select_repair_skills
   - build_validation_plan
   - collect_history_context
2. 先 try_apply_known_playbook(case, spec, skills, validation_plan, tools)。
3. Playbook 不成功时，进入 SpecGuidedMiniRepairAgent。
4. fixed 后 commit / push / create PR。
5. failed 后生成修复尝试报告，发送 ManualInterventionCard。

RepairJob 记录中新增字段：
- case_id
- selected_skills
- spec_id
- validation_summary
- transcript_path

============================================================
十、测试要求
============================================================

pytest -q 必须通过。

新增测试至少覆盖：

1. build_repair_case 能识别 4 个 demo bug。
2. build_repair_case 对 timezone bug 生成 allowed_files=demo_service/ticket_service.py。
3. build_repair_spec 生成 preconditions/postconditions/invariants。
4. select_repair_skills 能匹配 DateTimeTimezoneSkill、ZeroDivisionSkill、NullGuardSkill、IdempotencySkill。
5. ValidationPlan 修复前 target test 通过时返回 not_reproducible。
6. ValidationPlan target 失败时不继续 full test。
7. HistoryContext git 命令失败时不崩溃。
8. Agent 只能修改 allowed_files。
9. Agent 不能修改测试文件。
10. Agent 测试失败后能生成 SpecViolationFeedback。
11. Agent 验证更差时 rollback。
12. timezone Playbook 或 SpecGuided Agent 能修复主线 timezone bug。
13. zero_division 简单场景能被 Playbook 或 Agent 修复。
14. idempotency 场景如果修不了，应输出 needs_human，不应乱改无关文件。
15. executor fixed 后创建 PR。
16. executor failed 后不创建 PR。

============================================================
十一、演示验收
============================================================

完成后，至少保证：

1. ticket-nameerror-overdue：
   - Playbook 修复成功
   - pytest 通过
   - PR 创建

2. ticket-timezone-sla：
   - RepairSpec 明确 timezone 规格
   - DateTimeTimezoneSkill 匹配
   - Playbook 或 Agent 修复成功
   - pytest 通过
   - PR 创建

3. ticket-idempotency-duplicate：
   - IdempotencySkill 匹配
   - 如果未能修复，应输出高质量 needs_human 报告
   - 不允许乱改 app.py 或测试

4. user-missing-profile / order-zero-division：
   - 至少一个能通过 Agent 修复
   - 失败时必须有清晰 spec violation 报告

============================================================
十二、输出要求
============================================================

完成后输出：
1. 新增/修改文件列表。
2. RepairCase / RepairSpec / RepairSkill / ValidationPlan 的设计说明。
3. 选中的 RepairSkills 示例。
4. 新 Agent 阶段式循环说明。
5. pytest -q 结果。
6. 每个 demo bug 的修复结果表：
   - 是否匹配 Playbook
   - 是否进入 Agent
   - 是否测试通过
   - 是否创建 PR
7. repair_transcript 示例路径。
8. 失败案例的 needs_human 报告示例。
9. 明确说明：
   - Agent 只改 allowed_files。
   - Agent 默认不改测试。
   - Agent 不执行任意 shell 命令。
   - 测试失败不会创建 PR。