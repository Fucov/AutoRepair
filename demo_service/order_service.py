from pydantic import BaseModel


class OrderPreviewRequest(BaseModel):
    order_id: str
    total_amount: float
    discount_amount: float


class OrderPreviewResponse(BaseModel):
    order_id: str
    final_amount: float
    discount_rate: float


def calculate_order_discount(request: OrderPreviewRequest) -> OrderPreviewResponse:
    """
    计算订单折扣
    【故意预埋BUG】：当total_amount为0时触发ZeroDivisionError
    """
    # 直接计算折扣率，不处理total_amount <= 0的情况
    discount_rate = request.discount_amount / request.total_amount
    final_amount = request.total_amount - request.discount_amount
    
    return OrderPreviewResponse(
        order_id=request.order_id,
        final_amount=final_amount,
        discount_rate=round(discount_rate * 100, 2)
    )
