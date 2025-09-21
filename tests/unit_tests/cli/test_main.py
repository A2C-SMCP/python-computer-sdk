# -*- coding: utf-8 -*-
# filename: test_main.py
# @Time    : 2025/9/21 20:03
# @Author  : JQQ
# @Email   : jiaqia@qknode.com
# @Software: PyCharm
from contextlib import contextmanager

import pytest

from a2c_smcp_cc.cli.main import _interactive_loop
from a2c_smcp_cc.computer import Computer


class FakePromptSession:
    """A fake PromptSession to feed scripted inputs to the interactive loop."""

    def __init__(self, commands: list[str]) -> None:
        self._commands = commands

    async def prompt_async(self, *_: str, **__: str) -> str:  # noqa: D401
        if not self._commands:
            # Simulate Ctrl+D to exit if commands run out
            raise EOFError
        return self._commands.pop(0)


@contextmanager
def no_patch_stdout():
    """No-op context manager to replace patch_stdout() in tests."""
    yield


@pytest.mark.asyncio
async def test_interactive_help_and_exit(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    基础交互命令：help -> exit
    - 期望：不抛出异常即可
    """
    # Arrange: patch PromptSession and patch_stdout in module under test
    import a2c_smcp_cc.cli.main as cli_main

    commands = [
        "help",  # show help
        "exit",  # exit loop
    ]
    monkeypatch.setattr(cli_main, "PromptSession", lambda: FakePromptSession(commands))
    monkeypatch.setattr(cli_main, "patch_stdout", lambda: no_patch_stdout())

    # Use a computer with no auto-connect to avoid side-effects
    comp = Computer(inputs=[], mcp_servers=set(), auto_connect=False, auto_reconnect=False)

    # Act / Assert: should finish without raising
    await _interactive_loop(comp)


@pytest.mark.asyncio
async def test_server_add_and_status_without_auto_connect(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    在 auto_connect=False 时添加一个服务器配置，然后查询 status。
    - 期望：流程完成且无异常；状态打印不会触发客户端启动。
    """
    import a2c_smcp_cc.cli.main as cli_main

    # Minimal stdio server config (disabled=true to avoid start operations later)
    stdio_cfg = {
        "name": "test-stdio",
        "type": "stdio",
        "disabled": True,
        "forbidden_tools": [],
        "tool_meta": {},
        "server_parameters": {
            "command": "echo",
            "args": [],
            "env": None,
            "cwd": None,
            "encoding": "utf-8",
            "encoding_error_handler": "strict",
        },
    }

    # Compose scripted commands: add -> mcp -> status -> exit
    commands = [
        f"server add {stdio_cfg}",
        "mcp",
        "status",
        "exit",
    ]

    monkeypatch.setattr(cli_main, "PromptSession", lambda: FakePromptSession(commands))
    monkeypatch.setattr(cli_main, "patch_stdout", lambda: no_patch_stdout())

    comp = Computer(inputs=[], mcp_servers=set(), auto_connect=False, auto_reconnect=False)

    await _interactive_loop(comp)
