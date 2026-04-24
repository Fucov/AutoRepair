# Stage 1：最小可运行底座与可复现故障服务

## 阶段目标
实现一个本地 FastAPI Demo Web 服务，内置可稳定触发的 Python Bug，提供基础日志、测试和最小日志解析工具，作为后续 Agent 自动修复的底座。

## 功能范围
### 已实现
1. **Demo 服务**：FastAPI 服务，提供 /health 和 /users/{user_id}/profile 接口
2. **预埋 Bug**：用户不存在时直接访问 None 对象属性，触发 TypeError
3. **异常日志**：自动捕获异常并写入完整 Traceback 到日志文件
4. **基础配置**：项目配置、日志路径等基础配置项
5. **数据结构**：Incident 基础 Schema 定义
6. **日志解析工具**：读取最新 Traceback 的工具函数
7. **辅助脚本**：启动服务、触发 Bug、查看 Traceback 的命令行脚本
8. **测试用例**：
   - 基础功能测试（默认全部通过）
   - 故意失败的 Agent 修复目标测试

## 不做什么
本阶段不实现以下内容：
- 飞书 SDK、GitHub SDK、LLM SDK
- 自动修复、PR 创建、CI/CD 集成
- 数据库、Redis、Docker 等重型依赖
- 前端界面、多服务支持、多语言支持
- 任何超出最小可运行底座的功能

## 项目结构
```
FeishuAutoRepair/
├── autorepair/                 # 自动修复核心模块
│   ├── __init__.py
│   ├── config.py              # 配置文件
│   ├── schemas.py             # 数据结构定义
│   └── log_parser.py          # 日志解析工具
├── demo_service/              # 演示故障服务
│   ├── __init__.py
│   ├── app.py                 # FastAPI 应用入口
│   ├── logging_config.py      # 日志配置
│   ├── repository.py          # 数据层
│   ├── service.py             # 业务逻辑层（预埋 Bug）
│   ├── logs/                  # 日志目录
│   └── tests/                 # 测试用例
│       ├── test_health.py
│       ├── test_profile_success.py
│       └── test_profile_contract.py  # Agent 修复目标测试
├── scripts/                   # 辅助脚本
│   ├── run_demo_server.py
│   ├── trigger_demo_bug.py
│   └── print_latest_traceback.py
├── docs/                      # 文档
│   └── stage1_task_definition.md
├── .env.example               # 环境变量示例
├── .gitignore
├── pyproject.toml             # 项目配置
└── README.md
```

## Demo 服务说明
- **GET /health**：健康检查接口，返回 {"status": "ok"}
- **GET /users/{user_id}/profile**：查询用户 Profile 接口
  - 正常用户：u_1001（Alice）、u_1002（Bob）返回正确数据
  - 不存在用户：触发 TypeError 异常，返回 500

## 预埋 Bug 说明
在 `demo_service/service.py` 的 `build_user_profile` 函数中，故意不对 `get_user_by_id` 返回的 None 做判断，直接访问 `user["id"]` 等属性，当用户不存在时触发：
```
TypeError: 'NoneType' object is not subscriptable
```
**注意：本阶段不要修复该 Bug，它是后续 Agent 自动修复的目标。**

## 日志说明
- 日志路径：`demo_service/logs/app.log`
- 日志内容：包含请求方法、路径、完整 Traceback
- 自动创建：日志目录不存在时会自动创建

## 测试说明
### 默认测试（pytest -q）
- 运行 `test_health.py` 和 `test_profile_success.py`
- 预期全部通过

### Agent 修复目标测试（pytest -q -m agent_target）
- 运行 `test_profile_contract.py`
- 测试期望：不存在的用户返回 404 和 "User not found" 响应
- 本阶段预期：测试失败（返回 500）

## 验收标准
1. `pip install -e ".[dev]"` 安装成功
2. `python scripts/run_demo_server.py` 成功启动服务
3. `python scripts/trigger_demo_bug.py` 返回 500
4. `python scripts/print_latest_traceback.py` 能打印完整 TypeError Traceback
5. `pytest -q` 全部通过
6. `pytest -q -m agent_target` 测试失败
