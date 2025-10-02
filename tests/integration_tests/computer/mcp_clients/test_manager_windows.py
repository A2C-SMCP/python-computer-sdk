# -*- coding: utf-8 -*-
# filename: test_manager_windows.py
# @Time    : 2025/10/02 19:02
# @Author  : JQQ
# @Email   : jqq1716@gmail.com
# @Software: PyCharm
"""
中文: 集成测试 MCPServerManager.list_windows，使用 resources_stdio_server 与 resources_subscribe_stdio_server。
英文: Integration tests for MCPServerManager.list_windows using resources_stdio_server and resources_subscribe_stdio_server.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from mcp import StdioServerParameters

from a2c_smcp.computer.mcp_clients.manager import MCPServerManager
from a2c_smcp.computer.mcp_clients.model import StdioServerConfig


@pytest.mark.anyio
async def test_manager_list_windows_aggregates_only_subscribe_server() -> None:
    """
    中文: Manager 应仅聚合开启 resources.subscribe 的服务的窗口；非订阅服务应返回空。
    英文: Manager should aggregate windows only from servers with resources.subscribe enabled; non-subscribe returns empty.
    """
    base = Path(__file__).resolve().parents[2] / "computer" / "mcp_servers"
    sub_py = base / "resources_subscribe_stdio_server.py"
    nosub_py = base / "resources_stdio_server.py"
    assert sub_py.exists() and nosub_py.exists()

    sub_params = StdioServerParameters(command=sys.executable, args=[str(sub_py)])
    nosub_params = StdioServerParameters(command=sys.executable, args=[str(nosub_py)])

    manager = MCPServerManager(auto_connect=False)
    sub_cfg = StdioServerConfig(name="srv_sub", server_parameters=sub_params)
    nosub_cfg = StdioServerConfig(name="srv_nosub", server_parameters=nosub_params)

    await manager.ainitialize([sub_cfg, nosub_cfg])
    await manager.astart_all()

    try:
        results = await manager.list_windows()
        # 只应来自订阅服务 / Only from subscribe server
        assert all(srv == "srv_sub" for srv, _ in results)
        assert len(results) >= 1

        # 验证排序（dashboard priority=90 在 main priority=60 之前）
        uris = [str(res.uri) for _, res in results]
        assert any("/dashboard" in u for u in uris)
        assert any("/main" in u for u in uris)
        if len(uris) >= 2:
            assert "/dashboard" in uris[0]
            assert "/main" in uris[1]
    finally:
        await manager.astop_all()


@pytest.mark.anyio
async def test_manager_list_windows_filter_by_uri() -> None:
    """
    中文: Manager.list_windows(window_uri=...) 仅返回 URI 完全匹配的窗口与其 server 名称。
    英文: Manager.list_windows(window_uri=...) returns only the exact matched window with its server name.
    """
    base = Path(__file__).resolve().parents[2] / "computer" / "mcp_servers"
    sub_py = base / "resources_subscribe_stdio_server.py"
    assert sub_py.exists()

    sub_params = StdioServerParameters(command=sys.executable, args=[str(sub_py)])

    manager = MCPServerManager(auto_connect=False)
    sub_cfg = StdioServerConfig(name="srv_sub", server_parameters=sub_params)

    await manager.ainitialize([sub_cfg])
    await manager.astart_all()

    try:
        # 先获取全部，找到一个 URI
        results_all = await manager.list_windows()
        assert results_all, "should have at least one window from subscribe server"
        target_uri = str(results_all[0][1].uri)

        # 过滤后仅返回匹配项且 server 名称为 srv_sub
        results_filtered = await manager.list_windows(window_uri=target_uri)
        assert len(results_filtered) == 1
        srv_name, res = results_filtered[0]
        assert srv_name == "srv_sub"
        assert str(res.uri) == target_uri
    finally:
        await manager.astop_all()
