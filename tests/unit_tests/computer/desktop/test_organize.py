# -*- coding: utf-8 -*-
# filename: test_organize.py
# @Time    : 2025/10/02 16:27
# @Author  : JQQ
# @Email   : jqq1716@gmail.com
# @Software: PyCharm
"""
组织策略单元测试
Unit tests for desktop organizing policy

仅测试 organize_desktop 的行为，不依赖 Computer。
Only verify organize_desktop behavior, decoupled from Computer.
"""

from types import SimpleNamespace

import pytest

from a2c_smcp.computer.desktop.organize import organize_desktop


@pytest.mark.asyncio
async def test_priority_within_server_and_size_cap():
    """
    - 同一服务器内按 priority 降序
    - 全局 size 截断
    """
    windows = [
        ("srv", SimpleNamespace(uri="window://srv/w1?priority=10")),
        ("srv", SimpleNamespace(uri="window://srv/w2?priority=90")),
        ("srv", SimpleNamespace(uri="window://srv/w3")),  # 默认0
    ]
    ret = await organize_desktop(windows=windows, size=2, history=tuple())
    assert ret == ["window://srv/w2?priority=90", "window://srv/w1?priority=10"]


@pytest.mark.asyncio
async def test_fullscreen_one_per_server_then_next_server():
    """
    - 若遇到 fullscreen=True 的窗口，则该 MCP 仅推入这一个；然后进入下一个 MCP
    """
    windows = [
        ("A", SimpleNamespace(uri="window://A/a1?priority=50")),
        ("A", SimpleNamespace(uri="window://A/a2?fullscreen=true&priority=10")),
        ("A", SimpleNamespace(uri="window://A/a3?priority=90")),
        ("B", SimpleNamespace(uri="window://B/b1?priority=5")),
    ]
    # history 让 A 在前
    history = ({"server": "A"},)
    ret = await organize_desktop(windows=windows, size=None, history=history)
    # A 只应输出 fullscreen 的 a2，然后进入 B
    assert ret[0] == "window://A/a2?fullscreen=true&priority=10"
    assert "window://B/b1?priority=5" in ret  # B 的内容随后加入


@pytest.mark.asyncio
async def test_server_order_by_recent_history():
    """
    - 服务器顺序按最近历史倒序优先
    """
    windows = [
        ("A", SimpleNamespace(uri="window://A/a1?priority=1")),
        ("B", SimpleNamespace(uri="window://B/b1?priority=1")),
        ("C", SimpleNamespace(uri="window://C/c1?priority=1")),
    ]
    # 最近使用顺序：C -> A（B 未使用）
    history = (
        {"server": "A"},
        {"server": "C"},
    )
    ret = await organize_desktop(windows=windows, size=None, history=history)
    # C 在 A 前，剩余 B 按名称排序追加（B）
    assert ret[:2] == ["window://C/c1?priority=1", "window://A/a1?priority=1"]
    assert ret[2] == "window://B/b1?priority=1"


@pytest.mark.asyncio
async def test_size_zero_returns_empty():
    ret = await organize_desktop(windows=[], size=0, history=tuple())
    assert ret == []
