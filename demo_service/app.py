import logging
from fastapi import FastAPI, Request, Body, Path
from fastapi.responses import JSONResponse, HTMLResponse
from pydantic import BaseModel
from typing import Optional

from .service import build_user_profile
from .order_service import calculate_order_discount, OrderPreviewRequest
from .ticket_service import submit_ticket
from .ticket_repository import get_ticket
from .logging_config import setup_logging
from .ui import get_support_desk_html


# 初始化日志配置
setup_logging()
logger = logging.getLogger(__name__)

app = FastAPI(title="Demo Service")


# 全局异常捕获中间件
@app.middleware("http")
async def catch_exceptions_middleware(request: Request, call_next):
    try:
        return await call_next(request)
    except Exception as e:
        # 记录完整 Traceback
        logger.exception(f"请求处理异常: {request.method} {request.url.path}")
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal Server Error"},
        )


@app.get("/health")
async def health_check():
    return {"status": "ok"}


@app.get("/users/{user_id}/profile")
async def get_user_profile(user_id: str):
    return build_user_profile(user_id)


@app.get("/", response_class=HTMLResponse)
async def index_page():
    html_content = get_support_desk_html()
    # Add anti-caching headers to ensure latest support desk content is always loaded
    return HTMLResponse(
        content=html_content,
        headers={"Cache-Control": "no-cache, no-store, must-revalidate", "Pragma": "no-cache", "Expires": "0"}
    )


@app.post("/orders/preview")
async def preview_order(request: OrderPreviewRequest):
    return calculate_order_discount(request)


class TicketSubmitRequest(BaseModel):
    customer_id: str
    title: str
    priority: str
    channel: str
    sla_deadline: str
    idempotency_key: Optional[str] = None


@app.post("/tickets/submit")
async def submit_ticket_endpoint(request: TicketSubmitRequest):
    ticket = submit_ticket(request.model_dump())
    return ticket


@app.get("/tickets/{ticket_id}")
async def get_ticket_endpoint(ticket_id: str = Path(..., description="工单ID")):
    ticket = get_ticket(ticket_id)
    if not ticket:
        return JSONResponse(status_code=404, content={"detail": "Ticket not found"})
    return ticket


@app.post("/ticket/create")
async def create_ticket(priority: str = Body(...), sla_hours: Optional[int] = Body(None)):
    from datetime import datetime, timedelta
    # 模拟工单创建，当sla_hours=8时触发bug
    if sla_hours == 8:
        deadline = datetime.now() + timedelta(hours=sla_hours)
        priority_level = priority
    return {"status": "success", "ticket_id": "TK-" + str(datetime.now().timestamp()).split('.')[0], "priority": priority}


@app.post("/ticket/replay")
async def replay_ticket():
    # 模拟幂等性bug
    return {"status": "success", "message": "事件已重复提交", "duplicate": True}
