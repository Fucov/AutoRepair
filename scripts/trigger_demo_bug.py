import sys
from pathlib import Path

# 将项目根目录加入Python路径，解决模块找不到问题
sys.path.append(str(Path(__file__).parent.parent.resolve()))

import httpx
from autorepair.bug_scenarios import BUG_SCENARIOS, get_scenario_by_id


def trigger_scenario(scenario_id: str) -> bool:
    """触发指定场景的Bug"""
    scenario = get_scenario_by_id(scenario_id)
    if not scenario:
        print(f"错误: 找不到scenario_id: {scenario_id}")
        print("可用的scenario_id:")
        for s in BUG_SCENARIOS:
            print(f"  {s.scenario_id} - {s.title}")
        return False
    
    print(f"正在触发Bug场景: {scenario.title} ({scenario_id})")
    print(f"端点: {scenario.endpoint}")
    print(f"期望错误: {scenario.expected_error_type}")
    
    base_url = "http://127.0.0.1:8000"
    
    try:
        if scenario.scenario_id == "ticket-nameerror-overdue":
            # 触发ticket NameError bug（使用过期的sla_deadline）
            payload = {
                "customer_id": "c_1001",
                "title": "过期工单测试",
                "priority": "P1",
                "channel": "feishu",
                "sla_deadline": "2020-01-01T00:00:00",
                "idempotency_key": "evt_test_001"
            }
            response = httpx.post(f"{base_url}/tickets/submit", json=payload)
        elif scenario.scenario_id == "ticket-idempotency-duplicate":
            # 触发幂等性bug
            payload = {
                "customer_id": "c_1002",
                "title": "重复提交测试",
                "priority": "P2",
                "channel": "api",
                "sla_deadline": "2099-01-01T00:00:00",
                "idempotency_key": "evt_duplicate_001"
            }
            # 提交两次
            response = httpx.post(f"{base_url}/tickets/submit", json=payload)
            print(f"第一次提交: {response.status_code}")
            response = httpx.post(f"{base_url}/tickets/submit", json=payload)
        elif scenario.scenario_id == "order-zero-division":
            # 触发订单除零bug
            payload = {
                "customer_id": "c_2001",
                "items": [{"product_id": "p_1", "quantity": 2, "price": 0}],
                "discount": 0.8
            }
            response = httpx.post(f"{base_url}/orders/preview", json=payload)
        elif scenario.scenario_id == "user-missing-profile":
            # 触发用户缺失bug
            response = httpx.get(f"{base_url}/users/not-exist/profile")
        else:
            print(f"未实现的触发方式: {scenario_id}")
            return False
        
        print(f"状态码: {response.status_code}")
        print(f"响应: {response.text}")
        
        if response.status_code >= 500:
            print("✅ Bug触发成功！")
            return True
        else:
            print(f"⚠️  响应状态码不是500，可能没有触发Bug")
            return False
            
    except Exception as e:
        print(f"请求失败: {e}")
        return False


if __name__ == "__main__":
    scenario_id = sys.argv[1] if len(sys.argv) > 1 else "user-missing-profile"
    success = trigger_scenario(scenario_id)
    sys.exit(0 if success else 1)
