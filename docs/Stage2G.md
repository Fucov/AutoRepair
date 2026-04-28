你现在负责改造我的“飞书 Agent 自动修复系统”。当前系统已经支持：
1. FastAPI demo 服务；
2. 本地运行时异常日志采集；
3. GitHub Issue 入口；
4. Incident 结构；
5. 飞书卡片通知基础链路；
6. 后续计划接入 LLM 自动诊断、修改代码、运行测试、提交 PR。

现在我希望参考 ClawSweeper 的保守治理思路，但不要完整照搬。请实现一个 Stage2G：Incident Triage / Decision Gate，用于在自动修复前判断一个故障/Issue 是否应该进入自动修复链路。

核心要求：

一、设计目标
1. Review 阶段只做诊断和提案，不修改代码、不提交 PR、不关闭 Issue。
2. LLM 必须输出结构化 JSON decision。
3. 只有 decision=auto_fix 且 confidence=high，并且证据完整时，才允许进入后续 Repair Agent。
4. 证据不足、配置问题、重复问题、无法复现、外部依赖问题，都不要自动修复，而是生成飞书卡片提醒人工处理。
5. 每个 incident 都要生成可审计报告，便于 demo 展示。

二、请新增模块
建议路径如下，可以根据现有项目结构微调：

app/agent/triage/decision_schema.py
app/agent/triage/triage_prompt.py
app/agent/triage/triage_agent.py
app/agent/triage/evidence_collector.py
app/agent/triage/report_writer.py
app/agent/triage/policy_gate.py

三、Decision Schema
请定义 Pydantic 模型或 JSON Schema，字段包括：

decision:
  enum:
  - auto_fix
  - propose_fix
  - need_info
  - duplicate
  - cannot_reproduce
  - config_error
  - external_dependency
  - keep_open
  - escalate

confidence:
  enum: high, medium, low

severity:
  enum: p0, p1, p2, p3

incident_type:
  enum:
  - runtime_exception
  - test_failure
  - regression
  - dependency
  - config
  - flaky
  - product_request
  - unknown

summary: str
root_cause_hypothesis: str
evidence: list[Evidence]
risks: list[str]
recommended_action: str
fix_plan: str | None
requires_human_approval: bool
feishu_card: object

Evidence 字段：
label: str
detail: str
file: str | None
line: int | None
command: str | None
sha: str | None

四、Triage Prompt
请编写一个明确的 prompt，要求 LLM：
1. 把 Issue 讨论、日志、traceback、测试结果、相关文件作为证据，而不是背景；
2. 不允许凭标题直接判断；
3. 如果不能定位到具体代码/日志/测试证据，必须 keep_open / need_info / escalate；
4. 不能因为看起来像 bug 就自动修；
5. auto_fix 必须满足：
   - 有明确 traceback 或失败测试；
   - 能定位具体文件/函数；
   - 修改范围可控；
   - 风险不是安全、权限、支付、数据删除类；
   - 可以通过测试验证；
6. 输出必须是严格 JSON，不要输出解释性文本。

五、Policy Gate
实现 should_auto_fix(decision)：
只有满足以下条件才返回 True：
1. decision == auto_fix
2. confidence == high
3. evidence 非空
4. fix_plan 非空
5. requires_human_approval == False
6. risks 不包含 security/payment/permission/data_loss 等高风险关键词

否则返回 False，并给出 blocked_reason。

六、Report Writer
每个 incident 生成：
.agent/reports/items/<incident_id>.md
.agent/reports/items/<incident_id>.decision.json

Markdown 报告包含：
- incident 基本信息
- 来源：runtime_log / github_issue
- 当前 git sha
- decision
- confidence
- severity
- summary
- root cause hypothesis
- evidence
- risks
- recommended action
- fix plan
- policy gate result
- feishu message id，如果存在

七、飞书卡片适配
根据 decision 生成不同卡片状态：
1. auto_fix + high：标题“已完成诊断，准备自动修复”，按钮：查看证据、开始修复、转人工
2. need_info：标题“需要补充信息”，按钮：查看缺失信息、补充日志、转人工
3. duplicate：标题“疑似重复故障”，按钮：查看关联故障、合并处理
4. cannot_reproduce：标题“当前无法复现”，按钮：查看复现记录、重新扫描
5. config_error：标题“疑似配置问题”，按钮：查看配置建议、转人工
6. escalate：标题“高风险问题，建议人工处理”，按钮：查看风险、转人工

八、接入现有链路
在现有 GitHub Issue 入口和本地日志入口之后，先调用 triage：
incident -> collect_context -> triage_agent -> validate schema -> write report -> policy_gate

如果 policy_gate 通过，才进入后续 repair flow。
如果不通过，只发送/更新飞书卡片，不改代码。

九、测试
请添加 pytest：
1. valid auto_fix decision passes policy gate
2. low confidence auto_fix is blocked
3. need_info is blocked
4. high-risk evidence is blocked
5. invalid JSON/schema validation fails
6. report writer can generate md/json
7. same incident id should update existing report rather than duplicate

十、注意
不要现在实现复杂批量扫描、周期调度、自动关闭 Issue。
不要破坏现有链路。
保持实现简洁，优先让 demo 能展示“诊断-决策-飞书卡片-再进入修复”的闭环。