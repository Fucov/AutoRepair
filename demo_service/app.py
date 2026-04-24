import logging
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, HTMLResponse

from fastapi import Body
from .service import build_user_profile
from .order_service import calculate_order_discount, OrderPreviewRequest
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
    <title>Acme Lite Service Console</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f5f7fa; min-height: 100vh; }
        .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 1.5rem 2rem; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }
        .header h1 { font-size: 1.8rem; font-weight: 600; }
        .container { max-width: 1000px; margin: 2rem auto; padding: 0 2rem; }
        .card { background: white; border-radius: 8px; padding: 1.5rem; margin-bottom: 2rem; box-shadow: 0 2px 12px rgba(0,0,0,0.05); }
        .card-title { font-size: 1.2rem; font-weight: 600; color: #333; margin-bottom: 1rem; padding-bottom: 0.5rem; border-bottom: 1px solid #eee; }
        .status-badge { display: inline-block; padding: 0.3rem 0.8rem; border-radius: 20px; font-size: 0.9rem; font-weight: 500; background: #f6ffed; color: #52c41a; }
        .btn-group { display: flex; gap: 1rem; flex-wrap: wrap; margin-bottom: 1rem; }
        .btn { padding: 0.6rem 1.2rem; border: none; border-radius: 4px; font-size: 0.95rem; cursor: pointer; transition: all 0.2s; font-weight: 500; }
        .btn-primary { background: #1890ff; color: white; }
        .btn-primary:hover { background: #40a9ff; }
        .btn-success { background: #52c41a; color: white; }
        .btn-success:hover { background: #73d13d; }
        .btn-warning { background: #faad14; color: white; }
        .btn-warning:hover { background: #ffc53d; }
        .btn-danger { background: #ff4d4f; color: white; }
        .btn-danger:hover { background: #ff7875; }
        .btn-desc { font-size: 0.85rem; color: #8c8c8c; margin-top: 0.3rem; }
        .result-area { margin-top: 1.5rem; }
        .result-area h3 { font-size: 1rem; color: #333; margin-bottom: 0.8rem; }
        pre { background: #fafafa; border: 1px solid #eee; border-radius: 4px; padding: 1rem; overflow-x: auto; min-height: 120px; font-size: 0.9rem; color: #333; line-height: 1.5; }
    </style>
</head>
<body>
    <div class="header">
        <h1>Acme Lite CRM & Order Console</h1>
    </div>
    
    <div class="container">
        <div class="card">
            <div class="card-title">系统状态</div>
            <span class="status-badge">✅ 服务运行中</span>
            <div style="margin-top: 1rem; padding: 0.8rem; background: #f0f5ff; border-radius: 4px; font-size: 0.9rem; color: #333;">
                这是一个用于模拟企业内部用户画像与订单预览服务的轻量业务控制台。异常操作会触发服务端 Bug，供 AutoRepair Agent 捕获并修复。
            </div>
        </div>

        <div class="card">
            <div class="card-title">业务操作</div>
            
            <div class="btn-group">
                <div>
                    <button class="btn btn-primary" onclick="callHealthCheck()">系统健康检查</button>
                    <div class="btn-desc">查询服务运行状态</div>
                </div>
                <div>
                    <button class="btn btn-success" onclick="getNormalUserProfile()">查询正常员工画像</button>
                    <div class="btn-desc">查询员工ID u_1001 的信息</div>
                </div>
                <div>
                    <button class="btn btn-warning" onclick="getMissingUserProfile()">查询缺失员工画像</button>
                    <div class="btn-desc">Demo: 会触发 TypeError 异常</div>
                </div>
                <div>
                    <button class="btn btn-danger" onclick="previewAbnormalOrder()">提交 0 元异常订单</button>
                    <div class="btn-desc">Demo: 会触发 ZeroDivisionError 异常</div>
                </div>
            </div>
        </div>

        <div class="card">
            <div class="card-title">响应结果</div>
            <pre id="result">等待操作...</pre>
        </div>
    </div>

    <script>
        const resultEl = document.getElementById('result');

        async function callHealthCheck() {
            resultEl.textContent = '请求中...';
            try {
                const response = await fetch('/health');
                const text = await response.text();
                resultEl.textContent = `Status: ${response.status}\\n\\nResponse:\\n${text}`;
            } catch (e) {
                resultEl.textContent = `请求失败: ${e.message}`;
            }
        }

        async function getNormalUserProfile() {
            resultEl.textContent = '请求中...';
            try {
                const response = await fetch('/users/u_1001/profile');
                const text = await response.text();
                resultEl.textContent = `Status: ${response.status}\\n\\nResponse:\\n${text}`;
            } catch (e) {
                resultEl.textContent = `请求失败: ${e.message}`;
            }
        }

        async function getMissingUserProfile() {
            resultEl.textContent = '请求中...';
            try {
                const response = await fetch('/users/not-exist/profile');
                const text = await response.text();
                resultEl.textContent = `Status: ${response.status}\\n\\nResponse:\\n${text}`;
            } catch (e) {
                resultEl.textContent = `请求失败: ${e.message}`;
            }
        }

        async function previewAbnormalOrder() {
            resultEl.textContent = '请求中...';
            try {
                const response = await fetch('/orders/preview', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        order_id: "o_1001",
                        total_amount: 0,
                        discount_amount: 10
                    })
                });
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


@app.post("/orders/preview")
async def preview_order(request: OrderPreviewRequest):
    return calculate_order_discount(request)
