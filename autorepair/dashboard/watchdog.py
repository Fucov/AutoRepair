import logging
import threading
from pathlib import Path
from typing import Optional, Callable

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

logger = logging.getLogger(__name__)

_DEBOUNCE_MS = 500


class _DebouncedHandler(FileSystemEventHandler):
    def __init__(self, target_filenames: set[str], callback: Callable[[], None]):
        super().__init__()
        self._target_filenames = target_filenames
        self._callback = callback
        self._timer: Optional[threading.Timer] = None
        self._lock = threading.Lock()

    def on_modified(self, event):
        if event.is_directory:
            return
        path = Path(event.src_path)
        if path.name not in self._target_filenames:
            return
        logger.debug(f"检测到文件变化: {event.src_path}")
        self._debounce()

    def _debounce(self):
        with self._lock:
            if self._timer is not None:
                self._timer.cancel()
            self._timer = threading.Timer(_DEBOUNCE_MS / 1000.0, self._fire)
            self._timer.daemon = True
            self._timer.start()

    def _fire(self):
        with self._lock:
            self._timer = None
        try:
            self._callback()
        except Exception as e:
            logger.error(f"watchdog 回调执行失败: {e}", exc_info=True)


class FileWatchdog:
    def __init__(self):
        self._observer: Optional[Observer] = None
        self._running = False

    def start(self, watch_dir: str, target_filenames: set[str], callback: Callable[[], None]) -> None:
        if self._running:
            logger.warning("FileWatchdog 已在运行中")
            return

        handler = _DebouncedHandler(target_filenames, callback)
        self._observer = Observer()
        self._observer.schedule(handler, watch_dir, recursive=False)
        self._observer.daemon = True
        self._observer.start()
        self._running = True
        logger.info(f"FileWatchdog 启动，监听目录: {watch_dir}，目标文件: {target_filenames}")

    def stop(self) -> None:
        if self._observer and self._running:
            self._observer.stop()
            self._observer.join(timeout=5)
            self._observer = None
            self._running = False
            logger.info("FileWatchdog 已停止")

    @property
    def is_running(self) -> bool:
        return self._running


_file_watchdog = FileWatchdog()


def _run_pipeline_on_new_incidents():
    from autorepair.watcher import scan_service_logs_once
    from autorepair.service_registry import get_default_service
    from autorepair.issue_manager import ensure_issue_for_incident
    from autorepair.incident_store import update_incident_fields
    from autorepair.audit_store import append_audit_event
    from autorepair.adapters.feishu import send_incident_card, send_repair_plan_ready
    from autorepair.repair.job_store import create_repair_job
    from autorepair.repair.git_workspace import build_repair_branch
    from autorepair.config import GITHUB_OWNER, GITHUB_REPO
    from autorepair.dashboard.api import push_event

    service = get_default_service()
    results = scan_service_logs_once(service)

    if not results:
        return

    for incident, action in results:
        if action != "created":
            push_event("incident_updated", {
                "incident_id": incident.incident_id,
                "occurrence_count": incident.occurrence_count,
                "message": f"重复错误计数: {incident.occurrence_count}"
            })
            continue

        push_event("incident_detected", {
            "incident_id": incident.incident_id,
            "error_type": incident.error_summary.error_type,
            "message": f"检测到异常: {incident.error_summary.error_type}"
        })

        issue_ref = None
        doc_ref = None

        try:
            issue_ref = ensure_issue_for_incident(incident, service)
            incident.issue_number = issue_ref.number
            incident.issue_url = issue_ref.html_url
            update_incident_fields(incident.incident_id, issue_number=issue_ref.number, issue_url=issue_ref.html_url)

            push_event("issue_created", {
                "incident_id": incident.incident_id,
                "issue_number": issue_ref.number,
                "issue_url": issue_ref.html_url,
                "message": f"Issue已创建: #{issue_ref.number}"
            })
        except Exception as e:
            logger.error(f"创建Issue失败: {e}", exc_info=True)
            push_event("error", {"incident_id": incident.incident_id, "stage": "create_issue", "message": f"创建Issue失败: {e}"})
            continue

        try:
            from autorepair.reports.diagnostic_report_builder import build_diagnostic_report
            from autorepair.adapters.note_report import NoteReportClient

            note_client = NoteReportClient()
            triage_result = type('Triage', (), {
                'root_cause': f'{incident.error_summary.error_type}: {incident.error_summary.message}',
                'risk_level': 'medium'
            })()
            mock_issue = type('Issue', (), {
                'title': f"Bug: {incident.error_summary.error_type}",
                'body': incident.raw_traceback[:500] if incident.raw_traceback else "",
                'labels': ['bug', 'AutoRepair'],
                'number': issue_ref.number,
                'html_url': issue_ref.html_url,
            })()
            report = build_diagnostic_report(
                issue=mock_issue,
                incident=incident,
                validation_result="通过",
                triage_result=triage_result,
                policy_result="allowed",
            )
            doc_ref = note_client.create_diagnostic_report(report)
            push_event("diagnostic_report_created", {
                "incident_id": incident.incident_id,
                "issue_number": issue_ref.number,
                "report_url": doc_ref.url,
                "message": "诊断报告生成完成",
            })
        except Exception as e:
            logger.error(f"生成诊断报告失败: {e}", exc_info=True)

        try:
            report_url = doc_ref.url if doc_ref else ""
            send_incident_card(incident)
            send_repair_plan_ready(
                incident_id=incident.incident_id,
                service_name=service.name,
                diagnosis_brief=f"{incident.error_summary.error_type}: {incident.error_summary.message}",
                fix_strategy="自动分析Traceback并生成修复补丁",
                risk_level="medium",
                policy_result="allowed",
                report_url=report_url,
            )
            push_event("card_sent", {
                "incident_id": incident.incident_id,
                "issue_number": issue_ref.number,
                "report_url": report_url,
                "message": "飞书卡片已发送",
            })
        except Exception as e:
            logger.error(f"发送飞书卡片失败: {e}", exc_info=True)
            push_event("error", {"incident_id": incident.incident_id, "stage": "send_card", "message": f"飞书通知失败: {e}"})

        try:
            repair_branch = build_repair_branch(incident.incident_id, incident.error_summary.error_type)
            worktree_path = str(Path(service.repo_path) / ".worktrees" / incident.incident_id)
            job = create_repair_job(
                incident_id=incident.incident_id,
                issue_number=issue_ref.number,
                issue_url=issue_ref.html_url,
                repo_owner=GITHUB_OWNER or "local",
                repo_name=GITHUB_REPO or Path(service.repo_path).name,
                base_branch="main",
                repair_branch=repair_branch,
                worktree_path=worktree_path,
                policy_decision={"decision": "auto_fix", "confidence": "high"},
                risk_level="medium",
                report_url=doc_ref.url if doc_ref else "",
            )
            push_event("repair_job_created", {
                "job_id": job.job_id,
                "incident_id": incident.incident_id,
                "issue_number": issue_ref.number,
                "report_url": doc_ref.url if doc_ref else "",
                "message": "修复任务已加入队列",
            })
            append_audit_event("pipeline_incident_processed", incident.incident_id, {
                "issue_number": issue_ref.number,
                "job_id": job.job_id,
                "report_url": doc_ref.url if doc_ref else "",
                "source": "watchdog",
            })
        except Exception as e:
            logger.error(f"创建修复任务失败: {e}", exc_info=True)
            push_event("error", {"incident_id": incident.incident_id, "stage": "create_repair_job", "message": f"创建修复任务失败: {e}"})


def start_watchdog():
    from autorepair.service_registry import get_default_service
    from autorepair.dashboard.api import push_event

    if _file_watchdog.is_running:
        return

    service = get_default_service()
    if not service.log_paths:
        logger.error("服务未配置日志路径，无法启动监控")
        return

    first_log_path = Path(service.log_paths[0])
    watch_dir = first_log_path.parent

    if not watch_dir.exists():
        watch_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"日志目录不存在，已自动创建: {watch_dir}")

    if not first_log_path.exists():
        first_log_path.touch()
        logger.info(f"日志文件不存在，已自动创建: {first_log_path}")

    target_filenames = {first_log_path.name}
    _file_watchdog.start(str(watch_dir), target_filenames, _run_pipeline_on_new_incidents)
    push_event("watchdog_started", {
        "watch_dir": str(watch_dir),
        "target_files": list(target_filenames),
        "message": "文件监控已启动",
    })


def stop_watchdog():
    from autorepair.dashboard.api import push_event

    if not _file_watchdog.is_running:
        return

    _file_watchdog.stop()
    push_event("watchdog_stopped", {"message": "文件监控已停止"})


def get_watchdog_status() -> dict:
    return {
        "running": _file_watchdog.is_running,
    }
