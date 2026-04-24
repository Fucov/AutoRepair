from .repository import get_user_by_id


def build_user_profile(user_id: str) -> dict:
    """
    构建用户Profile返回数据
    【故意预埋BUG】：用户不存在时直接访问字典属性，触发 TypeError
    """
    user = get_user_by_id(user_id)
    return {
        "id": user["id"],
        "name": user["name"],
        "role": user["role"],
    }
