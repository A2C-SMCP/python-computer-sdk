"""
合并版 CLI 单测，包含基础与扩展用例
"""

from __future__ import annotations

import json
from collections.abc import Callable
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest

import a2c_smcp_cc.cli.main as cli_main
from a2c_smcp_cc.cli.main import _interactive_loop
from a2c_smcp_cc.computer import Computer


class DummyInteractive:
    called: bool = False
    last_comp: Any | None = None
    last_init_client: Any | None = None

    @classmethod
    async def coro(cls, comp: Any, init_client: Any | None = None) -> None:  # matches _interactive_loop signature
        cls.called = True
        cls.last_comp = comp
        cls.last_init_client = init_client


class FakeComputer:
    """A lightweight fake that matches Computer's init signature and async context manager."""

    def __init__(
        self,
        inputs: set[Any] | None = None,
        mcp_servers: set[Any] | None = None,
        auto_connect: bool = True,
        auto_reconnect: bool = True,
        confirm_callback: Callable[[str, str, str, dict], bool] | None = None,
        input_resolver: Any | None = None,
    ) -> None:
        self.init_args = {
            "inputs": inputs,
            "mcp_servers": mcp_servers,
            "auto_connect": auto_connect,
            "auto_reconnect": auto_reconnect,
            "confirm_callback": confirm_callback,
            "input_resolver": input_resolver,
        }

    async def __aenter__(self) -> FakeComputer:
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:  # noqa: ANN001
        return None


def test_run_impl_uses_default_computer_when_no_factory(monkeypatch: pytest.MonkeyPatch) -> None:
    from a2c_smcp_cc.cli import main as cli_main

    # Patch Computer to our fake and _interactive_loop to a dummy coro
    monkeypatch.setattr(cli_main, "Computer", FakeComputer, raising=True)
    monkeypatch.setattr(cli_main, "_interactive_loop", DummyInteractive.coro, raising=True)

    # Call implementation with no factory and no side-effect options
    cli_main._run_impl(
        auto_connect=True,
        auto_reconnect=True,
        url=None,
        namespace=None,
        auth=None,
        headers=None,
        computer_factory=None,
        config=None,
        inputs=None,
    )

    assert DummyInteractive.called is True
    assert isinstance(DummyInteractive.last_comp, FakeComputer)
    assert DummyInteractive.last_comp.init_args["auto_connect"] is True
    assert DummyInteractive.last_comp.init_args["auto_reconnect"] is True


def test_run_impl_uses_resolved_factory(monkeypatch: pytest.MonkeyPatch) -> None:
    from a2c_smcp_cc.cli import main as cli_main

    # Prepare a factory that returns our FakeComputer
    calls: dict[str, Any] = {"count": 0}

    def factory(**kwargs: Any) -> FakeComputer:
        calls["count"] += 1
        return FakeComputer(**kwargs)

    # Patch resolver to return our factory; patch interactive loop to avoid blocking
    monkeypatch.setattr(cli_main, "resolve_import_target", lambda s: factory, raising=True)
    monkeypatch.setattr(cli_main, "_interactive_loop", DummyInteractive.coro, raising=True)

    cli_main._run_impl(
        auto_connect=False,
        auto_reconnect=False,
        url=None,
        namespace=None,
        auth=None,
        headers=None,
        computer_factory="some.module:factory",
        config=None,
        inputs=None,
    )

    assert calls["count"] == 1
    assert isinstance(DummyInteractive.last_comp, FakeComputer)
    assert DummyInteractive.last_comp.init_args["auto_connect"] is False
    assert DummyInteractive.last_comp.init_args["auto_reconnect"] is False


def test_run_impl_factory_not_callable_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    from a2c_smcp_cc.cli import main as cli_main

    # Make resolve_import_target return a non-callable
    monkeypatch.setattr(cli_main, "resolve_import_target", lambda s: object(), raising=True)
    # Patch Computer fallback to our FakeComputer
    monkeypatch.setattr(cli_main, "Computer", FakeComputer, raising=True)
    monkeypatch.setattr(cli_main, "_interactive_loop", DummyInteractive.coro, raising=True)

    cli_main._run_impl(
        auto_connect=True,
        auto_reconnect=True,
        url=None,
        namespace=None,
        auth=None,
        headers=None,
        computer_factory="x.y:bad",
        config=None,
        inputs=None,
    )

    assert isinstance(DummyInteractive.last_comp, FakeComputer)


def test_run_impl_resolve_error_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    from a2c_smcp_cc.cli import main as cli_main

    def _raise(_: str) -> Any:
        raise ValueError("boom")

    monkeypatch.setattr(cli_main, "resolve_import_target", _raise, raising=True)
    monkeypatch.setattr(cli_main, "Computer", FakeComputer, raising=True)
    monkeypatch.setattr(cli_main, "_interactive_loop", DummyInteractive.coro, raising=True)

    cli_main._run_impl(
        auto_connect=True,
        auto_reconnect=True,
        url=None,
        namespace=None,
        auth=None,
        headers=None,
        computer_factory="x.y:z",
        config=None,
        inputs=None,
    )

    assert isinstance(DummyInteractive.last_comp, FakeComputer)


class FakePromptSession:
    """Feed scripted inputs to the interactive loop."""

    def __init__(self, commands: list[str]) -> None:
        self._commands = commands

    async def prompt_async(self, *_: str, **__: Any) -> str:  # noqa: D401
        if not self._commands:
            raise EOFError
        return self._commands.pop(0)


@contextmanager
def no_patch_stdout():
    """No-op context manager to replace patch_stdout() in tests."""
    yield


@pytest.mark.asyncio
async def test_interactive_help_and_exit(monkeypatch: pytest.MonkeyPatch) -> None:
    commands = [
        "help",
        "exit",
    ]
    monkeypatch.setattr(cli_main, "PromptSession", lambda: FakePromptSession(commands))
    monkeypatch.setattr(cli_main, "patch_stdout", lambda raw: no_patch_stdout())

    comp = Computer(inputs=set(), mcp_servers=set(), auto_connect=False, auto_reconnect=False)
    await _interactive_loop(comp)


@pytest.mark.asyncio
async def test_inputs_cli_crud_commands(monkeypatch: pytest.MonkeyPatch) -> None:
    """覆盖 inputs 子命令：add/update/rm/get/list，并在连接状态下触发配置更新通知。"""
    monkeypatch.setattr(cli_main, "SMCPComputerClient", FakeSMCPClient)

    # 使用 socket connect 建立连接，随后执行 inputs 的 CRUD 命令
    commands = [
        "socket connect http://localhost:7000",
        # add 单条
        'inputs add {"id":"USER","type":"promptString","description":"d","default":"a"}',
        # get + list
        "inputs get USER",
        "inputs list",
        # update 批量（数组）
        'inputs update [{"id":"USER","type":"promptString","description":"d2","default":"b"},'
        ' {"id":"REG","type":"pickString","description":"r","options":["us","eu"],"default":"us"}]',
        "inputs list",
        # rm
        "inputs rm USER",
        "inputs list",
        "exit",
    ]

    monkeypatch.setattr(cli_main, "PromptSession", lambda: FakePromptSession(commands))
    monkeypatch.setattr(cli_main, "patch_stdout", lambda raw: no_patch_stdout())

    comp = Computer(inputs=set(), mcp_servers=set(), auto_connect=False, auto_reconnect=False)
    await _interactive_loop(comp)

    last: FakeSMCPClient = FakeSMCPClient.last  # type: ignore[assignment]
    # 至少在 add/update/rm 期间触发了多次更新通知
    assert last.updated >= 3


@pytest.mark.asyncio
async def test_socket_connect_guided_inputs_parsing(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    验证在未提供 URL 的情况下，交互式引导输入 URL/Auth/Headers，并正确解析传给 connect(auth=..., headers=...).
    """
    monkeypatch.setattr(cli_main, "SMCPComputerClient", FakeSMCPClient)

    # 触发引导式：先输入命令，再依次回应 URL、Auth、Headers，然后退出
    commands = [
        "socket connect",
        "http://localhost:8000",
        "token:abc123",
        "app:demo,ver:1.0",
        "exit",
    ]

    monkeypatch.setattr(cli_main, "PromptSession", lambda: FakePromptSession(commands))
    monkeypatch.setattr(cli_main, "patch_stdout", lambda raw: no_patch_stdout())

    comp = Computer(inputs=set(), mcp_servers=set(), auto_connect=False, auto_reconnect=False)
    await _interactive_loop(comp)

    # 断言 FakeSMCPClient 收到了期望的参数
    last: FakeSMCPClient = FakeSMCPClient.last  # type: ignore[assignment]
    assert last.connected is True
    assert last.connect_args is not None
    assert last.connect_args["url"] == "http://localhost:8000"
    assert last.connect_args["auth"] == {"token": "abc123"}
    assert last.connect_args["headers"] == {"app": "demo", "ver": "1.0"}


def test_run_with_cli_url_auth_headers(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    验证通过 run(url=..., auth=..., headers=...) 启动时，会自动连接并传入解析后的参数，随后进入交互并退出。
    """
    monkeypatch.setattr(cli_main, "SMCPComputerClient", FakeSMCPClient)

    # 进入交互后立即退出
    commands = [
        "exit",
    ]
    monkeypatch.setattr(cli_main, "PromptSession", lambda: FakePromptSession(commands))
    monkeypatch.setattr(cli_main, "patch_stdout", lambda raw: no_patch_stdout())

    # 调用同步的 run()，其内部使用 asyncio.run() 执行
    cli_main.run(
        auto_connect=False,
        auto_reconnect=False,
        url="http://service:1234",
        namespace=cli_main.SMCP_NAMESPACE,
        auth="token:abc",
        headers="h1:v1,h2:v2",
    )

    last: FakeSMCPClient = FakeSMCPClient.last  # type: ignore[assignment]
    assert last.connected is True
    assert last.connect_args == {
        "url": "http://service:1234",
        "auth": {"token": "abc"},
        "headers": {"h1": "v1", "h2": "v2"},
        "namespaces": [cli_main.SMCP_NAMESPACE],
    }


@pytest.mark.asyncio
async def test_server_add_and_status_without_auto_connect(monkeypatch: pytest.MonkeyPatch) -> None:
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

    commands = [
        f"server add {stdio_cfg}",
        "mcp",
        "status",
        "exit",
    ]

    monkeypatch.setattr(cli_main, "PromptSession", lambda: FakePromptSession(commands))
    monkeypatch.setattr(cli_main, "patch_stdout", lambda raw: no_patch_stdout())

    comp = Computer(inputs=set(), mcp_servers=set(), auto_connect=False, auto_reconnect=False)
    await _interactive_loop(comp)


@pytest.mark.asyncio
async def test_unknown_and_status_manager_uninitialized(monkeypatch: pytest.MonkeyPatch) -> None:
    commands = [
        "unknown",
        "status",
        "exit",
    ]
    monkeypatch.setattr(cli_main, "PromptSession", lambda: FakePromptSession(commands))
    monkeypatch.setattr(cli_main, "patch_stdout", lambda raw: no_patch_stdout())

    comp = Computer(inputs=set(), mcp_servers=set(), auto_connect=False, auto_reconnect=False)
    await _interactive_loop(comp)


@pytest.mark.asyncio
async def test_server_rm_without_name_and_add_invalid_json(monkeypatch: pytest.MonkeyPatch) -> None:
    commands = [
        "server rm",
        "server add {invalid}",
        "exit",
    ]
    monkeypatch.setattr(cli_main, "PromptSession", lambda: FakePromptSession(commands))
    monkeypatch.setattr(cli_main, "patch_stdout", lambda raw: no_patch_stdout())

    comp = Computer(inputs=set(), mcp_servers=set(), auto_connect=False, auto_reconnect=False)
    await _interactive_loop(comp)


@pytest.mark.asyncio
async def test_start_stop_all_with_manager_initialized(monkeypatch: pytest.MonkeyPatch) -> None:
    comp = Computer(inputs=set(), mcp_servers=set(), auto_connect=False, auto_reconnect=False)
    await comp.boot_up()

    commands = [
        "start all",
        "stop all",
        "exit",
    ]
    monkeypatch.setattr(cli_main, "PromptSession", lambda: FakePromptSession(commands))
    monkeypatch.setattr(cli_main, "patch_stdout", lambda raw: no_patch_stdout())

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
    monkeypatch.setattr(cli_main, "patch_stdout", lambda raw: no_patch_stdout())

    comp = Computer(inputs=set(), mcp_servers=set(), auto_connect=False, auto_reconnect=False)
    await _interactive_loop(comp)


class FakeSMCPClient:
    def __init__(self, *args: Any, **kwargs: Any) -> None:  # noqa: D401
        self.connected = False
        self.office_id: str | None = None
        self.joined_args: tuple[str, str] | None = None
        self.updated = 0
        # 记录最后一个实例，便于断言
        FakeSMCPClient.last = self  # type: ignore[attr-defined]
        self.connect_args: dict[str, Any] | None = None

    async def connect(
        self,
        url: str,
        auth: dict[str, Any] | None = None,
        headers: dict[str, Any] | None = None,
        namespaces: list[str] | None = None,
    ) -> None:
        self.connected = True
        args: dict[str, Any] = {"url": url, "auth": auth, "headers": headers}
        if namespaces is not None:
            args["namespaces"] = namespaces
        self.connect_args = args

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
    monkeypatch.setattr(cli_main, "SMCPComputerClient", FakeSMCPClient)

    commands = [
        "notify update",
        "socket connect http://localhost:7000",
        "socket join office-1 compA",
        "notify update",
        "socket leave",
        "exit",
    ]

    monkeypatch.setattr(cli_main, "PromptSession", lambda: FakePromptSession(commands))
    monkeypatch.setattr(cli_main, "patch_stdout", lambda raw: no_patch_stdout())

    comp = Computer(inputs=set(), mcp_servers=set(), auto_connect=False, auto_reconnect=False)
    await _interactive_loop(comp)
