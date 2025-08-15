# filename: logger.py
# @Time    : 2025/8/15 14:39
# @Author  : JQQ
# @Email   : jqq1716@gmail.com
# @Software: PyCharm
"""
日志模块用于 a2c_smcp 项目。
Logger module for a2c_smcp project.

本模块提供集中式日志配置，支持通过环境变量 A2C_SMCP_LOG_LEVEL 控制日志等级（字符串），
并可通过环境变量 A2C_SMCP_LOG_SILENT 控制是否全局禁用日志输出（静默模式）。
This module provides centralized logging configuration for the a2c_smcp project, supporting log level
control via the A2C_SMCP_LOG_LEVEL environment variable (string), and global log disabling (silent mode)
via A2C_SMCP_LOG_SILENT.
"""

import logging
import os
import sys


class Logger:
    """
    a2c_smcp 日志集中管理类。
    Centralized logger for a2c_smcp.

    支持通过环境变量控制日志等级和静默状态。
    Supports log level and silent mode control via environment variables.
    """
    DEFAULT_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    _loggers = {}
    _silent = False

    @classmethod
    def _get_env_log_level(cls) -> str:
        """
        获取环境变量中的日志等级（字符串）。
        Get log level from environment variable (string).
        """
        return os.environ.get("A2C_SMCP_LOG_LEVEL", "info").lower()

    @classmethod
    def _is_silent(cls) -> bool:
        """
        检查是否处于静默模式（环境变量A2C_SMCP_LOG_SILENT为1或true时）。
        Check if silent mode is enabled (A2C_SMCP_LOG_SILENT is '1' or 'true').
        """
        val = os.environ.get("A2C_SMCP_LOG_SILENT", "0").lower()
        return val in ("1", "true", "yes")

    @classmethod
    def get_logger(cls, name: str = "a2c_smcp") -> logging.Logger:
        """
        获取指定名称的 logger 实例。
        Get a logger instance for the specified name.
        """
        if name in cls._loggers:
            return cls._loggers[name]
        log = logging.getLogger(name)
        cls._loggers[name] = log
        return log

    @classmethod
    def configure(
        cls,
        level: str | None = None,
        format_str: str | None = None,
        log_to_console: bool = True,
        log_to_file: str | None = None,
    ) -> None:
        """
        配置日志系统。
        Configure the root logger.

        Args:
            level: 日志等级（字符串），如 'debug', 'info', 'warning', 'error', 'critical'。
                   Log level as string, e.g., 'debug', 'info', 'warning', 'error', 'critical'.
            format_str: 日志格式字符串。Log format string.
            log_to_console: 是否输出到控制台。Whether to log to console.
            log_to_file: 日志文件路径。Path to log file.
        """
        root_logger = cls.get_logger()

        # 判断静默模式
        cls._silent = cls._is_silent()
        if cls._silent:
            root_logger.disabled = True
            return
        else:
            root_logger.disabled = False

        # 解析日志等级
        log_level = (level or cls._get_env_log_level()).lower()
        level_map = {
            "debug": logging.DEBUG,
            "info": logging.INFO,
            "warning": logging.WARNING,
            "error": logging.ERROR,
            "critical": logging.CRITICAL,
        }
        py_level = level_map.get(log_level, logging.INFO)
        root_logger.setLevel(py_level)

        # 清理已有 handler
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)

        formatter = logging.Formatter(format_str or cls.DEFAULT_FORMAT)

        if log_to_console:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setFormatter(formatter)
            root_logger.addHandler(console_handler)

        if log_to_file:
            log_dir = os.path.dirname(log_to_file)
            if log_dir and not os.path.exists(log_dir):
                os.makedirs(log_dir)
            file_handler = logging.FileHandler(log_to_file)
            file_handler.setFormatter(formatter)
            root_logger.addHandler(file_handler)

    @classmethod
    def set_silent(cls, silent: bool = True) -> None:
        """
        设置静默模式，禁用或启用日志。
        Set silent mode, disable or enable logging.
        """
        cls._silent = silent
        log = cls.get_logger()
        log.disabled = silent

    @classmethod
    def set_log_level(cls, level: str) -> None:
        """
        设置日志等级。
        Set log level.
        """
        log = cls.get_logger()
        level_map = {
            "debug": logging.DEBUG,
            "info": logging.INFO,
            "warning": logging.WARNING,
            "error": logging.ERROR,
            "critical": logging.CRITICAL,
        }
        py_level = level_map.get(level.lower(), logging.INFO)
        log.setLevel(py_level)


# 初始化配置
Logger.configure()
logger = Logger.get_logger()
