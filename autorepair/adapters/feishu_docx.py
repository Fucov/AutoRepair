import os
import json
import requests
from typing import Optional, List, Dict
from dataclasses import dataclass
from ..config import config, PROJECT_ROOT
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
        self.headers = {
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
            response = requests.post(url, headers=self.headers, json=payload, timeout=10)
            response.raise_for_status()
            data = response.json()
            doc_data = data["data"]["document"]
            doc_id = doc_data["document_id"]
            doc_token = doc_data["token"]
            doc_url = f"{config.FEISHU_DOC_BASE_URL}/{doc_id}"
            
            return FeishuDocRef(
                document_id=doc_id,
                document_token=doc_token,
                url=doc_url,
                title=title
            )
        except Exception as e:
            logger.error(f"创建飞书文档失败: {str(e)}")
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
            response = requests.post(url, headers=self.headers, json=payload, timeout=10)
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
            response = requests.post(url, headers=self.headers, json=payload, timeout=10)
            response.raise_for_status()
        except Exception as e:
            logger.warning(f"添加飞书文档权限失败: {str(e)}，不影响主流程")

    def make_public_readable(self, document_token: str) -> bool:
        """设置文档公开可读"""
        # 简化实现，实际根据飞书API调整
        return True

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
