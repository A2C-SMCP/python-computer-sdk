# -*- coding: utf-8 -*-
# filename: test_computer_desktop.py
# @Time    : 2025/10/02 16:22
# @Author  : JQQ
# @Email   : jqq1716@gmail.com
# @Software: PyCharm
"""
Computer.get_desktop 单元测试
Unit tests for Computer.get_desktop

说明 / Notes:
- 为了隔离不稳定的 organize 实现，本测试通过 monkeypatch 将
  `a2c_smcp.computer.computer.organize_desktop` 打桩，避免验证其内部策略；
- Since organize implementation is not stable yet, we patch
  `a2c_smcp.computer.computer.organize_desktop` to isolate get_desktop behavior.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from a2c_smcp.computer.computer import Computer
from a2c_smcp.computer.mcp_clients.manager import MCPServerManager


@pytest.mark.asyncio
async def test_get_desktop_calls_manager_and_organize(monkeypatch):
    """
    中文: 确认 get_desktop 会调用 manager.list_windows，并将结果与 size、history 传入 organize_desktop。
    English: Ensure get_desktop invokes manager.list_windows and forwards windows/size/history to organize_desktop.
    """
    # 准备 mock manager / Prepare mock manager
    mock_manager = MagicMock(spec=MCPServerManager)
    # manager.list_windows 返回两条 window 记录（使用 SimpleNamespace 模拟 Resource）
    res1 = SimpleNamespace(uri="window://mcp-a/w1")
    res2 = SimpleNamespace(uri="window://mcp-b/w2")
    mock_windows = [("mcp-a", res1), ("mcp-b", res2)]
    mock_manager.list_windows = AsyncMock(return_value=mock_windows)

    # 将构造函数替换为返回 mock_manager / Patch constructor to return mock manager
    monkeypatch.setattr("a2c_smcp.computer.computer.MCPServerManager", lambda *a, **kw: mock_manager)

    # 打桩 organize_desktop / Stub organize_desktop
    organized = ["window://mcp-a/w1", "window://mcp-b/w2"]
    mock_organize = AsyncMock(return_value=organized)
    monkeypatch.setattr("a2c_smcp.computer.computer.organize_desktop", mock_organize)

    # 实例化并启动 / Instantiate and boot
    computer = Computer()
    await computer.boot_up()

    # 调用 get_desktop / Call get_desktop
    size = 5
    uri = "window://mcp-a/w1"
    result = await computer.get_desktop(size=size, window_uri=uri)

    # 断言调用链 / Assertions
    mock_manager.list_windows.assert_awaited_once_with(uri)
    # history 通过实例方法读取，这里仅验证 organize 接口参数完整性
    call = mock_organize.await_args
    assert call.kwargs["windows"] == mock_windows
    assert call.kwargs["size"] == size
    assert isinstance(call.kwargs["history"], tuple)

    # 返回值为 organize 的产出 / Return value equals organize output
    assert result == organized


@pytest.mark.asyncio
async def test_get_desktop_when_manager_none_returns_empty():
    """
    中文: 当 mcp_manager 尚未初始化时，get_desktop 返回空列表。
    English: Return empty list when mcp_manager is not initialized.
    """
    computer = Computer()
    # 不调用 boot_up，保持 mcp_manager 为 None
    desktops = await computer.get_desktop()
    assert desktops == []
