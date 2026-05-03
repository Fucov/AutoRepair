import os
import json
import requests
from typing import Optional, List, Dict
from dataclasses import dataclass
from ..config import config, PROJECT_ROOT
from .feishu import token_manager
import logging

logger = logging.getLogger(__name__)

@dataclass
class FeishuDocRef:
    document_id: str
    document_token: str
    url: str
    title: str

class FeishuDocxClient:
    def __init__(self):
        self.base_url = config.FEISHU_API_BASE_URL.rstrip("/")
    
    def _get_headers(self) -> Dict[str, str]:
        """动态获取带有效token的请求头"""
        try:
            token = token_manager.get_token_sync()
            return {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }
        except Exception as e:
            logger.error(f"获取飞书token失败: {str(e)}")
            # 降级使用静态配置的token（兼容旧逻辑）
            return {
                "Authorization": f"Bearer {config.FEISHU_TENANT_ACCESS_TOKEN}",
                "Content-Type": "application/json"
            }

    def create_document(self, title: str, folder_token: Optional[str] = None) -> FeishuDocRef:
        """创建飞书文档"""
        url = f"{self.base_url}/docx/v1/documents"
        payload = {
            "title": title,
            "folder_token": folder_token or config.FEISHU_DOC_FOLDER_TOKEN
        }
        
        try:
            headers = self._get_headers()
            response = requests.post(url, headers=headers, json=payload, timeout=10)
            # 打印详细响应信息帮助排查
            if response.status_code != 200:
                logger.error(f"飞书API返回错误: 状态码={response.status_code}, 响应内容={response.text}")
            response.raise_for_status()
            data = response.json()
            
            if data.get("code") != 0:
                logger.error(f"飞书API业务错误: code={data.get('code')}, msg={data.get('msg')}")
                raise Exception(f"飞书API错误: {data.get('msg')}")
                
            doc_data = data["data"]["document"]
            doc_id = doc_data["document_id"]
            doc_token = doc_data["token"]
            doc_url = f"{config.FEISHU_DOC_BASE_URL}/{doc_id}"
            
            logger.info(f"飞书文档创建成功: {doc_url}")
            return FeishuDocRef(
                document_id=doc_id,
                document_token=doc_token,
                url=doc_url,
                title=title
            )
        except Exception as e:
            logger.error(f"创建飞书文档失败: {str(e)}")
            token_preview = headers.get("Authorization", "")[:20] if 'headers' in locals() else config.FEISHU_TENANT_ACCESS_TOKEN[:10]
            logger.error(f"请检查配置: FEISHU_TENANT_ACCESS_TOKEN={token_preview}... FEISHU_DOC_FOLDER_TOKEN={config.FEISHU_DOC_FOLDER_TOKEN}")
            # Fallback到本地Markdown
            return self._create_local_markdown_report(title)

    def append_blocks(self, document_id: str, blocks: List[Dict]) -> None:
        """向文档追加内容块"""
        url = f"{self.base_url}/docx/v1/documents/{document_id}/blocks/{document_id}/children"
        payload = {
            "children": blocks,
            "index": -1  # 追加到末尾
        }
        
        try:
            headers = self._get_headers()
            response = requests.post(url, headers=headers, json=payload, timeout=10)
            response.raise_for_status()
        except Exception as e:
            logger.error(f"写入飞书文档失败: {str(e)}")

    def add_view_permission(self, document_token: str, member_id: str, member_type: str = "openid") -> None:
        """添加文档查看权限"""
        url = f"{self.base_url}/drive/v1/permissions/{document_token}/members?type=docx"
        payload = {
            "member_id": member_id,
            "member_type": member_type,
            "perm": "view"
        }
        
        try:
            headers = self._get_headers()
            response = requests.post(url, headers=headers, json=payload, timeout=10)
            if response.status_code != 200:
                logger.error(f"添加权限API返回错误: 状态码={response.status_code}, 响应={response.text}")
            response.raise_for_status()
            data = response.json()
            if data.get("code") != 0:
                logger.warning(f"添加飞书文档权限业务错误: code={data.get('code')}, msg={data.get('msg')}，不影响主流程")
        except Exception as e:
            logger.warning(f"添加飞书文档权限失败: {str(e)}，不影响主流程")

    def make_public_readable(self, document_token: str) -> bool:
        """设置文档公开可读（企业内所有人可查看）"""
        url = f"{self.base_url}/drive/v1/permissions/{document_token}/members?type=docx"
        payload = {
            "member_type": "tenant",
            "member_id": "tenant",
            "perm": "view"
        }
        
        try:
            headers = self._get_headers()
            response = requests.post(url, headers=headers, json=payload, timeout=10)
            response.raise_for_status()
            data = response.json()
            if data.get("code") != 0:
                logger.warning(f"设置文档公开可读失败: code={data.get('code')}, msg={data.get('msg')}")
                return False
            logger.info(f"文档 {document_token} 已设置为企业内公开可读")
            return True
        except Exception as e:
            logger.warning(f"设置文档公开可读失败: {str(e)}，不影响主流程")
            return False

    def create_diagnostic_report(self, report: "DiagnosticReportData") -> FeishuDocRef:
        """创建诊断报告文档"""
        title = f"故障诊断报告 - {report.incident_id} - {report.service_name}"
        
        # 创建文档
        doc_ref = self.create_document(title)
        
        if doc_ref.document_id.startswith("local://"):
            # 本地报告，直接写入内容
            from ..reports.diagnostic_report_builder import render_diagnostic_report_markdown
            content = render_diagnostic_report_markdown(report)
            with open(doc_ref.document_id.replace("local://", ""), "w", encoding="utf-8") as f:
                f.write(content)
            return doc_ref
        
        # 渲染飞书文档块
        from ..reports.diagnostic_report_builder import render_diagnostic_report_blocks
        blocks = render_diagnostic_report_blocks(report)
        
        # 写入内容
        self.append_blocks(doc_ref.document_id, blocks)
        
        # 设置权限
        if config.FEISHU_DOC_PUBLIC_READABLE:
            self.make_public_readable(doc_ref.document_token)
        
        if config.FEISHU_DOC_SHARE_MEMBER_ID:
            self.add_view_permission(doc_ref.document_token, config.FEISHU_DOC_SHARE_MEMBER_ID, config.FEISHU_DOC_SHARE_MEMBER_TYPE)
        
        return doc_ref

    def _create_local_markdown_report(self, title: str) -> FeishuDocRef:
        """创建本地Markdown报告作为Fallback"""
        report_dir = PROJECT_ROOT / "autorepair" / "records" / "reports"
        report_dir.mkdir(parents=True, exist_ok=True)
        safe_title = title.replace('/', '_').replace('\\', '_').replace(':', '_')
        report_path = report_dir / f"{safe_title}.md"
        
        return FeishuDocRef(
            document_id=f"local://{report_path.absolute()}",
            document_token=report_path.name,
            url=f"file://{report_path.absolute()}",
            title=title
        )
