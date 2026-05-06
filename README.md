# FeishuAutoRepair

FeishuAutoRepair 是一个面向研发协作场景的服务自动化修复系统。它可以从 Demo 服务运行时异常或 GitHub Bug Issue 中收集证据，自动创建 Incident，经过合理性检查和策略门控后创建修复任务，在隔离 git worktree 中由 AI Agent 修复代码、运行 pytest 验证、创建 GitHub PR，并通过飞书卡片通知开发者 Review。

一句话概括：**它不是自动 merge 代码的机器人，而是自动生成可审阅修复 PR 的工程化 Agent。**

## 核心能力

- FastAPI Demo 服务：Acme SupportDesk Lite 工单场景。
- 可复现预埋 Bug：用户画像缺失、订单除零、SLA 时区、NameError、幂等性重复创建。
- 日志监控：增量扫描日志，提取 Traceback，生成 Incident。
- Incident 去重：基于 fingerprint 聚合同类错误，避免重复通知。
- GitHub 集成：Issue 创建、扫描、标签、评论、PR 创建，支持 Mock 模式。
- 飞书集成：异常发现、修复计划、PR 待 Review、人工介入、周期摘要等卡片。
- Triage / Policy Gate：借鉴 ClawSweeper 的保守治理，只让证据充分、低风险、可验证的问题进入自动修复。
- Spec-Guided Repair Agent：借鉴 FM-Agent 的规格思想，通过 RepairCase、RepairSpec、RepairSkill、ValidationPlan 指导修复。
- 安全执行：git worktree 隔离、repo lock 串行化、allowed_files 限制、测试失败不创建 PR。
- Dashboard：提供统计、扫描、修复、PR 同步和事件流展示。

## 当前闭环

```text
业务服务异常 / GitHub Bug Issue
→ Watcher / Issue Poller 发现问题
→ Incident 创建或聚合
→ GitHub Issue 创建 / 关联
→ 飞书异常发现卡片
→ Issue 合理性检查
→ Triage Decision + Policy Gate
→ RepairJob queued
→ repo lock + git worktree
→ RepairCase / RepairSpec / RepairSkill / ValidationPlan
→ Playbook 或 MiniRepairAgent 修复
→ 目标测试 + 全量测试
→ commit + push
→ GitHub PR
→ 飞书 PR 待 Review 卡片
→ PR 合并后同步关闭 Issue 并清理 worktree
```

## 环境要求

- Python 3.12+
- Conda 环境建议：`py312`
- Git
- 可选：飞书自建应用、GitHub Token、火山方舟 / Doubao API Key

安装依赖：

```bash
conda activate py312
pip install -e ".[dev]"
```

## 快速开始

### 1. 检查配置

```bash
python scripts/check_env.py
```

外部服务配置缺失时，系统会尽量降级到 Mock 模式，便于本地演示。

### 2. 重置演示状态

```bash
python scripts/reset_demo_state.py
```

该命令会清理演示日志、Incident、RepairJob、Mock Issue 等历史状态，保证录屏环境干净。

### 3. 启动 Demo 服务

```bash
python scripts/run_demo_server.py
```

打开：

```text
http://127.0.0.1:8000/
```

页面提供工单、用户画像、订单等业务操作，可触发预埋 Bug。

### 4. 启动 Dashboard

```bash
python scripts/run_dashboard.py
```

打开：

```text
http://127.0.0.1:8888/
```

Dashboard 可查看统计、Incident、Issue、RepairJob、PR，也可手动触发日志扫描、Issue 扫描、修复执行和 PR 同步。

## 推荐 Demo 流程

推荐主线：`ticket-timezone-sla`，即带 `+08:00` SLA deadline 的工单触发 `timezone-aware` 与 `naive datetime` 比较错误。

### 步骤 1：触发运行时异常

启动 Demo 服务后，在浏览器中点击带时区 SLA 的工单提交按钮。服务会返回 500，并在日志中写入 Traceback。

### 步骤 2：扫描日志生成 Incident

```bash
python scripts/watch_once.py
```

预期结果：

- 发现新增 Traceback。
- 创建 Incident。
- 创建或关联 GitHub Issue。
- 发送飞书 IncidentDetectedCard，或在 Mock 模式下打印卡片内容。

### 步骤 3：扫描 Issue 创建 RepairJob

```bash
python scripts/watch_github_issues_once.py
```

预期结果：

- Issue 合理性检查通过。
- Triage / Policy Gate 放行。
- 创建 RepairJob，状态为 queued。
- 发送 RepairPlanReadyCard。

### 步骤 4：执行自动修复

```bash
python scripts/repair_once.py
```

预期结果：

- 创建隔离 git worktree。
- 构建 RepairCase / RepairSpec / RepairSkill / ValidationPlan。
- 优先尝试 Skill-backed Playbook。
- 必要时进入 Spec-Guided MiniRepairAgent。
- 运行目标测试和全量测试。
- 测试通过后创建修复分支、commit、push、PR。
- 发送 FixPrReadyCard。

### 步骤 5：同步 PR 状态

PR 合并后执行：

```bash
python scripts/sync_pr_status_once.py
```

预期结果：

- PR merged：关闭 Issue，标记 `autorepair:closed`，清理 worktree 和安全临时分支。
- PR closed 未合并：RepairJob 转为 `human_required`，发送人工介入通知。

## 常用脚本

| 脚本 | 用途 |
| --- | --- |
| `scripts/check_env.py` | 检查飞书、GitHub、Ark 等配置 |
| `scripts/reset_demo_state.py` | 清理演示状态 |
| `scripts/run_demo_server.py` | 启动 Demo 业务服务 |
| `scripts/run_dashboard.py` | 启动 Dashboard |
| `scripts/watch_once.py` | 扫描服务日志并创建 Incident |
| `scripts/watch_github_issues_once.py` | 扫描 Bug Issue 并创建 RepairJob |
| `scripts/repair_once.py` | 执行一个 queued RepairJob |
| `scripts/sync_pr_status_once.py` | 同步 PR 合并/关闭状态 |
| `scripts/create_demo_issue.py` | 创建预设 Demo Bug Issue |
| `scripts/send_test_feishu_card.py` | 发送/Mock 飞书卡片 |
| `scripts/github_smoke_test.py` | GitHub Issue/PR 冒烟测试 |

## 预埋 Bug 场景

| 场景 ID | 类型 | 预期行为 |
| --- | --- | --- |
| `user-missing-profile` | NoneType / TypeError | 用户不存在时返回 404 |
| `order-zero-division` | ZeroDivisionError | total_amount <= 0 返回业务错误 |
| `ticket-timezone-sla` | timezone TypeError | 统一 datetime 时区，支持带时区 SLA |
| `ticket-nameerror-overdue` | NameError | 过期工单返回字符串状态 `overdue` |
| `ticket-idempotency-duplicate` | 业务幂等性 | 相同 idempotency_key 返回同一工单 |

## 关键设计

### ClawSweeper 式合理性检查

系统不会因为一个 Issue 看起来像 Bug 就自动修复。进入自动修复前必须检查：

- 是否有 bug 标签或 `[Bug]` 标题。
- 是否包含复现步骤。
- 是否包含期望行为和实际行为。
- 是否包含错误信息、Traceback 或失败测试。
- 是否不涉及安全、权限、密钥、生产数据库等高风险内容。
- 是否没有处于 repairing、pr-ready、closed 等已处理状态。

证据不足会评论 needs-info，高风险会转人工。

### FM-Agent 式规格驱动修复

系统通过 RepairSpec 明确：

- 调用方期望。
- 前置条件。
- 后置条件。
- 不变量。
- 当前实现违反了哪条规格。
- 目标测试和回归测试。

Agent 的目标不是“让异常消失”，而是满足 RepairSpec。

### 安全边界

- 不自动 merge PR。
- 不直接修改 main/master/develop。
- 所有修复发生在 git worktree。
- 同一仓库通过 repo lock 串行修复。
- 同一 Issue / Incident 不重复创建活跃任务。
- Agent 只修改 allowed_files。
- 默认禁止修改测试文件。
- 禁止读取或修改 `.env`、`.git`、secret、token、password 等敏感路径。
- 只允许运行 pytest / python -m pytest。
- 测试失败不创建 PR。

## 测试

推荐在已激活的 conda 环境中运行：

```bash
conda activate py312
python -m pytest -q
```

运行 Agent 目标测试：

```bash
python -m pytest -q -m agent_target
```

注意：`agent_target` 用于表达“Agent 应修复的目标行为”。某些预埋 Bug 在未进入自动修复前失败是预期现象。

## 项目结构

```text
FeishuAutoRepair/
├── autorepair/
│   ├── adapters/          # 飞书、GitHub、Ark / LLM 适配
│   ├── agent/triage/      # Triage、Decision Schema、Policy Gate
│   ├── cards/             # 飞书卡片变量
│   ├── dashboard/         # Dashboard API 与静态页面
│   ├── repair/            # RepairJob、worktree、repo lock、executor
│   ├── repair_agent/      # MiniRepairAgent、RepairSpec、Skill、Validation
│   ├── watcher.py         # 日志扫描入口
│   ├── log_parser.py      # Traceback 解析
│   └── incident_store.py  # Incident 持久化
├── demo_service/          # FastAPI Demo 业务服务
├── docs/                  # 设计文档与结项报告
├── scripts/               # 演示和运维脚本
└── tests/                 # 顶层集成测试
```

## 配置说明

复制 `.env.example` 为 `.env`，按需配置：

```env
FEISHU_APP_ID=
FEISHU_APP_SECRET=
FEISHU_CHAT_ID=

GITHUB_TOKEN=
GITHUB_OWNER=
GITHUB_REPO=
GITHUB_BASE_BRANCH=main

ARK_API_KEY=
ARK_BASE_URL=
ARK_MODEL_REPAIR=
ARK_MODEL_SUMMARY=
```

配置不完整时，飞书和 GitHub 会尽量进入 Mock 模式，方便本地演示；真实录屏建议配置真实飞书群和 GitHub 仓库。

## 文档

- 初赛结项报告：`docs/初赛结项报告.md`
- 技术白皮书：`docs/technical-whitepaper.md`
- 阶段设计记录：`docs/Stage*.md`
- 问题定义：`docs/问题定义.md`

