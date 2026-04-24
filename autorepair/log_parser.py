import re
import hashlib
from pathlib import Path
from typing import Optional

from .schemas import ErrorSummary


def read_latest_traceback(log_path: str | Path) -> str | None:
    """
    读取指定日志文件，返回最后一个完整的 Traceback 内容
    """
    log_path = Path(log_path)
    
    if not log_path.exists():
        return None
    
    try:
        with open(log_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except Exception:
        return None
    
    traceback_start = "Traceback (most recent call last):"
    traceback_blocks = []
    current_block = []
    in_traceback = False
    
    for line in lines:
        if traceback_start in line:
            if in_traceback and current_block:
                traceback_blocks.append("".join(current_block))
            current_block = [line]
            in_traceback = True
        elif in_traceback:
            current_block.append(line)
            # 检测 Traceback 结束：空行或正常日志格式开头（假设日志行以时间/级别开头）
            if line.strip() == "" or (len(line) > 10 and line[4] == "-" and line[7] == "-"):
                traceback_blocks.append("".join(current_block))
                in_traceback = False
                current_block = []
    
    # 处理文件末尾未结束的 Traceback
    if in_traceback and current_block:
        traceback_blocks.append("".join(current_block))
    
    return traceback_blocks[-1].strip() if traceback_blocks else None


def extract_error_summary(traceback_text: str) -> Optional[ErrorSummary]:
    """
    从Traceback文本中提取错误摘要，优先选择项目内文件而非第三方框架文件
    """
    if not traceback_text:
        return None
    
    # 匹配Traceback中的File行: File "xxx", line xxx, in xxx
    file_pattern = re.compile(r'File "([^"]+)", line (\d+), in (\w+)')
    # 匹配最后一行错误: ErrorType: message
    error_pattern = re.compile(r'^(\w+):\s*(.+)$', re.MULTILINE)
    
    # 提取所有File记录
    file_matches = list(file_pattern.finditer(traceback_text))
    if not file_matches:
        return None
    
    # 找到最后一个属于项目内的文件（排除site-packages、Python安装目录等第三方文件）
    project_file = None
    for match in reversed(file_matches):
        file_path = match.group(1)
        # 排除第三方库路径
        if 'site-packages' in file_path.lower() or 'lib/python' in file_path.lower():
            continue
        # 优先选择项目内的demo_service或autorepair目录下的文件
        if 'demo_service' in file_path or 'autorepair' in file_path:
            project_file = match
            break
    
    # 如果没有找到项目内文件，取最后一个File
    if not project_file:
        project_file = file_matches[-1]
    
    file_path = project_file.group(1)
    line_no = int(project_file.group(2))
    function = project_file.group(3)
    
    # 提取错误类型和消息
    error_match = list(error_pattern.finditer(traceback_text))
    if not error_match:
        return None
    
    # 最后一行是真正的错误
    error_match = error_match[-1]
    error_type = error_match.group(1)
    message = error_match.group(2).strip()
    
    # 简化文件路径，只保留相对路径部分
    suspected_file = None
    if 'demo_service' in file_path:
        suspected_file = file_path[file_path.find('demo_service'):]
    elif 'autorepair' in file_path:
        suspected_file = file_path[file_path.find('autorepair'):]
    else:
        suspected_file = Path(file_path).name
    
    # 生成指纹: error_type + suspected_file + line_no + message 取sha1前12位
    fingerprint_raw = f"{error_type}:{suspected_file}:{line_no}:{message}".encode('utf-8')
    fingerprint = hashlib.sha1(fingerprint_raw).hexdigest()[:12]
    
    return ErrorSummary(
        error_type=error_type,
        message=message,
        suspected_file=suspected_file,
        line_no=line_no,
        function=function,
        fingerprint=fingerprint
    )
