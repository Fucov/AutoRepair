from typing import Dict, Optional

# 模拟用户数据库
fake_users: Dict[str, Dict] = {
    "u_1001": {"id": "u_1001", "name": "Alice", "role": "developer"},
    "u_1002": {"id": "u_1002", "name": "Bob", "role": "tester"},
}


def get_user_by_id(user_id: str) -> Optional[Dict]:
    """
    根据用户ID查询用户信息
    :param user_id: 用户ID
    :return: 用户信息字典，不存在返回 None
    """
    return fake_users.get(user_id)
