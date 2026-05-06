from __future__ import annotations

import logging
import re

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

    if context.error_type == "UnboundLocalError" and context.suspected_file:
        return _fix_unbound_local_playbook(context, tools)

    if context.error_type == "NameError" and context.suspected_file:
        return _fix_nameerror_playbook(context, tools)

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


def _fix_unbound_local_playbook(
    context: RepairAgentContext,
    tools: MiniRepairTools,
) -> RepairAgentResult | None:
    target_file = context.suspected_file
    if not target_file:
        return None

    var_match = re.search(r"local variable '(\w+)'", context.error_message or "")
    if not var_match:
        return None
    var_name = var_match.group(1)

    read_result = tools.read_file(target_file)
    if not read_result.ok:
        return None

    lines = read_result.output.splitlines()
    import_line_idx = None
    import_text = None

    for i, line in enumerate(lines):
        stripped = line.strip()
        if re.match(rf"^from\s+\S+\s+import\s+.*\b{re.escape(var_name)}\b", stripped):
            indent = len(line) - len(line.lstrip())
            if indent >= 8:
                import_line_idx = i
                import_text = stripped
                break

    if import_line_idx is None or not import_text:
        return None

    func_line_idx = None
    for i in range(import_line_idx - 1, -1, -1):
        stripped = lines[i].strip()
        if stripped.startswith("async def ") or stripped.startswith("def "):
            func_line_idx = i
            break
    if func_line_idx is None:
        return None

    new_lines = lines[:import_line_idx] + lines[import_line_idx + 1:]
    func_body_indent = lines[func_line_idx + 1][: len(lines[func_line_idx + 1]) - len(lines[func_line_idx + 1].lstrip())] if func_line_idx + 1 < len(new_lines) else "    "
    new_import_line = f"{func_body_indent}{import_text}"
    insert_pos = func_line_idx + 1
    new_lines = new_lines[:insert_pos] + [new_import_line] + new_lines[insert_pos:]

    new_content = "\n".join(new_lines)
    if not new_content.endswith("\n"):
        new_content += "\n"

    r = tools.rewrite_file(target_file, new_content)
    if not r.ok:
        return None

    target_cmd = context.target_test_command or "pytest -q"
    target_result = tools.run_tests(target_cmd)
    full_result = tools.run_tests(context.full_test_command)

    if target_result.ok and full_result.ok:
        diff_result = tools.git_diff()
        return RepairAgentResult(
            ok=True,
            status="fixed",
            summary=f"Playbook 修复: 将 '{import_text}' 从条件块提升到函数顶层，解决 UnboundLocalError",
            changed_files=[target_file],
            tests_run=[target_cmd, context.full_test_command],
            target_test_passed=True,
            full_test_passed=True,
            diff=diff_result.output if diff_result.ok else None,
        )

    return RepairAgentResult(
        ok=False,
        status="test_failed",
        summary=f"Playbook 修复 UnboundLocalError 后测试仍失败",
        changed_files=[target_file],
        tests_run=[target_cmd, context.full_test_command],
        target_test_passed=target_result.ok,
        full_test_passed=full_result.ok,
    )


def _fix_nameerror_playbook(
    context: RepairAgentContext,
    tools: MiniRepairTools,
) -> RepairAgentResult | None:
    target_file = context.suspected_file
    if not target_file:
        return None

    var_match = re.search(r"name '(\w+)' is not defined", context.error_message or "")
    if not var_match:
        return None
    var_name = var_match.group(1)

    read_result = tools.read_file(target_file)
    if not read_result.ok:
        return None

    content = read_result.output
    lines = content.splitlines()
    fixed = False

    for line in lines:
        stripped = line.strip()
        if stripped.startswith('#'):
            continue
        if f'"{var_name}"' in line or f"'{var_name}'" in line:
            continue
        if var_name not in line:
            continue

        patterns = [
            (f"= {var_name}", f'= "{var_name}"'),
            (f"= {var_name}\n", f'= "{var_name}"\n'),
        ]
        for old_pat, new_pat in patterns:
            if old_pat in line:
                old_text = line.rstrip()
                new_text = line.replace(old_pat, new_pat).rstrip()
                r = tools.apply_replace(target_file, old_text, new_text)
                if r.ok:
                    fixed = True
                    break
        if fixed:
            break

    if not fixed:
        return None

    target_cmd = context.target_test_command or "pytest -q"
    target_result = tools.run_tests(target_cmd)
    full_result = tools.run_tests(context.full_test_command)

    if target_result.ok and full_result.ok:
        diff_result = tools.git_diff()
        return RepairAgentResult(
            ok=True,
            status="fixed",
            summary=f"Playbook 修复: 将 '{var_name}' 添加引号，解决 NameError",
            changed_files=[target_file],
            tests_run=[target_cmd, context.full_test_command],
            target_test_passed=True,
            full_test_passed=True,
            diff=diff_result.output if diff_result.ok else None,
        )

    return RepairAgentResult(
        ok=False,
        status="test_failed",
        summary=f"Playbook 修复 NameError 后测试仍失败",
        changed_files=[target_file],
        tests_run=[target_cmd, context.full_test_command],
        target_test_passed=target_result.ok,
        full_test_passed=full_result.ok,
    )
