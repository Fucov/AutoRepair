你现在继续开发 FeishuAutoRepair 项目。

当前问题：
1. Demo UI 仍然像按钮面板，不像真实工单系统。截图里只有系统状态、几个按钮、响应结果，没有顶部指标卡、工单队列、事件流、运行状态面板。
2. Feishu 冒烟测试仍然输出 Mock Feishu Card，说明配置没有被正确识别或真实发送失败。
3. GitHub 冒烟测试主要走 Mock Issue Store，真实 GitHub API 还没有可信打通。
4. Stage 2E 总结说 UI 已产品化，但实际页面不符合要求。现在必须严格按照验收标准修正，不要再只改文案。

本阶段名称：Stage 2F-Fix：演示可信度修复。

本阶段目标：
1. 把首页真正改成一个可信的企业工单管理系统 mock 页面。
2. 修复环境变量加载与命名不一致问题。
3. 明确区分 Feishu/GitHub 的 real mode 与 mock mode。
4. 新增严格的配置检查和冒烟测试输出。
5. 保持系统小而美，不接入 LLM，不自动修复，不创建 PR。

重要约束：
- 不要接入 LLM。
- 不要自动修复任何预埋 Bug。
- 不要创建 PR。
- 不要引入 React/Vue。
- 不要引入数据库。
- 不要泄露 .env 中任何密钥。
- pytest -q 必须通过。
- pytest -q -m agent_target 仍然必须失败。
- 所有脚本都必须显式加载 .env。

============================================================
一、统一环境变量加载
============================================================

请检查所有 scripts/*.py、autorepair/config.py、Feishu adapter、GitHub adapter、Ark adapter。

要求：
1. 使用 python-dotenv，在配置入口统一 load_dotenv。
2. 确保脚本直接运行时也能读取项目根目录 .env。
3. 项目根目录的 .env 路径应通过 Path(__file__).resolve() 向上定位，不要依赖当前工作目录。
4. 新增或修复 autorepair/config.py，使其统一读取以下变量：

FEISHU_API_BASE_URL=https://open.feishu.cn/open-apis
FEISHU_APP_ID
FEISHU_APP_SECRET
FEISHU_CHAT_ID

GITHUB_TOKEN
GITHUB_OWNER
GITHUB_REPO
GITHUB_BASE_BRANCH

ARK_API_KEY
ARK_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
ARK_MODEL_REPAIR
ARK_MODEL_SUMMARY

5. 删除或兼容旧变量名，但 README 和 .env.example 只保留新变量名。
6. 任何输出中不得打印完整 token、secret、app_secret。

============================================================
二、强制重做 Demo UI，不要只改按钮
============================================================

当前 demo_service/app.py 首页不符合要求。请重新组织首页 HTML。

要求：
- 仍然使用原生 HTML + CSS + JS。
- 不引入 React/Vue。
- 可以把 HTML 字符串拆到 demo_service/ui.py，避免 app.py 太长。
- 最终 GET / 返回一个完整的 SupportDesk mock 控制台。

页面必须包含以下区域，缺一不可：

1. 顶部 Header
标题：Acme SupportDesk Lite
副标题：企业客户支持工单与 SLA 管理平台
右侧显示：
- 环境：Local Demo
- Agent 接入：Black-box Log Watcher
- 服务 ID：supportdesk-lite

2. KPI 指标区，四张卡片横向排列：
- 今日工单：128
- P1 紧急工单：7
- SLA 风险工单：3
- 飞书渠道占比：64%

3. 主体双栏布局：
左侧 65%：工单队列表格
右侧 35%：服务运行状态面板

工单队列表格至少 5 条 mock 数据，列包括：
- 工单编号
- 客户
- 来源渠道
- 优先级
- SLA 截止时间
- 处理人
- 状态

示例数据：
TK-1024 / 北航实验室 / 飞书 / P1 / 今天 18:00 / oncall-zhang / SLA 风险
TK-1025 / Acme 财务部 / Web / P2 / 明天 12:00 / support-li / 处理中
TK-1026 / 华北客户A / 飞书 / P1 / 今天 16:30 / support-wang / 待分配
TK-1027 / 内部测试租户 / API / P3 / 后天 10:00 / bot / 已解决
TK-1028 / 客服质检组 / 飞书 / P2 / 明天 18:00 / support-chen / 待确认

服务运行状态面板显示：
- 服务状态：运行中
- 日志监听：demo_service/logs/app.log
- 仓库路径：当前仓库
- 健康检查：/health
- AutoRepair 状态：等待扫描

4. 操作面板
标题：演示操作

按钮：
- 系统健康检查
- 创建正常 P2 工单
- 创建带 +08:00 SLA 的紧急工单（触发 Runtime Bug）
- 重复提交同一飞书事件（模拟幂等性缺陷）

每个按钮下面有一句说明。

注意：按钮不应该占页面主体，只是操作面板的一部分。

5. 最近事件流
至少 5 条 mock 事件：
- 09:30 飞书渠道收到客户反馈
- 09:35 P1 工单进入 SLA 风险
- 09:36 SupportDesk 服务写入访问日志
- 09:38 AutoRepair 正在监听服务日志
- 09:40 新异常会被写入 demo_service/logs/app.log

6. API 响应结果区
展示：
- Status
- Response JSON
- 当 status >= 500 时，显示红色提示：
  “服务端已生成 traceback。请运行 python scripts/watch_once.py 扫描并生成 Incident。”

视觉要求：
- 页面最大宽度 1200px，居中。
- 背景浅灰。
- 卡片白底、圆角、轻微阴影。
- 表格要像后台系统，不要只显示按钮。
- 使用简洁配色，避免奇怪水印和无关装饰。
- 页面加载后不应空白。

验收要求：
请新增测试，读取 GET / 的 HTML，断言必须包含：
- 今日工单
- P1 紧急工单
- SLA 风险工单
- 工单队列
- 服务运行状态
- 最近事件流
- Agent 接入
- Black-box Log Watcher
- TK-1024
- 创建带 +08:00 SLA 的紧急工单

如果这些关键词缺失，pytest -q 必须失败。

============================================================
三、修复 Feishu 冒烟测试
============================================================

当前 send_test_feishu_card.py 只输出 Mock，说明配置不完整或未加载。

请修复：

1. scripts/check_env.py
输出格式必须清楚：

[Feishu]
FEISHU_APP_ID      OK
FEISHU_APP_SECRET  OK
FEISHU_CHAT_ID     MISSING

[GitHub]
GITHUB_TOKEN       OK
GITHUB_OWNER       OK
GITHUB_REPO        OK
GITHUB_BASE_BRANCH OK

[Ark]
ARK_API_KEY        OK
ARK_MODEL_REPAIR   OK
ARK_MODEL_SUMMARY  OK

Summary:
Feishu ready: no
GitHub ready: yes
Ark ready: yes

不得打印真实密钥，只显示 OK/MISSING。

2. scripts/send_test_feishu_card.py
必须先调用配置检查，输出当前模式：

Feishu mode: real
或
Feishu mode: mock，reason: missing FEISHU_CHAT_ID

3. Feishu adapter
修复 send_incident_card：
- 配置完整时必须尝试真实调用。
- 配置缺失时才 mock。
- 真实调用失败时输出 HTTP status、Feishu code/msg，但不要泄露 token。
- 不要出现重复打印 Mock Feishu Card 的问题。
- 检查是否存在重复 print、重复 logger handler、重复调用 send_incident_card。
- send_test_feishu_card.py 单次运行只能输出一张 mock 或一条真实发送结果，不能重复三次。

4. 飞书真实发送逻辑
调用方式：
- 先通过 FEISHU_APP_ID / FEISHU_APP_SECRET 获取 tenant_access_token。
- 再 POST 到 /im/v1/messages?receive_id_type=chat_id。
- receive_id 使用 FEISHU_CHAT_ID。
- msg_type 可以先用 text，确认成功后再用 interactive card。
- content 必须是 JSON 字符串。

5. 新增 scripts/feishu_token_test.py
只测试获取 tenant_access_token。
输出：
- token acquired: yes/no
- expire: xxx
- error code/msg
不要打印 token。

6. 新增 scripts/feishu_send_text_test.py
只发送一条最简单的 text 消息：
“AutoRepair Feishu text smoke test.”
用它验证最小链路。
这个脚本比卡片更容易排查问题。

============================================================
四、修复 GitHub 冒烟测试
============================================================

当前 GitHub mock 可以跑，但真实模式不清晰。

请修复 scripts/github_smoke_test.py：

1. 先输出模式：
GitHub mode: real
或
GitHub mode: mock，reason: missing GITHUB_TOKEN

2. 真实模式下：
- 创建 issue
- 添加 label：autorepair:smoke-test
- 添加评论：AutoRepair GitHub smoke test completed.
- 输出 issue number 和 html_url

3. 如果 label 不存在：
- 自动创建 label autorepair:smoke-test
- 再添加 label
- 如果创建 label 失败，提示原因，但不要中断 issue 创建和评论流程。

4. mock 模式下：
- 写入 mock_github_issues.jsonl
- 添加 mock label
- 添加 mock comment
- watch_github_issues_once.py 必须能读到 mock issue。

5. 新增测试：
- mock 创建 issue 后能被 list_open_bug_issues 读到。
- mock comment 后 comments 非空。
- mock add label 后 labels 包含 autorepair:smoke-test。
- 真实 API 不在 pytest 中调用，必须 monkeypatch。

============================================================
五、修复 watch_once 旧日志污染问题
============================================================

当前 watch_once.py 会扫到很多历史 incident，演示不干净。

请修改 scripts/reset_demo_state.py：
- 清空 demo_service/logs/app.log
- 删除 incidents.jsonl
- 删除 watch_state.json
- 删除 audit_events.jsonl
- 删除 repair_plans.jsonl 如存在
- 删除 mock_github_issues.jsonl
- 删除 mock_github_issue_comments.jsonl
- 打印清理列表

请确认 README 的演示步骤必须先运行：
python scripts/reset_demo_state.py

然后再触发新 Bug，再 watch_once。

============================================================
六、README 更新
============================================================

更新 README，加入“真实 API 排查顺序”：

1. 检查环境：
python scripts/check_env.py

2. 测飞书 token：
python scripts/feishu_token_test.py

3. 测飞书文本：
python scripts/feishu_send_text_test.py

4. 测飞书卡片：
python scripts/send_test_feishu_card.py

5. 测 GitHub：
python scripts/github_smoke_test.py

6. 启动业务服务：
python scripts/run_demo_server.py

7. 触发 Runtime Bug：
浏览器点击“创建带 +08:00 SLA 的紧急工单”

8. 扫描：
python scripts/watch_once.py

README 必须说明：
- Mock mode 是演示降级，不代表真实 API 成功。
- 最终录屏应尽量使用 real Feishu 和 real GitHub。
- Stage 2F-Fix 仍不调用 LLM、不自动修复、不创建 PR。

============================================================
七、测试要求
============================================================

pytest -q 必须通过。

新增测试至少覆盖：
1. 首页 HTML 包含完整业务系统关键词。
2. check_env 不泄露密钥。
3. 缺少 Feishu 配置时明确输出 mock reason。
4. send_test_feishu_card 单次运行不会重复打印三张卡片。
5. mock GitHub issue 可以创建、读取、评论、加 label。
6. reset_demo_state 会清理所有 records 文件。
7. pytest -q -m agent_target 仍然失败，不要修复预埋 Bug。

============================================================
八、输出要求
============================================================

完成后请输出：

1. 新增/修改文件列表。
2. 新首页包含的模块。
3. pytest -q 结果。
4. pytest -q -m agent_target 结果。
5. python scripts/check_env.py 示例输出。
6. python scripts/feishu_token_test.py 示例输出。
7. python scripts/feishu_send_text_test.py 示例输出。
8. python scripts/send_test_feishu_card.py 示例输出。
9. python scripts/github_smoke_test.py 示例输出。
10. 明确说明：
   - UI 已按关键词测试约束实现
   - Feishu 当前是 real 还是 mock
   - GitHub 当前是 real 还是 mock
   - 未接入 LLM
   - 未修复 Bug
   - 未创建 PR