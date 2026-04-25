import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))

from fastapi.testclient import TestClient
from demo_service.app import app

client = TestClient(app)

def test_homepage_contains_required_elements():
    response = client.get("/")
    assert response.status_code == 200
    
    # 检查统计卡片
    assert "今日工单" in response.text
    assert "P1 紧急工单" in response.text
    assert "SLA 风险工单" in response.text
    assert "飞书渠道占比" in response.text
    
    # 检查Header信息
    assert "Agent 接入" in response.text
    assert "Black-box Log Watcher" in response.text
    assert "环境：Local Demo" in response.text
    assert "服务 ID：supportdesk-lite" in response.text
    
    # 检查操作按钮
    assert "系统健康检查" in response.text
    assert "创建正常 P2 工单" in response.text
    assert "创建带 +08:00 SLA 的紧急工单（触发 Runtime Bug）" in response.text
    assert "重复提交同一飞书事件（模拟幂等性缺陷）" in response.text
    
    # 检查工单队列
    assert "工单队列" in response.text
    assert "工单编号" in response.text
    assert "客户" in response.text
    assert "来源渠道" in response.text
    assert "优先级" in response.text
    assert "SLA 截止时间" in response.text
    assert "处理人" in response.text
    assert "状态" in response.text
    
    # 检查服务运行状态
    assert "服务运行状态" in response.text
    assert "日志监听：demo_service/logs/app.log" in response.text
    assert "AutoRepair 状态：等待扫描" in response.text
    
    # 检查事件流
    assert "最近事件流" in response.text
    assert "飞书渠道收到客户反馈" in response.text
    assert "P1 工单进入 SLA 风险" in response.text
    assert "AutoRepair 正在监听服务日志" in response.text
    assert "新异常会被写入 demo_service/logs/app.log" in response.text
    
    # 检查响应区
    assert "API 响应结果" in response.text
    assert "服务端已生成 traceback。请运行 python scripts/watch_once.py 扫描并生成 Incident。" in response.text
    
    # 检查mock数据
    assert "TK-1024" in response.text
    assert "北航实验室" in response.text
    assert "Acme 财务部" in response.text
    assert "oncall-zhang" in response.text
    assert "support-chen" in response.text
