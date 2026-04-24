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

## 🚀 Stage 2B 演示流程
Stage 2B 支持两类问题入口：本地运行时异常 + GitHub Issue Bug反馈，实现完整的异常发现→生成Incident→通知闭环。

---

### 🔹 路线 A：本地日志触发
适合演示服务运行时异常场景

#### 1. 启动Demo服务
```bash
python scripts/run_demo_server.py
```
服务将运行在 http://127.0.0.1:8000

#### 2. 打开浏览器访问业务控制台
访问 http://127.0.0.1:8000/
页面提供四个业务功能按钮：
- 健康检查：查询服务运行状态
- 查询正常用户画像：查询用户ID u_1001 的信息（返回200）
- 查询缺失用户画像：Demo: 会触发 TypeError 异常（返回500）
- 提交异常订单：Demo: 会触发 ZeroDivisionError 异常（返回500）

#### 3. 触发异常
点击「查询缺失用户画像」或「提交异常订单」按钮，服务会返回500错误，同时生成完整Traceback日志。

#### 4. 扫描日志生成Incident
另开终端执行：
```bash
python scripts/watch_once.py
```
如果发现新的异常，会输出Incident ID、错误类型、位置等信息；如果没有新异常则显示"No new incident"。

> 同一个错误只会生成一次Incident，基于指纹自动去重。

---

### 🔹 路线 B：GitHub Issue 触发
适合演示外部Bug反馈场景

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
一行一个JSON格式的Incident对象。

#### 飞书通知（可选）
如果在`.env`中配置了完整的飞书参数（FEISHU_APP_ID、FEISHU_APP_SECRET、FEISHU_CHAT_ID），会自动发送飞书告警卡片；配置不完整时会在控制台打印模拟卡片内容。

---

### 📌 项目结构说明
- 当前为monorepo结构：Agent代码和demo_service在同一个仓库
- 初赛阶段不使用submodule
- 生产版本可将target_repo配置为独立业务仓库，与Agent代码分离

### 🎯 测试说明
- 默认测试全部通过：`pytest -q`
- 两个Agent修复目标测试预期失败：`pytest -q -m agent_target`
  - 用户画像缺失异常：预期返回404，当前返回500
  - 订单金额为0异常：预期返回400，当前返回500
- 不要手动修复预埋Bug，留待后续阶段Agent自动修复
