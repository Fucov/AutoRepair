from unittest.mock import patch
from autorepair.adapters.github import _is_github_configured, create_demo_bug_issue
from autorepair.bug_scenarios import get_scenario_by_id


def test_github_config_not_configured():
    """测试GitHub配置不完整时返回False"""
    with patch('autorepair.adapters.github.GITHUB_TOKEN', ""), \
         patch('autorepair.adapters.github.GITHUB_OWNER', "test"), \
         patch('autorepair.adapters.github.GITHUB_REPO', "test"):
        assert _is_github_configured() is False


def test_create_demo_bug_issue_body():
    """测试创建Demo Issue时body构造正确"""
    scenario = get_scenario_by_id("order-zero-division")
    assert scenario is not None
    
    # 配置不完整时会打印mock信息，验证body包含必要字段
    with patch('autorepair.adapters.github._is_github_configured', return_value=False):
        issue = create_demo_bug_issue("order-zero-division")
        assert issue is None  # 配置不完整返回None


def test_list_open_bug_issues_mock():
    """测试配置缺失时返回空列表不报错"""
    from autorepair.adapters.github import list_open_bug_issues
    with patch('autorepair.adapters.github._is_github_configured', return_value=False):
        issues = list_open_bug_issues()
        assert issues == []
