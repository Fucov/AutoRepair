def get_support_desk_html():
    return """
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
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        }
        body {
            background-color: #f5f7fa;
            padding: 20px;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
        }
        /* Header */
        .header {
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
            margin-bottom: 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .header-left h1 {
            font-size: 24px;
            color: #1d2129;
            margin-bottom: 4px;
        }
        .header-left p {
            color: #86909c;
            font-size: 14px;
        }
        .header-right {
            text-align: right;
            color: #4e5969;
            font-size: 13px;
            line-height: 1.6;
        }
        /* KPI Cards */
        .kpi-row {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 16px;
            margin-bottom: 20px;
        }
        .kpi-card {
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
            transition: all 0.3s ease;
            border-left: 4px solid transparent;
        }
        .kpi-card:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(0,0,0,0.12);
        }
        .kpi-card:nth-child(1) { border-left-color: #168cff; }
        .kpi-card:nth-child(2) { border-left-color: #f53f3f; }
        .kpi-card:nth-child(3) { border-left-color: #ff7d00; }
        .kpi-card:nth-child(4) { border-left-color: #00b42a; }
        .kpi-title {
            color: #86909c;
            font-size: 13px;
            margin-bottom: 8px;
            display: flex;
            align-items: center;
        }
        .kpi-value {
            font-size: 28px;
            font-weight: 600;
        }
        .kpi-card:nth-child(1) .kpi-value { color: #168cff; }
        .kpi-card:nth-child(2) .kpi-value { color: #f53f3f; }
        .kpi-card:nth-child(3) .kpi-value { color: #ff7d00; }
        .kpi-card:nth-child(4) .kpi-value { color: #00b42a; }
        /* Main Content */
        .main-content {
            display: grid;
            grid-template-columns: 65% 35%;
            gap: 20px;
            margin-bottom: 20px;
        }
        .card {
            background: white;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
            padding: 20px;
        }
        .card-title {
            font-size: 16px;
            font-weight: 600;
            color: #1d2129;
            margin-bottom: 16px;
            padding-bottom: 8px;
            border-bottom: 1px solid #e5e6eb;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .card-title::before {
            content: "";
            width: 4px;
            height: 16px;
            background: #168cff;
            border-radius: 2px;
        }
        /* Ticket Table */
        .ticket-table {
            width: 100%;
            border-collapse: collapse;
        }
        .ticket-table th {
            text-align: left;
            padding: 10px;
            background: #f7f8fa;
            color: #4e5969;
            font-size: 13px;
            font-weight: 500;
        }
        .ticket-table tr {
            transition: background-color 0.2s ease;
        }
        .ticket-table tr:hover {
            background-color: #f7f8fa;
        }
        .ticket-table td {
            padding: 12px 10px;
            border-bottom: 1px solid #e5e6eb;
            font-size: 13px;
            color: #1d2129;
        }
        .ticket-table tr:last-child td {
            border-bottom: none;
        }
        .priority-p1 {
            color: #f53f3f;
            font-weight: 500;
        }
        .priority-p2 {
            color: #ff7d00;
            font-weight: 500;
        }
        .priority-p3 {
            color: #00b42a;
            font-weight: 500;
        }
        .status-sla-risk {
            color: #f53f3f;
        }
        .status-processing {
            color: #168cff;
        }
        .status-pending {
            color: #ff7d00;
        }
        .status-resolved {
            color: #00b42a;
        }
        /* Status Panel */
        .status-item {
            display: flex;
            justify-content: space-between;
            padding: 10px 0;
            border-bottom: 1px solid #f2f3f5;
            font-size: 13px;
        }
        .status-item:last-child {
            border-bottom: none;
        }
        .status-label {
            color: #86909c;
        }
        .status-value.running {
            color: #00b42a;
            font-weight: 500;
        }
        /* Operation Panel */
        .operation-panel {
            margin-bottom: 20px;
        }
        .btn-group {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 12px;
        }
        .btn {
            padding: 12px 16px;
            border: none;
            border-radius: 6px;
            font-size: 14px;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.2s;
        }
        .btn-primary {
            background: #168cff;
            color: white;
        }
        .btn-primary:hover {
            background: #0e77d9;
        }
        .btn-danger {
            background: #f53f3f;
            color: white;
        }
        .btn-danger:hover {
            background: #d93636;
        }
        .btn-secondary {
            background: #f2f3f5;
            color: #4e5969;
        }
        .btn-secondary:hover {
            background: #e5e6eb;
        }
        .btn-desc {
            font-size: 12px;
            color: #86909c;
            margin-top: 4px;
            text-align: center;
        }
        /* Event Stream */
        .event-stream {
            margin-bottom: 20px;
        }
        .event-item {
            padding: 8px 0;
            font-size: 13px;
            color: #4e5969;
            border-bottom: 1px solid #f2f3f5;
        }
        .event-time {
            color: #86909c;
            margin-right: 8px;
        }
        /* Response Area */
        .response-area {
            background: white;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
            padding: 20px;
        }
        .response-status {
            font-size: 14px;
            font-weight: 500;
            margin-bottom: 12px;
        }
        .response-status.error {
            color: #f53f3f;
        }
        .response-json {
            background: #f7f8fa;
            padding: 12px;
            border-radius: 6px;
            font-family: monospace;
            font-size: 13px;
            overflow-x: auto;
            max-height: 200px;
        }
        .error-tip {
            margin-top: 12px;
            padding: 10px;
            background: #fff1f0;
            border: 1px solid #ffccc7;
            border-radius: 6px;
            color: #cf1322;
            font-size: 13px;
        }
    </style>
</head>
<body>
    <div class="container">
        <!-- Header -->
        <div class="header">
            <div class="header-left">
                <h1>Acme SupportDesk Lite</h1>
                <p>企业客户支持工单与 SLA 管理平台</p>
            </div>
            <div class="header-right">
                <div>环境：Local Demo</div>
                <div>Agent 接入：Black-box Log Watcher</div>
                <div>服务 ID：supportdesk-lite</div>
            </div>
        </div>

        <!-- KPI 指标区 -->
        <div class="kpi-row">
            <div class="kpi-card">
                <div class="kpi-title">今日工单</div>
                <div class="kpi-value">128</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-title">P1 紧急工单</div>
                <div class="kpi-value">7</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-title">SLA 风险工单</div>
                <div class="kpi-value">3</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-title">飞书渠道占比</div>
                <div class="kpi-value">64%</div>
            </div>
        </div>

        <!-- 主体双栏布局 -->
        <div class="main-content">
            <!-- 左侧：工单队列 -->
            <div class="card">
                <h2 class="card-title">工单队列</h2>
                <table class="ticket-table">
                    <thead>
                        <tr>
                            <th>工单编号</th>
                            <th>客户</th>
                            <th>来源渠道</th>
                            <th>优先级</th>
                            <th>SLA 截止时间</th>
                            <th>处理人</th>
                            <th>状态</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr>
                            <td>TK-1024</td>
                            <td>北航实验室</td>
                            <td>飞书</td>
                            <td><span class="priority-p1">P1</span></td>
                            <td>今天 18:00</td>
                            <td>oncall-zhang</td>
                            <td><span class="status-sla-risk">SLA 风险</span></td>
                        </tr>
                        <tr>
                            <td>TK-1025</td>
                            <td>Acme 财务部</td>
                            <td>Web</td>
                            <td><span class="priority-p2">P2</span></td>
                            <td>明天 12:00</td>
                            <td>support-li</td>
                            <td><span class="status-processing">处理中</span></td>
                        </tr>
                        <tr>
                            <td>TK-1026</td>
                            <td>华北客户A</td>
                            <td>飞书</td>
                            <td><span class="priority-p1">P1</span></td>
                            <td>今天 16:30</td>
                            <td>support-wang</td>
                            <td><span class="status-pending">待分配</span></td>
                        </tr>
                        <tr>
                            <td>TK-1027</td>
                            <td>内部测试租户</td>
                            <td>API</td>
                            <td><span class="priority-p3">P3</span></td>
                            <td>后天 10:00</td>
                            <td>bot</td>
                            <td><span class="status-resolved">已解决</span></td>
                        </tr>
                        <tr>
                            <td>TK-1028</td>
                            <td>客服质检组</td>
                            <td>飞书</td>
                            <td><span class="priority-p2">P2</span></td>
                            <td>明天 18:00</td>
                            <td>support-chen</td>
                            <td><span class="status-pending">待确认</span></td>
                        </tr>
                    </tbody>
                </table>
            </div>

            <!-- 右侧：服务运行状态 -->
            <div class="card">
                <h2 class="card-title">服务运行状态</h2>
                <div class="status-item">
                    <span class="status-label">服务状态</span>
                    <span class="status-value running">运行中</span>
                </div>
                <div class="status-item">
                    <span class="status-label">日志监听</span>
                    <span class="status-value">demo_service/logs/app.log</span>
                </div>
                <div class="status-item">
                    <span class="status-label">仓库路径</span>
                    <span class="status-value">当前仓库</span>
                </div>
                <div class="status-item">
                    <span class="status-label">健康检查</span>
                    <span class="status-value">/health</span>
                </div>
                <div class="status-item">
                    <span class="status-label">AutoRepair 状态</span>
                    <span class="status-value">等待扫描</span>
                </div>
            </div>
        </div>

        <!-- 操作面板 -->
        <div class="card operation-panel">
            <h2 class="card-title">演示操作</h2>
            <div class="btn-group">
                <div>
                    <button class="btn btn-primary" onclick="callApi('/health')">系统健康检查</button>
                    <div class="btn-desc">检查服务运行状态</div>
                </div>
                <div>
                    <button class="btn btn-secondary" onclick="callApi('/ticket/create', 'POST', {'priority': 'P2'})">创建正常 P2 工单</button>
                    <div class="btn-desc">生成标准服务工单</div>
                </div>
                <div>
                    <button class="btn btn-danger" onclick="callApi('/ticket/create', 'POST', {'priority': 'P1', 'sla_hours': 8})">创建带 +08:00 SLA 的紧急工单（触发 Runtime Bug）</button>
                    <div class="btn-desc">触发预设异常用于演示</div>
                </div>
                <div>
                    <button class="btn btn-secondary" onclick="callApi('/ticket/replay', 'POST')">重复提交同一飞书事件（模拟幂等性缺陷）</button>
                    <div class="btn-desc">测试重复事件处理逻辑</div>
                </div>
            </div>
        </div>

        <!-- 最近事件流 -->
        <div class="card event-stream">
            <h2 class="card-title">最近事件流</h2>
            <div class="event-item">
                <span class="event-time">09:30</span>飞书渠道收到客户反馈
            </div>
            <div class="event-item">
                <span class="event-time">09:35</span>P1 工单进入 SLA 风险
            </div>
            <div class="event-item">
                <span class="event-time">09:36</span>SupportDesk 服务写入访问日志
            </div>
            <div class="event-item">
                <span class="event-time">09:38</span>AutoRepair 正在监听服务日志
            </div>
            <div class="event-item">
                <span class="event-time">09:40</span>新异常会被写入 demo_service/logs/app.log
            </div>
        </div>

        <!-- API 响应结果区 -->
        <div class="response-area">
            <h2 class="card-title">API 响应结果</h2>
            <div id="response-status" class="response-status">等待操作...</div>
            <div id="response-json" class="response-json">{}</div>
            <div id="error-tip" class="error-tip" style="display: none;">
                服务端已生成 traceback。请运行 python scripts/watch_once.py 扫描并生成 Incident。
            </div>
        </div>
    </div>

    <script>
        async function callApi(endpoint, method = 'GET', body = null) {
            const statusEl = document.getElementById('response-status');
            const jsonEl = document.getElementById('response-json');
            const errorTipEl = document.getElementById('error-tip');
            
            statusEl.textContent = '加载中...';
            statusEl.className = 'response-status';
            errorTipEl.style.display = 'none';
            
            try {
                const options = { method };
                if (body) {
                    options.headers = { 'Content-Type': 'application/json' };
                    options.body = JSON.stringify(body);
                }
                
                const res = await fetch(endpoint, options);
                const data = await res.json();
                
                statusEl.textContent = `Status: ${res.status}`;
                if (res.status >= 400) {
                    statusEl.classList.add('error');
                }
                if (res.status >= 500) {
                    errorTipEl.style.display = 'block';
                }
                
                jsonEl.textContent = JSON.stringify(data, null, 2);
            } catch (err) {
                statusEl.textContent = `请求失败: ${err.message}`;
                statusEl.classList.add('error');
                jsonEl.textContent = JSON.stringify({ error: err.message }, null, 2);
            }
        }
    </script>
</body>
</html>
    """
