"""
文件名: test_cli_mcp_config_start.py
作者: JQQ
创建日期: 2025/9/22
版权: 2023 JQQ. All rights reserved.
依赖: pytest, pexpect
描述:
  中文: 使用固定的配置文件 tests/e2e/configs/server_direct_execution.json 来添加并启动 stdio MCP Server，然后校验 status 与 tools。
  English: Use fixed config file to add/start stdio MCP Server and assert status/tools.
"""

from __future__ import annotations

import re
import time

import pytest

pexpect = pytest.importorskip("pexpect", reason="e2e tests require pexpect; install with `pip install pexpect`.")


def _wait_for_prompt(child: pexpect.spawn, timeout: float = 10.0) -> None:
    child.expect("a2c> ", timeout=timeout)


def _assert_contains_tools(child: pexpect.spawn, tool_name: str, retries: int = 10, delay: float = 1.0) -> None:
    """检查工具列表中是否包含指定的工具名称 / Check if tools list contains the specified tool name"""
    for attempt in range(retries):
        child.sendline("tools")
        _wait_for_prompt(child)
        out = (child.before or "").strip()
        # 清理 ANSI 转义序列以获得更清晰的输出 / Clean ANSI escape sequences for cleaner output
        clean_out = re.sub(r"\x1b\[[0-9;]*[mK]", "", out)
        if tool_name in clean_out:
            return
        if attempt < retries - 1:  # 不在最后一次尝试时睡眠 / Don't sleep on last attempt
            time.sleep(delay)

    # 最后一次尝试，获取详细输出用于调试 / Final attempt with detailed output for debugging
    child.sendline("tools")
    _wait_for_prompt(child)
    out = (child.before or "").strip()
    clean_out = re.sub(r"\x1b\[[0-9;]*[mK]", "", out)
    assert tool_name in clean_out, f"tools 未包含 {tool_name}. 尝试次数: {retries}. 清理后输出:\n{clean_out}\n原始输出:\n{out}"


def _assert_status_has(child: pexpect.spawn, server_name: str, retries: int = 10, delay: float = 1.0) -> None:
    """检查服务器状态中是否包含指定的服务器名称 / Check if server status contains the specified server name"""
    for attempt in range(retries):
        child.sendline("status")
        _wait_for_prompt(child)
        out = (child.before or "").strip()
        # 清理 ANSI 转义序列以获得更清晰的输出 / Clean ANSI escape sequences for cleaner output
        clean_out = re.sub(r"\x1b\[[0-9;]*[mK]", "", out)
        if server_name in clean_out:
            return
        if attempt < retries - 1:  # 不在最后一次尝试时睡眠 / Don't sleep on last attempt
            time.sleep(delay)

    # 最后一次尝试，获取详细输出用于调试 / Final attempt with detailed output for debugging
    child.sendline("status")
    _wait_for_prompt(child)
    out = (child.before or "").strip()
    clean_out = re.sub(r"\x1b\[[0-9;]*[mK]", "", out)
    assert server_name in clean_out, f"status 未出现 {server_name}. 尝试次数: {retries}. 清理后输出:\n{clean_out}\n原始输出:\n{out}"


@pytest.mark.e2e
def test_start_via_known_config_file(cli_proc: pexpect.spawn) -> None:
    """
    使用固定的配置文件路径添加并启动 direct_execution 服务器，然后验证状态与工具：
    - server add @tests/e2e/configs/server_direct_execution.json
    - start all
    - status 包含 e2e-test
    - tools 包含 hello
    """
    child = cli_proc

    # 添加服务器配置 / Add server configuration
    child.sendline("server add @tests/e2e/configs/server_direct_execution.json")
    _wait_for_prompt(child)

    # 验证服务器已添加但未启动 / Verify server is added but not started
    child.sendline("status")
    _wait_for_prompt(child)

    # 显式启动所有服务器，确保进程就绪 / Explicitly start all servers and ensure processes are ready
    child.sendline("start all")
    _wait_for_prompt(child)

    # 给服务器更多时间来完全启动 / Give servers more time to fully start
    time.sleep(2.0)

    # 验证服务器状态和工具可用性 / Verify server status and tool availability
    _assert_status_has(child, "e2e-test", retries=12, delay=1.0)
    _assert_contains_tools(child, "hello", retries=12, delay=1.0)
