import uuid
from typing import Any, Optional

from .schemas import RepairPlanData
from ..schemas import Incident


def build_repair_plan(
    incident: Incident,
    service_name: str,
    root_cause: Optional[str] = None,
    test_command: Optional[str] = None,
) -> RepairPlanData:
    summary = incident.error_summary
    error_type = summary.error_type or "UnknownError"
    error_message = summary.message or "未提供错误信息"
    suspected_file = summary.suspected_file
    suspected_line = summary.line_no
    suspected_function = summary.function

    if root_cause:
        root_cause_analysis = root_cause
    else:
        root_cause_analysis = (
            f"在 {suspected_file or '未知文件'}"
            f"{'第' + str(suspected_line) + '行' if suspected_line else ''}"
            f"{'的 ' + suspected_function + ' 函数中' if suspected_function else ''}，"
            f"触发了 {error_type}: {error_message}。"
            f"根据 Traceback 分析，最可能的根因是代码缺少必要的空值检查或类型校验。"
        )

    fix_steps = [
        f"分析 {suspected_file or '相关文件'} 中的错误上下文，定位触发 {error_type} 的代码路径",
        "通过 LLM 生成针对性修复补丁，确保修复逻辑符合项目代码风格",
        "使用 fuzzy matching 将补丁应用到源文件，处理行偏移和格式差异",
        "在隔离 worktree 中运行目标测试（agent_target），验证修复是否生效",
        "运行完整测试套件（pytest -q），确保修复不引入回归",
        "创建修复分支并提交代码，推送至远程仓库",
        "创建 Pull Request，附带诊断报告链接和修复说明",
    ]

    affected_files = []
    if suspected_file:
        affected_files.append(suspected_file)

    test_strategy = (
        f"1. 首先运行目标测试: {test_command or 'pytest -q -m agent_target'} 验证修复是否解决了原始错误\n"
        f"2. 运行完整测试套件: pytest -q 确保无回归\n"
        f"3. 检查 traceback 中涉及的所有代码路径是否都已覆盖"
    )

    if summary.suspected_file:
        estimated_changes = f"预计修改文件: {summary.suspected_file}，变更范围约 5-20 行"
    else:
        estimated_changes = "预计修改 1-3 个文件，变更范围约 5-30 行"

    rollback_plan = (
        "1. 如果修复 PR 中发现问题，可以直接关闭 PR\n"
        "2. 修复在隔离 worktree 中执行，不影响主分支\n"
        "3. 如需回退已合并的修复，可通过 git revert PR 对应的 commit"
    )

    return RepairPlanData(
        plan_id=f"PLAN-{uuid.uuid4().hex[:8]}",
        incident_id=incident.incident_id,
        issue_number=incident.issue_number,
        service_name=service_name,
        error_type=error_type,
        error_message=error_message[:300],
        suspected_file=suspected_file,
        suspected_line=suspected_line,
        suspected_function=suspected_function,
        root_cause_analysis=root_cause_analysis,
        fix_steps=fix_steps,
        affected_files=affected_files,
        test_strategy=test_strategy,
        target_test_command=test_command,
        risk_level="medium",
        estimated_changes=estimated_changes,
        rollback_plan=rollback_plan,
    )


def render_repair_plan_plaintext(plan: RepairPlanData) -> str:
    lines = [
        "=" * 55,
        "FeishuAutoRepair 自动修复计划",
        "=" * 55,
        "",
        f"计划ID: {plan.plan_id}",
        f"事件ID: {plan.incident_id}",
        f"服务名称: {plan.service_name}",
        f"生成时间: {plan.created_at}",
        "",
        "-" * 55,
        "一、故障概述",
        "-" * 55,
        f"错误类型: {plan.error_type}",
        f"错误信息: {plan.error_message}",
        f"Issue编号: #{plan.issue_number}" if plan.issue_number else "",
        f"疑似文件: {plan.suspected_file or '待定位'}",
        f"疑似行号: {plan.suspected_line or '待定位'}",
        f"疑似函数: {plan.suspected_function or '待定位'}",
        "",
        "-" * 55,
        "二、根因分析",
        "-" * 55,
        plan.root_cause_analysis,
        "",
        "-" * 55,
        "三、修复步骤",
        "-" * 55,
    ]
    for i, step in enumerate(plan.fix_steps, 1):
        lines.append(f"  {i}. {step}")

    lines += [
        "",
        "-" * 55,
        "四、受影响文件",
        "-" * 55,
    ]
    if plan.affected_files:
        for f in plan.affected_files:
            lines.append(f"  - {f}")
    else:
        lines.append("  待修复执行时动态确定")

    lines += [
        "",
        "-" * 55,
        "五、测试策略",
        "-" * 55,
        plan.test_strategy,
        "",
        "-" * 55,
        "六、变更评估",
        "-" * 55,
        f"风险等级: {plan.risk_level}",
        f"预估变更: {plan.estimated_changes}",
        "",
        "-" * 55,
        "七、回退方案",
        "-" * 55,
        plan.rollback_plan,
        "",
        "=" * 55,
        "本修复计划由 AutoRepair Agent 自动生成。",
        "修复将在隔离 worktree 中执行，不会直接影响主分支。",
        "=" * 55,
    ]
    return "\n".join(lines)
