# -*- coding: utf-8 -*-
# filename: test_computer.py
# @Time    : 2025/8/26
# @Author  : JQQ
# @Email   : jiaqia@qknode.com
# @Software: PyCharm
"""
集成测试：Computer.aexecute_tool 工具调用
Integration test: Computer.aexecute_tool tool execution
"""

from unittest.mock import MagicMock

import pytest

from a2c_smcp_cc.computer import Computer
from a2c_smcp_cc.mcp_clients.model import SseServerConfig, StdioServerConfig, ToolMeta


@pytest.mark.anyio
async def test_computer_aexecute_tool_success(stdio_params, sse_params, sse_server) -> None:
    """
    测试通过Computer.aexecute_tool调用工具（自动通过）
    Test Computer.aexecute_tool with auto_apply tool

    StdioServer中只有一个可用工具 hello 参数为name 返回值 f"Hello, {name}!"
    """
    stdio_cfg = StdioServerConfig(name="stdio_server", server_parameters=stdio_params, tool_meta={"hello": ToolMeta(auto_apply=True)})
    sse_cfg = SseServerConfig(name="sse_server", server_parameters=sse_params)
    computer = Computer(mcp_servers={stdio_cfg, sse_cfg})
    await computer.boot_up()
    # 获取可用工具/Get available tools
    tools = await computer.aget_available_tools()
    assert tools, "No tools available"
    tool_name = "hello"
    # 调用工具/Call tool
    result = await computer.aexecute_tool("reqid", tool_name, {"name": "China"})
    assert hasattr(result, "content")
    assert result.content, "Tool call result should have content"
    assert result.content[0].text == "Hello, China!"


@pytest.mark.anyio
async def test_computer_aexecute_tool_confirm_callback_called(stdio_params):
    """
    测试tool_meta为空时会触发二次确认回调，并保证回调被调用
    Test that when tool_meta is empty, confirm_callback is triggered and called
    """
    from a2c_smcp_cc.mcp_clients.model import StdioServerConfig

    # tool_meta为空/No auto_apply
    confirm_mock = MagicMock(return_value=True)
    stdio_cfg = StdioServerConfig(name="stdio_server", server_parameters=stdio_params, tool_meta={})
    computer = Computer(mcp_servers={stdio_cfg}, confirm_callback=confirm_mock)
    await computer.boot_up()
    tools = await computer.aget_available_tools()
    tool_name = "hello"
    result = await computer.aexecute_tool("reqid", tool_name, {"name": "China"})
    assert hasattr(result, "content")
    assert confirm_mock.called, "confirm_callback should be called"
    assert result.content[0].text == "Hello, China!"
