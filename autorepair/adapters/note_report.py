import uuid
import time
import logging
from typing import Optional
from dataclasses import dataclass

import httpx

from ..config import config, PROJECT_ROOT

logger = logging.getLogger(__name__)

NOTE_MS_BASE = "https://note.ms"
_WRITE_API = "https://notems.dreamqjlight.us.kg/write"
_READ_API = "https://notems.dreamqjlight.us.kg/read"
_MIN_INTERVAL = 3.5


@dataclass
class NoteReportRef:
    document_id: str
    document_token: str
    url: str
    title: str


class NoteReportClient:
    def __init__(self):
        self._last_request_at: float = 0

    def _throttle(self):
        elapsed = time.time() - self._last_request_at
        if elapsed < _MIN_INTERVAL:
            time.sleep(_MIN_INTERVAL - elapsed)
        self._last_request_at = time.time()

    def _generate_page_name(self) -> str:
        return f"ar-{uuid.uuid4().hex}"

    def create_report(self, title: str, content: str) -> NoteReportRef:
        page_name = self._generate_page_name()
        self._write_page(page_name, content)
        url = f"{NOTE_MS_BASE}/{page_name}"
        logger.info(f"诊断报告已发布: {url}")
        return NoteReportRef(
            document_id=page_name,
            document_token=page_name,
            url=url,
            title=title,
        )

    def _write_page(self, page_name: str, text: str) -> None:
        self._throttle()
        try:
            resp = httpx.post(
                _WRITE_API,
                data={"page": page_name, "text": text},
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=30,
            )
            if resp.status_code == 429:
                logger.warning("note.ms 速率限制，等待后重试")
                time.sleep(5)
                resp = httpx.post(
                    _WRITE_API,
                    data={"page": page_name, "text": text},
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                    timeout=30,
                )
            resp.raise_for_status()
            data = resp.json()
            if data.get("status") != "success":
                logger.error(f"note.ms 写入失败: {data}")
        except Exception as e:
            logger.error(f"note.ms 写入异常: {e}", exc_info=True)

    def create_diagnostic_report(self, report) -> NoteReportRef:
        from ..reports.diagnostic_report_builder import render_diagnostic_report_plaintext

        title = f"故障诊断报告 - {report.incident_id} - {report.service_name}"
        content = render_diagnostic_report_plaintext(report)
        return self.create_report(title, content)

    def create_local_fallback(self, title: str, content: str) -> NoteReportRef:
        report_dir = PROJECT_ROOT / "autorepair" / "records" / "reports"
        report_dir.mkdir(parents=True, exist_ok=True)
        safe_title = title.replace("/", "_").replace("\\", "_").replace(":", "_")
        report_path = report_dir / f"{safe_title}.txt"
        report_path.write_text(content, encoding="utf-8")
        logger.warning(f"note.ms 不可用，降级为本地报告: {report_path}")
        return NoteReportRef(
            document_id=f"local://{report_path.absolute()}",
            document_token=report_path.name,
            url=f"file://{report_path.absolute()}",
            title=title,
        )
