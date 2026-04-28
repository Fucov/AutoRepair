import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))

from fastapi.testclient import TestClient
from demo_service.app import app

client = TestClient(app)

def test_homepage_contains_required_elements():
    response = client.get("/")
    assert response.status_code == 200

    # Stage3A2 企业工单与 SLA 管理后台关键词
    assert "工单总览" in response.text
    assert "SLA 风险" in response.text
    assert "飞书渠道" in response.text
    assert "客户租户" in response.text
    assert "系统设置" in response.text
    assert "Demo Tenant" in response.text
    assert "Acme SupportDesk Lite" in response.text
    assert "环境：Local Demo" in response.text
    assert "Agent 接入：Black-box Log Watcher" in response.text

    # KPI 和核心模块
    assert "今日新工单" in response.text
    assert "P1 工单" in response.text
    assert "飞书事件积压" in response.text
    assert "平均响应时长" in response.text
    assert "工单队列" in response.text
    assert "最近更新" in response.text
    assert "飞书事件流" in response.text

    # 业务动作区
    assert "系统健康检查" in response.text
    assert "创建 P1 飞书渠道工单" in response.text
    assert "重试飞书事件同步" in response.text
    assert "批量刷新 SLA 状态" in response.text
    assert "服务端处理失败，异常已写入服务日志" in response.text

    # 检查响应区
    assert "API 响应结果" in response.text
    assert "Status:" in response.text

    # 检查 mock 数据
    assert "TK-1024" in response.text
    assert "TK-1031" in response.text
    assert "北航实验室" in response.text
    assert "Acme 财务部" in response.text
    assert "oncall-zhang" in response.text
    assert "support-chen" in response.text

    # 页面不应暴露演示/修复提示
    assert "触发 Runtime Bug" not in response.text
    assert "请运行 python scripts/watch_once.py" not in response.text
    assert "供 AutoRepair 捕获" not in response.text
