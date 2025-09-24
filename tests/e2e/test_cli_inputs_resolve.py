"""
文件名: test_cli_inputs_resolve.py
作者: JQQ
创建日期: 2025/9/24
最后修改日期: 2025/9/24
版权: 2023 JQQ. All rights reserved.
依赖: pytest, pexpect
描述:
  中文: 通过 inputs load + server add 的方式，验证配置中的 ${input:xxx} 能被正确解析并用于启动 MCP Server。
  English: Verify that ${input:xxx} placeholders are correctly resolved after `inputs load` and used to start MCP Server.
"""

from __future__ import annotations

import re
import time

import pytest

pexpect = pytest.importorskip("pexpect", reason="e2e tests require pexpect; install with `pip install pexpect`.")

# 中文: ANSI 控制序列匹配与去除工具，避免 prompt_toolkit 的控制序列影响断言
# English: ANSI control-sequence helpers to avoid prompt_toolkit artifacts breaking assertions
ANSI = r"(?:\x1b\[[0-?]*[ -/]*[@-~])*"
PROMPT_RE = re.compile(ANSI + r"a2c>" + ANSI)


def strip_ansi(s: str) -> str:
    return re.sub(ANSI, "", s)


@pytest.mark.e2e
def test_inputs_resolve_then_server_start(cli_proc: pexpect.spawn) -> None:
    """
    中文: 加载 inputs_basic.json 后，添加引用 ${input:SCRIPT} 的 server 配置，应能正确渲染并启动。
    English: After loading inputs_basic.json, adding a server config that references ${input:SCRIPT} should render
             correctly and start.

    步骤 Steps:
      1) inputs load @tests/e2e/configs/inputs_basic.json
      2) server add @tests/e2e/configs/server_using_input.json
      3) start all
      4) status 包含 e2e-inputs-test，tools 包含 hello
    """
    child = cli_proc

    # 1) 加载 inputs 定义 / load inputs definitions
    child.sendline("inputs load @tests/e2e/configs/inputs_basic.json")
    child.expect(PROMPT_RE)

    # 2) 添加引用 ${input:SCRIPT} 的 server / add server that references ${input:SCRIPT}
    child.sendline("server add @tests/e2e/configs/server_using_input.json")
    # 给渲染/注册留一点时间 / allow a short time for render/registration
    time.sleep(1.0)
    # 输入一个回车，表示使用默认值
    child.sendline("\n")
    child.expect(PROMPT_RE)

    # 3) 启动所有服务 / start all servers
    child.sendline("start all")
    child.expect(PROMPT_RE)

    # 4) 轮询校验 status/tools / poll for status/tools
    def _assert_contains(cmd: str, needle: str, retries: int = 12, delay: float = 1.0) -> None:
        for _ in range(retries):
            child.sendline(cmd)
            child.expect(PROMPT_RE)
            time.sleep(delay)
            out = strip_ansi((child.before or "").strip())
            if needle in out:
                return
        # 最后再打一遍用于调试 / one more time for debug output
        child.sendline(cmd)
        child.expect(PROMPT_RE)
        out = strip_ansi((child.before or "").strip())
        assert needle in out, f"`{cmd}` 未包含 {needle}. 输出:\n{out}"

    _assert_contains("status", "e2e-inputs-test", retries=14, delay=0.8)
    _assert_contains("tools", "hello", retries=14, delay=1.0)
