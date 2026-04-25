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
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Acme SupportDesk Lite</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
        }
        body {
            background-color: #f5f7fa;
            color: #333;
            line-height: 1.6;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
        }
        .header {
            margin-bottom: 30px;
            padding-bottom: 20px;
            border-bottom: 1px solid #eaecef;
        }
        .header h1 {
            color: #2c3e50;
            font-size: 28px;
            margin-bottom: 8px;
        }
        .header p {
            color: #666;
            font-size: 16px;
        }
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        .stat-card {
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
        }
        .stat-card .label {
            color: #666;
            font-size: 14px;
            margin-bottom: 8px;
        }
        .stat-card .value {
            font-size: 28px;
            font-weight: 600;
            color: #2c3e50;
        }
        .stat-card.warning .value {
            color: #e67e22;
        }
        .stat-card.danger .value {
            color: #e74c3c;
        }
        .section {
            background: white;
            padding: 24px;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
            margin-bottom: 30px;
        }
        .section h2 {
            font-size: 18px;
            margin-bottom: 20px;
            color: #2c3e50;
            border-bottom: 1px solid #f0f2f5;
            padding-bottom: 10px;
        }
        .btn-group {
            display: flex;
            gap: 12px;
            flex-wrap: wrap;
        }
        .btn {
            padding: 10px 20px;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-size: 14px;
            font-weight: 500;
            transition: all 0.2s;
        }
        .btn-primary {
            background: #3498db;
            color: white;
        }
        .btn-primary:hover {
            background: #2980b9;
        }
        .btn-warning {
            background: #e67e22;
            color: white;
        }
        .btn-warning:hover {
            background: #d35400;
        }
        .btn-danger {
            background: #e74c3c;
            color: white;
        }
        .btn-danger:hover {
            background: #c0392b;
        }
        .ticket-table {
            width: 100%;
            border-collapse: collapse;
        }
        .ticket-table th, .ticket-table td {
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #f0f2f5;
        }
        .ticket-table th {
            background: #f8f9fa;
            font-weight: 600;
            font-size: 14px;
            color: #666;
        }
        .priority-p1 {
            color: #e74c3c;
            font-weight: 600;
        }
        .priority-p2 {
            color: #e67e22;
            font-weight: 500;
        }
        .priority-p3 {
            color: #3498db;
        }
        .status-open {
            color: #3498db;
        }
        .status-in-progress {
            color: #e67e22;
        }
        .status-resolved {
            color: #27ae60;
        }
        .event-stream {
            list-style: none;
        }
        .event-stream li {
            padding: 10px 0;
            border-bottom: 1px solid #f0f2f5;
            font-size: 14px;
        }
        .event-time {
            color: #999;
            margin-right: 10px;
        }
        #response-area {
            background: #f8f9fa;
            padding: 16px;
            border-radius: 4px;
            font-family: monospace;
            font-size: 13px;
            white-space: pre-wrap;
            max-height: 300px;
            overflow-y: auto;
        }
        .error-alert {
            background: #fdecea;
            color: #c0392b;
            padding: 12px;
            border-radius: 4px;
            margin-top: 12px;
            display: none;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Acme SupportDesk Lite</h1>
            <p>企业客户支持工单与 SLA 管理平台</p>
        </div>

        <div class="stats-grid">
            <div class="stat-card">
                <div class="label">今日工单</div>
                <div class="value">128</div>
            </div>
            <div class="stat-card danger">
                <div class="label">P1 紧急工单</div>
                <div class="value">7</div>
            </div>
            <div class="stat-card warning">
                <div class="label">SLA 风险工单</div>
                <div class="value">3</div>
            </div>
            <div class="stat-card">
                <div class="label">飞书渠道占比</div>
                <div class="value">64%</div>
            </div>
        </div>

        <div class="section">
            <h2>主操作区</h2>
            <div class="btn-group">
                <button class="btn btn-primary" onclick="callApi('/health')">系统健康检查</button>
                <button class="btn btn-primary" onclick="callApi('/ticket/p2')">提交正常 P2 工单</button>
                <button class="btn btn-warning" onclick="callApi('/ticket/p1-timezone')">提交带 +08:00 SLA 的紧急工单</button>
                <button class="btn btn-danger" onclick="callApi('/ticket/duplicate')">重复提交同一飞书事件</button>
            </div>
        </div>

        <div class="section">
            <h2>工单列表</h2>
            <table class="ticket-table">
                <thead>
                    <tr>
                        <th>工单编号</th>
                        <th>客户</th>
                        <th>来源</th>
                        <th>优先级</th>
                        <th>SLA 截止时间</th>
                        <th>状态</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td>INC-20240425-001</td>
                        <td>阿里巴巴集团</td>
                        <td>飞书</td>
                        <td><span class="priority-p1">P1</span></td>
                        <td>2024-04-25 14:30:00</td>
                        <td><span class="status-in-progress">处理中</span></td>
                    </tr>
                    <tr>
                        <td>INC-20240425-002</td>
                        <td>腾讯科技</td>
                        <td>官网</td>
                        <td><span class="priority-p2">P2</span></td>
                        <td>2024-04-25 18:00:00</td>
                        <td><span class="status-open">待处理</span></td>
                    </tr>
                    <tr>
                        <td>INC-20240425-003</td>
                        <td>字节跳动</td>
                        <td>飞书</td>
                        <td><span class="priority-p2">P2</span></td>
                        <td>2024-04-25 16:45:00</td>
                        <td><span class="status-in-progress">处理中</span></td>
                    </tr>
                    <tr>
                        <td>INC-20240425-004</td>
                        <td>百度公司</td>
                        <td>电话</td>
                        <td><span class="priority-p3">P3</span></td>
                        <td>2024-04-26 12:00:00</td>
                        <td><span class="status-resolved">已解决</span></td>
                    </tr>
                </tbody>
            </table>
        </div>

        <div class="section">
            <h2>最近事件流</h2>
            <ul class="event-stream">
                <li><span class="event-time">14:23:12</span>飞书渠道收到客户反馈，创建P1工单</li>
                <li><span class="event-time">14:20:05</span>P1工单 INC-20240425-001 进入 SLA 风险预警</li>
                <li><span class="event-time">14:18:33</span>AutoRepair Agent 正在监听服务异常</li>
                <li><span class="event-time">14:15:47</span>工单 INC-20240425-004 已解决，客户满意度5星</li>
                <li><span class="event-time">14:12:09</span>系统健康检查通过，所有服务运行正常</li>
            </ul>
        </div>

        <div class="section">
            <h2>响应结果</h2>
            <div id="response-area">点击上方按钮查看响应结果</div>
            <div class="error-alert" id="error-alert">
                后台已生成 traceback，可运行 python scripts/watch_once.py 扫描并生成 Incident。
            </div>
        </div>
    </div>

    <script>
        async function callApi(path) {
            const responseArea = document.getElementById('response-area');
            const errorAlert = document.getElementById('error-alert');
            
            responseArea.textContent = '请求中...';
            errorAlert.style.display = 'none';
            
            try {
                const response = await fetch(path);
                const data = await response.json();
                
                responseArea.textContent = `Status: ${response.status}\\n\\n${JSON.stringify(data, null, 2)}`;
                
                if (response.status >= 500) {
                    errorAlert.style.display = 'block';
                }
            } catch (error) {
                responseArea.textContent = `请求失败: ${error.message}`;
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
