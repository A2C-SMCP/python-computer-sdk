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
from mcp.types import ReadResourceResult, TextResourceContents

from a2c_smcp.computer.desktop.organize import organize_desktop


@pytest.mark.asyncio
async def test_priority_within_server_and_size_cap():
    """
    - 同一服务器内按 priority 降序
    - 全局 size 截断
    """
    # 资源详情：每个窗口都有一段不同的文本，便于断言渲染
    d1 = ReadResourceResult(contents=[TextResourceContents(text="w1-text", uri="window://srv/w1?priority=10")])
    d2 = ReadResourceResult(contents=[TextResourceContents(text="w2-text", uri="window://srv/w2?priority=90")])
    d3 = ReadResourceResult(contents=[TextResourceContents(text="w3-text", uri="window://srv/w3")])

    windows = [
        ("srv", SimpleNamespace(uri="window://srv/w1?priority=10"), d1),
        ("srv", SimpleNamespace(uri="window://srv/w2?priority=90"), d2),
        ("srv", SimpleNamespace(uri="window://srv/w3"), d3),  # 默认0
    ]
    ret = await organize_desktop(windows=windows, size=2, history=tuple())
    # 应优先 w2，再 w1；且渲染包含文本内容
    assert ret[0].startswith("window://srv/w2?priority=90") and "w2-text" in ret[0]
    assert ret[1].startswith("window://srv/w1?priority=10") and "w1-text" in ret[1]


@pytest.mark.asyncio
async def test_fullscreen_one_per_server_then_next_server():
    """
    - 若遇到 fullscreen=True 的窗口，则该 MCP 仅推入这一个；然后进入下一个 MCP
    """
    d_a1 = ReadResourceResult(contents=[TextResourceContents(uri="window://A/a1?priority=50", text="a1")])
    d_a2 = ReadResourceResult(contents=[TextResourceContents(uri="window://A/a2?fullscreen=true&priority=10", text="a2-full")])
    d_a3 = ReadResourceResult(contents=[TextResourceContents(uri="window://A/a3?priority=90", text="a3")])
    d_b1 = ReadResourceResult(contents=[TextResourceContents(uri="window://B/b1?priority=5", text="b1")])
    windows = [
        ("A", SimpleNamespace(uri="window://A/a1?priority=50"), d_a1),
        ("A", SimpleNamespace(uri="window://A/a2?fullscreen=true&priority=10"), d_a2),
        ("A", SimpleNamespace(uri="window://A/a3?priority=90"), d_a3),
        ("B", SimpleNamespace(uri="window://B/b1?priority=5"), d_b1),
    ]
    # history 让 A 在前
    history = ({"server": "A"},)
    ret = await organize_desktop(windows=windows, size=None, history=history)
    # A 只应输出 fullscreen 的 a2，然后进入 B
    assert ret[0].startswith("window://A/a2?fullscreen=true&priority=10") and "a2-full" in ret[0]
    assert any(x.startswith("window://B/b1?priority=5") and "b1" in x for x in ret)  # B 的内容随后加入


@pytest.mark.asyncio
async def test_server_order_by_recent_history():
    """
    - 服务器顺序按最近历史倒序优先
    """
    d_a = ReadResourceResult(contents=[TextResourceContents(uri="window://A/a1?priority=1", text="a")])
    d_b = ReadResourceResult(contents=[TextResourceContents(uri="window://B/b1?priority=1", text="b")])
    d_c = ReadResourceResult(contents=[TextResourceContents(uri="window://C/c1?priority=1", text="c")])
    windows = [
        ("A", SimpleNamespace(uri="window://A/a1?priority=1"), d_a),
        ("B", SimpleNamespace(uri="window://B/b1?priority=1"), d_b),
        ("C", SimpleNamespace(uri="window://C/c1?priority=1"), d_c),
    ]
    # 最近使用顺序：C -> A（B 未使用）
    history = (
        {"server": "A"},
        {"server": "C"},
    )
    ret = await organize_desktop(windows=windows, size=None, history=history)
    # C 在 A 前，剩余 B 按名称排序追加（B）
    assert ret[0].startswith("window://C/c1?priority=1") and "c" in ret[0]
    assert ret[1].startswith("window://A/a1?priority=1") and "a" in ret[1]
    assert ret[2].startswith("window://B/b1?priority=1") and "b" in ret[2]


@pytest.mark.asyncio
async def test_size_zero_returns_empty():
    ret = await organize_desktop(windows=[], size=0, history=tuple())
    assert ret == []
