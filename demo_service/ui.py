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
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", sans-serif;
        }
        body {
            min-height: 100vh;
            background: #f4f6f8;
            color: #1f2933;
        }
        .shell {
            min-height: 100vh;
            display: grid;
            grid-template-columns: 220px 1fr;
        }
        .sidebar {
            background: #17212f;
            color: #d7dee8;
            padding: 20px 14px;
        }
        .brand-mark {
            height: 40px;
            display: flex;
            align-items: center;
            gap: 10px;
            padding: 0 10px;
            margin-bottom: 22px;
            color: #ffffff;
            font-weight: 700;
            font-size: 15px;
        }
        .brand-dot {
            width: 10px;
            height: 10px;
            border-radius: 999px;
            background: #37b24d;
            box-shadow: 0 0 0 4px rgba(55, 178, 77, 0.18);
        }
        .nav-item {
            display: flex;
            align-items: center;
            gap: 10px;
            padding: 11px 12px;
            border-radius: 6px;
            color: #b8c2cf;
            font-size: 14px;
            margin-bottom: 4px;
        }
        .nav-item.active {
            background: #243246;
            color: #ffffff;
        }
        .nav-icon {
            width: 9px;
            height: 9px;
            border-radius: 2px;
            background: currentColor;
            opacity: 0.8;
        }
        .content {
            min-width: 0;
            display: flex;
            flex-direction: column;
        }
        .topbar {
            min-height: 66px;
            background: #ffffff;
            border-bottom: 1px solid #dce3ea;
            padding: 14px 24px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 20px;
        }
        .topbar-title {
            font-size: 20px;
            font-weight: 700;
            color: #111827;
        }
        .topbar-meta {
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
            justify-content: flex-end;
        }
        .meta-pill {
            border: 1px solid #d9e2ec;
            background: #f8fafc;
            color: #3e4c59;
            border-radius: 999px;
            padding: 6px 10px;
            font-size: 12px;
            white-space: nowrap;
        }
        .workspace {
            padding: 22px 24px 18px;
        }
        .kpi-grid {
            display: grid;
            grid-template-columns: repeat(5, minmax(0, 1fr));
            gap: 12px;
            margin-bottom: 18px;
        }
        .panel,
        .kpi-card {
            background: #ffffff;
            border: 1px solid #dce3ea;
            border-radius: 8px;
        }
        .kpi-card {
            padding: 14px;
            min-height: 92px;
        }
        .kpi-label {
            color: #627386;
            font-size: 12px;
            margin-bottom: 8px;
        }
        .kpi-value {
            font-size: 25px;
            font-weight: 700;
            color: #111827;
            line-height: 1.15;
        }
        .kpi-note {
            color: #8291a3;
            font-size: 12px;
            margin-top: 6px;
        }
        .layout-grid {
            display: grid;
            grid-template-columns: minmax(0, 1.8fr) minmax(300px, 0.9fr);
            gap: 16px;
            align-items: start;
        }
        .panel {
            margin-bottom: 16px;
            overflow: hidden;
        }
        .panel-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 12px;
            padding: 15px 16px;
            border-bottom: 1px solid #e5eaf0;
        }
        .panel-title {
            font-size: 15px;
            font-weight: 700;
            color: #1f2933;
        }
        .panel-subtitle {
            font-size: 12px;
            color: #8291a3;
            margin-top: 3px;
        }
        .table-wrap {
            overflow-x: auto;
        }
        .ticket-table {
            width: 100%;
            border-collapse: collapse;
            min-width: 860px;
        }
        .ticket-table th {
            text-align: left;
            padding: 11px 12px;
            color: #627386;
            background: #f7f9fb;
            font-size: 12px;
            font-weight: 600;
            border-bottom: 1px solid #e5eaf0;
        }
        .ticket-table td {
            padding: 12px;
            border-bottom: 1px solid #edf1f5;
            font-size: 13px;
            color: #25313f;
            white-space: nowrap;
        }
        .ticket-table tr:last-child td {
            border-bottom: none;
        }
        .ticket-id {
            color: #1264a3;
            font-weight: 700;
        }
        .badge {
            display: inline-flex;
            align-items: center;
            min-height: 22px;
            padding: 3px 8px;
            border-radius: 999px;
            font-size: 12px;
            font-weight: 600;
        }
        .p1 { color: #b42318; background: #fff1f0; }
        .p2 { color: #b45309; background: #fff7ed; }
        .p3 { color: #166534; background: #edf7ed; }
        .state-risk { color: #b42318; background: #fff1f0; }
        .state-open { color: #1d4ed8; background: #eff6ff; }
        .state-pending { color: #92400e; background: #fffbeb; }
        .state-done { color: #166534; background: #edf7ed; }
        .side-list {
            padding: 0 16px 8px;
        }
        .risk-item,
        .event-item {
            padding: 13px 0;
            border-bottom: 1px solid #edf1f5;
        }
        .risk-item:last-child,
        .event-item:last-child {
            border-bottom: none;
        }
        .risk-main,
        .event-main {
            display: flex;
            justify-content: space-between;
            gap: 10px;
            font-size: 13px;
            color: #25313f;
            margin-bottom: 5px;
        }
        .risk-detail,
        .event-detail {
            color: #718096;
            font-size: 12px;
            line-height: 1.45;
        }
        .actions {
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: 12px;
            padding: 16px;
        }
        .action {
            border: 1px solid #dce3ea;
            background: #ffffff;
            border-radius: 8px;
            padding: 13px;
            min-height: 106px;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            gap: 10px;
        }
        .action button {
            width: 100%;
            min-height: 36px;
            border: none;
            border-radius: 6px;
            background: #1264a3;
            color: #ffffff;
            font-size: 13px;
            font-weight: 700;
            cursor: pointer;
        }
        .action button.secondary {
            background: #edf2f7;
            color: #25313f;
        }
        .action button:hover {
            filter: brightness(0.96);
        }
        .action-desc {
            font-size: 12px;
            color: #718096;
            line-height: 1.45;
        }
        .response-area {
            padding: 16px;
        }
        .response-status {
            font-size: 13px;
            font-weight: 700;
            color: #25313f;
            margin-bottom: 10px;
        }
        .response-status.error {
            color: #b42318;
        }
        .response-json {
            background: #101828;
            color: #e5e7eb;
            border-radius: 7px;
            padding: 12px;
            font-family: "SFMono-Regular", Consolas, monospace;
            font-size: 12px;
            line-height: 1.5;
            min-height: 96px;
            max-height: 220px;
            overflow: auto;
        }
        .error-tip {
            display: none;
            margin-top: 10px;
            padding: 10px 12px;
            border-radius: 7px;
            background: #fff1f0;
            color: #b42318;
            border: 1px solid #ffd6d1;
            font-size: 13px;
        }
        .system-bar {
            display: flex;
            justify-content: space-between;
            gap: 12px;
            flex-wrap: wrap;
            color: #718096;
            font-size: 12px;
            padding: 2px 2px 0;
        }
        @media (max-width: 1100px) {
            .kpi-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); }
            .actions { grid-template-columns: repeat(2, minmax(0, 1fr)); }
            .layout-grid { grid-template-columns: 1fr; }
        }
        @media (max-width: 760px) {
            .shell { grid-template-columns: 1fr; }
            .sidebar { display: none; }
            .topbar { align-items: flex-start; flex-direction: column; }
            .topbar-meta { justify-content: flex-start; }
            .workspace { padding: 16px; }
            .kpi-grid { grid-template-columns: 1fr; }
            .actions { grid-template-columns: 1fr; }
        }
    </style>
</head>
<body>
    <div class="shell">
        <aside class="sidebar">
            <div class="brand-mark">
                <span class="brand-dot"></span>
                <span>SupportDesk</span>
            </div>
            <nav>
                <div class="nav-item active"><span class="nav-icon"></span>工单总览</div>
                <div class="nav-item"><span class="nav-icon"></span>SLA 风险</div>
                <div class="nav-item"><span class="nav-icon"></span>飞书渠道</div>
                <div class="nav-item"><span class="nav-icon"></span>客户租户</div>
                <div class="nav-item"><span class="nav-icon"></span>系统设置</div>
            </nav>
        </aside>

        <main class="content">
            <header class="topbar">
                <div>
                    <div class="topbar-title">Acme SupportDesk Lite</div>
                    <div class="panel-subtitle">企业客户支持工单与 SLA 管理后台</div>
                </div>
                <div class="topbar-meta">
                    <span class="meta-pill">当前租户：Demo Tenant</span>
                    <span class="meta-pill">环境：Local Demo</span>
                    <span class="meta-pill">Agent 接入：Black-box Log Watcher</span>
                </div>
            </header>

            <section class="workspace">
                <div class="kpi-grid">
                    <div class="kpi-card">
                        <div class="kpi-label">今日新工单</div>
                        <div class="kpi-value">128</div>
                        <div class="kpi-note">较昨日 +12</div>
                    </div>
                    <div class="kpi-card">
                        <div class="kpi-label">P1 工单</div>
                        <div class="kpi-value">7</div>
                        <div class="kpi-note">3 条等待响应</div>
                    </div>
                    <div class="kpi-card">
                        <div class="kpi-label">SLA 风险</div>
                        <div class="kpi-value">3</div>
                        <div class="kpi-note">最近 30 分钟</div>
                    </div>
                    <div class="kpi-card">
                        <div class="kpi-label">飞书事件积压</div>
                        <div class="kpi-value">14</div>
                        <div class="kpi-note">含 2 条待重试</div>
                    </div>
                    <div class="kpi-card">
                        <div class="kpi-label">平均响应时长</div>
                        <div class="kpi-value">4.8m</div>
                        <div class="kpi-note">SLA 目标 5m</div>
                    </div>
                </div>

                <div class="layout-grid">
                    <section class="panel">
                        <div class="panel-header">
                            <div>
                                <div class="panel-title">工单队列</div>
                                <div class="panel-subtitle">跨渠道客户问题处理视图</div>
                            </div>
                            <span class="meta-pill">Demo Tenant</span>
                        </div>
                        <div class="table-wrap">
                            <table class="ticket-table">
                                <thead>
                                    <tr>
                                        <th>工单编号</th>
                                        <th>客户</th>
                                        <th>来源</th>
                                        <th>优先级</th>
                                        <th>SLA</th>
                                        <th>处理人</th>
                                        <th>状态</th>
                                        <th>最近更新</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    <tr>
                                        <td class="ticket-id">TK-1024</td>
                                        <td>北航实验室</td>
                                        <td>飞书</td>
                                        <td><span class="badge p1">P1</span></td>
                                        <td>今天 18:00</td>
                                        <td>oncall-zhang</td>
                                        <td><span class="badge state-risk">SLA 风险</span></td>
                                        <td>09:40</td>
                                    </tr>
                                    <tr>
                                        <td class="ticket-id">TK-1025</td>
                                        <td>Acme 财务部</td>
                                        <td>Web</td>
                                        <td><span class="badge p2">P2</span></td>
                                        <td>明天 12:00</td>
                                        <td>support-li</td>
                                        <td><span class="badge state-open">处理中</span></td>
                                        <td>09:31</td>
                                    </tr>
                                    <tr>
                                        <td class="ticket-id">TK-1026</td>
                                        <td>华北客户A</td>
                                        <td>飞书</td>
                                        <td><span class="badge p1">P1</span></td>
                                        <td>今天 16:30</td>
                                        <td>support-wang</td>
                                        <td><span class="badge state-pending">待分配</span></td>
                                        <td>09:26</td>
                                    </tr>
                                    <tr>
                                        <td class="ticket-id">TK-1027</td>
                                        <td>内部测试租户</td>
                                        <td>API</td>
                                        <td><span class="badge p3">P3</span></td>
                                        <td>后天 10:00</td>
                                        <td>bot</td>
                                        <td><span class="badge state-done">已解决</span></td>
                                        <td>09:20</td>
                                    </tr>
                                    <tr>
                                        <td class="ticket-id">TK-1028</td>
                                        <td>客服质检组</td>
                                        <td>飞书</td>
                                        <td><span class="badge p2">P2</span></td>
                                        <td>明天 18:00</td>
                                        <td>support-chen</td>
                                        <td><span class="badge state-pending">待确认</span></td>
                                        <td>09:12</td>
                                    </tr>
                                    <tr>
                                        <td class="ticket-id">TK-1029</td>
                                        <td>华东零售事业部</td>
                                        <td>邮件</td>
                                        <td><span class="badge p2">P2</span></td>
                                        <td>今天 22:00</td>
                                        <td>support-lin</td>
                                        <td><span class="badge state-open">处理中</span></td>
                                        <td>08:58</td>
                                    </tr>
                                    <tr>
                                        <td class="ticket-id">TK-1030</td>
                                        <td>渠道集成团队</td>
                                        <td>API</td>
                                        <td><span class="badge p3">P3</span></td>
                                        <td>周五 17:00</td>
                                        <td>support-chen</td>
                                        <td><span class="badge state-open">排查中</span></td>
                                        <td>08:41</td>
                                    </tr>
                                    <tr>
                                        <td class="ticket-id">TK-1031</td>
                                        <td>上海运营中心</td>
                                        <td>飞书</td>
                                        <td><span class="badge p1">P1</span></td>
                                        <td>今天 15:45</td>
                                        <td>oncall-zhang</td>
                                        <td><span class="badge state-risk">即将超时</span></td>
                                        <td>08:33</td>
                                    </tr>
                                </tbody>
                            </table>
                        </div>
                    </section>

                    <aside>
                        <section class="panel">
                            <div class="panel-header">
                                <div>
                                    <div class="panel-title">SLA 风险</div>
                                    <div class="panel-subtitle">即将超时工单</div>
                                </div>
                            </div>
                            <div class="side-list">
                                <div class="risk-item">
                                    <div class="risk-main"><strong>TK-1031</strong><span>剩余 42m</span></div>
                                    <div class="risk-detail">上海运营中心，飞书渠道 P1，待 oncall 响应。</div>
                                </div>
                                <div class="risk-item">
                                    <div class="risk-main"><strong>TK-1026</strong><span>剩余 1h 18m</span></div>
                                    <div class="risk-detail">华北客户A，客户连续催办，等待分配处理人。</div>
                                </div>
                                <div class="risk-item">
                                    <div class="risk-main"><strong>TK-1024</strong><span>剩余 2h 36m</span></div>
                                    <div class="risk-detail">北航实验室，紧急客户问题，SLA 计时中。</div>
                                </div>
                            </div>
                        </section>

                        <section class="panel">
                            <div class="panel-header">
                                <div>
                                    <div class="panel-title">飞书事件流</div>
                                    <div class="panel-subtitle">消息、重试、审批通知</div>
                                </div>
                            </div>
                            <div class="side-list">
                                <div class="event-item">
                                    <div class="event-main"><strong>09:40</strong><span>消息入站</span></div>
                                    <div class="event-detail">飞书渠道收到 P1 客户问题，已进入工单队列。</div>
                                </div>
                                <div class="event-item">
                                    <div class="event-main"><strong>09:36</strong><span>事件重试</span></div>
                                    <div class="event-detail">最近一条飞书回调事件等待重新处理。</div>
                                </div>
                                <div class="event-item">
                                    <div class="event-main"><strong>09:28</strong><span>审批通知</span></div>
                                    <div class="event-detail">P1 升级审批已推送给值班组。</div>
                                </div>
                                <div class="event-item">
                                    <div class="event-main"><strong>09:12</strong><span>同步完成</span></div>
                                    <div class="event-detail">客户租户联系人信息已同步。</div>
                                </div>
                            </div>
                        </section>
                    </aside>
                </div>

                <section class="panel">
                    <div class="panel-header">
                        <div>
                            <div class="panel-title">操作区</div>
                            <div class="panel-subtitle">常用业务动作</div>
                        </div>
                    </div>
                    <div class="actions">
                        <div class="action">
                            <button onclick="callApi('/ticket/create', 'POST', {'priority': 'P1', 'sla_hours': 8})">创建 P1 飞书渠道工单</button>
                            <div class="action-desc">创建一个来自飞书渠道的紧急客户问题。</div>
                        </div>
                        <div class="action">
                            <button class="secondary" onclick="callApi('/ticket/replay', 'POST')">重试飞书事件同步</button>
                            <div class="action-desc">重新处理最近一条飞书事件。</div>
                        </div>
                        <div class="action">
                            <button class="secondary" onclick="callApi('/ticket/create', 'POST', {'priority': 'P2'})">批量刷新 SLA 状态</button>
                            <div class="action-desc">刷新即将到期工单的 SLA 状态。</div>
                        </div>
                        <div class="action">
                            <button class="secondary" onclick="callApi('/health')">系统健康检查</button>
                            <div class="action-desc">检查服务健康状态。</div>
                        </div>
                    </div>
                </section>

                <section class="panel">
                    <div class="panel-header">
                        <div>
                            <div class="panel-title">API 响应结果</div>
                            <div class="panel-subtitle">当前操作返回的 status 与 JSON</div>
                        </div>
                    </div>
                    <div class="response-area">
                        <div id="response-status" class="response-status">Status: 等待操作</div>
                        <pre id="response-json" class="response-json">{}</pre>
                        <div id="error-tip" class="error-tip">服务端处理失败，异常已写入服务日志。</div>
                    </div>
                </section>

                <footer class="system-bar">
                    <span>Service ID: supportdesk-lite</span>
                    <span>Log: demo_service/logs/app.log</span>
                    <span>Repo: current repository</span>
                </footer>
            </section>
        </main>
    </div>

    <script>
        async function callApi(endpoint, method = 'GET', body = null) {
            const statusEl = document.getElementById('response-status');
            const jsonEl = document.getElementById('response-json');
            const errorTipEl = document.getElementById('error-tip');

            statusEl.textContent = 'Status: loading';
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
                statusEl.textContent = `Status: request failed`;
                statusEl.classList.add('error');
                jsonEl.textContent = JSON.stringify({ error: err.message }, null, 2);
            }
        }
    </script>
</body>
</html>
    """
