import tempfile
from pathlib import Path
from autorepair.log_parser import read_latest_traceback, extract_error_summary

# 模拟包含框架噪声的Traceback示例
SAMPLE_TRACEBACK = """Traceback (most recent call last):
  File "/site-packages/starlette/middleware/errors.py", line 158, in __call__
    await self.app(scope, receive, send)
  File "/site-packages/starlette/routing.py", line 227, in app
    await route.handle(scope, receive, send)
  File "/site-packages/starlette/routing.py", line 68, in handle
    await self.app(scope, receive, send)
  File "/site-packages/starlette/routing.py", line 287, in app
    response = await func(request)
  File "/demo_service/app.py", line 37, in get_user_profile
    return build_user_profile(user_id)
  File "/demo_service/service.py", line 11, in build_user_profile
    "id": user["id"],
TypeError: 'NoneType' object is not subscriptable
"""


def test_read_latest_traceback_file_not_exist():
    """测试日志文件不存在时返回None"""
    result = read_latest_traceback("/non/existent/path/app.log")
    assert result is None


def test_extract_error_summary_from_traceback():
    """测试能正确从Traceback中提取错误信息"""
    summary = extract_error_summary(SAMPLE_TRACEBACK)
    assert summary is not None
    assert summary.error_type == "TypeError"
    assert summary.message == "'NoneType' object is not subscriptable"
    assert summary.suspected_file == "demo_service/service.py"
    assert summary.line_no == 11
    assert summary.function == "build_user_profile"
    assert len(summary.fingerprint) == 12


def test_extract_error_summary_prioritize_project_files():
    """测试优先选择项目内文件而非第三方框架文件"""
    summary = extract_error_summary(SAMPLE_TRACEBACK)
    assert summary is not None
    # 应该选择demo_service/service.py而不是site-packages里的文件
    assert "site-packages" not in summary.suspected_file
    assert "service.py" in summary.suspected_file


def test_fingerprint_stable():
    """测试相同错误的fingerprint是稳定的"""
    summary1 = extract_error_summary(SAMPLE_TRACEBACK)
    summary2 = extract_error_summary(SAMPLE_TRACEBACK)
    assert summary1.fingerprint == summary2.fingerprint
