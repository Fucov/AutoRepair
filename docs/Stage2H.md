你现在继续开发 FeishuAutoRepair 的飞书卡片模板系统。

当前问题：
之前设计的飞书卡片变量太多，每张卡超过十几个字段，移动端排版很差，卡片变成了字段堆叠。现在需要重新设计为“轻量摘要卡片”：每张卡片最多 10 个变量，只展示用户决策所需信息，详细信息放到报告、Issue 或 PR 中。

请重构飞书卡片模板变量和代码实现。

重要要求：
- 每张卡片变量数不得超过 10 个。
- 不要在卡片上展示 fingerprint、error_function、source、environment、service_id、完整 traceback、完整测试命令、完整文件列表。
- 只展示摘要信息。
- 所有详细信息放到 report_url / issue_url / pr_url。
- 不要做卡片回调。
- 不要使用 localhost 链接作为按钮。
- pytest -q 必须通过。
- pytest -q -m agent_target 仍然应该失败，不要修复预埋 Bug。

请支持 5 张卡片：

1. IncidentDetectedCard
2. RepairPlanReadyCard
3. FixPrReadyCard
4. ManualInterventionCard
5. PeriodicDigestCard

============================================================
一、变量定义
============================================================

IncidentDetectedCard 只允许以下变量：
- card_title
- status_label
- incident_id
- service_name
- severity
- error_brief
- occurrence_text
- next_step
- issue_url
- report_url

RepairPlanReadyCard 只允许以下变量：
- card_title
- status_label
- incident_id
- service_name
- diagnosis_brief
- fix_strategy
- risk_level
- policy_result
- report_url

FixPrReadyCard 只允许以下变量：
- card_title
- status_label
- incident_id
- service_name
- pr_title
- fix_brief
- test_brief
- risk_level
- pr_url
- report_url

ManualInterventionCard 只允许以下变量：
- card_title
- status_label
- incident_id
- service_name
- reason_brief
- evidence_brief
- suggested_action
- issue_url
- report_url

PeriodicDigestCard 只允许以下变量：
- card_title
- period_label
- summary_sentence
- metric_line_1
- metric_line_2
- top_issue_1
- top_issue_2
- todo_brief
- report_url
- pr_url

请新增一个常量或测试，强制校验每个 builder 返回的 key 集合必须等于上述列表，不允许多字段。

============================================================
二、变量构造器
============================================================

修改 autorepair/cards/variables.py。

实现：

build_incident_detected_variables(...)
build_repair_plan_ready_variables(...)
build_fix_pr_ready_variables(...)
build_manual_intervention_variables(...)
build_periodic_digest_variables(...)

要求：
- 每个函数返回变量数不得超过 10。
- 所有长文本都要压缩到一句话。
- error_brief 由 error_type + message 简化生成，长度建议不超过 80 字。
- occurrence_text 形如“近 10 分钟发生 6 次”。
- next_step 形如“正在收集证据并执行自动诊断”。
- diagnosis_brief 和 fix_strategy 不超过 100 字。
- files_to_modify / tests_to_run 不直接放卡片，写入报告即可。
- 如果链接不存在，传空字符串。

============================================================
三、Prompt / README 同步
============================================================

更新 README 中的飞书卡片模板说明，明确每个模板只需要配置上述变量。

删除旧文档中超过 10 个变量的字段说明。

新增一节：
“卡片是摘要，不是详情页。详细 traceback、fingerprint、测试命令、修改文件列表均写入报告或 PR 描述。”

============================================================
四、测试要求
============================================================

新增或修改测试：

1. test_incident_detected_variables_keys
   - 断言返回 key 集合严格等于指定 10 个变量。

2. test_repair_plan_ready_variables_keys
   - 断言返回 key 集合严格等于指定 9 个变量。

3. test_fix_pr_ready_variables_keys
   - 断言返回 key 集合严格等于指定 10 个变量。

4. test_manual_intervention_variables_keys
   - 断言返回 key 集合严格等于指定 9 个变量。

5. test_periodic_digest_variables_keys
   - 断言返回 key 集合严格等于指定 10 个变量。

6. 测试所有变量值都是可 JSON 序列化的 string/number/bool/list，不允许复杂 Pydantic 对象。

7. 保留 FeishuClient 发送 template card 的测试：
   - content 必须是 JSON 字符串
   - content 解析后 type == template
   - data.template_id 正确
   - data.template_variable 等于瘦身后的变量

8. 旧的 build_incident_card_payload 可以保留兼容，但新主路径必须使用瘦身变量。

============================================================
五、脚本要求
============================================================

scripts/send_test_feishu_card.py 支持：

python scripts/send_test_feishu_card.py --type incident_detected
python scripts/send_test_feishu_card.py --type repair_plan_ready
python scripts/send_test_feishu_card.py --type fix_pr_ready
python scripts/send_test_feishu_card.py --type manual_intervention
python scripts/send_test_feishu_card.py --type periodic_digest

每次输出：
- template_name
- template_id
- variable_count
- variables keys
- mode real/mock
- ok true/false

如果 variable_count > 10，脚本应报错。

============================================================
六、输出要求
============================================================

完成后输出：
1. 修改文件列表。
2. 五张卡片的最终变量清单。
3. pytest -q 结果。
4. 每个 send_test_feishu_card.py --type 的示例输出。
5. 明确说明：所有卡片变量均不超过 10 个，详细信息改由 report_url / issue_url / pr_url 承载。