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

## 🚀 Stage 2A 演示流程
Stage 2A 实现了极简Demo UI + Incident Watcher本地闭环，无需接入外部服务即可演示完整异常监控链路。

### 1. 启动Demo服务
```bash
python scripts/run_demo_server.py
```
服务将运行在 http://127.0.0.1:8000

### 2. 打开浏览器访问Demo UI
访问 http://127.0.0.1:8000/
页面提供三个功能按钮：
- 健康检查：测试服务是否正常
- 查询正常用户：查询u_1001用户信息（返回200）
- 触发 Bug：访问不存在的用户，触发预埋的TypeError（返回500）

### 3. 触发异常
点击页面上的「触发 Bug」按钮，服务会返回500错误，同时生成完整Traceback日志。

### 4. 扫描日志生成Incident
另开终端执行：
```bash
python scripts/watch_once.py
```
如果发现新的异常，会输出Incident ID、错误类型、位置等信息；如果没有新异常则显示"No new incident"。

> 同一个错误只会生成一次Incident，基于指纹自动去重。

### 5. 查看Incident记录
所有异常记录保存在：
```
autorepair/records/incidents.jsonl
```
一行一个JSON格式的Incident对象。

### 6. 飞书通知（可选）
如果在`.env`中配置了完整的飞书参数（FEISHU_APP_ID、FEISHU_APP_SECRET、FEISHU_CHAT_ID），扫描到新异常时会自动发送飞书告警卡片；配置不完整时会在控制台打印模拟卡片内容。

### 一键演示脚本
```bash
python scripts/run_stage2_demo.py
```
按照脚本提示操作即可完成完整演示流程。
