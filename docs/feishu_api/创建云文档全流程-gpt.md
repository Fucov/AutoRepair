FeishuAgent 发现 bug / 扫描 Issue
        ↓
Agent 生成结构化诊断报告 JSON / Markdown
        ↓
飞书应用机器人用 tenant_access_token 调用云文档 API
        ↓
在指定报告根目录下创建日期/Issue 文件夹
        ↓
创建 DocX 文档
        ↓
写入诊断报告 blocks
        ↓
给用户/群组授权
        ↓
把文档链接回填到飞书卡片、GitHub Issue、PR 描述飞书新版云文档推荐用 DocX v1；文件夹属于 Drive v1。DocX 文档的核心模型是“文档 + 块”，文档由 document_id 标识，正文内容通过 block 创建、更新和删除来完成。([飞书开放平台][1])
---
1. 你应该采用的方案
不要让 Agent 只把诊断报告塞进飞书卡片。正确做法是：
卡片 = 摘要和操作入口
云文档 = 完整诊断报告 / 修复计划 / 测试结果 / PR 记录
GitHub Issue = 追踪和审计入口也就是说，飞书卡片只展示：
异常类型
影响接口
GitHub Issue
诊断报告链接
修复计划链接
当前状态
操作按钮完整内容放在飞书云文档里。
---
2. 一次性前置配置
2.1 创建飞书企业自建应用
进入飞书开放平台：
开发者后台 → 创建企业自建应用拿到：
FEISHU_APP_ID=cli_xxx
FEISHU_APP_SECRET=xxx企业自建应用通过 app_id 和 app_secret 获取 tenant_access_token，该 token 有效期为 2 小时。([飞书开放平台][2])
2.2 开通权限
你至少需要这些权限能力：
能力
用途

创建 / 编辑新版文档
创建 DocX 诊断报告，写入 blocks

创建文件夹
按日期、Issue 编号创建报告目录

获取文件夹清单
判断目录是否已存在，避免重复创建

添加云文档协作者
把报告授权给用户或群组

发送消息 / 卡片
把文档链接发到飞书群

飞书权限页里名称可能会随版本显示略有差异，你可以在权限管理里搜索这些关键词：
docx
document
新版文档
folder
文件夹
云空间
permission
协作者
message官方权限列表中，DocX 权限包含创建新版文档、增删改查新版文档内容；协作者权限对应“添加云文档协作者”。([飞书开放平台][3])
注意：开通权限后要发布应用版本，否则你的本地代码拿到 token 也可能报 no scope auth 或 forbidden。
---
3. 文件夹怎么准备
这里有一个非常关键的工程点：不要让机器人随便创建在未知根目录里。你应该先手动创建一个“锚点文件夹”。
推荐手动建：
飞书Agent自动修复报告然后在这个文件夹下由机器人自动创建：
飞书Agent自动修复报告/
  2026-05/
    issue-12-ZeroDivisionError/
      诊断报告
      修复计划
      测试报告文件夹 token 可以从文件夹 URL 中取。官方 FAQ 也说明，文件夹 token 可从浏览器地址栏获取，或通过开放平台接口获取。([飞书开放平台][4])
例如：
https://xxx.feishu.cn/drive/folder/fldcnxxxxxxxxxxxx其中：
fldcnxxxxxxxxxxxx就是 folder_token。
你可以把它配置到 .env：
FEISHU_REPORT_ROOT_FOLDER_TOKEN=fldcnxxxxxxxxxxxx
FEISHU_TENANT_DOMAIN=https://xxx.feishu.cn---
4. 完整 API 流程
Step 1：获取 tenant_access_token
接口：
POST /open-apis/auth/v3/tenant_access_token/internal/请求：
{
  "app_id": "cli_xxx",
  "app_secret": "xxx"
}返回里取：
{
  "tenant_access_token": "t-xxx",
  "expire": 7200
}后续所有 API 都带：
Authorization: Bearer <tenant_access_token>---
Step 2：检查目标文件夹下是否已有日期目录
接口：
GET /open-apis/drive/v1/files用途是获取指定文件夹下的文件清单。该接口只获取当前层级，不会递归获取子文件夹。([飞书开放平台][5])
建议逻辑：
list root folder
  ↓
如果存在 2026-05 文件夹，复用它
  ↓
如果不存在，创建 2026-05 文件夹---
Step 3：创建文件夹
接口：
POST /open-apis/drive/v1/files/create_folder飞书 Drive v1 提供创建文件夹接口，官方文档给出的 HTTP URL 就是 /open-apis/drive/v1/files/create_folder，限频为 5 次/秒。([飞书开放平台][6])
请求：
{
  "name": "issue-12-ZeroDivisionError",
  "folder_token": "父文件夹 token"
}建议你的目录规则：
issue-{issue_number}-{error_type}例如：
issue-12-ZeroDivisionError
issue-13-KeyError
issue-14-DependencyError---
Step 4：创建 DocX 文档
接口：
POST /open-apis/docx/v1/documents飞书 DocX 创建文档接口支持通过 title 和 folder_token 创建文档，限频为每秒 3 次，成功后返回 document_id 等信息。([飞书开放平台][7])
请求：
{
  "folder_token": "issue 文件夹 token",
  "title": "诊断报告 - Issue #12 - ZeroDivisionError"
}返回：
{
  "code": 0,
  "msg": "success",
  "data": {
    "document": {
      "document_id": "doxcnxxxx",
      "revision_id": 1,
      "title": "诊断报告 - Issue #12 - ZeroDivisionError"
    }
  }
}文档链接一般可按租户域名拼：
https://xxx.feishu.cn/docx/{document_id}为了更稳，也可以后续通过 Drive 元数据接口获取正式 URL。
---
Step 5：获取文档根块
接口：
GET /open-apis/docx/v1/documents/{document_id}/blocksDocX 文档正文需要写入 blocks。官方“获取文档所有块”接口会分页返回文档所有块，限频为每秒 5 次。([飞书 API][8])
新建文档一般会有一个页面根块：
{
  "block_id": "doxcnxxxx",
  "block_type": 1
}你要拿这个 block_id 作为后续插入内容的父块。
---
Step 6：写入诊断报告 blocks
接口：
POST /open-apis/docx/v1/documents/{document_id}/blocks/{block_id}/children创建块接口可以在指定父块下创建一批子块，并插入到指定位置；官方说明该接口适用于创建多个子块，限频为每秒 3 次。([Apifox][9])
最小可用 block 类型：
block_type=2 文本段落
block_type=3 一级标题
block_type=4 二级标题
block_type=7 无序列表建议你不要一开始追求复杂表格。诊断报告最稳定的形态是：
H1：自动诊断报告
H2：一、异常摘要
文本：异常类型、影响接口、触发时间
H2：二、复现步骤
列表：步骤 1、步骤 2、步骤 3
H2：三、根因分析
文本：...
H2：四、修复策略
列表：...
H2：五、测试计划
列表：...
H2：六、关联链接
文本：GitHub Issue / PR / 日志路径---
Step 7：添加协作者权限
接口：
POST /open-apis/drive/v1/permissions/{token}/members?type=docx飞书提供“增加协作者权限”接口，可以给指定云文档添加用户、群组、部门、用户组等协作者；调用身份需要有该云文档添加协作者的权限。([飞书开放平台][10])
请求示例：
{
  "member_type": "openid",
  "member_id": "ou_xxx",
  "perm": "edit"
}权限可选常用值：
view
edit
full_access你的项目里可以先做两种：
报告创建者 / 管理员：full_access
飞书群成员：view 或 edit---
5. 推荐的 FeishuAgent 文档生成链路
我建议你新增一个服务：
ReportService目录结构可以这样改：
app/
  integrations/
    feishu_auth.py
    feishu_drive_client.py
    feishu_docx_client.py
    feishu_permission_client.py

  reports/
    report_schema.py
    diagnosis_report_builder.py
    feishu_block_renderer.py
    report_service.py核心流程
async def create_diagnosis_report(incident_id: str):
    incident = await incident_repo.get(incident_id)

    report = await agent.generate_diagnosis_report(incident)

    month_folder = await drive.ensure_folder(
        parent_token=REPORT_ROOT_FOLDER_TOKEN,
        name="2026-05",
    )

    issue_folder = await drive.ensure_folder(
        parent_token=month_folder.token,
        name=f"issue-{incident.issue_number}-{incident.error_type}",
    )

    doc = await docx.create_document(
        folder_token=issue_folder.token,
        title=f"诊断报告 - Issue #{incident.issue_number} - {incident.error_type}",
    )

    root_block_id = await docx.get_root_block_id(doc.document_id)

    blocks = render_diagnosis_report_to_blocks(report)

    await docx.create_blocks(
        document_id=doc.document_id,
        parent_block_id=root_block_id,
        blocks=blocks,
    )

    await permission.add_member(
        token=doc.document_id,
        doc_type="docx",
        member_type="openid",
        member_id=incident.report_owner_open_id,
        perm="edit",
    )

    report_url = f"{FEISHU_TENANT_DOMAIN}/docx/{doc.document_id}"

    await incident_repo.update_report_url(incident_id, report_url)

    await feishu_card.send_report_created_card(incident, report_url)

    return report_url---
6. Agent 不要直接输出飞书 Block，先输出结构化 JSON
你现在的 Agent 最好不要直接生成飞书 block JSON。原因是 block JSON 容易格式错，一错整个写入失败。
推荐让 LLM 输出这个结构：
{
  "title": "自动诊断报告 - Issue #12 - ZeroDivisionError",
  "summary": {
    "error_type": "ZeroDivisionError",
    "severity": "P1",
    "entrypoint": "POST /orders/preview",
    "first_seen": "2026-05-03 00:31:22",
    "status": "已复现"
  },
  "root_cause": [
    "订单金额为 0 时，服务端仍进入单价比例计算逻辑。",
    "核心函数缺少 amount <= 0 的参数保护。",
    "当前测试集只覆盖正常金额，没有覆盖 0 或负数输入。"
  ],
  "reproduction_steps": [
    "启动本地 FastAPI 服务。",
    "调用 POST /orders/preview，传入 amount=0。",
    "服务返回 500，并在日志中出现 ZeroDivisionError。"
  ],
  "fix_strategy": [
    "在订单预览入口增加 amount <= 0 的参数校验。",
    "将非法金额返回 400 业务错误，而不是进入计算逻辑。",
    "新增 amount=0 和 amount<0 的回归测试。"
  ],
  "test_plan": [
    "运行 pytest tests/test_order_preview.py。",
    "验证正常金额仍返回 200。",
    "验证 amount=0 返回明确错误响应。"
  ],
  "risk": "低风险，修改范围集中在订单预览参数校验。",
  "links": {
    "github_issue": "https://github.com/xxx/repo/issues/12",
    "branch": "feishu-agent/fix-12",
    "pr": ""
  }
}然后你自己写一个稳定的 renderer：
DiagnosisReport JSON → Feishu Blocks这样比让模型直接吐飞书 API JSON 稳定很多。
---
7. Python 最小实现参考
下面是一个可以直接给 Codex / Trae 改造的版本。
import os
import time
import httpx
from typing import Any, Dict, List, Optional


FEISHU_BASE = "https://open.feishu.cn/open-apis"


class FeishuClientError(RuntimeError):
    pass


class FeishuTokenManager:
    def __init__(self, app_id: str, app_secret: str):
        self.app_id = app_id
        self.app_secret = app_secret
        self._token: Optional[str] = None
        self._expire_at: float = 0

    async def get_token(self) -> str:
        if self._token and time.time() < self._expire_at - 300:
            return self._token

        url = f"{FEISHU_BASE}/auth/v3/tenant_access_token/internal/"
        payload = {
            "app_id": self.app_id,
            "app_secret": self.app_secret,
        }

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()

        if data.get("code") != 0:
            raise FeishuClientError(f"failed to get tenant_access_token: {data}")

        self._token = data["tenant_access_token"]
        self._expire_at = time.time() + int(data.get("expire", 7200))
        return self._token


class FeishuDocService:
    def __init__(self, token_manager: FeishuTokenManager, tenant_domain: str):
        self.token_manager = token_manager
        self.tenant_domain = tenant_domain.rstrip("/")

    async def _headers(self) -> Dict[str, str]:
        token = await self.token_manager.get_token()
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    async def list_folder(self, folder_token: str) -> List[Dict[str, Any]]:
        url = f"{FEISHU_BASE}/drive/v1/files"
        headers = await self._headers()

        params = {
            "folder_token": folder_token,
            "page_size": 50,
        }

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(url, headers=headers, params=params)
            resp.raise_for_status()
            data = resp.json()

        if data.get("code") != 0:
            raise FeishuClientError(f"failed to list folder: {data}")

        return data.get("data", {}).get("files", [])

    async def create_folder(self, parent_folder_token: str, name: str) -> str:
        url = f"{FEISHU_BASE}/drive/v1/files/create_folder"
        headers = await self._headers()

        payload = {
            "name": name,
            "folder_token": parent_folder_token,
        }

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()

        if data.get("code") != 0:
            raise FeishuClientError(f"failed to create folder: {data}")

        folder_data = data.get("data", {})
        return (
            folder_data.get("token")
            or folder_data.get("file", {}).get("token")
            or folder_data.get("folder", {}).get("token")
        )

    async def ensure_folder(self, parent_folder_token: str, name: str) -> str:
        files = await self.list_folder(parent_folder_token)

        for item in files:
            if item.get("name") == name and item.get("type") == "folder":
                return item.get("token")

        return await self.create_folder(parent_folder_token, name)

    async def create_document(self, folder_token: str, title: str) -> Dict[str, Any]:
        url = f"{FEISHU_BASE}/docx/v1/documents"
        headers = await self._headers()

        payload = {
            "folder_token": folder_token,
            "title": title,
        }

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()

        if data.get("code") != 0:
            raise FeishuClientError(f"failed to create document: {data}")

        document = data["data"]["document"]
        document["url"] = f"{self.tenant_domain}/docx/{document['document_id']}"
        return document

    async def get_root_block_id(self, document_id: str) -> str:
        url = f"{FEISHU_BASE}/docx/v1/documents/{document_id}/blocks"
        headers = await self._headers()

        params = {
            "page_size": 50,
            "document_revision_id": -1,
        }

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(url, headers=headers, params=params)
            resp.raise_for_status()
            data = resp.json()

        if data.get("code") != 0:
            raise FeishuClientError(f"failed to get document blocks: {data}")

        items = data.get("data", {}).get("items", [])
        if not items:
            raise FeishuClientError("document has no root block")

        for block in items:
            if block.get("block_type") == 1:
                return block["block_id"]

        return items[0]["block_id"]

    async def create_blocks(
        self,
        document_id: str,
        parent_block_id: str,
        blocks: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        url = (
            f"{FEISHU_BASE}/docx/v1/documents/"
            f"{document_id}/blocks/{parent_block_id}/children"
        )
        headers = await self._headers()

        payload = {
            "children": blocks,
            "index": 0,
        }

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()

        if data.get("code") != 0:
            raise FeishuClientError(f"failed to create blocks: {data}")

        return data["data"]

    async def add_doc_member(
        self,
        document_id: str,
        member_type: str,
        member_id: str,
        perm: str = "edit",
    ) -> None:
        url = f"{FEISHU_BASE}/drive/v1/permissions/{document_id}/members"
        headers = await self._headers()

        params = {
            "type": "docx",
            "need_notification": "false",
        }

        payload = {
            "member_type": member_type,
            "member_id": member_id,
            "perm": perm,
        }

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(url, headers=headers, params=params, json=payload)
            resp.raise_for_status()
            data = resp.json()

        if data.get("code") != 0:
            raise FeishuClientError(f"failed to add document member: {data}")---
8. Block 渲染器示例
def text_run(content: str, bold: bool = False) -> Dict[str, Any]:
    return {
        "text_run": {
            "content": content,
            "text_element_style": {
                "bold": bold,
            },
        }
    }


def text_block(content: str) -> Dict[str, Any]:
    return {
        "block_type": 2,
        "text": {
            "elements": [text_run(content)],
            "style": {},
        },
    }


def heading1(content: str) -> Dict[str, Any]:
    return {
        "block_type": 3,
        "heading1": {
            "elements": [text_run(content, bold=True)],
            "style": {},
        },
    }


def heading2(content: str) -> Dict[str, Any]:
    return {
        "block_type": 4,
        "heading2": {
            "elements": [text_run(content, bold=True)],
            "style": {},
        },
    }


def bullet_block(content: str) -> Dict[str, Any]:
    return {
        "block_type": 7,
        "bullet": {
            "elements": [text_run(content)],
            "style": {},
        },
    }


def render_diagnosis_report(report: Dict[str, Any]) -> List[Dict[str, Any]]:
    blocks: List[Dict[str, Any]] = []

    blocks.append(heading1(report["title"]))

    blocks.append(heading2("一、异常摘要"))
    summary = report["summary"]
    blocks.append(text_block(f"异常类型：{summary.get('error_type', '')}"))
    blocks.append(text_block(f"严重程度：{summary.get('severity', '')}"))
    blocks.append(text_block(f"影响入口：{summary.get('entrypoint', '')}"))
    blocks.append(text_block(f"首次发现：{summary.get('first_seen', '')}"))
    blocks.append(text_block(f"当前状态：{summary.get('status', '')}"))

    blocks.append(heading2("二、复现步骤"))
    for item in report.get("reproduction_steps", []):
        blocks.append(bullet_block(item))

    blocks.append(heading2("三、根因分析"))
    for item in report.get("root_cause", []):
        blocks.append(bullet_block(item))

    blocks.append(heading2("四、修复策略"))
    for item in report.get("fix_strategy", []):
        blocks.append(bullet_block(item))

    blocks.append(heading2("五、测试计划"))
    for item in report.get("test_plan", []):
        blocks.append(bullet_block(item))

    blocks.append(heading2("六、风险评估"))
    blocks.append(text_block(report.get("risk", "未评估")))

    links = report.get("links", {})
    blocks.append(heading2("七、关联链接"))
    if links.get("github_issue"):
        blocks.append(text_block(f"GitHub Issue：{links['github_issue']}"))
    if links.get("branch"):
        blocks.append(text_block(f"修复分支：{links['branch']}"))
    if links.get("pr"):
        blocks.append(text_block(f"Pull Request：{links['pr']}"))

    return blocks---
9. FeishuAgent 里应该怎么接
你现在可以把“创建诊断报告”作为一个明确节点插入状态机。
DETECTED
  ↓
ISSUE_CREATED
  ↓
DIAGNOSING
  ↓
DOC_CREATING
  ↓
DOC_CREATED
  ↓
PLAN_READY
  ↓
QUEUED_FOR_REPAIR新增字段：
ALTER TABLE incidents ADD COLUMN feishu_report_doc_id TEXT;
ALTER TABLE incidents ADD COLUMN feishu_report_url TEXT;
ALTER TABLE incidents ADD COLUMN feishu_report_folder_token TEXT;
ALTER TABLE repair_jobs ADD COLUMN feishu_plan_doc_id TEXT;
ALTER TABLE repair_jobs ADD COLUMN feishu_plan_url TEXT;每次日志触发 bug 后：
1. 创建 GitHub Issue
2. Agent 生成诊断报告 JSON
3. 飞书创建报告文件夹
4. 飞书创建诊断报告 DocX
5. 写入 blocks
6. 把报告 URL 写回 incident
7. 飞书卡片展示“查看诊断报告”
8. GitHub Issue 追加报告链接---
10. 推荐报告目录命名
飞书Agent自动修复报告/
  2026-05/
    issue-12-ZeroDivisionError/
      01-诊断报告
      02-修复计划
      03-测试报告
      04-PR复盘文档标题建议：
诊断报告 - Issue #12 - ZeroDivisionError - /orders/preview
修复计划 - Issue #12 - 参数校验缺失
测试报告 - PR #15 - pytest passed这样评委看起来会很完整。
