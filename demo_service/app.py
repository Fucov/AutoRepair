import logging
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, HTMLResponse

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


@app.get("/", response_class=HTMLResponse)
async def index_page():
    html_content = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>Feishu AutoRepair Demo Service</title>
    <style>
        body { font-family: Arial, sans-serif; max-width: 800px; margin: 2rem auto; padding: 0 1rem; }
        .btn { padding: 0.5rem 1rem; margin-right: 1rem; margin-bottom: 1rem; cursor: pointer; }
        pre { background: #f5f5f5; padding: 1rem; border-radius: 4px; overflow-x: auto; min-height: 100px; }
    </style>
</head>
<body>
    <h1>Feishu AutoRepair Demo Service</h1>
    
    <button class="btn" onclick="callApi('/health')">健康检查</button>
    <button class="btn" onclick="callApi('/users/u_1001/profile')">查询正常用户</button>
    <button class="btn" onclick="callApi('/users/not-exist/profile')">触发 Bug</button>
    
    <h3>响应结果：</h3>
    <pre id="result"></pre>

    <script>
        async function callApi(path) {
            const resultEl = document.getElementById('result');
            resultEl.textContent = '请求中...';
            
            try {
                const response = await fetch(path);
                const text = await response.text();
                resultEl.textContent = `Status: ${response.status}\\n\\nResponse:\\n${text}`;
            } catch (e) {
                resultEl.textContent = `请求失败: ${e.message}`;
            }
        }
    </script>
</body>
</html>
    """
    return HTMLResponse(content=html_content)
