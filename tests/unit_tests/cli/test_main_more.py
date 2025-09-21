# -*- coding: utf-8 -*-
# filename: test_main_more.py
# 增强 CLI 覆盖率的单元测试
from __future__ import annotations

import json
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest

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
async def test_unknown_and_status_manager_uninitialized(monkeypatch: pytest.MonkeyPatch) -> None:
    commands = [
        "unknown",
        "status",
        "exit",
    ]
    monkeypatch.setattr(cli_main, "PromptSession", lambda: FakePromptSession(commands))
    monkeypatch.setattr(cli_main, "patch_stdout", lambda: no_patch_stdout())

    comp = Computer(inputs=[], mcp_servers=set(), auto_connect=False, auto_reconnect=False)
    await _interactive_loop(comp)


@pytest.mark.asyncio
async def test_server_rm_without_name_and_add_invalid_json(monkeypatch: pytest.MonkeyPatch) -> None:
    commands = [
        "server rm",
        "server add {invalid}",
        "exit",
    ]
    monkeypatch.setattr(cli_main, "PromptSession", lambda: FakePromptSession(commands))
    monkeypatch.setattr(cli_main, "patch_stdout", lambda: no_patch_stdout())

    comp = Computer(inputs=[], mcp_servers=set(), auto_connect=False, auto_reconnect=False)
    await _interactive_loop(comp)


@pytest.mark.asyncio
async def test_start_stop_all_with_manager_initialized(monkeypatch: pytest.MonkeyPatch) -> None:
    # 初始化 manager（无任何 server，不会真正启动外部进程）
    comp = Computer(inputs=[], mcp_servers=set(), auto_connect=False, auto_reconnect=False)
    await comp.boot_up()

    commands = [
        "start all",
        "stop all",
        "exit",
    ]
    monkeypatch.setattr(cli_main, "PromptSession", lambda: FakePromptSession(commands))
    monkeypatch.setattr(cli_main, "patch_stdout", lambda: no_patch_stdout())

    await _interactive_loop(comp)


@pytest.mark.asyncio
async def test_inputs_load_and_render(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    inputs_file = tmp_path / "inputs.json"
    inputs_file.write_text(
        json.dumps(
            [
                {"id": "VAR1", "type": "promptString", "description": "v", "default": "abc"},
                {"id": "CHOICE", "type": "pickString", "description": "d", "options": ["x", "y"], "default": "x"},
            ]
        ),
        encoding="utf-8",
    )

    any_file = tmp_path / "any.json"
    any_file.write_text(json.dumps({"k": "${input:VAR1}", "c": "${input:CHOICE}"}), encoding="utf-8")

    commands = [
        f"inputs load @{inputs_file}",
        f"render @{any_file}",
        "exit",
    ]

    monkeypatch.setattr(cli_main, "PromptSession", lambda: FakePromptSession(commands))
    monkeypatch.setattr(cli_main, "patch_stdout", lambda: no_patch_stdout())

    comp = Computer(inputs=[], mcp_servers=set(), auto_connect=False, auto_reconnect=False)
    await _interactive_loop(comp)


class FakeSMCPClient:
    def __init__(self, *args: Any, **kwargs: Any) -> None:  # noqa: D401
        self.connected = False
        self.office_id: str | None = None
        self.joined_args: tuple[str, str] | None = None
        self.updated = 0

    async def connect(self, url: str) -> None:
        self.connected = True

    async def join_office(self, office_id: str, computer_name: str) -> None:
        assert self.connected
        self.office_id = office_id
        self.joined_args = (office_id, computer_name)

    async def leave_office(self, office_id: str) -> None:
        assert self.connected
        self.office_id = None

    async def emit_update_mcp_config(self) -> None:
        self.updated += 1


@pytest.mark.asyncio
async def test_socket_and_notify_branches(monkeypatch: pytest.MonkeyPatch) -> None:
    # 替换 SMCPComputerClient 为假的客户端
    monkeypatch.setattr(cli_main, "SMCPComputerClient", FakeSMCPClient)

    commands = [
        "notify update",  # not connected -> skip
        "socket connect http://localhost:7000",
        "socket join office-1 compA",
        "notify update",  # should call emit_update_mcp_config
        "socket leave",
        "exit",
    ]

    monkeypatch.setattr(cli_main, "PromptSession", lambda: FakePromptSession(commands))
    monkeypatch.setattr(cli_main, "patch_stdout", lambda: no_patch_stdout())

    comp = Computer(inputs=[], mcp_servers=set(), auto_connect=False, auto_reconnect=False)
    await _interactive_loop(comp)
