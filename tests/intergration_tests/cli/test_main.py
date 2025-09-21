# -*- coding: utf-8 -*-
# filename: test_main_integration.py
# 基于真实 stdio MCP Server 的 CLI 集成测试
from __future__ import annotations

import json
from contextlib import contextmanager
from typing import Any

import pytest
from mcp import StdioServerParameters

import a2c_smcp_cc.cli.main as cli_main
from a2c_smcp_cc.cli.main import _interactive_loop
from a2c_smcp_cc.computer import Computer


class FakePromptSession:
    def __init__(self, commands: list[str]) -> None:
        self._commands = commands

    async def prompt_async(self, *_: str, **__: Any) -> str:
        if not self._commands:
            raise EOFError
        return self._commands.pop(0)


@contextmanager
def no_patch_stdout():
    yield


@pytest.mark.asyncio
async def test_cli_with_real_stdio(stdio_params: StdioServerParameters) -> None:
    """
    集成测试：通过 CLI 交互完成以下流程（使用真实 stdio MCP server 参数）：
    1) 添加 server 配置（disabled=false）
    2) 启动该 server
    3) 列出工具与状态
    4) 停止该 server
    5) 退出
    期望：流程执行无异常。
    """
    server_cfg = {
        "name": "it-stdio",
        "type": "stdio",
        "disabled": False,
        "forbidden_tools": [],
        "tool_meta": {},
        "server_parameters": json.loads(stdio_params.model_dump_json()),
    }

    commands = [
        f"server add {json.dumps(server_cfg)}",
        "start it-stdio",
        "tools",
        "status",
        "stop it-stdio",
        "exit",
    ]

    # Patch interactive IO
    cli_main.PromptSession = lambda: FakePromptSession(commands)  # type: ignore
    cli_main.patch_stdout = lambda: no_patch_stdout()  # type: ignore

    comp = Computer(inputs=[], mcp_servers=set(), auto_connect=False, auto_reconnect=False)

    await _interactive_loop(comp)
