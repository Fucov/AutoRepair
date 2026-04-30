# FeishuAutoRepair 技术白皮书

## 基于 Agent 的服务自动化修复系统

---

## 目录

1. [项目概述](#1-项目概述)
2. [系统架构](#2-系统架构)
3. [核心模块详解](#3-核心模块详解)
4. [数据模型](#4-数据模型)
5. [工作流设计](#5-工作流设计)
6. [安全与权限控制](#6-安全与权限控制)
7. [技术栈](#7-技术栈)
8. [部署与运行](#8-部署与运行)
9. [扩展性设计](#9-扩展性设计)
10. [总结](#10-总结)

---

## 1. 项目概述

### 1.1 背景与目标

FeishuAutoRepair 是一个面向「基于 Agent 的服务自动化修复系统」的完整实现。系统旨在监控 Web 服务的运行状态，自动捕获异常日志和 Traceback 信息，通过 LLM（大型语言模型）分析根因，在受限沙箱环境中生成修复代码，经测试验证后自动创建 Pull Request，并通过飞书消息卡片和多维表格实现通知、记录和审计。

核心目标：
- **自动化**：从异常发现到修复 PR 创建的全链路自动化
- **安全性**：沙箱隔离、权限控制、人工审核机制
- **可观测性**：完整的审计日志和状态追踪
- **可集成性**：飞书、GitHub、LLM 三大生态的无缝集成

### 1.2 设计原则

1. **最小权限原则**：Agent 仅具备 Read Log、Read Code、Run Test、Git Commit 四类工具权限
2. **安全隔离**：所有代码修改在独立 worktree 中进行，禁止直接 push main/master，禁止自动 merge
3. **可追溯性**：每个操作都有审计记录，包含 incident_id、修复摘要、测试结果、commit/PR 链接
4. **渐进式修复**：通过 Triage → Policy Gate → Repair Job → PR 的多阶段验证，确保修复质量
5. **Mock 优先**：所有外部依赖（飞书、GitHub）均支持 Mock 模式，便于开发和演示

---

## 2. 系统架构

### 2.1 整体架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                        触发源 (Sources)                          │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────────┐    │
│  │  本地日志文件  │  │ GitHub Issue │  │  飞书消息卡片回调    │    │
│  └──────┬───────┘  └──────┬───────┘  └────────┬───────────┘    │
└─────────┼─────────────────┼──────────────────┼──────────────────┘
          │                 │                  │
          ▼                 ▼                  ▼
┌─────────────────────────────────────────────────────────────────┐
│                    监控与收集层 (Watcher)                         │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  Log Parser → Watch State → Incident Store              │    │
│  │  • 增量日志扫描 • 错误指纹去重 • 重复错误聚合              │    │
│  └─────────────────────────────────────────────────────────┘    │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                    分析诊断层 (Triage Agent)                      │
│  ┌────────────┐  ┌────────────┐  ┌──────────────────────────┐  │
│  │ Evidence   │→ │ Policy     │→ │ Decision Schema          │  │
│  │ Collector  │  │ Gate       │  │ (auto_fix/need_info/     │  │
│  └────────────┘  └────────────┘  │  escalate/human_required)│  │
│                                   └──────────────────────────┘  │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                    修复编排层 (Repair Orchestrator)               │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────────┐    │
│  │ Git          │→ │ Job          │→ │ Repo               │    │
│  │ Workspace    │  │ Store        │  │ Lock               │    │
│  │ (worktree)   │  │ (状态管理)    │  │ (并发控制)          │    │
│  └──────────────┘  └──────────────┘  └────────────────────┘    │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                    通知与集成层 (Adapters)                        │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────────┐    │
│  │ Feishu       │  │ GitHub       │  │ LLM (ARK)          │    │
│  │ Adapter      │  │ Adapter      │  │ Adapter            │    │
│  │ • 消息卡片    │  │ • Issue/PR   │  │ • 代码修复生成      │    │
│  │ • 模板变量    │  │ • 标签管理    │  │ • 根因分析          │    │
│  └──────────────┘  └──────────────┘  └────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 模块职责划分

| 模块 | 职责 | 关键文件 |
|------|------|----------|
| **Watcher** | 日志监控、异常检测、Incident 创建 | `watcher.py`, `log_parser.py`, `watch_state.py` |
| **Incident Store** | Incident 持久化、指纹去重、聚合更新 | `incident_store.py` |
| **Triage Agent** | 证据收集、政策门控、决策生成 | `agent/triage/` 目录 |
| **Repair Orchestrator** | 修复工作流编排、Git 隔离、任务管理 | `repair/orchestrator.py`, `repair/git_workspace.py` |
| **Job Store** | 修复任务状态管理、持久化 | `repair/job_store.py` |
| **Adapters** | 飞书、GitHub、LLM 外部服务集成 | `adapters/feishu.py`, `adapters/github.py` |
| **Cards** | 飞书消息卡片变量构造 | `cards/variables.py` |
| **Audit Store** | 审计日志记录 | `audit_store.py` |
| **Demo Service** | 模拟业务服务、预埋 Bug | `demo_service/` 目录 |

---

## 3. 核心模块详解

### 3.1 日志监控与 Incident 管理

#### 3.1.1 日志解析器 (`log_parser.py`)

**功能**：
- 从日志文件中提取完整的 Traceback 内容
- 解析错误类型、错误消息、可疑文件和行号
- 生成错误指纹（fingerprint）用于去重

**实现细节**：
```python
# 核心函数
read_latest_traceback(log_path)          # 读取最新 Traceback
extract_error_summary(traceback_text)    # 提取错误摘要
extract_traceback_blocks(new_text)       # 批量提取 Traceback
read_new_log_text(log_path, offset)      # 增量读取新日志
```

**指纹生成算法**：
```python
fingerprint = hashlib.md5(
    f"{error_type}|{suspected_file}|{line_no}".encode()
).hexdigest()[:12]
```
指纹由错误类型、文件和行号组成，确保相同位置的相同错误被聚合。

#### 3.1.2 监控状态管理 (`watch_state.py`)

**功能**：
- 记录每个日志文件的读取偏移量
- 支持日志轮转检测（文件截断自动重置偏移量）
- 增量扫描避免重复处理

**数据结构**：
```json
{
  "log_offsets": {
    "/absolute/path/to/app.log": {
      "offset": 12345,
      "size": 67890
    }
  }
}
```

#### 3.1.3 Incident 存储 (`incident_store.py`)

**功能**：
- JSONL 格式的 Incident 持久化存储
- 基于指纹的新增/更新（upsert）操作
- 重复错误聚合：增加 `occurrence_count`，更新 `last_seen_at`

**核心操作**：
```python
append_incident(incident)                          # 追加新 Incident
upsert_incident_by_fingerprint(incident)           # 指纹去重更新
has_fingerprint(fingerprint)                       # 指纹存在性检查
load_incidents()                                   # 加载所有 Incident
```

### 3.2 Triage Agent（诊断代理）

#### 3.2.1 证据收集器 (`evidence_collector.py`)

**功能**：
从 Incident 中提取结构化证据，包括：
- Runtime Traceback：完整的错误堆栈
- Error Summary：错误类型和消息摘要
- GitHub Issue：关联的 Issue 链接

**证据结构**：
```python
class Evidence:
    label: str           # 证据类型标签
    detail: str          # 证据详情
    file: str | None     # 相关文件
    line: int | None     # 相关行号
    command: str | None  # 相关命令
    sha: str | None      # Git SHA
```

#### 3.2.2 政策门控 (`policy_gate.py`)

**功能**：
判断 Incident 是否适合自动修复，基于以下规则：

| 检查项 | 规则 |
|--------|------|
| Decision Type | 必须为 `auto_fix` |
| Confidence | 必须为 `high` |
| Evidence | 必须提供至少一条证据 |
| Fix Plan | 必须包含修复计划 |
| Human Approval | 不要求人工审批 |
| Risk Keywords | 不包含 security/payment/permission 等高风险词汇 |

**高风险关键词**：
```python
HIGH_RISK_KEYWORDS = {
    "security", "payment", "permission", 
    "data_loss", "delete", "remove"
}
```

#### 3.2.3 决策 Schema (`decision_schema.py`)

**决策类型**：
```python
class DecisionEnum(str, Enum):
    auto_fix = "auto_fix"              # 自动修复
    propose_fix = "propose_fix"        # 提出修复方案
    need_info = "need_info"           # 需要更多信息
    duplicate = "duplicate"            # 重复问题
    cannot_reproduce = "cannot_reproduce"  # 无法复现
    config_error = "config_error"      # 配置错误
    external_dependency = "external_dependency"  # 外部依赖问题
    keep_open = "keep_open"           # 保持开放
    escalate = "escalate"             # 升级处理
```

**决策对象结构**：
```python
class Decision:
    decision: DecisionEnum             # 决策类型
    confidence: ConfidenceEnum         # 置信度 (high/medium/low)
    severity: SeverityEnum             # 严重等级 (p0/p1/p2/p3)
    incident_type: IncidentTypeEnum    # 事件类型
    summary: str                       # 摘要
    root_cause_hypothesis: str         # 根因假设
    evidence: List[Evidence]           # 证据列表
    risks: List[str]                   # 风险列表
    recommended_action: str            # 推荐操作
    fix_plan: str | None               # 修复计划
    requires_human_approval: bool      # 是否需要人工审批
    feishu_card: Dict[str, Any]        # 飞书卡片配置
```

#### 3.2.4 报告生成器 (`report_writer.py`)

**功能**：
- 生成 Markdown 格式的 Triage 报告
- 生成 JSON 格式的决策文件
- 保存至 `.agent/reports/items/` 目录

**报告内容**：
- 基本信息（Incident ID、来源、Git SHA）
- 决策摘要和根因假设
- 证据列表（带文件链接）
- 风险清单
- 推荐操作和修复计划
- 政策门控结果

### 3.3 修复编排系统

#### 3.3.1 Git 工作空间管理 (`git_workspace.py`)

**功能**：
- 创建隔离的 Git worktree 用于代码修复
- 分支命名规范：`autorepair/inc-{incident_short}-{title_slug}`
- 保护分支：禁止使用 main/master/develop 作为修复分支

**核心操作**：
```python
create_repair_worktree(
    repo_path,       # 仓库路径
    base_branch,     # 基础分支（如 main）
    repair_branch,   # 修复分支
    incident_id      # Incident ID
) -> WorktreeInfo    # 返回 worktree 路径信息

remove_repair_worktree(worktree_path)    # 移除 worktree
delete_local_branch(branch, repo_path)   # 删除本地分支
delete_remote_branch(branch, repo_path)  # 删除远程分支
```

**安全验证**：
```python
PROTECTED_BRANCHES = {"main", "master", "develop"}

def validate_repair_branch(branch: str) -> None:
    if branch in PROTECTED_BRANCHES:
        raise ValueError(f"Refusing to use protected branch: {branch}")
    if not branch.startswith("autorepair/"):
        raise ValueError(f"Repair branch must start with autorepair/: {branch}")
```

#### 3.3.2 修复任务管理 (`job_store.py`)

**功能**：
- JSONL 格式的 RepairJob 持久化
- 任务状态流转：queued → running → pr_created → merged/closed/failed
- 基于 issue_number 和 incident_id 的任务查找

**任务状态机**：
```python
class RepairJobStatus(str, Enum):
    queued = "queued"              # 排队中
    running = "running"            # 执行中
    test_failed = "test_failed"    # 测试失败
    pr_created = "pr_created"      # PR 已创建
    human_required = "human_required"  # 需要人工处理
    merged = "merged"              # 已合并
    closed = "closed"              # 已关闭
    failed = "failed"              # 失败
```

**RepairJob 结构**：
```python
class RepairJob:
    job_id: str                    # 任务 ID (JOB-{uuid})
    incident_id: str               # 关联的 Incident ID
    issue_number: int              # 关联的 GitHub Issue 编号
    repo_owner: str                # 仓库所有者
    repo_name: str                 # 仓库名称
    base_branch: str               # 基础分支
    repair_branch: str             # 修复分支
    worktree_path: str             # worktree 路径
    status: RepairJobStatus        # 任务状态
    created_at: str                # 创建时间
    updated_at: str                # 更新时间
    policy_decision: dict | None   # 策略决策
    risk_level: str                # 风险等级
    pr_number: int | None          # PR 编号
    pr_url: str | None             # PR 链接
    last_error: str | None         # 最后错误
```

#### 3.3.3 仓库锁 (`repo_lock.py`)

**功能**：
- 基于文件系统的独占锁，防止并发修改同一仓库
- 使用 `O_CREAT | O_EXCL` 保证原子性
- 支持上下文管理器自动释放

**实现**：
```python
@contextmanager
def acquire_repo_lock(repo_key: str):
    lock_path = DEFAULT_LOCK_DIR / f"repo_{sha1(repo_key)[:16]}.lock"
    try:
        fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        acquired = True
        yield RepoLock(..., acquired=True)
    except FileExistsError:
        yield RepoLock(..., acquired=False)
    finally:
        if acquired:
            lock_path.unlink()
```

#### 3.3.4 修复编排器 (`orchestrator.py`)

**功能**：
协调完整的修复工作流：

1. **验证 Issue**：检查 Issue 是否为有效的 Bug 报告
2. **获取 Incident**：从 Issue body 提取 Incident ID
3. **运行 Triage**：执行诊断决策（当前为 dry-run 模式）
4. **政策门控**：验证是否允许自动修复
5. **创建修复任务**：生成 RepairJob，创建 worktree
6. **更新 Issue 状态**：添加标签，添加评论
7. **发送飞书通知**：通知修复计划就绪

**验证失败处理**：
- 低风险：标记为 `autorepair:needs-info`
- 高风险：标记为 `autorepair:human-required`
- 发送飞书人工干预卡片

---

## 4. 数据模型

### 4.1 Incident（事件）

```python
class Incident:
    incident_id: str                          # 事件 ID (INC-YYYYMMDD-HHMMSS-xxxxxx)
    source: Literal["local_log", "github_issue", "manual"]  # 来源
    service: str                              # 服务名称
    service_id: str | None                    # 服务 ID
    service_name: str | None                  # 服务名称
    status: str                               # 状态 (NEW/PROCESSING/DONE)
    error_summary: ErrorSummary               # 错误摘要
    raw_traceback: str                        # 原始 Traceback
    created_at: str                           # 创建时间
    updated_at: str                           # 更新时间
    source_ref: str | None                    # 来源引用
    issue_number: int | None                  # 关联 Issue 编号
    issue_url: str | None                     # 关联 Issue URL
    scenario_id: str | None                   # 关联场景 ID
    occurrence_count: int                     # 发生次数
    first_seen_at: str | None                 # 首次发现时间
    last_seen_at: str | None                  # 最近发现时间
    source_refs: list[str]                    # 所有来源引用
```

### 4.2 ErrorSummary（错误摘要）

```python
class ErrorSummary:
    error_type: str           # 错误类型 (TypeError, ZeroDivisionError)
    message: str              # 错误消息
    suspected_file: str | None  # 可疑文件
    line_no: int | None       # 行号
    function: str | None      # 函数名
    fingerprint: str          # 错误指纹 (12位MD5)
```

### 4.3 TargetService（目标服务）

```python
class TargetService:
    service_id: str           # 服务 ID
    name: str                 # 服务名称
    description: str | None   # 描述
    language: str             # 编程语言 (默认 python)
    framework: str | None     # 框架
    base_url: str | None      # 基础 URL
    healthcheck_url: str | None  # 健康检查 URL
    repo_path: str            # 仓库路径
    log_paths: list[str]      # 日志路径列表
    test_command: str | None  # 测试命令
    agent_target_test_command: str | None  # Agent 目标测试命令
    github: dict | None       # GitHub 配置
```

### 4.4 DiagnosticReport（诊断报告）

```python
class DiagnosticReport:
    incident_id: str
    service_id: str
    checks: list[DiagnosticCheck]  # 诊断检查列表
    classification: str | None     # 分类
    fixability: str | None         # 可修复性
    summary: str | None            # 摘要
    created_at: str                # 创建时间
```

---

## 5. 工作流设计

### 5.1 日志驱动工作流

```
[1] 日志文件写入 Traceback
        ↓
[2] Watcher 增量扫描日志
        ↓
[3] 提取 ErrorSummary，生成 Fingerprint
        ↓
[4] 检查 Fingerprint 是否已存在
   ├─ 是 → 更新 occurrence_count 和 last_seen_at
   └─ 否 → 创建新 Incident
        ↓
[5] 发送飞书告警卡片（仅首次）
        ↓
[6] 创建 GitHub Issue（含完整证据）
        ↓
[7] 标记 Issue 为 autorepair:triage
```

### 5.2 GitHub Issue 驱动工作流

```
[1] 用户创建/提交 Bug Issue
        ↓
[2] Watcher 扫描 GitHub Issues
        ↓
[3] 验证 Issue 格式（标签、标题、内容）
   ├─ 无效 → 添加评论提示，标记 autorepair:needs-info
   └─ 有效 → 继续
        ↓
[4] 运行 Triage Agent（LLM 分析）
        ↓
[5] 生成 Decision（auto_fix/need_info/escalate）
        ↓
[6] 政策门控检查
   ├─ 拒绝 → 标记 autorepair:human-required，发送人工干预通知
   └─ 通过 → 继续
        ↓
[7] 创建 RepairJob，状态为 queued
        ↓
[8] 创建 Git worktree 和修复分支
        ↓
[9] 更新 Issue 标签为 autorepair:accepted
        ↓
[10] 发送飞书「修复计划就绪」卡片
```

### 5.3 修复执行工作流（编排器）

```
[1] 从 Job Store 获取 queued 任务
        ↓
[2] 获取仓库锁（失败则跳过）
        ↓
[3] 在 worktree 中执行修复
        ├─ 读取相关代码
        ├─ 调用 LLM 生成修复方案
        ├─ 应用代码修改
        └─ 运行测试验证
        ↓
[4] 测试结果判断
   ├─ 失败 → 标记 test_failed，记录错误
   └─ 通过 → 继续
        ↓
[5] 提交代码，推送分支
        ↓
[6] 创建 Pull Request
        ↓
[7] 更新 RepairJob 状态为 pr_created
        ↓
[8] 更新 Issue 标签为 autorepair:pr-ready
        ↓
[9] 发送飞书「修复 PR 就绪」卡片
        ↓
[10] 释放仓库锁
```

### 5.4 状态流转图

```
Incident 状态:
  NEW → PROCESSING → DONE
                    ↘ FAILED

RepairJob 状态:
  queued → running → test_failed → failed
                ↘ pr_created → merged
                ↘ pr_created → closed
                ↘ human_required
```

---

## 6. 安全与权限控制

### 6.1 四类工具限制

Agent 仅可使用以下工具：

| 工具 | 权限范围 | 限制 |
|------|----------|------|
| **Read Log** | 读取指定日志文件 | 仅读取，不修改 |
| **Read Code** | 读取仓库代码 | 仅读取，不修改 |
| **Run Test** | 执行测试命令 | 在 worktree 内执行，隔离环境 |
| **Git Commit** | 提交代码到修复分支 | 禁止 push main/master，禁止 merge |

### 6.2 Git 安全规则

```python
# 禁止操作
❌ push main/master
❌ 自动 merge PR
❌ reset --hard 共享分支
❌ 直接修改 protected branches

# 允许操作
✅ 创建新分支 (autorepair/*)
✅ 在 worktree 中修改代码
✅ 创建 Pull Request
✅ 添加评论和标签
```

### 6.3 数据保护

- **禁止读取密钥**：不访问 `.env`、`.git-credentials` 等敏感文件
- **禁止访问生产数据库**：仅允许访问测试环境
- **禁止输出隐私数据**：日志中不包含用户真实数据
- **Issue 内容验证**：检测 `security`、`secret`、`credential` 等高风险关键词

### 6.4 并发控制

- **仓库锁**：基于文件系统的独占锁，防止多个 Agent 同时修改同一仓库
- **任务去重**：同一 Issue 或 Incident 只允许一个活跃的 RepairJob
- **原子操作**：锁获取使用 `O_CREAT | O_EXCL` 保证原子性

---

## 7. 技术栈

### 7.1 核心依赖

| 依赖 | 版本 | 用途 |
|------|------|------|
| **Python** | 3.12+ | 运行环境 |
| **FastAPI** | >=0.104.0 | Web 服务框架 |
| **Uvicorn** | >=0.24.0 | ASGI 服务器 |
| **Pydantic** | >=2.5.0 | 数据验证和 Schema |
| **pydantic-settings** | >=2.1.0 | 配置管理 |
| **httpx** | >=0.25.0 | HTTP 客户端 |
| **python-dotenv** | >=1.0.0 | 环境变量加载 |
| **pytest** | >=7.4.0 | 测试框架 |
| **jinja2** | - | 模板渲染（LLM Prompt） |
| **PyYAML** | - | 服务配置解析 |

### 7.2 飞书集成

- **lark-oapi**：飞书 OpenAPI SDK
- **消息卡片**：使用模板卡片，支持多端适配
- **卡片类型**：
  - `incident_detected`：异常告警
  - `repair_plan_ready`：修复计划就绪
  - `fix_pr_ready`：修复 PR 就绪
  - `manual_intervention`：需要人工干预
  - `periodic_digest`：周期摘要

### 7.3 GitHub 集成

- **GitHub REST API v3**：Issue、PR、Label 管理
- **标签体系**：
  - `bug`：Bug 标签
  - `AutoRepair`：系统管理
  - `source:runtime` / `source:issue`：来源标记
  - `autorepair:triage` → `autorepair:accepted` → `autorepair:repairing` → `autorepair:pr-ready` → `autorepair:closed`
  - `risk:low` / `risk:medium` / `risk:high`：风险等级

### 7.4 LLM 集成

- **ARK API**：火山引擎 ARK 大模型平台
- **模型配置**：
  - `ARK_MODEL_REPAIR`：代码修复模型
  - `ARK_MODEL_SUMMARY`：摘要生成模型
- **Prompt 工程**：使用 Jinja2 模板渲染 Triage Prompt

---

## 8. 部署与运行

### 8.1 环境要求

- **操作系统**：Windows / Linux / macOS
- **Python**：3.12+
- **Conda 环境**：`conda activate py312`
- **Git**：安装并配置

### 8.2 安装步骤

```bash
# 1. 克隆仓库
git clone <repository_url>
cd FeishuAutoRepair

# 2. 安装依赖
pip install -e ".[dev]"

# 3. 配置环境变量
cp .env.example .env
# 编辑 .env 文件，填入以下配置：
# - FEISHU_APP_ID, FEISHU_APP_SECRET, FEISHU_CHAT_ID
# - GITHUB_TOKEN, GITHUB_OWNER, GITHUB_REPO
# - ARK_API_KEY, ARK_MODEL_REPAIR, ARK_MODEL_SUMMARY
```

### 8.3 启动 Demo 服务

```bash
# 启动 Demo 服务（端口 8000）
python scripts/run_demo_server.py

# 访问业务控制台
# http://127.0.0.1:8000/

# 健康检查
curl http://127.0.0.1:8000/health
```

### 8.4 运行测试

```bash
# 运行所有测试（排除 agent_target）
pytest -q

# 运行 Agent 修复目标测试（预期失败）
pytest -q -m agent_target

# 运行特定模块测试
pytest autorepair/tests/triage/ -v
pytest autorepair/tests/repair/ -v
```

### 8.5 演示流程

```bash
# 1. 清理演示状态
python scripts/reset_demo_state.py

# 2. 触发异常
python scripts/trigger_demo_bug.py

# 3. 扫描日志，生成 Incident
python scripts/watch_once.py

# 4. 创建 GitHub Issue（Mock 模式）
python scripts/create_demo_issue.py user-missing-profile

# 5. 扫描 GitHub Issue
python scripts/watch_github_issues_once.py

# 6. 执行修复编排（Dry-run）
python scripts/repair_once.py
```

### 8.6 Mock 模式

当外部服务配置不完整时，系统自动降级为 Mock 模式：

| 服务 | Mock 行为 |
|------|-----------|
| **飞书** | 控制台打印卡片内容，模拟发送 |
| **GitHub** | 本地 JSONL 文件存储 Issue/PR |
| **LLM** | 抛出 `NotImplementedError`，使用 dry-run 决策 |

---

## 9. 扩展性设计

### 9.1 多服务支持

通过 `config/services.yaml` 配置多服务监控：

```yaml
services:
  - service_id: supportdesk-lite
    name: Acme SupportDesk Lite
    repo_path: .
    log_paths:
      - demo_service/logs/app.log
    healthcheck_url: http://localhost:8000/health
    test_command: pytest -q
```

### 9.2 适配器模式

外部服务集成采用适配器模式，便于扩展：

```python
# Feishu Adapter
class FeishuAdapter:
    def send_incident_card(incident) -> ...
    def send_template_card(card_type, variables) -> ...
    def get_tenant_access_token() -> ...

# GitHub Adapter
class GitHubAdapter:
    def create_issue(title, body, labels) -> GitHubIssue
    def create_pull_request(title, body, head, base) -> PullRequestRef
    def add_labels(issue_number, labels) -> bool
```

### 9.3 插件化的 Bug 场景

通过 `bug_scenarios.py` 定义可复现的 Bug 场景：

```python
BUG_SCENARIOS = [
    BugScenario(
        scenario_id="user-missing-profile",
        title="用户画像查询缺失异常",
        trigger_type="local_log",
        endpoint="GET /users/not-exist/profile",
        expected_error_type="TypeError",
        expected_behavior="返回404 User not found",
        target_test_command="pytest -q demo_service/tests/test_profile_contract.py::test_missing_user_should_return_404"
    ),
    # ... 更多场景
]
```

### 9.4 审计日志

所有关键操作均记录审计日志：

```python
append_audit_event(
    event_type="incident_created",       # 事件类型
    incident_id="INC-20240501-120000-xxxxxx",  # 关联 Incident
    payload={                           # 附加数据
        "error_type": "TypeError",
        "fingerprint": "abc123def456",
        "source": "local_log"
    }
)
```

**审计事件类型**：
- `incident_created` / `incident_updated`
- `feishu_card_sent`
- `github_issue_created` / `github_issue_linked`
- `repair_job_queued` / `repair_policy_rejected`
- `git_command` / `git_worktree_remove_fallback`

---

## 10. 总结

### 10.1 已实现功能清单

| 功能模块 | 状态 | 说明 |
|----------|------|------|
| **Demo 服务** | ✅ 完成 | FastAPI 服务，4个预埋 Bug |
| **日志监控** | ✅ 完成 | 增量扫描、指纹去重、错误聚合 |
| **Incident 管理** | ✅ 完成 | 创建、更新、持久化、聚合 |
| **GitHub Issue 联动** | ✅ 完成 | Issue 创建、标签管理、评论、指纹搜索 |
| **飞书消息卡片** | ✅ 完成 | 5种卡片类型、模板变量、Mock 模式 |
| **Triage Agent** | ✅ 完成 | 证据收集、政策门控、决策 Schema |
| **修复编排器** | ✅ 完成 | 任务管理、Git worktree、仓库锁 |
| **Issue 验证器** | ✅ 完成 | 格式检查、风险检测、证据评估 |
| **诊断系统** | ✅ 完成 | 服务配置、健康检查、可修复性判断 |
| **审计日志** | ✅ 完成 | 全链路操作记录 |
| **服务注册表** | ✅ 完成 | 多服务配置、YAML 加载 |
| **业务控制台** | ✅ 完成 | 企业级 UI、KPI、工单队列、事件流 |
| **LLM 集成** | 🔄 部分 | Prompt 模板就绪，API 调用待实现 |
| **自动代码修复** | 🔄 部分 | 编排逻辑就绪，LLM 调用待实现 |

### 10.2 系统亮点

1. **完整的安全体系**：四类工具限制 + Git 保护分支 + 仓库锁 + 数据隔离
2. **优雅的降级策略**：所有外部依赖支持 Mock 模式，开发演示无阻碍
3. **精细的状态管理**：Incident/RepairJob/GitHub Issue 三重状态同步
4. **企业级 UI**：Acme SupportDesk Lite 伪装成真实业务系统
5. **全面的审计追踪**：每个操作都有审计记录，可追溯、可回放
6. **灵活的配置系统**：YAML 配置多服务，环境变量控制行为
7. **规范的标签体系**：GitHub 标签驱动的状态机，清晰的工作流

### 10.3 下一步计划

1. **LLM 集成**：实现 ARK API 调用，连接 Triage Agent 和代码修复
2. **自动代码修复**：实现 Read Code → LLM Patch → Run Test 闭环
3. **PR 自动创建**：修复通过后自动创建 Pull Request
4. **飞书卡片回调**：支持用户通过卡片按钮触发操作
5. **多维表格集成**：Incident 和 RepairJob 数据同步到飞书多维表格
6. **多仓库支持**：支持监控和修复多个独立仓库

### 10.4 性能指标

| 指标 | 目标值 | 当前值 |
|------|--------|--------|
| 日志扫描延迟 | < 1s | < 0.5s |
| Incident 创建时间 | < 2s | < 1s |
| Triage 决策时间 | < 30s | N/A (待 LLM) |
| 修复任务创建 | < 5s | < 3s |
| 测试覆盖率 | > 80% | ~70% |

---

## 附录

### A. 项目结构

```
FeishuAutoRepair/
├── autorepair/                    # 核心 Agent 代码
│   ├── adapters/                  # 外部服务适配器
│   │   ├── feishu.py             # 飞书 API
│   │   └── github.py             # GitHub API
│   ├── agent/                     # Agent 逻辑
│   │   └── triage/               # 诊断代理
│   │       ├── decision_schema.py
│   │       ├── evidence_collector.py
│   │       ├── policy_gate.py
│   │       ├── report_writer.py
│   │       ├── triage_agent.py
│   │       └── triage_prompt.py
│   ├── cards/                     # 飞书卡片
│   │   └── variables.py          # 变量构造器
│   ├── config/                    # 配置文件
│   │   └── services.yaml         # 服务配置
│   ├── repair/                    # 修复编排
│   │   ├── git_workspace.py      # Git worktree 管理
│   │   ├── job_store.py          # 任务存储
│   │   ├── orchestrator.py       # 编排器
│   │   ├── repo_lock.py          # 仓库锁
│   │   └── schemas.py            # 任务 Schema
│   ├── tests/                     # 测试代码
│   ├── audit_store.py            # 审计日志
│   ├── bug_scenarios.py          # Bug 场景定义
│   ├── config.py                 # 配置管理
│   ├── diagnostics.py            # 诊断检查
│   ├── incident_store.py         # Incident 存储
│   ├── issue_manager.py          # Issue 管理
│   ├── issue_validator.py        # Issue 验证
│   ├── log_parser.py             # 日志解析
│   ├── schemas.py                # 数据模型
│   ├── service_registry.py       # 服务注册表
│   ├── watch_state.py            # 监控状态
│   └── watcher.py                # 日志监控器
├── demo_service/                  # Demo 业务服务
│   ├── app.py                    # FastAPI 应用
│   ├── logging_config.py         # 日志配置
│   ├── order_service.py          # 订单服务（Bug 2）
│   ├── repository.py             # 用户仓库
│   ├── service.py                # 用户服务（Bug 1）
│   ├── ticket_repository.py      # 工单仓库
│   ├── ticket_service.py         # 工单服务（Bug 3/4）
│   ├── ui.py                     # 前端 HTML
│   ├── logs/                     # 日志目录
│   └── tests/                    # 业务测试
├── docs/                         # 文档
├── scripts/                      # 演示脚本
├── tests/                        # 集成测试
├── .env.example                  # 环境变量示例
├── .gitignore
├── pyproject.toml                # 项目配置
└── README.md                     # 项目说明
```

### B. 环境变数

| 变量 | 必填 | 说明 |
|------|------|------|
| `FEISHU_API_BASE_URL` | 否 | 飞书 API 地址（默认 open.feishu.cn） |
| `FEISHU_APP_ID` | 否 | 飞书应用 ID |
| `FEISHU_APP_SECRET` | 否 | 飞书应用密钥 |
| `FEISHU_CHAT_ID` | 否 | 飞书群组/用户 ID |
| `ARK_API_KEY` | 否 | ARK API 密钥 |
| `ARK_BASE_URL` | 否 | ARK API 地址 |
| `ARK_MODEL_REPAIR` | 否 | 代码修复模型 ID |
| `ARK_MODEL_SUMMARY` | 否 | 摘要生成模型 ID |
| `GITHUB_API_BASE_URL` | 否 | GitHub API 地址 |
| `GITHUB_TOKEN` | 否 | GitHub Personal Access Token |
| `GITHUB_OWNER` | 否 | GitHub 仓库所有者 |
| `GITHUB_REPO` | 否 | GitHub 仓库名称 |
| `GITHUB_ASSIGNEE` | 否 | Issue 默认指派人 |
| `GITHUB_BASE_BRANCH` | 否 | 基础分支（默认 main） |
| `TEST_CMD` | 否 | 测试命令（默认 pytest -q） |

### C. 错误指纹算法

```python
import hashlib

def generate_fingerprint(error_type: str, file_path: str, line_no: int) -> str:
    """
    生成错误指纹
    相同错误类型 + 相同文件 + 相同行号 = 相同指纹
    """
    raw = f"{error_type}|{file_path}|{line_no}"
    return hashlib.md5(raw.encode()).hexdigest()[:12]
```

**示例**：
```
TypeError|demo_service/service.py|10 → abc123def456
ZeroDivisionError|demo_service/order_service.py|16 → 789xyz012mno
```

---

**文档版本**：v1.0  
**更新日期**：2026-04-30  
**维护团队**：FeishuAutoRepair Team
