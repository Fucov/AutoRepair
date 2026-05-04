from __future__ import annotations

import logging

from autorepair.repair_agent.schemas import RepairAgentContext, RepairAgentResult
from autorepair.repair_agent.tools import MiniRepairTools

logger = logging.getLogger(__name__)


def try_apply_known_playbook(
    context: RepairAgentContext,
    tools: MiniRepairTools,
) -> RepairAgentResult | None:
    if context.error_message and "timezone" in context.error_message.lower():
        return _fix_timezone_playbook(context, tools)

    if context.error_message and "cannot compare" in context.error_message.lower():
        if context.suspected_file and "ticket" in context.suspected_file.lower():
            return _fix_timezone_playbook(context, tools)

    return None


def _fix_timezone_playbook(
    context: RepairAgentContext,
    tools: MiniRepairTools,
) -> RepairAgentResult | None:
    target_file = context.suspected_file
    if not target_file:
        return None

    read_result = tools.read_file(target_file)
    if not read_result.ok:
        return None

    content = read_result.output
    if "from datetime import datetime" not in content and "utcnow" not in content:
        return None

    changed_files: list[str] = [target_file]

    if "from datetime import datetime" in content and "timezone" not in content:
        r = tools.apply_replace(
            target_file,
            "from datetime import datetime",
            "from datetime import datetime, timezone",
        )
        if not r.ok:
            logger.warning("Playbook timezone import 替换失败: %s", r.error)

    r = tools.apply_replace(
        target_file,
        "datetime.utcnow()",
        "datetime.now(timezone.utc)",
    )
    if not r.ok:
        logger.debug("Playbook utcnow 替换跳过: %s", r.error)

    r = tools.apply_replace(
        target_file,
        ".replace(tzinfo=None)",
        ".astimezone(timezone.utc)",
    )
    if not r.ok:
        logger.debug("Playbook replace tzinfo 跳过: %s", r.error)

    r = tools.apply_replace(
        target_file,
        ".replace(tzinfo=timezone.utc)",
        ".astimezone(timezone.utc)",
    )
    if not r.ok:
        logger.debug("Playbook replace tzinfo=utc 跳过: %s", r.error)

    target_cmd = context.target_test_command or "pytest -q"
    target_result = tools.run_tests(target_cmd)

    full_result = tools.run_tests(context.full_test_command)

    if target_result.ok and full_result.ok:
        diff_result = tools.git_diff()
        return RepairAgentResult(
            ok=True,
            status="fixed",
            summary="Playbook 修复: 统一 datetime 时区为 timezone.utc",
            changed_files=changed_files,
            tests_run=[target_cmd, context.full_test_command],
            target_test_passed=True,
            full_test_passed=True,
            diff=diff_result.output if diff_result.ok else None,
        )

    return RepairAgentResult(
        ok=False,
        status="test_failed",
        summary="Playbook 修复后测试仍失败",
        changed_files=changed_files,
        tests_run=[target_cmd, context.full_test_command],
        target_test_passed=target_result.ok,
        full_test_passed=full_result.ok,
    )
