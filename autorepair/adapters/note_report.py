import logging
from dataclasses import dataclass

import httpx

from ..config import PROJECT_ROOT

logger = logging.getLogger(__name__)

_PASTE_RS_API = "https://paste.rs/"


@dataclass
class NoteReportRef:
    document_id: str
    document_token: str
    url: str
    title: str


class NoteReportClient:
    def create_report(self, title: str, content: str) -> NoteReportRef:
        ref = self._upload_to_paste_rs(content)
        if ref:
            ref.title = title
            logger.info(f"诊断报告已发布: {ref.url}")
            return ref

        return self._local_fallback(title, content)

    def _upload_to_paste_rs(self, text: str) -> NoteReportRef | None:
        try:
            resp = httpx.post(
                _PASTE_RS_API,
                content=text.encode("utf-8"),
                headers={"Content-Type": "text/plain; charset=utf-8"},
                timeout=30,
            )
            if resp.status_code == 201:
                url = resp.text.strip()
                paste_id = url.rstrip("/").split("/")[-1]
                return NoteReportRef(
                    document_id=paste_id,
                    document_token=paste_id,
                    url=url,
                    title="",
                )
            if resp.status_code == 206:
                logger.warning("paste.rs 部分上传（内容过大），降级为本地文件")
                return None
            logger.error(f"paste.rs 写入失败: status={resp.status_code} body={resp.text}")
        except Exception as e:
            logger.error(f"paste.rs 写入异常: {e}", exc_info=True)
        return None

    def _verify(self, url: str) -> bool:
        try:
            resp = httpx.get(url, timeout=15)
            return resp.status_code == 200 and len(resp.text) > 0
        except Exception as e:
            logger.warning(f"paste.rs 校验异常: {e}")
            return False

    def create_diagnostic_report(self, report) -> NoteReportRef:
        from ..reports.diagnostic_report_builder import render_diagnostic_report_plaintext

        title = f"故障诊断报告 - {report.incident_id} - {report.service_name}"
        content = render_diagnostic_report_plaintext(report)

        ref = self.create_report(title, content)
        if ref.document_id.startswith("local://"):
            return ref

        if self._verify(ref.url):
            logger.info(f"paste.rs 报告校验通过: {ref.url}")
            return ref

        logger.warning("paste.rs 报告校验失败，降级为本地文件")
        return self._local_fallback(title, content)

    def _local_fallback(self, title: str, content: str) -> NoteReportRef:
        report_dir = PROJECT_ROOT / "autorepair" / "records" / "reports"
        report_dir.mkdir(parents=True, exist_ok=True)
        safe_title = title.replace("/", "_").replace("\\", "_").replace(":", "_")
        report_path = report_dir / f"{safe_title}.txt"
        report_path.write_text(content, encoding="utf-8")
        logger.warning(f"报告已降级保存到本地: {report_path}")
        return NoteReportRef(
            document_id=f"local://{report_path.absolute()}",
            document_token=report_path.name,
            url=f"file://{report_path.absolute()}",
            title=title,
        )
