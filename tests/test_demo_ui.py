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
    
    # 检查操作按钮
    assert "系统健康检查" in response.text
    assert "提交正常 P2 工单" in response.text
    assert "提交带 +08:00 SLA 的紧急工单" in response.text
    assert "重复提交同一飞书事件" in response.text
    
    # 检查工单列表
    assert "工单列表" in response.text
    assert "工单编号" in response.text
    assert "客户" in response.text
    assert "来源渠道" in response.text
    assert "优先级" in response.text
    assert "SLA 截止时间" in response.text
    assert "处理人" in response.text
    assert "状态" in response.text
    
    # 检查事件流
    assert "最近事件流" in response.text
    assert "飞书渠道收到客户反馈" in response.text
    assert "P1 工单" in response.text
    assert "进入 SLA 风险" in response.text
    assert "AutoRepair 正在监听服务日志" in response.text
    assert "最近一次异常将写入 demo_service/logs/app.log" in response.text
    
    # 检查响应区
    assert "响应结果" in response.text
    assert "后台已生成 traceback，可运行 python scripts/watch_once.py 扫描并生成 Incident。" in response.text
    
    # 检查mock数据
    assert "TKT-20260425-001" in response.text
    assert "阿里巴巴" in response.text
    assert "华为技术" in response.text
    assert "张三" in response.text
    assert "孙七" in response.text
