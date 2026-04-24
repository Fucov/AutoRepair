from pathlib import Path


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
