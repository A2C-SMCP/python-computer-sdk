"""
文件名: utils.py
作者: JQQ
创建日期: 2025/9/25
最后修改日期: 2025/9/25
版权: 2023 JQQ. All rights reserved.
依赖: rich
描述:
  中文: CLI 层通用工具：键值解析与表格打印，统一 Console 管理。
  English: Common CLI utilities: key-value parsing and table printers with unified Console management.
"""

from __future__ import annotations

import json
from typing import Any

from rich.table import Table

from a2c_smcp_cc.computer import Computer
from a2c_smcp_cc.utils import console as console_util

# 使用全局 Console（引用模块属性，便于后续动态切换）
# Use a global Console (module attribute reference for dynamic switching)
console = console_util.console


def parse_kv_pairs(text: str | None) -> dict[str, Any] | None:
    """
    中文: 将形如 "k1:v1,k2:v2" 的字符串解析为 dict；容错处理空格。
    English: Parse a string like "k1:v1,k2:v2" into a dict; tolerant to spaces.

    Args:
        text: 原始输入字符串；None 或空字符串时返回 None。

    Returns:
        dict 或 None / dict or None
    """
    if text is None:
        return None
    s = text.strip()
    if s == "":
        return None
    # 优先尝试 JSON 反序列化：支持直接传入合法的 JSON 对象字符串
    # Try JSON deserialization first: support passing a valid JSON object string directly
    try:
        parsed = json.loads(s)
    except Exception:
        pass
    else:
        if isinstance(parsed, dict):
            return parsed
        # 合法 JSON 但不是对象（如数组/字符串/数字），给出明确错误
        raise ValueError('JSON 字符串必须是对象类型（例如 {"k":"v"}）')
    result: dict[str, Any] = {}
    for seg in s.split(","):
        seg = seg.strip()
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


def print_status(comp: Computer) -> None:
    """
    中文: 打印服务器状态表。
    English: Print servers status table.
    """
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


def print_tools(tools: list[dict[str, Any]]) -> None:
    """
    中文: 打印工具列表。
    English: Print tools list.
    """
    table = Table(title="工具列表 / Tools")
    table.add_column("Name")
    table.add_column("Description")
    table.add_column("Has Return")
    for t in tools:
        table.add_row(t.get("name", ""), (t.get("description") or "")[:80], "Yes" if t.get("return_schema") else "No")
    console.print(table)


def print_mcp_config(config: dict[str, Any]) -> None:
    """
    中文: 打印当前 MCP 配置（servers 与 inputs）。
    English: Print current MCP config (servers and inputs).
    """
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
