你现在继续开发 FeishuAutoRepair 项目。

当前项目已经完成 Stage 2E：
1. demo_service 是被监控目标服务，业务场景为 Acme SupportDesk Lite。
2. AutoRepair Agent 已通过 autorepair/config/services.yaml 与 demo_service 解耦。
3. watcher 支持基于服务配置扫描日志。
4. diagnostics.py 已实现基础诊断。
5. audit_store.py 已实现审计记录。
6. Feishu adapter 和 GitHub adapter 都已有真实 API 与 Mock 降级能力。
7. 当前没有接入 LLM，没有自动修复，没有创建 PR。
8. pytest -q 通过，pytest -q -m agent_target 预期失败。
9. 不要修复任何预埋 Bug。

现在请完成 Stage 2F：真实 Feishu / GitHub 冒烟测试 + Demo UI 最后收口。

本阶段目标：
1. 让 Demo UI 看起来更像真实企业工单系统，但仍保持原生 HTML/CSS/JS，不引入前端框架。
2. 增加 Feishu 真实发送冒烟测试脚本。
3. 增加 GitHub 真实 Issue 冒烟测试脚本。
4. 增加环境变量检查脚本，方便演示前检查配置。
5. 保持系统小而美，为下一阶段 Doubao 分析做准备。

重要约束：
- 不要接入 LLM。
- 不要自动修复代码。
- 不要创建 PR。
- 不要修复任何 agent_target 测试对应的预埋 Bug。
- 不要引入 React/Vue。
- 不要引入数据库。
- 不要泄露 .env 中任何真实密钥。
- pytest -q 必须通过。
- pytest -q -m agent_target 仍然应该失败。

## 一、Demo UI 最后收口

请检查 demo_service/app.py 的首页 HTML。

当前截图仍然像按钮面板，不够像真实业务系统。请改成一个更真实但轻量的 SupportDesk 控制台。

页面必须包含：

1. 顶部统计卡片区域：
- 今日工单：128
- P1 紧急工单：7
- SLA 风险工单：3
- 飞书渠道占比：64%

2. 主操作区：
- 系统健康检查
- 提交正常 P2 工单
- 提交带 +08:00 SLA 的紧急工单（触发时区 Bug）
- 重复提交同一飞书事件（模拟幂等性缺陷）

3. 工单列表区：
展示 5 条 mock 工单，字段包括：
- 工单编号
- 客户
- 来源渠道
- 优先级
- SLA 截止时间
- 处理人
- 状态

4. 最近事件流：
展示 4 条 mock 事件：
- 飞书渠道收到客户反馈
- P1 工单进入 SLA 风险
- AutoRepair 正在监听服务日志
- 最近一次异常将写入 demo_service/logs/app.log

5. 响应结果区：
展示 status code 和 response body。
当 status >= 500 时显示提示：
“后台已生成 traceback，可运行 python scripts/watch_once.py 扫描并生成 Incident。”

要求：
- 只使用原生 HTML/CSS/JS。
- 不引入构建工具。
- 不引入 React/Vue。
- UI 只用于模拟被监控业务系统，不要把 Agent 管理功能塞进这个页面。
- 页面风格干净专业，不要奇怪水印、无关装饰。

## 二、环境变量检查脚本

新增：

scripts/check_env.py

功能：
检查以下配置是否存在：

Feishu:
- FEISHU_APP_ID
- FEISHU_APP_SECRET
- FEISHU_CHAT_ID

GitHub:
- GITHUB_TOKEN
- GITHUB_OWNER
- GITHUB_REPO
- GITHUB_BASE_BRANCH

Ark:
- ARK_API_KEY
- ARK_MODEL_REPAIR
- ARK_MODEL_SUMMARY

输出要求：
- 不要打印真实密钥。
- 只输出 OK / MISSING。
- 对密钥只显示前后少量字符，例如 ark_****abcd，或者完全不显示。
- 最后给出 summary：
  - Feishu ready: yes/no
  - GitHub ready: yes/no
  - Ark ready: yes/no

不要因为缺少配置就报错退出，除非用户传入 --strict。

## 三、Feishu 冒烟测试脚本

新增：

scripts/send_test_feishu_card.py

功能：
1. 构造一个假的 Incident，service_name=Acme SupportDesk Lite。
2. error_type=SmokeTest。
3. message=Feishu integration smoke test。
4. 调用现有 send_incident_card。
5. 如果配置完整，应真实发送到飞书。
6. 如果配置缺失，应输出 Mock Feishu Card。
7. 不要泄露 token。

输出：
- Feishu card sent successfully
或
- Feishu config missing, fallback to mock card

要求：
- 复用现有 autorepair/adapters/feishu.py。
- 不要重复实现 token 获取逻辑。

## 四、GitHub 冒烟测试脚本

新增：

scripts/github_smoke_test.py

功能：
1. 调用现有 GitHub adapter 创建一个演示 Issue。
2. Issue 标题：
[SmokeTest] AutoRepair GitHub integration
3. Issue body：
说明这是 AutoRepair 的 GitHub API 冒烟测试。
4. 创建后调用 list_open_bug_issues 或对应扫描函数确认能扫描到。
5. 调用 comment_issue 添加评论：
AutoRepair GitHub smoke test completed.
6. 调用 add_labels 添加 label：
autorepair:smoke-test
7. 如果 GitHub 配置缺失，则走 Mock Issue Store，也必须能完整演示创建、扫描、评论、加 label。

输出：
- issue_number
- issue_url 或 mock issue ref
- comment result
- label result

注意：
- 不要关闭 Issue。
- 不要创建 PR。
- 不要修改代码。
- 如果真实 GitHub label 不存在导致 add_labels 失败，可以友好提示，不中断整个测试。

## 五、README 更新

更新 README，新增 Stage 2F 说明。

增加演示路径：

1. 检查环境：
python scripts/check_env.py

2. 启动业务服务：
python scripts/run_demo_server.py

3. 打开 UI：
http://127.0.0.1:8000/

4. 触发运行时异常：
点击“提交带 +08:00 SLA 的紧急工单”

5. 扫描日志：
python scripts/watch_once.py

6. 测试飞书发送：
python scripts/send_test_feishu_card.py

7. 测试 GitHub Issue：
python scripts/github_smoke_test.py

说明：
- Stage 2F 仍不调用 LLM。
- Stage 2F 仍不自动修复。
- Stage 2F 仍不创建 PR。
- 下一阶段 Stage 3A 会接入 Doubao 生成根因分析和修复计划。

## 六、测试

新增或更新 pytest，确保 pytest -q 通过。

至少测试：
1. check_env 能在缺失环境变量时输出 missing，但不泄露密钥。
2. send_test_feishu_card 在缺少 Feishu 配置时走 mock，不报错。
3. github_smoke_test 在缺少 GitHub 配置时走 mock issue store。
4. 首页 HTML 包含“今日工单”“SLA 风险工单”“工单列表”“最近事件流”等关键字。
5. pytest -q -m agent_target 仍然失败，不要修复预埋 Bug。

测试不要真实调用飞书或 GitHub，使用 monkeypatch。

## 七、输出要求

完成后请输出：
1. 新增/修改文件列表。
2. pytest -q 结果。
3. pytest -q -m agent_target 结果。
4. 新 UI 包含哪些业务模块。
5. check_env.py 示例输出。
6. send_test_feishu_card.py 示例输出。
7. github_smoke_test.py 示例输出。
8. 明确说明没有接入 LLM、没有修复 Bug、没有创建 PR。