"""
文件名: main.py
作者: JQQ
创建日期: 2025/9/18
最后修改日期: 2025/9/22
版权: 2023 JQQ. All rights reserved.
依赖: typer, rich, prompt_toolkit
描述:
  中文: A2C 计算机客户端的命令行入口，提供持续运行模式与基础交互命令。
  English: CLI entry for A2C Computer client. Provides persistent run mode and basic interactive commands.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import typer
from prompt_toolkit import PromptSession
from prompt_toolkit.patch_stdout import patch_stdout
from pydantic import TypeAdapter
from rich.table import Table

from a2c_smcp_cc.computer import Computer
from a2c_smcp_cc.mcp_clients.model import MCPServerInput as MCPServerInputModel
from a2c_smcp_cc.socketio.client import SMCPComputerClient
from a2c_smcp_cc.socketio.smcp import MCPServerConfig as SMCPServerConfigDict
from a2c_smcp_cc.socketio.smcp import MCPServerInput as SMCPServerInputDict
from a2c_smcp_cc.utils import console as console_util

app = typer.Typer(add_completion=False, help="A2C Computer CLI")
# 使用全局 Console（引用模块属性，便于后续动态切换）
console = console_util.console


def _parse_kv_pairs(text: str | None) -> dict[str, Any] | None:
    """
    将形如 "k1:v1,k2:v2" 的字符串解析为 dict。
    要求：多个键值对之间用逗号分隔，逗号后不要空格；若有空格会自动忽略并给出宽容解析。

    Args:
        text: 原始输入字符串；None 或空字符串时返回 None。

    Returns:
        dict 或 None
    """
    if text is None:
        return None
    s = text.strip()
    if s == "":
        return None
    result: dict[str, Any] = {}
    for seg in s.split(","):
        seg = seg.strip()  # 宽容处理潜在空格
        if seg == "":
            continue
        if ":" not in seg:
            raise ValueError(f"无效的键值对: {seg}，应为 key:value 形式")
        k, v = seg.split(":", 1)
        k = k.strip()
        v = v.strip()
        if not k:
            raise ValueError(f"无效的键名: '{seg}'")
        result[k] = v
    return result if result else None


def _print_status(comp: Computer) -> None:
    if not comp.mcp_manager:
        console.print("[yellow]Manager 未初始化 / Manager not initialized[/yellow]")
        return
    rows = comp.mcp_manager.get_server_status()
    table = Table(title="服务器状态 / Servers Status")
    table.add_column("Name")
    table.add_column("Active")
    table.add_column("State")
    for name, active, state in rows:
        table.add_row(name, "Yes" if active else "No", state)
    console.print(table)


def _print_tools(tools: list[dict[str, Any]]) -> None:
    table = Table(title="工具列表 / Tools")
    table.add_column("Name")
    table.add_column("Description")
    table.add_column("Has Return")
    for t in tools:
        table.add_row(t.get("name", ""), (t.get("description") or "")[:80], "Yes" if t.get("return_schema") else "No")
    console.print(table)


def _print_mcp_config(config: dict[str, Any]) -> None:
    servers = config.get("servers") or {}
    inputs = config.get("inputs") or []
    console.print("[bold]Servers:[/bold]")
    s_table = Table()
    s_table.add_column("Name")
    s_table.add_column("Type")
    s_table.add_column("Disabled")
    for name, cfg in servers.items():
        s_table.add_row(name, cfg.get("type", ""), "Yes" if cfg.get("disabled") else "No")
    console.print(s_table)

    console.print("[bold]Inputs:[/bold]")
    i_table = Table()
    i_table.add_column("ID")
    i_table.add_column("Type")
    i_table.add_column("Description")
    for i in inputs:
        i_table.add_row(i.get("id", ""), i.get("type", ""), (i.get("description") or "")[:60])
    console.print(i_table)


@app.callback(invoke_without_command=True)
def _root(
    ctx: typer.Context,
    auto_connect: bool = typer.Option(True, help="是否自动连接 / Auto connect"),
    auto_reconnect: bool = typer.Option(True, help="是否自动重连 / Auto reconnect"),
    url: str | None = typer.Option(None, help="Socket.IO 服务器URL，例如 https://host:port"),
    auth: str | None = typer.Option(None, help="认证参数，形如 key:value,foo:bar"),
    headers: str | None = typer.Option(None, help="请求头参数，形如 key:value,foo:bar"),
    no_color: bool = typer.Option(
        False,
        "--no-color",
        help="关闭彩色输出（PyCharm控制台不渲染ANSI时可使用） / Disable ANSI colors",
    ),
) -> None:
    """
    根级入口：
    - 若未指定子命令，则等价于执行 `run`，保持 `a2c-computer` 和 `a2c-computer run` 两种用法都可用。
    - 若指定了子命令，则不做处理，交给子命令。
    """
    # 根据 no_color 动态调整全局 Console
    if no_color:
        global console
        console_util.set_no_color(True)
        # 重新绑定本地引用
        console = console_util.console

    if ctx.invoked_subcommand is None:
        # 注意：不要直接调用被 @app.command 装饰的 run()，否则未传入的参数会保留 OptionInfo 默认值
        # 这里改为调用纯实现函数 _run_impl，并显式传入 config=None 与 inputs=None。
        _run_impl(
            auto_connect=auto_connect,
            auto_reconnect=auto_reconnect,
            url=url,
            auth=auth,
            headers=headers,
            config=None,
            inputs=None,
        )


async def _interactive_loop(comp: Computer, init_client: SMCPComputerClient | None = None) -> None:
    session = PromptSession()
    smcp_client: SMCPComputerClient | None = init_client
    console.print("[bold]进入交互模式，输入 help 查看命令 / Enter interactive mode, type 'help' for commands[/bold]")
    # 如果当前输出不被识别为 TTY，ANSI 颜色可能无法渲染（如 PyCharm 未开启仿真终端）
    if not console.is_terminal and not console.no_color:
        console.print(
            "[yellow]检测到控制台可能不支持 ANSI 颜色。若在 PyCharm 中运行，请在 Run/Debug 配置中启用 'Emulate terminal in "
            "output console'；或者使用 --no-color 关闭彩色输出。[/yellow]"
        )
    while True:
        try:
            with patch_stdout(raw=True):
                raw = (await session.prompt_async("a2c> ")).strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n[cyan]Bye[/cyan]")
            break

        if raw == "":
            # 空输入直接跳过；不显示帮助 / Ignore empty input; do nothing
            continue

        if raw.lower() in {"help", "?"}:
            # 使用 Rich Table 美化帮助信息
            help_table = Table(
                title="可用命令 / Commands",
                header_style="bold magenta",
                show_lines=False,
                expand=False,
            )
            help_table.add_column("Command", style="bold cyan", no_wrap=True)
            help_table.add_column("Description", style="white")

            help_table.add_row("status", "查看服务器状态 / show server status")
            help_table.add_row("tools", "列出可用工具 / list tools")
            help_table.add_row("mcp", "显示当前 MCP 配置 / show current MCP config")
            help_table.add_row("server add <json|@file>", "添加或更新 MCP 配置 / add or update config")
            help_table.add_row("server rm <name>", "移除 MCP 配置 / remove config")
            help_table.add_row("start <name>|all", "启动客户端 / start client(s)")
            help_table.add_row("stop <name>|all", "停止客户端 / stop client(s)")
            help_table.add_row("inputs load <@file>", "从文件加载 inputs 定义 / load inputs")
            # 中文: 新增当前 inputs 值的增删改查命令
            # English: Add CRUD commands for current inputs values
            help_table.add_row("inputs value list", "列出当前 inputs 的缓存值 / list current cached input values")
            help_table.add_row("inputs value get <id>", "获取指定 id 的值 / get cached value by id")
            help_table.add_row("inputs value set <id> <json|text>", "设置指定 id 的值 / set cached value by id")
            help_table.add_row("inputs value rm <id>", "删除指定 id 的值 / remove cached value by id")
            help_table.add_row("inputs value clear [<id>]", "清空全部或指定 id 的缓存 / clear all or one cached value")
            help_table.add_row(
                "socket connect [<url>]",
                "连接 Socket.IO（省略 URL 将进入引导式输入） / connect to Socket.IO (guided if URL omitted)",
            )
            help_table.add_row("socket join <office_id> <computer_name>", "加入房间 / join office")
            help_table.add_row("socket leave", "离开房间 / leave office")
            help_table.add_row("notify update", "触发配置更新通知 / emit config updated notification")
            help_table.add_row("render <json|@file>", "测试渲染（占位符解析） / test rendering (placeholders)")
            help_table.add_row("quit | exit", "退出 / quit")

            console.print(help_table)
            console.print("[dim]提示: 输入命令后按回车执行；输入 'help' 或 '?' 重新查看命令列表。[/dim]")
            continue

        parts = raw.split()
        cmd = parts[0].lower()

        try:
            if cmd in {"quit", "exit"}:
                break

            elif cmd == "status":
                _print_status(comp)

            elif cmd == "tools":
                tools = await comp.aget_available_tools()
                _print_tools(tools)

            elif cmd == "mcp":
                # 复用 SMCP 协议的返回结构打印当前配置
                servers: dict[str, dict] = {}
                for cfg in comp.mcp_servers:
                    servers[cfg.name] = json.loads(json.dumps(cfg.model_dump(mode="json")))
                inputs = [json.loads(json.dumps(i.model_dump(mode="json"))) for i in comp.inputs]
                _print_mcp_config({"servers": servers, "inputs": inputs})

            elif cmd == "server" and len(parts) >= 2:
                sub = parts[1].lower()
                payload = raw.split(" ", 2)[2] if len(parts) >= 3 else ""
                if sub == "add":
                    # 支持 @file 载入或直接 JSON 字符串
                    if payload.startswith("@"):
                        data = json.loads(Path(payload[1:]).read_text(encoding="utf-8"))
                    else:
                        data = json.loads(payload)
                    # 校验为 SMCP 协议定义，再交由 Computer 处理（内部会渲染 inputs）
                    validated = TypeAdapter(SMCPServerConfigDict).validate_python(data)

                    # 中文: 直接复用当前 PromptSession 进行 inputs 解析，避免与 a2c> 提示符冲突
                    # English: Reuse current PromptSession for inputs resolution to avoid conflict with 'a2c>' prompt
                    try:
                        await comp.aadd_or_aupdate_server(validated, session=session)
                        console.print("[green]✅ 服务器配置已添加/更新并正在启动 / Server config added/updated and starting[/green]")
                        if smcp_client:
                            await smcp_client.emit_update_mcp_config()
                    except Exception as e:
                        console.print(f"[red]❌ 添加/更新服务器失败 / Failed to add/update server: {e}[/red]")
                elif sub in {"rm", "remove"}:
                    if len(parts) < 3:
                        console.print("[yellow]用法: server rm <name>[/yellow]")
                    else:
                        await comp.aremove_server(parts[2])
                        console.print("[green]已移除配置 / Removed[/green]")
                        if smcp_client:
                            await smcp_client.emit_update_mcp_config()
                else:
                    console.print("[yellow]未知的 server 子命令 / Unknown subcommand[/yellow]")

            elif cmd == "start" and len(parts) >= 2:
                target = parts[1]
                if not comp.mcp_manager:
                    console.print("[yellow]Manager 未初始化[/yellow]")
                else:
                    # 中文: 改为同步等待启动完成，避免测试中出现竞态条件
                    # English: Await start to complete to avoid race conditions in tests
                    try:
                        if target == "all":
                            await comp.mcp_manager.astart_all()
                            console.print("[green]✅ 所有服务器启动完成 / All servers started[/green]")
                        else:
                            await comp.mcp_manager.astart_client(target)
                            console.print(f"[green]✅ 服务器 '{target}' 启动完成 / Server '{target}' started[/green]")
                    except Exception as e:
                        console.print(f"[red]❌ 启动服务器失败 / Failed to start server: {e}[/red]")

            elif cmd == "stop" and len(parts) >= 2:
                target = parts[1]
                if not comp.mcp_manager:
                    console.print("[yellow]Manager 未初始化[/yellow]")
                else:
                    # 中文: 改为同步等待停止完成，避免测试中出现竞态条件
                    # English: Await stop to complete to avoid race conditions in tests
                    try:
                        if target == "all":
                            await comp.mcp_manager.astop_all()
                            console.print("[green]✅ 所有服务器停止完成 / All servers stopped[/green]")
                        else:
                            await comp.mcp_manager.astop_client(target)
                            console.print(f"[green]✅ 服务器 '{target}' 停止完成 / Server '{target}' stopped[/green]")
                    except Exception as e:
                        console.print(f"[red]❌ 停止服务器失败 / Failed to stop server: {e}[/red]")

            elif cmd == "inputs" and len(parts) >= 2:
                sub = parts[1].lower()
                if sub == "load":
                    if len(parts) < 3 or not parts[2].startswith("@"):
                        console.print("[yellow]用法: inputs load @file.json[/yellow]")
                    else:
                        data = json.loads(Path(parts[2][1:]).read_text(encoding="utf-8"))
                        raw_items = TypeAdapter(list[SMCPServerInputDict]).validate_python(data)
                        models = {TypeAdapter(MCPServerInputModel).validate_python(item) for item in raw_items}
                        comp.update_inputs(models)
                        console.print("[green]Inputs 已更新 / Inputs updated[/green]")
                        if smcp_client:
                            await smcp_client.emit_update_mcp_config()
                elif sub == "add":
                    # 支持 @file 或 单对象 JSON
                    if len(parts) < 3:
                        console.print("[yellow]用法: inputs add <json|@file.json>[/yellow]")
                    else:
                        payload = raw.split(" ", 2)[2]
                        if payload.startswith("@"):  # 文件里可为单个或数组
                            data = json.loads(Path(payload[1:]).read_text(encoding="utf-8"))
                        else:
                            data = json.loads(payload)
                        if isinstance(data, list):
                            items = TypeAdapter(list[SMCPServerInputDict]).validate_python(data)
                            for item in items:
                                comp.add_or_update_input(TypeAdapter(MCPServerInputModel).validate_python(item))
                        else:
                            item = TypeAdapter(SMCPServerInputDict).validate_python(data)
                            comp.add_or_update_input(TypeAdapter(MCPServerInputModel).validate_python(item))
                        console.print("[green]Input(s) 已添加/更新 / Added/Updated[/green]")
                        if smcp_client:
                            await smcp_client.emit_update_mcp_config()
                elif sub in {"update"}:
                    # 语义与 add 相同，提供同义词
                    if len(parts) < 3:
                        console.print("[yellow]用法: inputs update <json|@file.json>[/yellow]")
                    else:
                        payload = raw.split(" ", 2)[2]
                        if payload.startswith("@"):  # 文件里可为单个或数组
                            data = json.loads(Path(payload[1:]).read_text(encoding="utf-8"))
                        else:
                            data = json.loads(payload)
                        if isinstance(data, list):
                            items = TypeAdapter(list[SMCPServerInputDict]).validate_python(data)
                            for item in items:
                                comp.add_or_update_input(TypeAdapter(SMCPServerInputDict).validate_python(item))
                        else:
                            item = TypeAdapter(SMCPServerInputDict).validate_python(data)
                            comp.add_or_update_input(item)
                        console.print("[green]Input(s) 已添加/更新 / Added/Updated[/green]")
                        if smcp_client:
                            await smcp_client.emit_update_mcp_config()
                elif sub in {"rm", "remove"}:
                    if len(parts) < 3:
                        console.print("[yellow]用法: inputs rm <id>[/yellow]")
                    else:
                        ok = comp.remove_input(parts[2])
                        if ok:
                            console.print("[green]已移除 / Removed[/green]")
                            if smcp_client:
                                await smcp_client.emit_update_mcp_config()
                        else:
                            console.print("[yellow]不存在的 id / Not found[/yellow]")
                elif sub == "get":
                    if len(parts) < 3:
                        console.print("[yellow]用法: inputs get <id>[/yellow]")
                    else:
                        item = comp.get_input(parts[2])
                        if item is None:
                            console.print("[yellow]不存在的 id / Not found[/yellow]")
                        else:
                            console.print_json(data=item.model_dump(mode="json"))
                elif sub == "list":
                    items = [i.model_dump(mode="json") for i in comp.inputs]
                    console.print_json(data=items)
                elif sub == "value":
                    # 中文: 管理当前 inputs 值（缓存）
                    # English: Manage current inputs values (cache)
                    if len(parts) < 3:
                        console.print("[yellow]用法: inputs value <list|get|set|rm|clear> ...[/yellow]")
                    else:
                        vsub = parts[2].lower()
                        if vsub == "list":
                            values = comp.list_input_values()
                            # 无则为空对象 / empty when none
                            console.print_json(data=values or {})
                        elif vsub == "get":
                            if len(parts) < 4:
                                console.print("[yellow]用法: inputs value get <id>[/yellow]")
                            else:
                                val = comp.get_input_value(parts[3])
                                if val is None:
                                    console.print("[yellow]未找到或尚未解析 / Not found or not resolved yet[/yellow]")
                                else:
                                    # 尝试作为 JSON 打印，不可序列化时回退为字符串
                                    try:
                                        console.print_json(data=val)
                                    except Exception:
                                        console.print(repr(val))
                        elif vsub == "set":
                            if len(parts) < 5:
                                console.print("[yellow]用法: inputs value set <id> <json|text>[/yellow]")
                            else:
                                target_id = parts[3]
                                payload = raw.split(" ", 4)[4]
                                # 允许 JSON 或普通文本
                                try:
                                    data = json.loads(payload)
                                except Exception:
                                    data = payload
                                ok = comp.set_input_value(target_id, data)
                                if ok:
                                    console.print("[green]已设置 / Set[/green]")
                                else:
                                    console.print("[yellow]不存在的 id / Not found[/yellow]")
                        elif vsub in {"rm", "remove"}:
                            if len(parts) < 4:
                                console.print("[yellow]用法: inputs value rm <id>[/yellow]")
                            else:
                                ok = comp.remove_input_value(parts[3])
                                console.print("[green]已删除 / Removed[/green]" if ok else "[yellow]无此缓存 / No such cache[/yellow]")
                        elif vsub == "clear":
                            # 可选 id，省略则清空全部
                            target_id = parts[3] if len(parts) >= 4 else None
                            comp.clear_input_values(target_id)
                            console.print("[green]缓存已清理 / Cache cleared[/green]")
                        else:
                            console.print("[yellow]未知的 inputs value 子命令 / Unknown subcommand[/yellow]")
                else:
                    console.print("[yellow]未知的 inputs 子命令 / Unknown subcommand[/yellow]")

            elif cmd == "socket" and len(parts) >= 2:
                sub = parts[1].lower()
                if sub == "connect":
                    if smcp_client and smcp_client.connected:
                        console.print("[yellow]已连接 / Already connected[/yellow]")
                    else:
                        # 若提供了 URL，直接使用；否则进入引导式输入
                        url: str | None = parts[2] if len(parts) >= 3 else None
                        if not url:
                            with patch_stdout(raw=True):
                                url = (await session.prompt_async("URL: ")).strip()
                        if not url:
                            console.print("[yellow]URL 不能为空 / URL required[/yellow]")
                            continue

                        if len(parts) < 3:
                            with patch_stdout(raw=True):
                                auth_str = (await session.prompt_async("Auth (key:value, 可留空): ")).strip()
                            with patch_stdout(raw=True):
                                headers_str = (await session.prompt_async("Headers (key:value, 可留空): ")).strip()
                        else:
                            auth_str = ""
                            headers_str = ""

                        try:
                            auth = _parse_kv_pairs(auth_str)
                            headers = _parse_kv_pairs(headers_str)
                        except Exception as e:
                            console.print(f"[red]参数解析失败 / Parse error: {e}[/red]")
                            continue

                        smcp_client = SMCPComputerClient(computer=comp)
                        await smcp_client.connect(url, auth=auth, headers=headers)
                        console.print("[green]已连接 / Connected[/green]")
                elif sub == "join":
                    if not smcp_client or not smcp_client.connected:
                        console.print("[yellow]请先连接 / Connect first[/yellow]")
                    elif len(parts) < 4:
                        console.print("[yellow]用法: socket join <office_id> <computer_name>[/yellow]")
                    else:
                        await smcp_client.join_office(parts[2], parts[3])
                        console.print("[green]已加入房间 / Joined office[/green]")
                elif sub == "leave":
                    if not smcp_client or not smcp_client.connected:
                        console.print("[yellow]未连接 / Not connected[/yellow]")
                    elif not smcp_client.office_id:
                        console.print("[yellow]未加入房间 / Not in any office[/yellow]")
                    else:
                        await smcp_client.leave_office(smcp_client.office_id)
                        console.print("[green]已离开房间 / Left office[/green]")
                else:
                    console.print("[yellow]未知的 socket 子命令 / Unknown subcommand[/yellow]")

            elif cmd == "notify" and len(parts) >= 2:
                sub = parts[1].lower()
                if sub == "update":
                    if not smcp_client:
                        console.print("[yellow]未连接 Socket.IO，已跳过 / Not connected, skip[/yellow]")
                    else:
                        await smcp_client.emit_update_mcp_config()
                        console.print("[green]已触发配置更新通知 / Update notification emitted[/green]")
                else:
                    console.print("[yellow]未知的 notify 子命令 / Unknown subcommand[/yellow]")

            elif cmd == "render":
                payload = raw.split(" ", 1)[1] if len(parts) >= 2 else ""
                if payload.startswith("@"):
                    data = json.loads(Path(payload[1:]).read_text(encoding="utf-8"))
                else:
                    data = json.loads(payload)
                # 使用 Computer 内的渲染器与解析器
                rendered = await comp._config_render.arender(
                    data,
                    lambda x: comp._input_resolver.aresolve_by_id(x, session=session),
                )
                console.print_json(data=rendered)

            else:
                console.print("[yellow]未知命令 / Unknown command[/yellow]")
        except Exception as e:  # pragma: no cover
            console.print(f"[red]执行失败 / Failed: {e}[/red]")


def _run_impl(
    *,
    auto_connect: bool,
    auto_reconnect: bool,
    url: str | None,
    auth: str | None,
    headers: str | None,
    config: str | None,
    inputs: str | None,
) -> None:
    """
    纯实现函数：不要在此处使用 Typer 的 Option 默认值，避免 OptionInfo 泄露到运行时。
    Both CLI (@app.command) 与回调 (@app.callback) 在需要时调用本函数。
    """

    async def _amain() -> None:
        # 初始化空配置，后续通过交互动态维护 / init with empty config, then manage dynamically
        comp = Computer(inputs=set(), mcp_servers=set(), auto_connect=auto_connect, auto_reconnect=auto_reconnect)
        async with comp:
            init_client: SMCPComputerClient | None = None
            if url:
                try:
                    auth_dict = _parse_kv_pairs(auth)
                    headers_dict = _parse_kv_pairs(headers)
                except Exception as e:
                    console.print(f"[red]启动参数解析失败 / Failed to parse CLI params: {e}[/red]")
                    auth_dict = None
                    headers_dict = None
                init_client = SMCPComputerClient(computer=comp)
                await init_client.connect(url, auth=auth_dict, headers=headers_dict)
                console.print("[green]已通过启动参数连接到 Socket.IO / Connected via CLI options[/green]")

            # 启动参数加载 inputs 与 servers 配置
            # Load inputs first (so that servers config rendering can use them if needed later via interactive commands)
            if inputs:
                try:
                    ipath = inputs[1:] if inputs.startswith("@") else inputs
                    data = json.loads(Path(ipath).read_text(encoding="utf-8"))
                    # 允许单个对象或数组
                    if isinstance(data, list):
                        raw_items = TypeAdapter(list[SMCPServerInputDict]).validate_python(data)
                        models = {TypeAdapter(MCPServerInputModel).validate_python(item) for item in raw_items}
                        comp.update_inputs(models)
                    else:
                        item = TypeAdapter(SMCPServerInputDict).validate_python(data)
                        comp.add_or_update_input(TypeAdapter(MCPServerInputModel).validate_python(item))
                    console.print("[green]已加载 Inputs 配置 / Inputs loaded[/green]")
                except Exception as e:  # pragma: no cover
                    console.print(f"[red]加载 Inputs 失败 / Failed to load inputs: {e}[/red]")

            if config:
                try:
                    spath = config[1:] if config.startswith("@") else config
                    data = json.loads(Path(spath).read_text(encoding="utf-8"))
                    # 允许单个对象或数组

                    async def _add_server(cfg_obj: dict[str, Any]) -> None:
                        validated = TypeAdapter(SMCPServerConfigDict).validate_python(cfg_obj)
                        await comp.aadd_or_aupdate_server(validated)

                    if isinstance(data, list):
                        for cfg in data:
                            await _add_server(cfg)
                    else:
                        await _add_server(data)
                    console.print("[green]已加载 Servers 配置 / Servers loaded[/green]")
                except Exception as e:  # pragma: no cover
                    console.print(f"[red]加载 Servers 失败 / Failed to load servers: {e}[/red]")

            await _interactive_loop(comp, init_client=init_client)

    asyncio.run(_amain())


@app.command()
def run(
    auto_connect: bool = typer.Option(True, help="是否自动连接 / Auto connect"),
    auto_reconnect: bool = typer.Option(True, help="是否自动重连 / Auto reconnect"),
    url: str | None = typer.Option(None, help="Socket.IO 服务器URL，例如 https://host:port"),
    auth: str | None = typer.Option(None, help="认证参数，形如 key:value,foo:bar"),
    headers: str | None = typer.Option(None, help="请求头参数，形如 key:value,foo:bar"),
    config: str | None = typer.Option(
        None,
        "--config",
        "-c",
        help="在启动时从文件加载 MCP Servers 配置（支持 @file 语法或直接文件路径） / Load MCP Servers from file at startup",
    ),
    inputs: str | None = typer.Option(
        None,
        "--inputs",
        "-i",
        help="在启动时从文件加载 Inputs 定义（支持 @file 语法或直接文件路径） / Load Inputs from file at startup",
    ),
) -> None:
    """
    中文: 启动计算机并进入持续运行模式。后续将支持从配置文件加载 servers 与 inputs。
    English: Boot the computer and enter persistent loop. Config-file loading will be added later.
    """
    _run_impl(
        auto_connect=auto_connect,
        auto_reconnect=auto_reconnect,
        url=url,
        auth=auth,
        headers=headers,
        config=config,
        inputs=inputs,
    )


# 为 console_scripts 兼容提供入口
def main() -> None:  # pragma: no cover
    # 使用 Typer 应用入口，而不是直接调用命令函数
    # 直接调用被 @app.command 装饰的函数会传入 OptionInfo 默认值，导致参数类型错误
    app()
