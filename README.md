# FeishuAutoRepair：基于 Agent 的服务自动化修复系统

## 项目简介
本项目是飞书比赛参赛项目，实现了一个能够自动监控服务异常、通过 LLM 分析 Traceback、自动修复代码并提交 PR 的完整链路。

## Stage 1 当前能力
✅ 最小可运行 FastAPI Demo 服务
✅ 预埋可稳定触发的 Python Bug
✅ 完整异常 Traceback 日志记录
✅ pytest 测试框架配置
✅ 最小日志解析工具
❌ 飞书 API、GitHub API、LLM Agent、自动修复、PR 创建等后续能力尚未实现

## 快速开始
### 1. 安装依赖
```bash
pip install -e ".[dev]"
```

### 2. 启动 Demo 服务
```bash
python scripts/run_demo_server.py
```
服务将运行在 http://127.0.0.1:8000

### 3. 正常请求测试
```bash
curl http://127.0.0.1:8000/health
# 返回: {"status": "ok"}

curl http://127.0.0.1:8000/users/u_1001/profile
# 返回: {"id": "u_1001", "name": "Alice", "role": "developer"}
```

### 4. 触发预埋 Bug
```bash
# 另开终端执行
python scripts/trigger_demo_bug.py
# 输出 Status Code: 500，Response: {"detail":"Internal Server Error"}
```

### 5. 查看最新 Traceback
```bash
python scripts/print_latest_traceback.py
```
将打印出完整的 TypeError: 'NoneType' object is not subscriptable 错误栈。

### 6. 运行默认测试
```bash
pytest -q
```
默认排除 Agent 修复目标测试，应当全部通过。

### 7. 运行 Agent 修复目标测试（当前故意失败）
```bash
pytest -q -m agent_target
```
该测试期望不存在的用户返回 404，当前由于预埋 Bug 会返回 500，所以测试失败，作为后续 Agent 自动修复的目标。

⚠️ 注意：
- agent_target 测试失败是**预期行为**，不要为了通过测试而手动修复预埋 Bug
- 该失败测试是后续阶段 Agent 自动修复的唯一目标
- 预埋 Bug 位于 `demo_service/service.py` 的 `build_user_profile` 函数中

## 技术栈
- Python 3.12+
- FastAPI
- Uvicorn
- Pydantic
- pytest
- httpx

## 🚀 Stage 2C 演示流程
Stage 2C 实现鲁棒 Incident Pipeline，支持增量日志扫描、重复错误聚合、避免重复通知，适合演示完整的异常监控流程。

---

### 完整演示步骤
#### 1. 清理演示状态
每次演示前先重置状态，避免历史数据干扰：
```bash
python scripts/reset_demo_state.py
```
会清空日志、Incident记录和监控偏移量。

#### 2. 启动Demo服务
```bash
python scripts/run_demo_server.py
```
服务将运行在 http://127.0.0.1:8000

#### 3. 打开浏览器访问业务控制台
访问 http://127.0.0.1:8000/
页面提供四个业务功能按钮：
- 系统健康检查：查询服务运行状态
- 查询正常员工画像：查询员工ID u_1001 的信息（返回200）
- 查询缺失员工画像：Demo: 会触发 TypeError 异常（返回500）
- 提交 0 元异常订单：Demo: 会触发 ZeroDivisionError 异常（返回500）

#### 4. 连续触发多个异常
依次点击以下按钮各2次：
- 查询缺失员工画像（点击2次）
- 提交 0 元异常订单（点击2次）

共触发4次异常请求，服务会返回500错误，同时生成完整Traceback日志。

#### 5. 扫描新增日志生成Incident
另开终端执行：
```bash
python scripts/watch_once.py
```

**预期输出：**
```
[created] INC-20240501-120000-xxxxxx TypeError demo_service/service.py:11 occurrence_count=2
[created] INC-20240501-120000-yyyyyy ZeroDivisionError demo_service/order_service.py:16 occurrence_count=2
```
- 相同错误被自动聚合，4次异常只生成2个Incident
- occurrence_count分别为2，表示每个错误各发生2次
- 只有首次创建的Incident会发送飞书卡片，重复错误不重复通知（避免刷屏）

#### 6. 再次运行扫描
```bash
python scripts/watch_once.py
```
**预期输出：**
```
No new incident.
```
没有新增日志，不会重复处理。

---

### 🔹 GitHub Issue 触发路线（可选）
#### 1. 创建演示Bug Issue
```bash
# 可选scenario_id: user-missing-profile / order-zero-division
python scripts/create_demo_issue.py order-zero-division
```
- 配置完整时会真实创建GitHub Issue
- 配置缺失时会在控制台打印Mock Issue内容

#### 2. 扫描GitHub Issue
```bash
python scripts/watch_github_issues_once.py
```
- 自动识别未处理的Bug Issue
- 生成对应Incident写入本地记录
- 标记Issue为处理中并添加评论
- 发送飞书通知或Mock通知

---

### 通用操作
#### 查看所有Incident记录
所有异常记录保存在：
```
autorepair/records/incidents.jsonl
```
包含occurrence_count、first_seen_at、last_seen_at、source_refs等聚合字段。

#### 飞书通知（可选）
如果在`.env`中配置了完整的飞书参数（FEISHU_APP_ID、FEISHU_APP_SECRET、FEISHU_CHAT_ID），只有**首次创建**的Incident会发送飞书告警卡片；重复错误不会重复发送通知，避免刷屏。配置不完整时会在控制台打印模拟卡片内容。

---

### 📌 项目结构说明
- 当前为monorepo结构：Agent代码和demo_service在同一个仓库
- 初赛阶段不使用submodule
- 生产版本可将target_repo配置为独立业务仓库，与Agent代码分离

### 🎯 测试说明
- 默认测试全部通过：`pytest -q`（新增功能测试已覆盖，共10+测试用例）
- 两个Agent修复目标测试预期失败：`pytest -q -m agent_target`
  - 用户画像缺失异常：预期返回404，当前返回500
  - 订单金额为0异常：预期返回400，当前返回500
- 不要手动修复预埋Bug，留待后续阶段Agent自动修复

---

## 🚀 Stage 2D 演示流程
Stage 2D 升级为更贴近企业研发协作的「Acme SupportDesk Lite 工单与 SLA 服务」场景，补齐 Mock GitHub Issue 离线闭环，优化演示体验。

### 🎯 演示路线 A：运行时异常场景
#### 1. 清理演示状态
```bash
python scripts/reset_demo_state.py
```
会清空日志、Incident记录、监控偏移量和Mock GitHub Issue记录。

#### 2. 启动Demo服务
```bash
python scripts/run_demo_server.py
```
服务将运行在 http://127.0.0.1:8000

#### 3. 打开浏览器访问业务控制台
访问 http://127.0.0.1:8000/
页面包含：
- 🔥 主线工单场景（4个按钮）
  - 系统健康检查
  - 提交正常 P2 工单
  - 提交带 +08:00 SLA 的紧急工单（触发时区 Bug）
  - 重复提交同一幂等键工单（模拟业务缺陷）
- 📦 Legacy Bug 场景（原有2个Bug）

#### 4. 触发时区Bug
点击「提交带 +08:00 SLA 的紧急工单」按钮，会返回500错误。

#### 5. 扫描日志生成Incident
另开终端执行：
```bash
python scripts/watch_once.py
```

**预期输出：**
```
============================================================
📊 Scan Summary
============================================================
- Created incidents: 1
- Updated occurrences: 0
- Feishu cards sent: 1
============================================================

Details:
[created] INC-xxxxxx TypeError demo_service/ticket_service.py:23 occurrence_count=1
```
- 生成TypeError Incident，错误信息包含"can't compare offset-naive and offset-aware datetimes"
- 飞书真实通知或控制台打印Mock卡片

---

### 🎯 演示路线 B：GitHub Issue 离线闭环场景
#### 1. 清理演示状态
```bash
python scripts/reset_demo_state.py
```

#### 2. 创建Mock GitHub Issue
即使没有真实GitHub Token，也可以完整演示：
```bash
python scripts/create_demo_issue.py ticket-idempotency-duplicate
```
会在控制台打印Mock Issue内容，并写入本地mock_github_issues.jsonl。

#### 3. 扫描GitHub Issue
```bash
python scripts/watch_github_issues_once.py
```

**预期输出：**
- 从本地mock文件发现刚创建的Issue
- 生成source=github_issue的Incident
- 写入incidents.jsonl
- 输出Mock飞书卡片
- Mock Issue被添加processing标签和评论

---

### 📌 测试说明
- 默认测试全部通过：`pytest -q`（新增ticket模块测试，共12+测试用例）
- 四个Agent修复目标测试预期失败：`pytest -q -m agent_target`
  1. 用户画像缺失异常：预期返回404，当前返回500
  2. 订单金额为0异常：预期返回400，当前返回500
  3. 带时区SLA工单创建：预期成功，当前返回500
  4. 重复幂等键提交：预期返回同一工单，当前创建多个
- 所有预埋Bug均未修复，留待后续阶段Agent自动修复
