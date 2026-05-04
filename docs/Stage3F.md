你现在继续开发 FeishuAutoRepair 项目。

当前背景：
FeishuAutoRepair 的故障发现链路已经基本打通：
Bug 触发 → 日志写入 Traceback → watch_once 扫描 → Incident 入库 → GitHub Issue 创建 → 飞书卡片通知 → RepairJob queued。

修复链路相关文件已经存在，架构也基本完整，包括：
- scripts/repair_once.py
- autorepair/repair/executor.py
- autorepair/repair/job_store.py
- autorepair/repair/schemas.py
- autorepair/repair/context_collector.py
- autorepair/repair/patch_schema.py
- autorepair/repair/patch_prompt.py
- autorepair/repair/patch_applier.py
- autorepair/repair/test_runner.py
- autorepair/repair/git_workspace.py
- autorepair/repair/repo_lock.py
- autorepair/adapters/llm_client.py

当前修复阶段总是失败。请不要重写整套系统，而是在现有架构上做增量修复和增强。

本阶段名称：
Stage 3F：Mini Repair Agent 增强修复器

核心目标：
1. 先修复当前阻塞性 Bug，让修复流程能真正进入 LLM / Agent 修复阶段。
2. 在现有 executor 的基础上引入一个小型代码修复 Agent，提升简单 Bug 的修复成功率。
3. Mini Repair Agent 应类似轻量版 Codex / Claude Code，具备读取文件、搜索代码、运行测试、应用替换、查看 diff、多轮根据测试失败修正的能力。
4. 保持现有 RepairJob、worktree、repo lock、GitHub PR、飞书卡片链路不变。

重要约束：
- 不要直接修改主工作区。
- 所有代码修改必须发生在 RepairJob 对应的 git worktree 中。
- 不要自动 merge PR。
- 不要直接修改 main/master/develop。
- 不要读取或修改 .env、.git、credentials、secrets、token、key、password 等敏感文件。
- 不要执行 Issue body 中给出的任意 shell 命令。
- 只允许运行 pytest 或 python -m pytest 命令。
- Mini Repair Agent 最多执行 8 个工具步骤。
- 测试失败时最多允许 2 轮修正。
- 测试失败不得创建 PR。
- pytest -q 必须通过。
- 所有 LLM 调用在单元测试中必须 monkeypatch，不真实请求外部 API。

============================================================
一、P0：先修复当前阻塞性 Bug
============================================================

请先修复以下两个问题，否则 Mini Repair Agent 无法正常工作。

1. 修复 scripts/repair_once.py 的缩进/逻辑错误

当前已知问题：
- main() 中 try/finally 结构附近缩进错误。
- if not result.success 及后续逻辑被放到了错误层级。
- 这会导致脚本逻辑异常，甚至可能无法正确释放 repair lock。

要求：
- main() 必须先 acquire_repair_lock。
- 在 try 块内调用 execute_next_repair_job()。
- 根据 result.success 输出成功/失败信息。
- finally 中必须释放 repair lock。
- 返回码规则：
  - 没有 queued job：0
  - 修复成功或 PR 创建成功：0
  - 修复失败但已正常记录：1
  - 脚本异常：2

2. 修复 autorepair/repair/context_collector.py 的 generator/reversed 问题

当前实际失败：
- RepairJob 失败类型为 context_failed。
- last_error 为：
  'generator' object is not reversible
- 修复流程在 collect_repair_context 阶段失败，根本没有进入 LLM 修复。

要求：
- 检查 _parse_traceback(raw, worktree) 中所有 reversed(...) 的调用。
- 确保传入 reversed 的一定是 list，而不是 generator。
- 如果 frames 可能来自生成器，先显式 frames = list(frames)。
- 增加健壮性：
  - raw_traceback 为空时返回空 TracebackInfo，不抛异常。
  - 无法解析项目帧时，仍然保留 error_type / error_message。
  - suspected_file 可以为空，但 collect_repair_context 不应崩溃。
- 新增单元测试覆盖：
  - raw_traceback 正常解析。
  - frames 是 generator 时不会报错。
  - raw_traceback 为空时不会报错。
  - 无项目文件帧时不会报错。

验收：
- 执行 scripts/repair_once.py 不再因为 repair_once.py 缩进错误失败。
- 当前 JOB-1e344f61457f 这类 context_failed 不应再出现 generator not reversible。
- collect_repair_context 可以正常返回 RepairContext。

============================================================
二、保留现有 PatchPlan 机制，但新增 Mini Repair Agent 作为默认路径
============================================================

当前 executor.py 的逻辑是：
RepairJob queued
→ repo lock
→ collect_repair_context
→ build_patch_prompt
→ LLM 返回 PatchPlan
→ apply_patch_plan
→ run target test
→ run full test
→ commit/push/create PR

这个逻辑不要删除，可以保留为 fallback。

现在新增 Mini Repair Agent，并让 executor 默认使用 MiniRepairAgent。
如果 MiniRepairAgent 出现 agent_error，可以 fallback 到原 PatchPlan 流程。

新增目录：

autorepair/repair_agent/

新增文件：
- autorepair/repair_agent/__init__.py
- autorepair/repair_agent/schemas.py
- autorepair/repair_agent/safety.py
- autorepair/repair_agent/tools.py
- autorepair/repair_agent/context.py
- autorepair/repair_agent/prompts.py
- autorepair/repair_agent/loop.py
- autorepair/repair_agent/transcript_store.py

============================================================
三、schemas.py
============================================================

定义以下模型：

ToolCall:
- tool: str
- args: dict[str, Any]

ToolResult:
- tool: str
- ok: bool
- output: str
- error: str | None = None
- changed: bool = False

AgentStep:
- step_index: int
- tool_call: ToolCall | None = None
- tool_result: ToolResult | None = None
- note: str | None = None

RepairAgentContext:
- job_id: str
- incident_id: str
- issue_number: int | None
- service_name: str
- worktree_path: str
- repo_path: str
- error_type: str | None
- error_message: str | None
- suspected_file: str | None
- line_no: int | None
- raw_traceback: str | None
- issue_body: str | None
- target_test_command: str | None
- full_test_command: str = "pytest -q"

RepairAgentResult:
- ok: bool
- status: Literal[
    "fixed",
    "test_failed",
    "not_reproducible",
    "unsafe_patch",
    "needs_human",
    "agent_error"
  ]
- summary: str
- changed_files: list[str] = []
- tests_run: list[str] = []
- target_test_passed: bool = False
- full_test_passed: bool = False
- diff: str | None = None
- transcript_path: str | None = None
- error: str | None = None

============================================================
四、safety.py
============================================================

实现安全工具：

is_sensitive_path(path: str) -> bool
is_safe_relative_path(path: str) -> bool
resolve_worktree_path(worktree_path: str, relative_path: str) -> Path
validate_test_command(command: str) -> bool

规则：
1. path 必须在 worktree 内，不能通过 ../ 逃逸。
2. 禁止路径包含：
   - .git
   - .env
   - secret
   - secrets
   - credential
   - credentials
   - token
   - key
   - password
3. 测试命令只允许：
   - pytest ...
   - python -m pytest ...
4. 禁止执行：
   - rm / del
   - curl / wget
   - pip install / conda install
   - git reset
   - git clean
   - 任意非 pytest 命令
5. 所有不安全操作返回失败，不抛出未捕获异常。

============================================================
五、tools.py
============================================================

实现 MiniRepairTools。

class MiniRepairTools:
    def __init__(self, worktree_path: str):
        self.worktree_path = Path(worktree_path)
        self.read_files: set[str] = set()

工具方法：

1. read_file(path: str, start_line: int | None = None, end_line: int | None = None) -> ToolResult
   - 只能读取 worktree 内文件。
   - 禁止读取敏感文件。
   - 支持按行范围读取。
   - 输出最多 12000 字符，超过则截断。
   - 成功后记录到 self.read_files。

2. get_file_excerpt(path: str, line_no: int, radius: int = 50) -> ToolResult
   - 读取指定行附近代码。
   - 内部可调用 read_file。
   - 用于 suspected_file + line_no 的初始查看。

3. search_text(query: str, include_glob: str = "*.py") -> ToolResult
   - 在 worktree 内搜索文本。
   - 跳过 .git、.venv、__pycache__、node_modules、.worktrees。
   - 最多返回 30 条结果。
   - 不搜索敏感文件。

4. run_tests(command: str, timeout: int = 120) -> ToolResult
   - 只允许 pytest / python -m pytest。
   - 在 worktree_path 下执行。
   - 捕获 stdout / stderr / returncode。
   - 输出保留失败摘要，最多 12000 字符。
   - changed=False。

5. apply_replace(path: str, old: str, new: str) -> ToolResult
   - path 必须安全。
   - 文件必须已经 read_file 过。
   - old / new 非空。
   - old 在文件中必须唯一出现。
   - 替换成功后写回。
   - changed=True。
   - 如果 old 不存在，返回最相似片段提示。
   - 如果 old 出现多次，返回失败，避免误改。

6. rewrite_file(path: str, content: str) -> ToolResult
   - 仅允许重写已 read_file 过的文件。
   - 仅允许重写小文件，默认小于 500 行。
   - 禁止重写测试文件，除非上下文明确 allow_test_edit=True；本阶段默认不允许修改测试。
   - 禁止重写敏感文件。
   - content 不能为空。
   - changed=True。
   - 这是 apply_replace 多次失败时的兜底。

7. git_diff() -> ToolResult
   - 执行 git diff。
   - 输出当前 worktree diff。
   - changed=False。

8. finish(status: str, summary: str) -> ToolResult
   - 用于模型声明 fixed / needs_human。
   - 不直接判断测试是否通过，测试通过仍由 loop 负责确认。

注意：
- 工具不访问网络。
- 工具不 commit，不 push，不创建 PR。
- 工具只负责让 worktree 代码变为测试通过。

============================================================
六、context.py
============================================================

实现：

build_repair_agent_context(job: RepairJob, incident: Incident, issue=None, service=None) -> RepairAgentContext

要求：
1. 从 job 中读取：
   - job_id
   - incident_id
   - issue_number
   - worktree_path
2. 从 incident 中读取：
   - error_type
   - error_message
   - suspected_file
   - line_no
   - raw_traceback
3. 从 issue 中读取 issue_body。
4. 从 service 配置中读取 target_test_command / full_test_command。
5. 如果能识别主线 ticket-timezone-sla，则 target_test_command 优先为：
   pytest -q demo_service/tests/test_ticket_contract.py::test_timezone_aware_sla_deadline_should_create_ticket -m agent_target
6. 如果 incident.error_summary.suspected_file 使用 Windows 反斜杠，需要转成当前系统可用的相对路径。
7. 缺失字段不要崩溃。

============================================================
七、prompts.py
============================================================

实现：

build_repair_agent_system_prompt() -> str
build_initial_user_prompt(context: RepairAgentContext, initial_test_output: str, initial_code_excerpt: str | None) -> str
build_next_step_prompt(last_tool_result: ToolResult, current_diff: str | None = None) -> str

Prompt 要求：
1. 模型是谨慎的代码修复 Agent。
2. 目标是在 git worktree 中修复 Bug，并让测试通过。
3. 模型必须先读取相关代码，再修改代码。
4. 没有 read_file 过的文件，不允许 apply_replace / rewrite_file。
5. 优先最小修改。
6. 默认禁止修改测试。
7. 不要修改 .env、.git、依赖配置。
8. 不要删除功能，不要绕过测试。
9. 不要执行任意 shell 命令。
10. 输出必须是 JSON ToolCall，不要 markdown，不要解释性长文。

ToolCall JSON 格式：
{
  "tool": "read_file",
  "args": {
    "path": "demo_service/ticket_service.py"
  }
}

可用工具：
- read_file
- get_file_excerpt
- search_text
- run_tests
- apply_replace
- rewrite_file
- git_diff
- finish

finish 示例：
{
  "tool": "finish",
  "args": {
    "status": "needs_human",
    "summary": "无法定位稳定修复点，需要人工检查"
  }
}

对于 SLA timezone bug，提示模型优先考虑：
- 使用 datetime.now(timezone.utc)
- 将 datetime.fromisoformat 得到的 deadline 统一转为 timezone-aware UTC
- naive deadline 可补 timezone.utc
- aware deadline 使用 astimezone(timezone.utc)
- 不要使用 datetime.utcnow() 与 aware datetime 直接比较

============================================================
八、loop.py
============================================================

实现：

class MiniRepairAgent:
    def __init__(self, llm_client, max_steps: int = 8, max_retries: int = 2):
        ...

    def run(self, context: RepairAgentContext) -> RepairAgentResult:
        ...

主流程：

1. 初始化 MiniRepairTools。
2. 先运行 target_test_command。
   - 如果 target_test_command 为空，则运行 full_test_command。
   - 如果目标测试一开始已经通过，返回 not_reproducible，不修改代码。
3. 初始读取：
   - 如果 suspected_file + line_no 存在，调用 get_file_excerpt。
   - 如果没有 suspected_file，则 search_text(error_message 中的关键词)。
4. 构建 initial prompt。
5. 进入工具循环，最多 max_steps。
6. 每轮调用 llm_client.chat_json，要求返回 ToolCall JSON。
7. 执行工具。
8. 如果工具 changed=True：
   - 自动运行 target_test_command。
   - 如果目标测试通过，再运行 full_test_command。
   - 如果 full_test 通过：
     - 调 git_diff。
     - 保存 transcript。
     - 返回 fixed。
   - 如果测试失败：
     - 把失败输出和当前 diff 反馈给模型。
     - retry 次数 +1。
     - 超过 max_retries 后返回 test_failed。
9. 如果模型调用 finish needs_human，返回 needs_human。
10. 如果达到 max_steps 仍未成功，返回 test_failed 或 needs_human。
11. 所有异常返回 agent_error，但不要崩溃。

关键要求：
- loop.py 不 commit。
- loop.py 不 push。
- loop.py 不创建 PR。
- loop.py 只负责修复 worktree 中的代码并验证测试。

============================================================
九、transcript_store.py
============================================================

实现：

save_repair_transcript(job_id: str, steps: list[AgentStep], result: RepairAgentResult) -> str

保存路径：
autorepair/records/repair_transcripts/{job_id}.json

要求：
- 保存每轮 tool_call、tool_result。
- stdout/stderr 要截断。
- 不保存 API Key、token、secret。
- 返回 transcript_path。

============================================================
十、接入现有 executor.py
============================================================

修改 autorepair/repair/executor.py。

当前 execute_next_repair_job() 已经包含：
queued job
→ repo lock
→ collect context
→ LLM PatchPlan
→ apply_patch
→ run tests
→ commit / push / PR
→ feishu card

请修改为：

1. 从 job_store 取最早 queued job。
2. 获取 repo lock。
3. 创建 worktree / repair branch。
4. 更新 job status=running。
5. 先调用 collect_repair_context。
6. 构建 RepairAgentContext。
7. 调用 MiniRepairAgent.run(context)。
8. 如果 result.status == fixed：
   - 检查 git diff 非空。
   - git_commit_all。
   - git_push_branch。
   - create_pull_request。
   - 更新 job status=pr_created。
   - 写入 pr_number / pr_url。
   - GitHub Issue 打 autorepair:pr-ready。
   - 发送 FixPrReadyCard。
   - 写 audit event。
9. 如果 result.status != fixed：
   - 如果 status 是 not_reproducible：更新 job status=human_required。
   - 如果 status 是 test_failed：更新 job status=test_failed。
   - 其他失败：更新 job status=human_required 或 failed。
   - 评论 GitHub Issue。
   - 发送 ManualInterventionCard。
   - 写 audit event。
   - 不创建 PR。
10. 如果 MiniRepairAgent 发生 agent_error，可以 fallback 到原 PatchPlan 流程。
11. 保留原 PatchPlan 代码，但不再作为默认路径。

============================================================
十一、主线 Bug 修复目标
============================================================

优先保证 ticket-timezone-sla 修复成功。

主线 Bug：
demo_service/ticket_service.py 中：
deadline = datetime.fromisoformat(payload["sla_deadline"])
if deadline < datetime.utcnow():
    ...

错误：
TypeError: can't compare offset-naive and offset-aware datetimes

目标测试：
pytest -q demo_service/tests/test_ticket_contract.py::test_timezone_aware_sla_deadline_should_create_ticket -m agent_target

正向测试：
pytest -q demo_service/tests/test_ticket_success.py

全量测试：
pytest -q

Agent 修复后应满足：
1. 带 +08:00 的 SLA deadline 可以创建 ticket。
2. 不带时区的 deadline 仍然可以创建 ticket。
3. 不要修复幂等性 Bug，除非当前 RepairJob 明确对应幂等性 Issue。
4. 不要修改测试来绕过问题。

============================================================
十二、可选但强烈建议：Repair Playbook 兜底
============================================================

为了提高演示稳定性，请新增一个轻量 Repair Playbook。

新增：
autorepair/repair_agent/playbooks.py

实现：
try_apply_known_playbook(context, tools) -> RepairAgentResult | None

规则：
1. 如果 error_message 包含：
   "can't compare offset-naive and offset-aware datetimes"
   且 suspected_file 包含 ticket_service.py
   则使用确定性策略修复：
   - 确保导入 timezone：
     from datetime import datetime, timezone
   - 将 deadline 统一转 UTC aware datetime。
   - 使用 now = datetime.now(timezone.utc)。
2. Playbook 必须通过工具 read_file / apply_replace 修改文件。
3. Playbook 修改后仍必须运行目标测试和 full test。
4. Playbook 成功时返回 fixed。
5. Playbook 失败时返回 None，让 LLM Agent 继续尝试。

说明：
这不是硬编码答案，而是低风险已知模式修复策略库，可提升演示稳定性。

============================================================
十三、测试要求
============================================================

pytest -q 必须通过。

新增测试至少覆盖：

1. repair_once.py main 正常调用 execute_next_repair_job，并释放 repair lock。
2. context_collector 不再出现 generator object is not reversible。
3. safety 禁止 .env / .git / secrets 路径。
4. validate_test_command 只允许 pytest / python -m pytest。
5. read_file 只能读 worktree 内文件。
6. apply_replace 成功替换。
7. apply_replace old 不存在失败。
8. apply_replace old 多次出现失败。
9. rewrite_file 只能重写已读取文件。
10. run_tests 拒绝非 pytest 命令。
11. MiniRepairAgent 在 mock LLM 下可以：
    - 先读取文件
    - apply_replace
    - target test 通过
    - full test 通过
    - 返回 fixed
12. MiniRepairAgent 在目标测试一开始通过时返回 not_reproducible。
13. MiniRepairAgent 在测试失败后能 retry。
14. executor 在 MiniRepairAgent fixed 后进入 commit / push / PR 创建逻辑。
15. executor 在 MiniRepairAgent failed 后不创建 PR，发送 ManualInterventionCard。
16. Repair Playbook 能修复 timezone-aware vs naive datetime 的主线 Bug。
17. 所有 LLM / GitHub / Feishu 调用在测试中 monkeypatch，不真实请求网络。

============================================================
十四、演示验收
============================================================

完成后，ticket-timezone-sla 必须可以按以下流程演示：

1. 触发 SLA 时区 Bug。
2. watch_once 创建 Incident 和 GitHub Issue。
3. watch_github_issues_once 创建 RepairJob queued。
4. repair_once 启动 MiniRepairAgent。
5. Agent 先运行目标测试，确认失败。
6. Agent 读取 ticket_service.py。
7. Agent 应用最小修改。
8. Agent 运行目标测试通过。
9. Agent 运行 pytest -q 通过。
10. repair_once commit / push / create PR。
11. 飞书发送 PR 待 Review 卡片。

============================================================
十五、输出要求
============================================================

完成后输出：

1. 新增/修改文件列表。
2. P0 阻塞 Bug 修复说明：
   - repair_once.py 修了什么
   - context_collector.py 修了什么
3. MiniRepairAgent 的工具列表。
4. MiniRepairAgent 主循环说明。
5. 是否启用 Repair Playbook。
6. pytest -q 结果。
7. ticket-timezone-sla 修复演示输出。
8. repair_transcript 示例路径。
9. 生成的 PR URL 或 mock PR URL。
10. 明确说明：
    - Agent 不直接改主工作区。
    - Agent 不执行任意 shell 命令。
    - Agent 不自动 merge。
    - 测试失败不会创建 PR。