"""
文件名: main.py
作者: JQQ
创建日期: 2025/9/18
最后修改日期: 2025/9/18
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
from rich.console import Console
from rich.table import Table

from a2c_smcp_cc.computer import Computer
from a2c_smcp_cc.socketio.client import SMCPComputerClient
from a2c_smcp_cc.socketio.smcp import MCPServerConfig as SMCPServerConfigDict
from a2c_smcp_cc.socketio.smcp import MCPServerInput as SMCPServerInputDict

app = typer.Typer(add_completion=False, help="A2C Computer CLI")
console = Console()


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


async def _interactive_loop(comp: Computer, init_client: SMCPComputerClient | None = None) -> None:
    session = PromptSession()
    smcp_client: SMCPComputerClient | None = init_client
    console.print("[bold]进入交互模式，输入 help 查看命令 / Enter interactive mode, type 'help' for commands[/bold]")
    with patch_stdout():
        while True:
            try:
                raw = (await session.prompt_async("a2c> ")).strip()
            except (EOFError, KeyboardInterrupt):
                console.print("\n[cyan]Bye[/cyan]")
                break

            if raw == "" or raw.lower() in {"help", "?"}:
                console.print(
                    "\n".join(
                        [
                            "可用命令 / Commands:",
                            "  status                                   # 查看服务器状态 / show server status",
                            "  tools                                    # 列出可用工具 / list tools",
                            "  mcp                                       # 显示当前MCP配置 / show current MCP config",
                            "  server add <json|@file>                  # 添加或更新MCP配置 / add or update config",
                            "  server rm <name>                          # 移除MCP配置 / remove config",
                            "  start <name>|all                          # 启动客户端 / start client(s)",
                            "  stop <name>|all                           # 停止客户端 / stop client(s)",
                            "  inputs load <@file>                        # 从文件加载inputs定义 / load inputs",
                            "  socket connect [<url>]                    # 连接Socket.IO（若省略URL将进入引导式输入）",
                            "  socket join <office_id> <computer_name>   # 加入房间",
                            "  socket leave                               # 离开房间",
                            "  notify update                              # 触发配置更新通知",
                            "  render <json|@file>                        # 测试渲染（占位符解析）",
                            "  quit|exit                                  # 退出",
                        ]
                    )
                )
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
                        await comp.aadd_or_aupdate_server(validated)
                        console.print("[green]已添加/更新服务器配置 / Added/Updated server config[/green]")
                        if smcp_client:
                            await smcp_client.emit_update_mcp_config()
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
                        if target == "all":
                            await comp.mcp_manager.astart_all()
                        else:
                            await comp.mcp_manager.astart_client(target)
                        console.print("[green]启动完成 / Started[/green]")

                elif cmd == "stop" and len(parts) >= 2:
                    target = parts[1]
                    if not comp.mcp_manager:
                        console.print("[yellow]Manager 未初始化[/yellow]")
                    else:
                        if target == "all":
                            await comp.mcp_manager.astop_all()
                        else:
                            await comp.mcp_manager.astop_client(target)
                        console.print("[green]停止完成 / Stopped[/green]")

                elif cmd == "inputs" and len(parts) >= 2:
                    sub = parts[1].lower()
                    if sub == "load":
                        if len(parts) < 3 or not parts[2].startswith("@"):
                            console.print("[yellow]用法: inputs load @file.json[/yellow]")
                        else:
                            data = json.loads(Path(parts[2][1:]).read_text(encoding="utf-8"))
                            inputs = TypeAdapter(list[SMCPServerInputDict]).validate_python(data)
                            comp.update_inputs(inputs)
                            console.print("[green]Inputs 已更新 / Inputs updated[/green]")
                            if smcp_client:
                                await smcp_client.emit_update_mcp_config()
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
                                url = (await session.prompt_async("URL: ")).strip()
                            if not url:
                                console.print("[yellow]URL 不能为空 / URL required[/yellow]")
                                continue

                            auth_str = (await session.prompt_async("Auth (key:value, 可留空): ")).strip() if len(parts) < 3 else ""
                            headers_str = (await session.prompt_async("Headers (key:value, 可留空): ")).strip() if len(parts) < 3 else ""

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
                    rendered = await comp._config_render.arender(data, lambda x: comp._input_resolver.aresolve_by_id(x))
                    console.print_json(data=rendered)

                else:
                    console.print("[yellow]未知命令 / Unknown command[/yellow]")
            except Exception as e:  # pragma: no cover
                console.print(f"[red]执行失败 / Failed: {e}[/red]")


@app.command()
def run(
    auto_connect: bool = typer.Option(True, help="是否自动连接 / Auto connect"),
    auto_reconnect: bool = typer.Option(True, help="是否自动重连 / Auto reconnect"),
    url: str | None = typer.Option(None, help="Socket.IO 服务器URL，例如 https://host:port"),
    auth: str | None = typer.Option(None, help="认证参数，形如 key:value,foo:bar"),
    headers: str | None = typer.Option(None, help="请求头参数，形如 key:value,foo:bar"),
) -> None:
    """
    中文: 启动计算机并进入持续运行模式。后续将支持从配置文件加载 servers 与 inputs。
    English: Boot the computer and enter persistent loop. Config-file loading will be added later.
    """

    async def _amain() -> None:
        # 初始化空配置，后续通过交互动态维护 / init with empty config, then manage dynamically
        comp = Computer(inputs=[], mcp_servers=set(), auto_connect=auto_connect, auto_reconnect=auto_reconnect)
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

            await _interactive_loop(comp, init_client=init_client)

    asyncio.run(_amain())


# 为 console_scripts 兼容提供入口
def main() -> None:  # pragma: no cover
    run()
