# -*- coding: utf-8 -*-
# filename: test_computer.py
# @Time    : 2025/8/26 14:03
# @Author  : JQQ
# @Email   : jqq1716@gmail.com
# @Software: PyCharm
"""
Computer 类测试
Test for Computer class
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from mcp.types import CallToolResult, TextContent
from polyfactory.factories.pydantic_factory import ModelFactory

from a2c_smcp_cc.computer import Computer
from a2c_smcp_cc.mcp_clients.manager import MCPServerManager
from a2c_smcp_cc.mcp_clients.model import MCPServerConfig, StdioServerConfig, ToolMeta


@pytest.fixture
def mock_stdio_client() -> StdioServerConfig:
    """生成一个Mock数据"""
    server_config = ModelFactory.create_factory(model=StdioServerConfig).build()
    return server_config


@pytest.fixture
def mock_mcp_manager(mock_stdio_client: StdioServerConfig) -> MCPServerManager:
    """创建模拟的 MCP 管理器"""
    manager = MagicMock(spec=MCPServerManager)
    manager.avalidate_tool_call = AsyncMock()
    manager.acall_tool = AsyncMock()
    manager.get_server_config = AsyncMock()
    return manager


@pytest.fixture
def computer_with_mock_manager(mock_mcp_manager):
    """创建带有模拟管理器的 Computer 实例"""
    computer = Computer(auto_connect=False)
    computer.mcp_manager = mock_mcp_manager
    return computer


@pytest.mark.anyio
async def test_aexecute_tool_auto_apply(computer_with_mock_manager, mock_mcp_manager):
    """
    测试自动应用的工具调用
    Test tool execution with auto_apply enabled
    """
    # 设置模拟
    server_config = ModelFactory.create_factory(model=StdioServerConfig).build()
    mock_mcp_manager.avalidate_tool_call.return_value = ("test_server", "test_tool")
    mock_mcp_manager.get_server_config.return_value = server_config
    mock_mcp_manager.acall_tool.return_value = CallToolResult(content=[TextContent(text="Success", type="text")])

    # 执行测试
    result = await computer_with_mock_manager.aexecute_tool("req_123", "test_tool", {"param": "value"})

    # 验证结果
    assert result.content[0].text == "Success"
    mock_mcp_manager.avalidate_tool_call.assert_called_once_with("test_tool", {"param": "value"})
    mock_mcp_manager.acall_tool.assert_called_once_with("test_server", "test_tool", {"param": "value"}, None)


@pytest.mark.anyio
async def test_aexecute_tool_confirm_callback_approved(computer_with_mock_manager, mock_mcp_manager):
    """
    测试需要确认且用户批准的工具调用
    Test tool execution with confirmation callback and user approval
    """
    # 设置模拟
    mock_mcp_manager.avalidate_tool_call.return_value = ("test_server", "test_tool")
    mock_mcp_manager.get_server_config.return_value = MCPServerConfig(
        name="test_server", tool_meta={"test_tool": ToolMeta(auto_apply=False)}
    )
    mock_mcp_manager.acall_tool.return_value = CallToolResult(content=[TextContent(text="Success", type="text")])

    # 设置确认回调
    confirm_callback = MagicMock(return_value=True)
    computer_with_mock_manager._confirm_callback = confirm_callback

    # 执行测试
    result = await computer_with_mock_manager.aexecute_tool("req_123", "test_tool", {"param": "value"})

    # 验证结果
    assert result.content[0].text == "Success"
    confirm_callback.assert_called_once_with("req_123", "test_server", "test_tool", {"param": "value"})
    mock_mcp_manager.acall_tool.assert_called_once_with("test_server", "test_tool", {"param": "value"}, None)


@pytest.mark.anyio
async def test_aexecute_tool_confirm_callback_rejected(computer_with_mock_manager, mock_mcp_manager):
    """
    测试需要确认但用户拒绝的工具调用
    Test tool execution with confirmation callback and user rejection
    """
    # 设置模拟
    mock_mcp_manager.avalidate_tool_call.return_value = ("test_server", "test_tool")
    mock_mcp_manager.get_server_config.return_value = MCPServerConfig(
        name="test_server", tool_meta={"test_tool": ToolMeta(auto_apply=False)}
    )

    # 设置确认回调
    confirm_callback = MagicMock(return_value=False)
    computer_with_mock_manager._confirm_callback = confirm_callback

    # 执行测试
    result = await computer_with_mock_manager.aexecute_tool("req_123", "test_tool", {"param": "value"})

    # 验证结果
    assert result.content[0].text == "工具调用二次确认被拒绝，请稍后再试"
    confirm_callback.assert_called_once_with("req_123", "test_server", "test_tool", {"param": "value"})
    mock_mcp_manager.acall_tool.assert_not_called()


@pytest.mark.anyio
async def test_aexecute_tool_confirm_callback_timeout(computer_with_mock_manager, mock_mcp_manager):
    """
    测试确认回调超时的情况
    Test confirmation callback timeout
    """
    # 设置模拟
    mock_mcp_manager.avalidate_tool_call.return_value = ("test_server", "test_tool")
    mock_mcp_manager.get_server_config.return_value = MCPServerConfig(
        name="test_server", tool_meta={"test_tool": ToolMeta(auto_apply=False)}
    )

    # 设置确认回调超时
    def timeout_callback(*args):
        raise TimeoutError()

    computer_with_mock_manager._confirm_callback = timeout_callback

    # 执行测试
    result = await computer_with_mock_manager.aexecute_tool("req_123", "test_tool", {"param": "value"})

    # 验证结果
    assert result.isError is True
    assert "确认超时" in result.content[0].text
    mock_mcp_manager.acall_tool.assert_not_called()


@pytest.mark.anyio
async def test_aexecute_tool_confirm_callback_exception(computer_with_mock_manager, mock_mcp_manager):
    """
    测试确认回调抛出异常的情况
    Test confirmation callback raising exception
    """
    # 设置模拟
    mock_mcp_manager.avalidate_tool_call.return_value = ("test_server", "test_tool")
    mock_mcp_manager.get_server_config.return_value = MCPServerConfig(
        name="test_server", tool_meta={"test_tool": ToolMeta(auto_apply=False)}
    )

    # 设置确认回调抛出异常
    def exception_callback(*args):
        raise ValueError("Test exception")

    computer_with_mock_manager._confirm_callback = exception_callback

    # 执行测试
    result = await computer_with_mock_manager.aexecute_tool("req_123", "test_tool", {"param": "value"})

    # 验证结果
    assert result.isError is True
    assert "发生异常" in result.content[0].text
    mock_mcp_manager.acall_tool.assert_not_called()


@pytest.mark.anyio
async def test_aexecute_tool_no_confirm_callback(computer_with_mock_manager, mock_mcp_manager):
    """
    测试需要确认但没有设置确认回调的情况
    Test tool execution requiring confirmation but no callback set
    """
    # 设置模拟
    mock_mcp_manager.avalidate_tool_call.return_value = ("test_server", "test_tool")
    mock_mcp_manager.get_server_config.return_value = MCPServerConfig(
        name="test_server", tool_meta={"test_tool": ToolMeta(auto_apply=False)}
    )

    # 确保没有确认回调
    computer_with_mock_manager._confirm_callback = None

    # 执行测试
    result = await computer_with_mock_manager.aexecute_tool("req_123", "test_tool", {"param": "value"})

    # 验证结果
    assert result.isError is True
    assert "没有实现二次确认回调方法" in result.content[0].text
    mock_mcp_manager.acall_tool.assert_not_called()


@pytest.mark.anyio
async def test_aexecute_tool_timeout(computer_with_mock_manager, mock_mcp_manager):
    """
    测试带超时的工具调用
    Test tool execution with timeout
    """
    # 设置模拟
    mock_mcp_manager.avalidate_tool_call.return_value = ("test_server", "test_tool")
    mock_mcp_manager.get_server_config.return_value = MCPServerConfig(
        name="test_server", tool_meta={"test_tool": ToolMeta(auto_apply=True)}
    )
    mock_mcp_manager.acall_tool.return_value = CallToolResult(content=[TextContent(text="Success", type="text")])

    # 执行测试
    result = await computer_with_mock_manager.aexecute_tool("req_123", "test_tool", {"param": "value"}, timeout=30.0)

    # 验证结果
    assert result.content[0].text == "Success"
    mock_mcp_manager.acall_tool.assert_called_once_with("test_server", "test_tool", {"param": "value"}, 30.0)


@pytest.mark.anyio
async def test_aexecute_tool_no_tool_meta(computer_with_mock_manager, mock_mcp_manager):
    """
    测试没有工具元数据的情况
    Test tool execution without tool metadata
    """
    # 设置模拟
    mock_mcp_manager.avalidate_tool_call.return_value = ("test_server", "test_tool")
    mock_mcp_manager.get_server_config.return_value = MCPServerConfig(
        name="test_server",
        tool_meta={},  # 没有该工具的元数据
    )

    # 设置确认回调
    confirm_callback = MagicMock(return_value=True)
    computer_with_mock_manager._confirm_callback = confirm_callback

    # 执行测试
    result = await computer_with_mock_manager.aexecute_tool("req_123", "test_tool", {"param": "value"})

    # 验证结果 - 没有元数据时应视为需要确认
    confirm_callback.assert_called_once_with("req_123", "test_server", "test_tool", {"param": "value"})
    mock_mcp_manager.acall_tool.assert_called_once_with("test_server", "test_tool", {"param": "value"}, None)


@pytest.mark.anyio
async def test_aexecute_tool_no_server_config(computer_with_mock_manager, mock_mcp_manager):
    """
    测试没有服务器配置的情况
    Test tool execution without server config
    """
    # 设置模拟
    mock_mcp_manager.avalidate_tool_call.return_value = ("test_server", "test_tool")
    mock_mcp_manager.get_server_config.return_value = None  # 没有服务器配置

    # 设置确认回调
    confirm_callback = MagicMock(return_value=True)
    computer_with_mock_manager._confirm_callback = confirm_callback

    # 执行测试 - 没有服务器配置时应视为需要确认
    result = await computer_with_mock_manager.aexecute_tool("req_123", "test_tool", {"param": "value"})

    # 验证结果
    confirm_callback.assert_called_once_with("req_123", "test_server", "test_tool", {"param": "value"})
    mock_mcp_manager.acall_tool.assert_called_once_with("test_server", "test_tool", {"param": "value"}, None)


@pytest.mark.anyio
async def test_computer_lifecycle():
    """
    测试 Computer 的生命周期管理
    Test Computer lifecycle management
    """
    computer = Computer(auto_connect=False)

    # 测试异步上下文管理器
    async with computer:
        assert computer.mcp_manager is not None
        assert hasattr(computer.mcp_manager, "ainitialize")

    # 测试关闭后管理器为 None
    assert computer.mcp_manager is None
