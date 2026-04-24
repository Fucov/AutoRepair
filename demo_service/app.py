import logging
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from .service import build_user_profile
from .logging_config import setup_logging


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
