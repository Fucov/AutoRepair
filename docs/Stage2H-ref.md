对，现在这个问题本质上是：**飞书卡片不是网页详情页，不能塞太多变量**。尤其移动端预览宽度很窄，一旦变量超过 10 个，就会变成你截图这种“字段堆叠”，视觉很差、用户也抓不住重点。

所以要重新定一个原则：

> **每张卡片只展示“让用户决定下一步动作所必需的信息”，详细信息放到 GitHub Issue / PR / 审计报告 / 日志报告里。**

下面我把 5 张卡全部重新压缩，每张卡的变量控制在 **8~10 个以内**。
不再展示 fingerprint、function、source、environment、line、stage 等低优先级字段，除非它们对决策非常关键。

---

# 一、卡片总体变量设计原则

## 每张卡只保留 3 类信息

```text
1. 发生了什么？
2. 影响/结论是什么？
3. 用户下一步要点哪里？
```

---

## 不建议直接展示的字段

下面这些字段不要放在卡片正文里：

```text
fingerprint
error_function
source
service_id
environment
updated_at
first_seen_at
last_seen_at
raw_traceback
audit_ref
scenario_id
具体 line_no
完整 tests_to_run
完整 files_to_modify
```

这些都应该写进报告或 PR 描述里。

---

## 建议保留的统一基础字段

最多保留这些：

```text
incident_id
service_name
summary
severity / risk_level
status_label
primary_url
secondary_url
```

其他都做成 `summary` 文本，而不是多个字段散开。

---

# 二、推荐保留的 5 张卡

我建议还是保留 5 张：

```text
1. 故障发现卡 IncidentDetectedCard
2. 修复计划卡 RepairPlanReadyCard
3. PR 待 Review 卡 FixPrReadyCard
4. 人工介入卡 ManualInterventionCard
5. 周期总结卡 PeriodicDigestCard
```

不单独做“重复故障升级卡”，而是把它合并到故障发现卡里，用 `severity` 和 `summary` 体现。

---

# 三、五张卡片重新设计 Prompt

---

## 1. 故障发现卡：IncidentDetectedCard

### 用途

首次发现故障，或重复故障升级时发送。

### 变量数量：9 个

```text
card_title
status_label
incident_id
service_name
severity
error_brief
occurrence_text
next_step
issue_url
report_url
```

严格算是 10 个；如果按钮只保留一个，可以去掉 `issue_url`。

### 变量解释

| 变量                | 示例                       | 说明       |
| ----------------- | ------------------------ | -------- |
| `card_title`      | `【P1】检测到服务异常`            | 标题       |
| `status_label`    | `已受理`                    | 状态标签     |
| `incident_id`     | `INC-20260426-xxxx`      | 故障 ID    |
| `service_name`    | `Acme SupportDesk Lite`  | 服务名称     |
| `severity`        | `P1`                     | 严重级别     |
| `error_brief`     | `SLA 截止时间比较触发 TypeError` | 错误摘要，一句话 |
| `occurrence_text` | `近 10 分钟发生 6 次`          | 发生次数文本   |
| `next_step`       | `正在收集证据并执行自动诊断`          | 下一步      |
| `issue_url`       | GitHub Issue URL，可空      | 按钮       |
| `report_url`      | 诊断报告 URL，可空              | 按钮       |

---

### 设计 Prompt

```text
请设计一张飞书卡片模板：IncidentDetectedCard，用于 AutoRepair 首次发现服务异常并已受理的场景。

设计目标：
这张卡不是详情页，只展示用户判断是否需要关注的最少信息。不要堆字段，不要展示 traceback、fingerprint、函数名、环境、source、line_no 等细节。

视觉风格：
- 企业内部告警通知风
- 红色或橙红色标题栏
- 移动端优先
- 信息简洁、重点突出
- 不要大图，不要宣传海报风

卡片结构：
1. 顶部标题栏：
   - 标题：{{card_title}}
   - 状态标签：{{status_label}}

2. 一句话说明区：
   - 文案：AutoRepair 已接收该异常，并开始自动诊断。

3. 核心信息区，只展示 4 行：
   - Incident：{{incident_id}}
   - 服务：{{service_name}}
   - 级别：{{severity}}
   - 摘要：{{error_brief}}

4. 发生情况区：
   - {{occurrence_text}}

5. 下一步区：
   - {{next_step}}

6. 底部按钮：
   - 查看 Issue：绑定 {{issue_url}}，如果为空则隐藏
   - 查看诊断报告：绑定 {{report_url}}，如果为空则隐藏

变量清单：
{{card_title}}
{{status_label}}
{{incident_id}}
{{service_name}}
{{severity}}
{{error_brief}}
{{occurrence_text}}
{{next_step}}
{{issue_url}}
{{report_url}}

注意：
- 总变量不超过 10 个。
- 不要使用两列字段堆叠。
- 不要展示完整错误位置。
- 不要展示 fingerprint。
- 这张卡只表达“发现了、已受理、正在诊断”。
```

---

## 2. 修复计划卡：RepairPlanReadyCard

### 用途

Agent / Doubao 已完成诊断，生成修复计划，但还没改代码。

### 变量数量：9 个

```text
card_title
status_label
incident_id
service_name
diagnosis_brief
fix_strategy
risk_level
policy_result
report_url
```

### 变量解释

| 变量                | 示例                              |
| ----------------- | ------------------------------- |
| `card_title`      | `已生成修复计划`                       |
| `status_label`    | `待执行`                           |
| `incident_id`     | `INC-xxx`                       |
| `service_name`    | `Acme SupportDesk Lite`         |
| `diagnosis_brief` | `带时区时间与无时区时间直接比较导致 TypeError`   |
| `fix_strategy`    | `统一转换为 UTC aware datetime 后再比较` |
| `risk_level`      | `低风险`                           |
| `policy_result`   | `允许进入自动修复` / `需人工确认`            |
| `report_url`      | 诊断报告链接                          |

---

### 设计 Prompt

```text
请设计一张飞书卡片模板：RepairPlanReadyCard，用于 AutoRepair 完成诊断并生成修复计划的场景。

设计目标：
这张卡用于告诉开发者：Agent 已经理解问题，并给出了修复计划，但尚未修改代码。卡片应突出“根因、策略、风险、准入结果”。

视觉风格：
- 蓝色或蓝紫色标题栏
- 工程分析报告风
- 简洁、可信
- 不要大图
- 不要展示过多技术字段

卡片结构：
1. 顶部标题栏：
   - 标题：{{card_title}}
   - 状态标签：{{status_label}}

2. 基础信息：
   - Incident：{{incident_id}}
   - 服务：{{service_name}}

3. 诊断结论块：
   - 根因：{{diagnosis_brief}}

4. 修复计划块：
   - 策略：{{fix_strategy}}

5. 风险与准入块：
   - 风险等级：{{risk_level}}
   - 准入判断：{{policy_result}}

6. 底部按钮：
   - 查看完整诊断报告：绑定 {{report_url}}，如果为空则隐藏

变量清单：
{{card_title}}
{{status_label}}
{{incident_id}}
{{service_name}}
{{diagnosis_brief}}
{{fix_strategy}}
{{risk_level}}
{{policy_result}}
{{report_url}}

注意：
- 总变量不超过 9 个。
- 不要展示 files_to_modify 的完整列表。
- 不要展示 tests_to_run 的完整命令。
- 不要说“已修复”。
- 这张卡只表示“计划已生成，等待执行/确认”。
```

---

## 3. 修复完成 / PR 待 Review 卡：FixPrReadyCard

### 用途

自动 patch、测试通过、PR 已创建。

### 变量数量：10 个

```text
card_title
status_label
incident_id
service_name
pr_title
fix_brief
test_brief
risk_level
pr_url
report_url
```

### 变量解释

| 变量             | 示例                                      |
| -------------- | --------------------------------------- |
| `card_title`   | `AutoRepair 已完成修复，PR 待 Review`          |
| `status_label` | `待 Review`                              |
| `incident_id`  | `INC-xxx`                               |
| `service_name` | `Acme SupportDesk Lite`                 |
| `pr_title`     | `#12 Fix timezone-aware SLA comparison` |
| `fix_brief`    | `统一 SLA 时间为 UTC aware datetime`         |
| `test_brief`   | `pytest 18/18 通过`                       |
| `risk_level`   | `低风险`                                   |
| `pr_url`       | PR 链接                                   |
| `report_url`   | 修复报告链接                                  |

---

### 设计 Prompt

```text
请设计一张飞书卡片模板：FixPrReadyCard，用于 AutoRepair 已完成自动修复并创建 PR，等待开发者 Review 的场景。

设计目标：
这张卡要突出三件事：已经修复、测试通过、请 Review PR。不要展示太多修复细节，详细 diff 放在 PR 里。

视觉风格：
- 绿色成功态
- 专业工程工具风
- 简洁、可信
- 不要大图
- 不要营销海报风

卡片结构：
1. 顶部标题栏：
   - 标题：{{card_title}}
   - 状态标签：{{status_label}}

2. 基础信息：
   - Incident：{{incident_id}}
   - 服务：{{service_name}}

3. PR 信息：
   - {{pr_title}}

4. 修复摘要：
   - {{fix_brief}}

5. 验证结果：
   - {{test_brief}}
   - 风险等级：{{risk_level}}

6. 底部按钮：
   - 查看 PR：绑定 {{pr_url}}，主按钮
   - 查看修复报告：绑定 {{report_url}}，如果为空则隐藏

变量清单：
{{card_title}}
{{status_label}}
{{incident_id}}
{{service_name}}
{{pr_title}}
{{fix_brief}}
{{test_brief}}
{{risk_level}}
{{pr_url}}
{{report_url}}

注意：
- 总变量不超过 10 个。
- 不要展示完整修改文件列表。
- 不要展示完整测试命令。
- 不要提供一键合并按钮。
- 这张卡只负责引导 Review PR。
```

---

## 4. 需人工介入卡：ManualInterventionCard

### 用途

问题不适合自动修复，或者策略门禁拒绝。

### 变量数量：9 个

```text
card_title
status_label
incident_id
service_name
reason_brief
evidence_brief
suggested_action
issue_url
report_url
```

### 变量解释

| 变量                 | 示例                     |
| ------------------ | ---------------------- |
| `card_title`       | `问题需人工介入`              |
| `status_label`     | `人工处理`                 |
| `incident_id`      | `INC-xxx`              |
| `service_name`     | `PaymentGateway`       |
| `reason_brief`     | `疑似外部数据库连接异常，不适合自动改代码` |
| `evidence_brief`   | `健康检查失败，日志未定位到业务代码变更点` |
| `suggested_action` | `请检查数据库连接、网络与服务凭证`     |
| `issue_url`        | Issue 链接               |
| `report_url`       | 诊断报告链接                 |

---

### 设计 Prompt

```text
请设计一张飞书卡片模板：ManualInterventionCard，用于 AutoRepair 判断问题不适合自动修复、需要人工介入的场景。

设计目标：
这张卡要让用户快速知道：为什么不能自动修、系统已经确认了什么、人工下一步该做什么。不要堆字段，不要显得系统“失败”，而是强调安全边界和谨慎治理。

视觉风格：
- 橙色标题栏
- 风险提示但不恐慌
- 简洁、专业
- 不放大图

卡片结构：
1. 顶部标题栏：
   - 标题：{{card_title}}
   - 状态标签：{{status_label}}

2. 基础信息：
   - Incident：{{incident_id}}
   - 服务：{{service_name}}

3. 人工介入原因：
   - {{reason_brief}}

4. 证据摘要：
   - {{evidence_brief}}

5. 建议动作：
   - {{suggested_action}}

6. 底部按钮：
   - 查看 Issue：绑定 {{issue_url}}，如果为空则隐藏
   - 查看诊断报告：绑定 {{report_url}}，如果为空则隐藏

变量清单：
{{card_title}}
{{status_label}}
{{incident_id}}
{{service_name}}
{{reason_brief}}
{{evidence_brief}}
{{suggested_action}}
{{issue_url}}
{{report_url}}

注意：
- 总变量不超过 9 个。
- 不要展示完整动作列表。
- 不要展示完整日志。
- 不要展示 policy gate 的全部规则。
- 卡片要解释“为什么需要人工”，而不是简单说失败。
```

---

## 5. 周期性总结卡：PeriodicDigestCard

### 用途

日报 / 周报 / 阶段性总结。

### 变量数量：10 个

```text
card_title
period_label
summary_sentence
metric_line_1
metric_line_2
top_issue_1
top_issue_2
todo_brief
report_url
pr_url
```

### 变量解释

| 变量                 | 示例                                            |
| ------------------ | --------------------------------------------- |
| `card_title`       | `AutoRepair 每日修复摘要`                           |
| `period_label`     | `2026-04-26`                                  |
| `summary_sentence` | `今日发现 8 个问题，自动修复 5 个，2 个需人工介入`                |
| `metric_line_1`    | `新增 8｜自动修复 5｜人工介入 2`                          |
| `metric_line_2`    | `成功率 62.5%｜平均诊断 4.2m｜平均修复 12.8m`              |
| `top_issue_1`      | `高频故障：SLA 时间比较错误、数据库超时、缓存不可用`                 |
| `top_issue_2`      | `风险服务：SupportDesk、PaymentGateway、AuthService` |
| `todo_brief`       | `当前有 3 个 PR 待 Review，1 个 P0 需人工处理`            |
| `report_url`       | 完整报告链接                                        |
| `pr_url`           | 待 Review PR 列表链接                              |

---

### 设计 Prompt

```text
请设计一张飞书卡片模板：PeriodicDigestCard，用于 AutoRepair 每日或每周运行摘要。

设计目标：
这张卡是管理摘要，不是单个故障详情。它应该让用户在 10 秒内知道本周期自动修复系统运行情况和待办事项。

视觉风格：
- 灰蓝或深蓝标题栏
- 管理驾驶舱风
- 简洁的数据摘要
- 不要大图
- 不要展示单个 traceback

卡片结构：
1. 顶部标题栏：
   - 标题：{{card_title}}
   - 周期：{{period_label}}

2. 一句话摘要：
   - {{summary_sentence}}

3. 指标摘要区：
   - {{metric_line_1}}
   - {{metric_line_2}}

4. Top 风险区：
   - {{top_issue_1}}
   - {{top_issue_2}}

5. 待办区：
   - {{todo_brief}}

6. 底部按钮：
   - 查看完整报告：绑定 {{report_url}}，如果为空则隐藏
   - 查看待 Review PR：绑定 {{pr_url}}，如果为空则隐藏

变量清单：
{{card_title}}
{{period_label}}
{{summary_sentence}}
{{metric_line_1}}
{{metric_line_2}}
{{top_issue_1}}
{{top_issue_2}}
{{todo_brief}}
{{report_url}}
{{pr_url}}

注意：
- 总变量不超过 10 个。
- 不要做 6 个独立指标卡，移动端会很挤。
- 用两行 metric_line 汇总即可。
- 这张卡强调趋势、摘要和待办。
```

---

# 四、代码侧变量构造也要同步简化

你后续代码不要再传几十个变量。建议统一做成这些函数：

```python
build_incident_detected_variables(...)
build_repair_plan_ready_variables(...)
build_fix_pr_ready_variables(...)
build_manual_intervention_variables(...)
build_periodic_digest_variables(...)
```

每个函数最多返回 10 个 key。

---

## 1. IncidentDetectedCard 变量构造

```python
{
    "card_title": f"【{severity}】检测到服务异常",
    "status_label": "已受理",
    "incident_id": incident.incident_id,
    "service_name": incident.service_name or incident.service,
    "severity": severity,
    "error_brief": make_error_brief(incident),
    "occurrence_text": f"近 10 分钟发生 {incident.occurrence_count} 次",
    "next_step": "正在收集证据并执行自动诊断",
    "issue_url": incident.issue_url or "",
    "report_url": links.report_url or "",
}
```

---

## 2. RepairPlanReadyCard 变量构造

```python
{
    "card_title": "已生成修复计划",
    "status_label": "待执行",
    "incident_id": incident.incident_id,
    "service_name": service.name,
    "diagnosis_brief": plan.root_cause,
    "fix_strategy": plan.fix_strategy,
    "risk_level": plan.risk_level,
    "policy_result": policy_result.summary,
    "report_url": links.report_url or "",
}
```

---

## 3. FixPrReadyCard 变量构造

```python
{
    "card_title": "AutoRepair 已完成修复，PR 待 Review",
    "status_label": "待 Review",
    "incident_id": incident.incident_id,
    "service_name": service.name,
    "pr_title": f"{pr.number} {pr.title}",
    "fix_brief": repair_result.summary,
    "test_brief": test_result.summary,
    "risk_level": repair_result.risk_level,
    "pr_url": pr.url,
    "report_url": links.report_url or "",
}
```

---

## 4. ManualInterventionCard 变量构造

```python
{
    "card_title": "问题需人工介入",
    "status_label": "人工处理",
    "incident_id": incident.incident_id,
    "service_name": service.name,
    "reason_brief": decision.human_reason,
    "evidence_brief": decision.evidence_summary,
    "suggested_action": decision.next_action,
    "issue_url": incident.issue_url or "",
    "report_url": links.report_url or "",
}
```

---

## 5. PeriodicDigestCard 变量构造

```python
{
    "card_title": "AutoRepair 每日修复摘要",
    "period_label": summary.period_label,
    "summary_sentence": summary.sentence,
    "metric_line_1": f"新增 {n}｜自动修复 {fixed}｜人工介入 {manual}",
    "metric_line_2": f"成功率 {rate}｜平均诊断 {triage_time}｜平均修复 {repair_time}",
    "top_issue_1": summary.top_errors_text,
    "top_issue_2": summary.top_services_text,
    "todo_brief": summary.todo_text,
    "report_url": summary.report_url or "",
    "pr_url": summary.pending_pr_url or "",
}
```

---

