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

import typer
from prompt_toolkit import PromptSession
from prompt_toolkit.patch_stdout import patch_stdout
from rich.console import Console
from rich.table import Table

from a2c_smcp_cc.computer import Computer

app = typer.Typer(add_completion=False, help="A2C Computer CLI")
console = Console()


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


async def _interactive_loop(comp: Computer) -> None:
    session = PromptSession()
    console.print("[bold]进入交互模式，输入 help 查看命令 / Enter interactive mode, type 'help' for commands[/bold]")
    with patch_stdout():
        while True:
            try:
                cmd = (await session.prompt_async("a2c> ")).strip()
            except (EOFError, KeyboardInterrupt):
                console.print("\n[cyan]Bye[/cyan]")
                break

            if cmd == "" or cmd.lower() in {"help", "?"}:
                console.print("可用命令 / Commands: status, quit/exit")
                continue
            if cmd.lower() in {"quit", "exit"}:
                break
            if cmd.lower().startswith("status"):
                _print_status(comp)
                continue
            console.print("[yellow]未知命令 / Unknown command[/yellow]")


@app.command()
def run(
    auto_connect: bool = typer.Option(True, help="是否自动连接 / Auto connect"),
    auto_reconnect: bool = typer.Option(True, help="是否自动重连 / Auto reconnect"),
) -> None:
    """
    中文: 启动计算机并进入持续运行模式。后续将支持从配置文件加载 servers 与 inputs。
    English: Boot the computer and enter persistent loop. Config-file loading will be added later.
    """

    async def _amain() -> None:
        # 目前未接入外部配置，先使用空配置以演示交互与生命周期
        comp = Computer(inputs=[], mcp_servers=set(), auto_connect=auto_connect, auto_reconnect=auto_reconnect)
        async with comp:
            await _interactive_loop(comp)

    asyncio.run(_amain())


# 为 console_scripts 兼容提供入口
def main() -> None:  # pragma: no cover
    run()
