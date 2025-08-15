# filename: test_logger.py
# @Time    : 2025/8/15 19:36
# @Author  : JQQ
# @Email   : jqq1716@gmail.com
# @Software: PyCharm
import io
import logging
import os
import sys
import threading

import pytest

from a2c_smcp.utils.logger import Logger


@pytest.fixture(autouse=True)
def clear_env():
    """
    中文：自动清除和恢复相关环境变量
    English: Automatically clear and restore related environment variables
    """
    # 备份环境变量
    log_level_backup = os.environ.get("A2C_SMCP_LOG_LEVEL")
    log_silent_backup = os.environ.get("A2C_SMCP_LOG_SILENT")

    # 清除当前环境变量
    os.environ.pop("A2C_SMCP_LOG_LEVEL", None)
    os.environ.pop("A2C_SMCP_LOG_SILENT", None)

    yield  # 执行测试函数

    # 测试结束后恢复环境变量
    if log_level_backup is not None:
        os.environ["A2C_SMCP_LOG_LEVEL"] = log_level_backup

    if log_silent_backup is not None:
        os.environ["A2C_SMCP_LOG_SILENT"] = log_silent_backup


def test_get_logger_basic() -> None:
    """
    中文：基础 logger 获取
    English: Basic logger retrieval
    """
    logger1 = Logger.get_logger()
    logger2 = Logger.get_logger("a2c_smcp.test")
    assert isinstance(logger1, logging.Logger)
    assert isinstance(logger2, logging.Logger)
    assert logger1 is Logger.get_logger()  # 单例
    assert logger2 is Logger.get_logger("a2c_smcp.test")


def test_log_level_env(monkeypatch) -> None:
    """
    中文：环境变量控制日志等级
    English: Log level controlled by environment variable
    """
    monkeypatch.setenv("A2C_SMCP_LOG_LEVEL", "error")
    Logger.configure()
    logger = Logger.get_logger()
    assert logger.level == logging.ERROR


def test_log_silent_env(monkeypatch) -> None:
    """
    中文：环境变量控制静默模式
    English: Silent mode by environment variable
    """
    monkeypatch.setenv("A2C_SMCP_LOG_SILENT", "1")
    Logger.configure()
    logger = Logger.get_logger()
    assert logger.disabled


def test_log_to_file_and_console(tmp_path) -> None:
    """
    中文：日志输出到文件和控制台
    English: Log output to file and console
    """
    log_file = tmp_path / "test.log"
    Logger.configure(level="debug", log_to_console=False, log_to_file=str(log_file))
    logger = Logger.get_logger()
    logger.debug("file debug message")
    logger.error("file error message")
    with open(log_file, encoding="utf-8") as f:
        content = f.read()
    assert "file debug message" in content
    assert "file error message" in content


def test_log_to_console_capture(monkeypatch) -> None:
    """
    中文：日志输出到控制台捕获
    English: Capture log output to console
    """
    stream = io.StringIO()
    monkeypatch.setattr(sys, "stdout", stream)
    Logger.configure(level="info", log_to_console=True, log_to_file=None)
    logger = Logger.get_logger()
    logger.info("console info message")
    sys.stdout = sys.__stdout__  # 恢复
    assert "console info message" in stream.getvalue()


def test_set_silent_and_set_log_level() -> None:
    """
    中文：set_silent 和 set_log_level 的边界测试
    English: set_silent and set_log_level edge test
    """
    Logger.configure(level="debug")
    logger = Logger.get_logger()
    Logger.set_silent(True)
    assert logger.disabled
    Logger.set_silent(False)
    assert not logger.disabled
    Logger.set_log_level("warning")
    assert logger.level == logging.WARNING
    Logger.set_log_level("invalid")
    assert logger.level == logging.INFO  # fallback


def test_invalid_log_level(monkeypatch) -> None:
    """
    中文：无效日志等级回退
    English: Invalid log level fallback
    """
    monkeypatch.setenv("A2C_SMCP_LOG_LEVEL", "notalevel")
    Logger.configure()
    logger = Logger.get_logger()
    assert logger.level == logging.INFO


def test_multiple_configure(tmp_path) -> None:
    """
    中文：多次 configure 不应报错且可切换输出
    English: Multiple configure calls should not error and can switch outputs
    """
    log_file1 = tmp_path / "a.log"
    log_file2 = tmp_path / "b.log"
    Logger.configure(level="debug", log_to_console=False, log_to_file=str(log_file1))
    logger = Logger.get_logger()
    logger.info("msg1")
    Logger.configure(level="debug", log_to_console=False, log_to_file=str(log_file2))
    logger.info("msg2")
    with open(log_file1, encoding="utf-8") as f1:
        assert "msg1" in f1.read()
    with open(log_file2, encoding="utf-8") as f2:
        assert "msg2" in f2.read()


def test_log_file_dir_creation(tmp_path) -> None:
    """
    中文：日志文件目录自动创建
    English: Log file directory auto-creation
    """
    sub_dir = tmp_path / "subdir"
    log_file = sub_dir / "log.txt"
    Logger.configure(level="info", log_to_console=False, log_to_file=str(log_file))
    logger = Logger.get_logger()
    logger.info("auto create dir message")
    assert log_file.exists()
    with open(log_file, encoding="utf-8") as f:
        assert "auto create dir message" in f.read()


def test_thread_safety() -> None:
    """
    中文：多线程下 logger 获取和配置
    English: Logger get/configure in multithreaded environment
    """
    results = []

    def worker(idx):
        Logger.configure(level="debug")
        logger = Logger.get_logger(f"thread{idx}")
        results.append(logger.name)
    threads = [threading.Thread(target=worker, args=(i,)) for i in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(set(results)) == 5
