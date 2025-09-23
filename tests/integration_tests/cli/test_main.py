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
    cli_main.patch_stdout = lambda raw: no_patch_stdout()  # type: ignore

    comp = Computer(inputs=set(), mcp_servers=set(), auto_connect=False, auto_reconnect=False)

    await _interactive_loop(comp)


class FakeSMCPClient:
    def __init__(self, *args: Any, **kwargs: Any) -> None:  # noqa: D401
        self.connected = False
        self.connect_args: dict[str, Any] | None = None
        FakeSMCPClient.last = self  # type: ignore[attr-defined]

    async def connect(self, url: str, auth: dict[str, Any] | None = None, headers: dict[str, Any] | None = None) -> None:
        self.connected = True
        self.connect_args = {"url": url, "auth": auth, "headers": headers}


@pytest.mark.asyncio
async def test_cli_socket_connect_guided_inputs_without_real_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    集成层面验证 CLI 的交互式引导输入 URL/Auth/Headers 的行为，但不依赖真实网络。
    """
    # Patch client to fake
    cli_main.SMCPComputerClient = FakeSMCPClient  # type: ignore

    commands = [
        "socket connect",
        "http://127.0.0.1:9000",
        "apikey:xyz",
        "app:demo,build:42",
        "exit",
    ]

    # Patch interactive IO
    cli_main.PromptSession = lambda: FakePromptSession(commands)  # type: ignore
    cli_main.patch_stdout = lambda raw: no_patch_stdout()  # type: ignore

    comp = Computer(inputs=set(), mcp_servers=set(), auto_connect=False, auto_reconnect=False)
    await _interactive_loop(comp)

    last: FakeSMCPClient = FakeSMCPClient.last  # type: ignore[assignment]
    assert last.connected is True
    assert last.connect_args == {
        "url": "http://127.0.0.1:9000",
        "auth": {"apikey": "xyz"},
        "headers": {"app": "demo", "build": "42"},
    }
