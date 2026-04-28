请继续完善 demo_service 的 Acme SupportDesk Lite 界面。

当前问题：
页面虽然已经有工单队列、KPI、事件流，但仍然过于针对 AutoRepair 演示。用户能明显看出某些按钮是“触发 Bug”按钮。现在需要把它进一步包装成真实的企业工单与 SLA 管理后台。

目标：
让页面看起来像一个真实业务系统，而不是 Bug 触发器。真实有效逻辑仍然只保留少量接口，其余数据可以 mock。

要求：
1. 不引入 React/Vue。
2. 继续使用原生 HTML/CSS/JS。
3. 不改变现有接口行为。
4. 不修复任何预埋 Bug。

页面结构：
1. 左侧导航栏：
   - 工单总览
   - SLA 风险
   - 飞书渠道
   - 客户租户
   - 系统设置

2. 顶部栏：
   - Acme SupportDesk Lite
   - 当前租户：Demo Tenant
   - 环境：Local Demo
   - Agent 接入：Black-box Log Watcher

3. KPI 卡：
   - 今日新工单
   - P1 工单
   - SLA 风险
   - 飞书事件积压
   - 平均响应时长

4. 主表格：
   工单队列，至少 8 条 mock 数据。
   字段：
   - 工单编号
   - 客户
   - 来源
   - 优先级
   - SLA
   - 处理人
   - 状态
   - 最近更新

5. SLA 风险面板：
   显示 3 条即将超时工单。

6. 飞书事件流：
   显示飞书消息、事件重试、审批通知等 mock 日志。

7. 操作区：
   按钮文案必须像业务动作，不要写“触发 Bug”：
   - 创建 P1 飞书渠道工单
   - 重试飞书事件同步
   - 批量刷新 SLA 状态
   - 系统健康检查

按钮说明也不要写“触发 Runtime Bug”。可以写：
   - 创建一个来自飞书渠道的紧急客户问题
   - 重新处理最近一条飞书事件
   - 刷新即将到期工单的 SLA 状态
   - 检查服务健康状态

8. API 响应区域：
   保留 status 和 JSON。
   如果 status >= 500，只提示：
   “服务端处理失败，异常已写入服务日志。”

不要写：
   “请运行 watch_once.py”
   “供 AutoRepair 捕获”
这些是演示说明，不应该出现在业务系统里。

9. 页面底部可以有一个小的系统信息栏：
   - Service ID: supportdesk-lite
   - Log: demo_service/logs/app.log
   - Repo: current repository

测试：
新增 HTML 关键词测试，断言页面包含：
- 工单总览
- SLA 风险
- 飞书渠道
- 客户租户
- Demo Tenant
- 工单队列
- 飞书事件流
- 创建 P1 飞书渠道工单
- 重试飞书事件同步
- 服务端处理失败，异常已写入服务日志

输出：
1. 修改文件列表。
2. 新页面模块说明。
3. pytest -q 结果。