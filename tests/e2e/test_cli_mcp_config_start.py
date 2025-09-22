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

import time

import pytest

pexpect = pytest.importorskip("pexpect", reason="e2e tests require pexpect; install with `pip install pexpect`.")


def _wait_for_prompt(child: pexpect.spawn, timeout: float = 10.0) -> None:
    child.expect("a2c> ", timeout=timeout)


def _assert_contains_tools(child: pexpect.spawn, tool_name: str, retries: int = 8, delay: float = 1.0) -> None:
    for _ in range(retries):
        child.sendline("tools")
        _wait_for_prompt(child)
        out = (child.before or "").strip()
        if tool_name in out:
            return
        time.sleep(delay)
    child.sendline("tools")
    _wait_for_prompt(child)
    out = (child.before or "").strip()
    assert tool_name in out, f"tools 未包含 {tool_name}. 输出:\n{out}"


def _assert_status_has(child: pexpect.spawn, server_name: str, retries: int = 8, delay: float = 0.8) -> None:
    for _ in range(retries):
        child.sendline("status")
        _wait_for_prompt(child)
        out = (child.before or "").strip()
        if server_name in out:
            return
        time.sleep(delay)
    child.sendline("status")
    _wait_for_prompt(child)
    out = (child.before or "").strip()
    assert server_name in out, f"status 未出现 {server_name}. 输出:\n{out}"


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

    child.sendline("server add @tests/e2e/configs/server_direct_execution.json")
    _wait_for_prompt(child)

    # 显式启动，确保进程就绪
    child.sendline("start all")
    _wait_for_prompt(child)

    _assert_status_has(child, "e2e-test", retries=8, delay=0.8)
    _assert_contains_tools(child, "hello", retries=10, delay=1.0)
