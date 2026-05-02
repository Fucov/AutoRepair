import tempfile
from pathlib import Path
from autorepair.log_parser import extract_traceback_blocks, read_new_log_text


SAMPLE_LOG_CONTENT = """2024-05-01 12:00:00 - INFO - Service started
Traceback (most recent call last):
  File "demo_service/app.py", line 37, in get_user_profile
    return build_user_profile(user_id)
  File "demo_service/service.py", line 11, in build_user_profile
    "id": user["id"],
TypeError: 'NoneType' object is not subscriptable

2024-05-01 12:00:01 - INFO - Another request
Traceback (most recent call last):
  File "demo_service/app.py", line 179, in preview_order
    return calculate_order_discount(request)
  File "demo_service/order_service.py", line 16, in calculate_order_discount
    discount_rate = request.discount_amount / request.total_amount
ZeroDivisionError: division by zero
"""


def test_extract_traceback_blocks_multiple():
    """测试能从包含多个Traceback的文本中提取两个块"""
    blocks = extract_traceback_blocks(SAMPLE_LOG_CONTENT)
    assert len(blocks) == 2
    assert "TypeError: 'NoneType' object is not subscriptable" in blocks[0]
    assert "ZeroDivisionError: division by zero" in blocks[1]


def test_extract_traceback_blocks_empty():
    """测试空文本返回空列表"""
    assert extract_traceback_blocks("") == []
    assert extract_traceback_blocks("2024-05-01 12:00:00 - INFO - Normal log") == []


def test_read_new_log_text_offset():
    """测试按偏移量读取新增内容"""
    content = b"line1\nline2\nline3\n"
    with tempfile.NamedTemporaryFile(mode="wb", delete=False, suffix=".log") as f:
        f.write(content)
        temp_path = Path(f.name)
    
    try:
        # 从偏移量0读取全部
        text, offset = read_new_log_text(temp_path, 0)
        expected = content.decode("utf-8")
        assert text == expected
        assert offset == len(content)
        
        # 从偏移量6读取剩余内容
        text2, offset2 = read_new_log_text(temp_path, 6)
        assert text2 == expected[6:]
        assert offset2 == offset
    finally:
        temp_path.unlink()


def test_read_new_log_text_truncated():
    """测试日志被截断时偏移量重置为0"""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".log") as f:
        f.write("long content here" * 100)
        temp_path = Path(f.name)
    
    try:
        original_size = temp_path.stat().st_size
        
        # 模拟文件被截断
        with open(temp_path, "w", encoding="utf-8") as f:
            f.write("short content")
        
        # 传入大于当前文件大小的偏移量，应该返回0和全部内容
        text, new_offset = read_new_log_text(temp_path, original_size)
        assert new_offset == len("short content")
        assert text == "short content"
    finally:
        temp_path.unlink()


def test_read_new_log_text_file_not_exist():
    """测试文件不存在时返回空"""
    text, offset = read_new_log_text("/non/existent/file.log", 0)
    assert text == ""
    assert offset == 0
