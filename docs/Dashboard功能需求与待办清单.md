# Dashboard 功能需求与待办清单

## ✅ 已完成功能
1. **修复飞书卡片发送问题**
   - 新增 `send_fix_pr_ready_card` 函数，兼容executor调用
   - 新增 `send_manual_intervention_card` 函数，兼容executor和sync_pr_status调用
   - 自动适配服务名和参数格式，保证卡片正确发送

2. **优化Issue创建逻辑**
   - 配置缺失或创建失败时，自动返回mock IssueRef
   - 保证流程不中断，不会因为GitHub配置问题导致整个链路失败
   - 生成唯一的mock issue编号和URL

3. **实现统计模块 (autorepair/dashboard/stats.py)**
   - `get_system_stats()` - 获取系统整体统计数据
   - `get_incident_list()` - 获取Incident列表
   - `get_repair_job_list()` - 获取修复任务列表
   - `get_issue_list()` - 获取Issue列表
   - `get_pr_list()` - 获取PR列表
   - 支持错误类型分布、服务分布、任务状态分布统计
   - 支持最近24小时Incident趋势统计

## 🚀 待实现功能

### 1. Web Dashboard 后端API (端口8888)
- **文件位置**：autorepair/dashboard/api.py
- **框架**：FastAPI
- **接口列表**：
  - `GET /api/stats` - 获取系统统计数据
  - `GET /api/incidents` - 获取Incident列表（支持分页、筛选）
  - `GET /api/issues` - 获取Issue列表（支持分页、筛选）
  - `GET /api/repair_jobs` - 获取修复任务列表（支持分页、筛选）
  - `GET /api/prs` - 获取PR列表（支持分页、筛选）
  - `POST /api/trigger/scan_logs` - 手动触发日志扫描
  - `POST /api/trigger/scan_issues` - 手动触发Issue扫描
  - `POST /api/trigger/run_repair` - 手动触发修复任务
  - `POST /api/trigger/sync_prs` - 手动触发PR状态同步
  - `POST /api/trigger/send_digest` - 手动发送统计摘要
  - `GET /api/config` - 获取系统配置
  - `POST /api/config` - 修改系统配置
- **启动脚本**：scripts/run_dashboard.py

### 2. Web Dashboard 前端界面
- **文件位置**：autorepair/dashboard/static/
- **技术栈**：纯HTML + Tailwind CSS + Vanilla JS（无依赖）
- **页面结构**：
  - **仪表盘首页**
    - 关键指标卡片（总Bug数、今日新增、修复成功率、待处理任务等）
    - 24小时趋势图
    - 错误类型分布饼图
    - 服务分布柱状图
    - 最近Incident列表
  - **Incident管理页**
    - 完整Incident列表
    - 搜索、筛选功能
    - Incident详情弹窗
  - **Issue管理页**
    - Issue列表，按状态筛选
    - 支持跳转到GitHub Issue
  - **修复任务页**
    - 修复任务列表，按状态筛选
    - 查看任务详情、错误日志
  - **操作中心**
    - 手动触发各种任务的按钮
    - 配置修改表单
    - 操作日志输出

### 3. 定期摘要飞书卡片
- **文件位置**：autorepair/cards/variables.py 新增 `build_periodic_digest_variables`
- **卡片内容**：
  - 统计周期（小时/天/周）
  - 关键指标汇总
  - Top 3错误类型
  - 修复统计
  - 待处理任务提醒
- **发送触发**：定时任务或手动触发

### 4. 定时任务调度器
- **文件位置**：autorepair/core/scheduler.py
- **依赖**：APScheduler
- **配置项**（新增到config.py）：
  - `WATCHER_SCAN_INTERVAL = 60` # 日志扫描周期（秒）
  - `ISSUE_SCAN_INTERVAL = 300` # Issue扫描周期（秒）
  - `REPAIR_INTERVAL = 300` # 修复任务执行周期（秒）
  - `SYNC_PR_INTERVAL = 600` # PR状态同步周期（秒）
  - `DIGEST_INTERVAL = 86400` # 统计摘要发送周期（秒，默认每天）
- **启动脚本**：scripts/run_scheduler.py

### 5. 命令行状态工具
- **文件位置**：scripts/status.py
- **功能**：
  - 输出系统统计摘要
  - 支持输出JSON格式
  - 支持查看列表（incidents/jobs/issues/prs）

## 📋 实现优先级
1. **P0（最高）**：Web Dashboard后端API + 启动脚本
2. **P0**：Web Dashboard前端界面
3. **P1**：定时任务调度器 + 配置
4. **P1**：定期摘要飞书卡片
5. **P2**：命令行状态工具

## 🎯 验收标准
1. 运行 `python scripts/run_dashboard.py` 后，访问 http://localhost:8888 可以正常打开Dashboard
2. Dashboard上显示所有统计数据正确，图表正常渲染
3. 可以通过Dashboard手动触发所有操作，执行成功
4. 定时任务可以按配置周期自动执行
5. 定期摘要卡片可以正常发送到飞书（或mock输出）
